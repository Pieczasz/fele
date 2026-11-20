"""Time-respecting feature store for both model families (AGENT_PLAN.md §5.2).

One chronological pass over the games: for each game the features are computed from the *state before the game*
(only strictly earlier games), then the game's result updates the state. Nothing can leak from the future, and
the leakage tests verify it by perturbing later games.

Outputs
- `outcome`: one row per game, blue-minus-red differences of draft features + champion/team ids for models that
  learn their own effects (fold-fitted inside the model).
- `ActionData`: per (game, team) candidate-feature tensors over the champion vocabulary, plus per-action rows
  (slot, action, true champion, availability mask, roles still open) — models assemble X on the fly.

Assumption: a player's role in a game (inferred from positions, Phase 2) is known before the game: the pick →
player assignment is visible once the draft ends, which is when the outcome model predicts.
"""

import math
import uuid
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import numpy.typing as npt
import polars as pl

from fele.prefs import Role
from fele.static.ddragon import patch_key

type Floats = npt.NDArray[np.float32]

WINDOW = 3  # trailing GRID patches for champion strength / presence
CHAMP_PRIOR = 100.0  # pseudo-games shrinking champion win rates toward 0.5 (Phase 5: pro WRs are mostly noise)
PLAYER_PRIOR = 10.0  # pseudo-games shrinking player-on-champion win rates
FORM_GAMES = 10
HALF_LIFE_DAYS = 60.0
ROLES = tuple(str(r) for r in Role)
TAG_COLS = ("ap_share", "engage", "disengage", "peel", "frontline", "poke", "dive", "splitpush", "waveclear", "hard_cc")
SCALING = {"early": 0.0, "mid": 1.0, "late": 2.0}
TEAM_FEATURES = (
    "elo",  # filled from stats.elo by the caller
    "form",
    "champ_wr",
    "champ_presence",
    "comfort",
    "comfort_wr",
    "first_time",
    "delta",
    *TAG_COLS,
    "scaling",
    "damage_balance",
)
CANDIDATE_FEATURES = (
    "pick_presence",  # share of window games the champion was picked
    "ban_presence",
    "champ_wr",
    "team_pick",  # recency-weighted share of this team's picks
    "team_ban",
    "own_pool",  # log1p recency-weighted pro games of this team's players on the champion (max)
    "opp_pool",  # same for the opponent's players (ban-target signal)
    "delta",
)


def patch_age() -> pl.Expr:
    """Days since the first game on this patch in the data, bucketed (that first game is never later)."""
    days = (pl.col("started_at") - pl.col("started_at").min().over("patch")).dt.total_days()
    return pl.when(days < 7).then(pl.lit("week 1")).when(days < 14).then(pl.lit("week 2")).otherwise(pl.lit("week 3+"))  # noqa: PLR2004


def _decay(age_days: float) -> float:
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


@dataclass
class _State:
    vocab: list[str]
    index: dict[str, int]
    patches: list[str]  # GRID patches, oldest first
    champ_pick: dict[str, Floats] = field(default_factory=dict[str, Floats])  # patch -> picks per champion
    champ_win: dict[str, Floats] = field(default_factory=dict[str, Floats])
    champ_ban: dict[str, Floats] = field(default_factory=dict[str, Floats])
    pair: dict[str, Floats] = field(default_factory=dict[str, Floats])  # patch -> V x V same-team co-picks
    games: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    team_hist: dict[str, list[tuple[datetime, int, str]]] = field(default_factory=lambda: defaultdict(list))
    team_results: dict[str, list[bool]] = field(default_factory=lambda: defaultdict(list))
    player_hist: dict[str, list[tuple[datetime, int, bool]]] = field(default_factory=lambda: defaultdict(list))

    def _vec(self, store: dict[str, Floats], patch: str) -> Floats:
        if patch not in store:
            store[patch] = np.zeros(len(self.vocab), np.float32)
        return store[patch]

    def add(self, patch: str, bans: list[int], champs: dict[str, list[int]], winner: str, g: dict[str, Any]) -> None:
        """Count one finished game: picks, wins, bans and same-team co-picks per champion for its patch."""
        self._vec(self.champ_ban, patch)[bans] += 1
        for side, picks in champs.items():
            self._vec(self.champ_pick, patch)[picks] += 1
            if winner == g[f"{side}_team_id"]:
                self._vec(self.champ_win, patch)[picks] += 1
            if patch not in self.pair:
                self.pair[patch] = np.zeros((len(self.vocab), len(self.vocab)), np.float32)
            for i in picks:
                self.pair[patch][i, picks] += 1

    def window(self, patch: str | None) -> list[str]:
        if patch is None:
            return []
        i = bisect_left(self.patches, patch_key(patch), key=patch_key)
        return self.patches[max(0, i - WINDOW + 1) : i + 1]

    def champ_stats(self, patch: str | None) -> tuple[Floats, Floats, Floats, Floats]:
        """(pick share, ban share, shrunk win rate, picks) over the window, as vectors over the vocabulary."""
        w = self.window(patch)
        v = len(self.vocab)
        picks, wins, bans = np.zeros(v, np.float32), np.zeros(v, np.float32), np.zeros(v, np.float32)
        for p in w:
            picks += self.champ_pick.get(p, 0)
            wins += self.champ_win.get(p, 0)
            bans += self.champ_ban.get(p, 0)
        n = max(1, sum(self.games[p] for p in w))
        wr = (wins + 0.5 * CHAMP_PRIOR) / (picks + CHAMP_PRIOR)
        as32 = np.float32
        return (picks / n).astype(as32), (bans / n).astype(as32), wr.astype(as32), picks

    def pmi(self, patch: str | None) -> Floats:
        """Smoothed pointwise mutual information of same-team co-picks over the window (0 = independent)."""
        v = len(self.vocab)
        co = np.zeros((v, v), np.float32)
        for p in self.window(patch):
            if p in self.pair:
                co += self.pair[p]
        n = np.diag(co).copy()
        total = max(1.0, float(sum(2 * self.games[p] for p in self.window(patch))))
        return np.log((co + 1) * total / np.outer(n + 1, n + 1)).astype(np.float32)

    def team_freq(self, team: str, action: str, now: datetime) -> Floats:
        vec = np.zeros(len(self.vocab), np.float32)
        for t, c, a in self.team_hist[team]:
            if a == action:
                vec[c] += _decay((now - t).total_seconds() / 86400)
        total = vec.sum()
        return vec / total if total > 0 else vec

    def player_pool(self, player: str, now: datetime) -> Floats:
        vec = np.zeros(len(self.vocab), np.float32)
        for t, c, _ in self.player_hist[player]:
            vec[c] += _decay((now - t).total_seconds() / 86400)
        return np.log1p(vec)

    def player_on(self, player: str, champ: int, now: datetime) -> tuple[float, float, int]:
        """(log1p recency-weighted games, shrunk win rate, raw games) of a player on a champion."""
        w = games = wins = 0.0
        for t, c, win in self.player_hist[player]:
            if c == champ:
                w += _decay((now - t).total_seconds() / 86400)
                games += 1
                wins += win
        return math.log1p(w), (wins + 0.5 * PLAYER_PRIOR) / (games + PLAYER_PRIOR), int(games)


@dataclass
class ActionData:
    vocab: list[str]
    role_rank: npt.NDArray[np.int8]  # V x 5: 0 = primary role, UNTAGGED = not tagged
    team_x: Floats  # (game-team, V, len(CANDIDATE_FEATURES))
    rows: pl.DataFrame  # one row per action: gt (index into team_x), action, phase, slot, y (true idx), ...
    unavailable: npt.NDArray[np.bool_]  # (actions, V)
    own_picks: npt.NDArray[np.int32]  # (actions, 4): this team's earlier picks in the game, -1 padded
    opp_picks: npt.NDArray[np.int32]  # (actions, 5): the opponent's earlier picks, -1 padded
    synergy: Floats  # (actions, V): mean co-pick PMI of each candidate with this team's earlier picks
    opp_synergy: Floats  # (actions, V): same with the opponent's earlier picks (deny value of a ban)


UNTAGGED = 9  # role_rank value for a role the champion isn't tagged with


def _tags(champions: pl.DataFrame, cmap: pl.DataFrame, vocab: list[str]) -> tuple[Floats, npt.NDArray[np.int8]]:
    """Tag matrix and role_rank (V x 5): 0 = primary role, 1 = second tagged role, ..., UNTAGGED otherwise."""
    key = dict(zip(cmap["grid_name"].to_list(), cmap["champion"].to_list(), strict=True))
    tags = {r["champion"]: r for r in champions.iter_rows(named=True)}
    mat = np.zeros((len(vocab), len(TAG_COLS) + 1), np.float32)
    roles = np.full((len(vocab), len(ROLES)), UNTAGGED, np.int8)
    for i, name in enumerate(vocab):
        t = tags.get(key.get(name, ""))
        if t is None:
            continue
        mat[i, : len(TAG_COLS)] = [float(t[c]) for c in TAG_COLS]
        mat[i, -1] = SCALING.get(t["scaling"], 1.0)
        for rank, r in enumerate(r for r in str(t["roles"]).split("|") if r in ROLES):
            roles[i, ROLES.index(r)] = rank
    return mat, roles


@dataclass(frozen=True)
class Inputs:
    """Every table the feature store reads (ingest + static + Elo)."""

    games: pl.DataFrame
    series: pl.DataFrame
    draft: pl.DataFrame
    parts: pl.DataFrame
    fearless: pl.DataFrame
    champions: pl.DataFrame
    cmap: pl.DataFrame
    deltas: pl.DataFrame
    elo: pl.DataFrame


class Builder:
    """Accumulates feature rows while walking the games in time order."""

    def __init__(self, inp: Inputs) -> None:
        draft, parts = inp.draft, inp.parts
        # vocabulary from the static champion map, never from the games (that set would depend on future drafts)
        self.vocab = sorted(set(inp.cmap["grid_name"].to_list()))
        self.index = {c: i for i, c in enumerate(self.vocab)}
        self.tag_mat, self.role_rank = _tags(inp.champions, inp.cmap, self.vocab)
        self.delta_by = self._deltas(inp.deltas, inp.cmap)
        self.st = _State(
            self.vocab, self.index, sorted(inp.games["patch"].drop_nulls().unique().to_list(), key=patch_key)
        )
        self.roster = {
            (g, t): grp.sort("player_id").select("player_id", "champion", "inferred_role").rows()
            for (g, t), grp in parts.group_by("game_id", "team_id")
        }
        self.drafts = {g[0]: grp.drop_nulls("slot").sort("slot") for g, grp in draft.group_by("game_id")}
        self.series_wins: dict[str, Counter[str]] = defaultdict(Counter)  # picklable (no lambda factory)
        self.locked: dict[str, set[int]] = defaultdict(set)  # series -> champions picked in earlier games
        self.out_rows: list[dict[str, object]] = []
        self.team_x: list[Floats] = []
        self.gt_index: dict[tuple[str, str], int] = {}
        self.act_rows: list[dict[str, object]] = []
        self.unavailable: list[npt.NDArray[np.bool_]] = []
        self.own_picks: list[list[int]] = []
        self.opp_picks: list[list[int]] = []
        self.synergy: list[Floats] = []
        self.opp_synergy: list[Floats] = []

    def _deltas(self, deltas: pl.DataFrame, cmap: pl.DataFrame) -> dict[str, Floats]:
        key_of = dict(zip(cmap["grid_name"].to_list(), cmap["champion"].to_list(), strict=True))
        out: dict[str, Floats] = {}
        for patch, g in deltas.group_by("patch"):
            score = dict(zip(g["champion"].to_list(), g["score"].to_list(), strict=True))
            out[str(patch[0])] = np.array([score.get(key_of.get(n, ""), 0.0) for n in self.vocab], np.float32)
        return out

    def team_features(
        self, g: dict[str, Any], side: str, picks: list[int], champ: tuple[Floats, Floats, Floats]
    ) -> dict[str, float]:
        pick_share, ban_share, wr = champ
        team, now = g[f"{side}_team_id"], g["started_at"]
        members = self.roster.get((g["game_id"], team), [])
        comforts = [self.st.player_on(p, self.index[c], now) for p, c, _ in members if c in self.index]
        results = self.st.team_results[team][-FORM_GAMES:]
        tags = self.tag_mat[picks].mean(axis=0) if picks else np.zeros(self.tag_mat.shape[1], np.float32)
        delta = self.delta_by.get(g["patch"] or "", np.zeros(len(self.vocab), np.float32))
        f: dict[str, float] = {
            "elo": g[f"{side}_elo"],
            "form": (sum(results) + 0.5 * FORM_GAMES) / (len(results) + FORM_GAMES),
            "champ_wr": float(wr[picks].mean()) if picks else 0.5,
            "champ_presence": float((pick_share + ban_share)[picks].mean()) if picks else 0.0,
            "comfort": float(np.mean([c[0] for c in comforts])) if comforts else 0.0,
            "comfort_wr": float(np.mean([c[1] for c in comforts])) if comforts else 0.5,
            "first_time": float(sum(c[2] == 0 for c in comforts)),
            "delta": float(delta[picks].sum()) if picks else 0.0,
            "scaling": float(tags[-1]),
            "damage_balance": abs(float(tags[0]) - 0.5),
        }
        return f | {c: float(tags[i]) for i, c in enumerate(TAG_COLS)}

    def candidate_matrix(
        self,
        team: str,
        own_players: list[str],
        opp_players: list[str],
        patch: str | None,
        now: datetime,
        champ: tuple[Floats, Floats, Floats],
    ) -> Floats:
        """(V, len(CANDIDATE_FEATURES)) features of every champion for `team` drafting against `opp_players`."""
        pick_share, ban_share, wr = champ
        own_pool = np.zeros(len(self.vocab), np.float32)
        for p in own_players:
            own_pool = np.maximum(own_pool, self.st.player_pool(p, now))
        opp_pool = np.zeros(len(self.vocab), np.float32)
        for p in opp_players:
            opp_pool = np.maximum(opp_pool, self.st.player_pool(p, now))
        delta = self.delta_by.get(patch or "", np.zeros(len(self.vocab), np.float32))
        team_pick, team_ban = self.st.team_freq(team, "pick", now), self.st.team_freq(team, "ban", now)
        return np.stack([pick_share, ban_share, wr, team_pick, team_ban, own_pool, opp_pool, delta], axis=1)

    def candidate_tensor(self, g: dict[str, Any], side: str, champ: tuple[Floats, Floats, Floats]) -> None:
        gid = g["game_id"]
        team, opp = g[f"{side}_team_id"], g["red_team_id" if side == "blue" else "blue_team_id"]
        own = [p for p, _, _ in self.roster.get((gid, team), [])]
        theirs = [p for p, _, _ in self.roster.get((gid, opp), [])]
        self.gt_index[gid, team] = len(self.team_x)
        self.team_x.append(self.candidate_matrix(team, own, theirs, g["patch"], g["started_at"], champ))

    # --- "now" queries for live drafts (state after every game in the data) ---
    def live_candidates(
        self, team: str, own_players: list[str], opp_players: list[str], patch: str | None, now: datetime
    ) -> Floats:
        pick_share, ban_share, wr, _ = self.st.champ_stats(patch)
        return self.candidate_matrix(team, own_players, opp_players, patch, now, (pick_share, ban_share, wr))

    def live_team_features(
        self, team: str, lineup: list[tuple[str, str]], patch: str | None, now: datetime, elo: float, side: str
    ) -> dict[str, float]:
        """Outcome-model team features for a hypothetical lineup [(player_id, champion)] drafted now."""
        gid = f"live-{side}-{uuid.uuid4().hex}"  # unique per call: concurrent requests never share a lineup
        self.roster[gid, team] = [(p, c, "") for p, c in lineup]
        try:
            g = {"game_id": gid, f"{side}_team_id": team, "started_at": now, "patch": patch, f"{side}_elo": elo}
            pick_share, ban_share, wr, _ = self.st.champ_stats(patch)
            picks = [self.index[c] for _, c in lineup if c in self.index]
            return self.team_features(g, side, picks, (pick_share, ban_share, wr))
        finally:
            del self.roster[gid, team]

    def pmi(self, patch: str | None) -> Floats:
        return self.st.pmi(patch)

    def draft_actions(self, g: dict[str, Any], pmi: Floats) -> None:
        """Rows for this game's picks/bans: state before the game plus the earlier actions of the same game."""
        gid, sid = g["game_id"], g["series_id"]
        d = self.drafts.get(gid)
        if d is None:
            return
        zero = np.zeros(len(self.vocab), np.float32)
        taken: list[int] = []
        picks_by: dict[str, list[int]] = defaultdict(list)
        for a in d.iter_rows(named=True):
            team, champ = a["team_id"], a["champion"]
            if champ not in self.index or (gid, team) not in self.gt_index:
                continue
            opp = g["red_team_id"] if team == g["blue_team_id"] else g["blue_team_id"]
            mask = np.zeros(len(self.vocab), bool)
            mask[taken] = True
            mask[list(self.locked[sid])] = True
            mine, theirs = picks_by[team], picks_by[opp]
            self.act_rows.append(
                {
                    "gt": self.gt_index[gid, team],
                    "game_id": gid,
                    "series_id": sid,
                    "started_at": g["started_at"],
                    "team_id": team,
                    "patch": g["patch"],
                    "champion": champ,
                    "action": a["action"],
                    "phase": a["phase"],
                    "slot": a["slot"],
                    "game_number": g["game_number"],
                    "y": self.index[champ],
                }
            )
            self.unavailable.append(mask)
            self.own_picks.append((mine + [-1] * 4)[:4])
            self.opp_picks.append((theirs + [-1] * 5)[:5])
            self.synergy.append(pmi[mine].mean(axis=0) if mine else zero)
            self.opp_synergy.append(pmi[theirs].mean(axis=0) if theirs else zero)
            taken.append(self.index[champ])
            if a["action"] == "pick":
                picks_by[team].append(self.index[champ])

    def update(self, g: dict[str, Any], champs: dict[str, list[int]]) -> None:
        """Add this game's results to the state (after its features were computed)."""
        st, gid, now, patch = self.st, g["game_id"], g["started_at"], g["patch"]
        d = self.drafts.get(gid)
        if patch is not None:
            st.games[patch] += 1
            bans = [] if d is None else d.filter(pl.col("action") == "ban")["champion"].to_list()
            st.add(patch, [self.index[c] for c in bans if c in self.index], champs, g["winner_team_id"], g)
        if d is not None:
            for a in d.iter_rows(named=True):
                if a["champion"] in self.index:
                    st.team_hist[a["team_id"]].append((now, self.index[a["champion"]], a["action"]))
        for side in ("blue", "red"):
            team = g[f"{side}_team_id"]
            won = g["winner_team_id"] == team
            st.team_results[team].append(won)
            for p, c, _ in self.roster.get((gid, team), []):
                if c in self.index:
                    st.player_hist[p].append((now, self.index[c], won))
            self.locked[g["series_id"]].update(champs[side])
        self.series_wins[g["series_id"]][g["winner_team_id"]] += 1

    def game(self, g: dict[str, Any]) -> None:
        pick_share, ban_share, wr, _ = self.st.champ_stats(g["patch"])
        champ = (pick_share, ban_share, wr)
        champs: dict[str, list[int]] = {}
        feats: dict[str, dict[str, float]] = {}
        for side in ("blue", "red"):
            members = self.roster.get((g["game_id"], g[f"{side}_team_id"]), [])
            champs[side] = [self.index[c] for _, c, _ in members if c in self.index]
            feats[side] = self.team_features(g, side, champs[side], champ)
            self.candidate_tensor(g, side, champ)
        wins = self.series_wins[g["series_id"]]
        row: dict[str, object] = {
            "game_id": g["game_id"],
            "series_id": g["series_id"],
            "started_at": g["started_at"],
            "league": g["league"],
            "patch": g["patch"],
            "game_number": g["game_number"],
            "blue_team_id": g["blue_team_id"],
            "red_team_id": g["red_team_id"],
            "y": float(g["winner_team_id"] == g["blue_team_id"]),
            "series_score_diff": float(wins[g["blue_team_id"]] - wins[g["red_team_id"]]),
            "locked_count": float(g["locked_count"] or 0),
            "blue_champs": [self.vocab[i] for i in champs["blue"]],
            "red_champs": [self.vocab[i] for i in champs["red"]],
        }
        self.out_rows.append(row | {f"d_{k}": feats["blue"][k] - feats["red"][k] for k in TEAM_FEATURES})
        self.draft_actions(g, self.st.pmi(g["patch"]))
        self.update(g, champs)

    def slim(self) -> None:
        """Drop the per-game walk data (drafts, rosters, training rows) once result() has been taken. The live engine
        needs only the accumulated state, and the cached/deployed context then holds no per-game draft rows."""
        self.drafts, self.roster, self.gt_index = {}, {}, {}
        self.out_rows, self.team_x, self.act_rows, self.unavailable = [], [], [], []
        self.own_picks, self.opp_picks, self.synergy, self.opp_synergy = [], [], [], []

    def result(self) -> tuple[pl.DataFrame, ActionData]:
        actions = ActionData(
            vocab=self.vocab,
            role_rank=self.role_rank,
            team_x=np.stack(self.team_x),
            rows=pl.DataFrame(self.act_rows),
            unavailable=np.stack(self.unavailable),
            own_picks=np.array(self.own_picks, np.int32),
            opp_picks=np.array(self.opp_picks, np.int32),
            synergy=np.stack(self.synergy),
            opp_synergy=np.stack(self.opp_synergy),
        )
        return pl.DataFrame(self.out_rows), actions


def build(inp: Inputs) -> tuple[pl.DataFrame, ActionData]:
    """Walk the games in time order; each game's features use only strictly earlier games."""
    out, act, _ = build_with_state(inp)
    return out, act


def build_with_state(inp: Inputs) -> tuple[pl.DataFrame, ActionData, Builder]:
    """Like build(), and also returns the builder holding the state after the last game (for live drafts)."""
    ctx = (
        inp.games.join(inp.series.select("series_id", "league"), on="series_id", how="left")
        .join(inp.elo.select("game_id", "blue_elo", "red_elo"), on="game_id")
        .join(inp.fearless.select("game_id", "locked_count"), on="game_id", how="left")
        .drop_nulls(["started_at", "winner_team_id"])
        .sort("started_at", "game_id")
    )
    b = Builder(inp)
    for g in ctx.iter_rows(named=True):
        b.game(g)
    out, act = b.result()
    return out, act, b
