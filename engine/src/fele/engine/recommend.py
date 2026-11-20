"""Draft recommendations: ranked options with reasons, never orders (Riot policy, AGENT_PLAN.md ground rule 8).

Score of a candidate = sum of evidence-backed parts, with FIXED weights (chosen by design, not tuned on results):

  picks: pro   = log P(LambdaRank: a pro team in this spot picks it)          validated: 64% top-10 on the holdout
         coach = comfort tier of the role's player x preferences.weight       coach input
         form  = the player's recency-weighted pro games / wins on it         GRID, n shown
         comp  = fills a damage / frontline / engage / peel gap               champion tags
         style = fits the coach's style tags and the team's own pick profile  tags + team history
         lane  = shrunk solo-queue matchup vs the enemy laner                 Riot API sample, n shown
         edge  = win-probability change (and after their likely answer)       outcome model, weak evidence
         save  = penalty for champions saved for later Fearless games          coach input
  bans:  threat = log P(the enemy picks it at their next pick) + their players' comfort on it,
         coach must-ban / "hates playing against", and the pro ban prior.
"""

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import numpy.typing as npt
import polars as pl

from fele.engine.draft import THEM, US, DraftState
from fele.engine.live import Live, Player
from fele.features import state
from fele.models.action import open_roles, role_assignment
from fele.prefs import Comfort, Preferences

type Floats = npt.NDArray[np.float64]

ROLES = tuple(str(r) for r in state.ROLES)
COMFORT = {Comfort.signature: 1.0, Comfort.comfortable: 0.6, Comfort.playable: 0.2, Comfort.learning: -0.3}
W = {"pro": 1.0, "coach": 1.5, "form": 0.4, "comp": 0.6, "style": 0.4, "lane": 4.0, "edge": 8.0, "save": 1.0}
BAN_W = {"threat": 1.0, "comfort": 0.5, "coach": 1.5, "pro": 0.5, "edge": 8.0}
STYLE_TAGS = {  # coach style tag -> champion tags it wants
    "early": {"scaling": -1.0},
    "scaling": {"scaling": 1.0},
    "skirmish": {"dive": 1.0, "engage": 0.5},
    "teamfight": {"engage": 1.0, "frontline": 0.5},
    "pick": {"engage": 0.5, "hard_cc": 1.0},
    "poke": {"poke": 1.0},
    "siege": {"poke": 0.5, "waveclear": 1.0},
    "split": {"splitpush": 1.0},
    "protect": {"peel": 1.0, "disengage": 0.5},
}
TOP_N = 5
LATE_GAME = 3
REPLIES = 3  # enemy answers considered by the depth-1 expectimax
ROLLOUTS = 24
SHORTLIST = 12
DEFAULT_WEIGHT = 0.5  # preferences.weight default; coach ban bonus = BAN_W['coach'] at this weight
Mode = Literal["best", "comfort_only", "save"]


@dataclass
class Matchup:
    """A live game: our team vs theirs, lineups and per-team candidate features (from the live state)."""

    live: Live
    us: str
    them: str
    our_players: list[Player]
    their_players: list[Player]
    we_are_blue: bool
    game_number: int = 1
    series_score: int = 0  # our wins - their wins in this series so far
    cand: dict[str, npt.NDArray[np.float32]] = field(default_factory=dict[str, npt.NDArray[np.float32]])

    def __post_init__(self) -> None:
        lv = self.live
        ours = [p.player_id for p in self.our_players]
        theirs = [p.player_id for p in self.their_players]
        self.cand = {
            US: lv.builder.live_candidates(self.us, ours, theirs, lv.patch, lv.now_for(self.us)),
            THEM: lv.builder.live_candidates(self.them, theirs, ours, lv.patch, lv.now_for(self.them)),
        }
        self.pmi = lv.builder.pmi(lv.patch)


def matchup(
    live: Live, us: str, them: str, *, we_are_blue: bool, game_number: int = 1, series_score: int = 0
) -> Matchup:
    us_id, them_id = live.team_id(us), live.team_id(them)
    return Matchup(
        live,
        us_id,
        them_id,
        live.lineups.get(us_id, []),
        live.lineups.get(them_id, []),
        we_are_blue,
        game_number,
        series_score,
    )


# --- model B on arbitrary draft states ---------------------------------------------------------------------------
def _idx(live: Live, champs: list[str]) -> list[int]:
    index = live.builder.index
    return [index[c] for c in champs if c in index]


def action_probs(m: Matchup, states: list[DraftState], *, as_pick_for: str | None = None) -> Floats:
    """(len(states), V): LambdaRank probabilities for whoever acts next in each state.

    as_pick_for: score the next *pick* of that side instead (used for ban threat: what would they pick?).
    """
    lv = m.live
    v = len(lv.vocab)
    rows: list[dict[str, object]] = []
    unavailable: list[npt.NDArray[np.bool_]] = []
    own: list[list[int]] = []
    opp: list[list[int]] = []
    syn: list[npt.NDArray[np.float32]] = []
    opp_syn: list[npt.NDArray[np.float32]] = []
    for i, s in enumerate(states):
        actor = as_pick_for or s.who(s.slot)
        kind = "pick" if as_pick_for else s.kind(s.slot)
        other = THEM if actor == US else US
        mine, theirs = _idx(lv, s.picks(actor)), _idx(lv, s.picks(other))
        mask = np.zeros(v, bool)
        mask[_idx(lv, sorted(s.taken()))] = True
        rows.append(
            {
                "gt": 0 if actor == US else 1,
                "idx": i,
                "action": kind,
                "phase": "pick1" if as_pick_for else s.phase(s.slot),
            }
        )
        unavailable.append(mask)
        own.append((mine + [-1] * 4)[:4])
        opp.append((theirs + [-1] * 5)[:5])
        syn.append(m.pmi[mine].mean(axis=0) if mine else np.zeros(v, np.float32))
        opp_syn.append(m.pmi[theirs].mean(axis=0) if theirs else np.zeros(v, np.float32))
    act = state.ActionData(
        vocab=lv.vocab,
        role_rank=lv.roles,
        team_x=np.stack([m.cand[US], m.cand[THEM]]),
        rows=pl.DataFrame(rows),
        unavailable=np.stack(unavailable),
        own_picks=np.array(own, np.int32),
        opp_picks=np.array(opp, np.int32),
        synergy=np.stack(syn).astype(np.float32),
        opp_synergy=np.stack(opp_syn).astype(np.float32),
    )
    return lv.ranker.scores_for(act.rows, act)


# --- roles and win probability -----------------------------------------------------------------------------------
def assign_roles(live: Live, champs: list[str]) -> dict[str, str]:
    """champion -> role: each pick takes its primary role if free, else its next tagged role, else any free role
    (`role_assignment`, the same rule the draft model uses). Every pick gets a role, so all five reach the model."""
    known = [c for c in champs if c in live.builder.index]
    return {c: ROLES[k] for c, k in zip(known, role_assignment(_idx(live, known), live.roles), strict=True)}


def _lineup(live: Live, players: list[Player], champs: list[str]) -> list[tuple[str, str]]:
    by_role = {p.role: p.player_id for p in players}
    return [(by_role.get(role, ""), c) for c, role in assign_roles(live, champs).items()]


def win_prob(m: Matchup, ours: list[str], theirs: list[str]) -> float:
    """P(we win) from the draft-aware outcome model (Elo-dominated: drafts move it a few points at most)."""
    lv = m.live
    side_us, side_them = ("blue", "red") if m.we_are_blue else ("red", "blue")
    f = {
        side_us: lv.builder.live_team_features(
            m.us, _lineup(lv, m.our_players, ours), lv.patch, lv.now_for(m.us), lv.ratings.get(m.us, 1500.0), side_us
        ),
        side_them: lv.builder.live_team_features(
            m.them,
            _lineup(lv, m.their_players, theirs),
            lv.patch,
            lv.now_for(m.them),
            lv.ratings.get(m.them, 1500.0),
            side_them,
        ),
    }
    blue_minus_red = {f"d_{k}": f["blue"][k] - f["red"][k] for k in state.TEAM_FEATURES}
    score = m.series_score if m.we_are_blue else -m.series_score
    row = pl.DataFrame([blue_minus_red | {"series_score_diff": float(score), "game_number": m.game_number}])
    p_blue = float(lv.outcome.predict(row)[0])
    return p_blue if m.we_are_blue else 1 - p_blue


def rollout_win_prob(m: Matchup, s: DraftState, n: int = ROLLOUTS, seed: int = 0) -> tuple[float, float, float]:
    """Live win probability: complete the draft n times by sampling both teams from LambdaRank; (mean, p10, p90)."""
    rng = np.random.default_rng(seed)
    states = [s] * n
    while not states[0].complete:
        probs = action_probs(m, states)
        states = [st.play(m.live.vocab[rng.choice(len(p), p=p)]) for st, p in zip(states, probs, strict=True)]
    wins = np.array([win_prob(m, st.picks(US), st.picks(THEM)) for st in states])
    return float(wins.mean()), float(np.percentile(wins, 10)), float(np.percentile(wins, 90))


# --- recommendations ---------------------------------------------------------------------------------------------
@dataclass
class Option:
    champion: str
    role: str | None
    score: float
    parts: dict[str, float]
    reasons: list[str]
    win_prob: float | None = None


def _by_score(option: Option) -> float:
    return -option.score


def _player(m: Matchup, role: str | None) -> Player | None:
    return next((p for p in m.our_players if p.role == role), None)


def _comfort(prefs: Preferences | None, role: str | None, champion: str) -> Comfort | None:
    if prefs is None:
        return None
    player = next((p for p in prefs.players if p.role == role), None)
    note = next((c for c in player.pool if c.champion == champion), None) if player else None
    return note.comfort if note else None


def comp_fit(all_tags: dict[str, dict[str, float]], ours: list[str], champion: str) -> tuple[float, list[str]]:
    """Composition gaps a candidate fills (0-1 tags scaled 0-3 except ap_share/hard_cc)."""
    tags = all_tags.get(champion)
    if tags is None:
        return 0.0, []
    team = [all_tags[c] for c in ours if c in all_tags]
    score, reasons = 0.0, list[str]()
    ap = [t["ap_share"] for t in team]
    lopsided = len(ap) >= 2 and abs(float(np.mean(ap)) - 0.5) > 0.25  # noqa: PLR2004 - damage so far
    if lopsided and (float(np.mean(ap)) - 0.5) * (tags["ap_share"] - 0.5) < 0:
        score += 1.0
        reasons.append(f"balances damage (team is {'AP' if np.mean(ap) > 0.5 else 'AD'}-heavy so far)")  # noqa: PLR2004
    for tag, label, need in (("frontline", "frontline", 2), ("engage", "engage", 2), ("peel", "peel", 2)):
        if team and max(t[tag] for t in team) < need <= tags[tag]:
            score += 0.7
            reasons.append(f"adds {label} the comp lacks")
    return score, reasons


def style_fit(
    all_tags: dict[str, dict[str, float]],
    profile: npt.NDArray[np.float32] | None,
    prefs: Preferences | None,
    champion: str,
) -> tuple[float, list[str]]:
    """Fit with the coach's style tags and the team's own pick profile (recency-weighted mean tags)."""
    tags = all_tags.get(champion)
    if tags is None:
        return 0.0, []
    cols = (*state.TAG_COLS, "scaling")
    vec = np.array([tags[c] for c in cols])
    score, reasons = 0.0, list[str]()
    for style in prefs.strategy.style_tags if prefs else []:
        want = STYLE_TAGS.get(style.lower(), {})
        fit = sum(w * (tags[t] - 1.0) for t, w in want.items())  # tags are 0-3; 1 = average-ish
        if fit > 0.9:  # noqa: PLR2004
            score += 0.5
            reasons.append(f"fits the coach's '{style}' style")
    if profile is not None:
        cos = float(vec @ profile / (np.linalg.norm(vec) * np.linalg.norm(profile) + 1e-9))
        score += cos - 0.8  # most champions are ~0.8 similar; reward the clearly similar ones
        if cos > 0.93:  # noqa: PLR2004
            reasons.append("matches the team's recent pick profile")
    return score, reasons


@dataclass(frozen=True)
class _PickContext:
    ours: list[str]
    theirs: list[str]
    opp_roles: dict[str, str]
    prefs: Preferences | None
    mode: Mode
    saved: set[str]  # champions kept for a later game of this series (coach list + the planner's save plan)


def _score_pick(m: Matchup, ctx: _PickContext, champ: str, role: str, p: float) -> Option | None:
    """One candidate's parts and reasons, or None when the coach rules it out."""
    lv, prefs = m.live, ctx.prefs
    comfort = _comfort(prefs, role, champ)
    if comfort == Comfort.refuses or (
        ctx.mode == "comfort_only" and comfort not in {Comfort.signature, Comfort.comfortable}
    ):
        return None
    parts = {"pro": W["pro"] * float(np.log(p))}
    reasons = [f"pro teams in this spot pick it {p:.0%} of the time (model)"]
    if comfort is not None and comfort in COMFORT and prefs is not None:
        parts["coach"] = W["coach"] * prefs.weight * COMFORT[comfort]
        reasons.append(f"coach: {comfort} for the {role}")
    player = _player(m, role)
    if player is not None:
        recency, wr, n = lv.builder.st.player_on(player.player_id, lv.builder.index[champ], lv.now_for(m.us))
        if n:
            parts["form"] = W["form"] * recency
            reasons.append(f"{player.name}: {n} pro games on it (adj. win rate {wr:.0%})")
    comp, why = comp_fit(lv.tags, ctx.ours, champ)
    style, why_style = style_fit(lv.tags, lv.style.get(m.us), prefs, champ)
    parts["comp"], parts["style"] = W["comp"] * comp, W["style"] * style
    reasons += why + why_style
    enemy = next((e for e, r in ctx.opp_roles.items() if r == role), None)
    if enemy is not None:
        wr, games = lv.matchup(role, champ, enemy)
        parts["lane"] = W["lane"] * (wr - 0.5)
        if games >= 10:  # noqa: PLR2004
            reasons.append(f"vs {enemy}: {wr:.0%} adj. win rate in high-elo solo queue ({games} games)")
    if champ in ctx.saved:
        parts["save"] = -W["save"]
        reasons.append("saved for a later game of this series (Fearless)")
    return Option(champ, role, sum(parts.values()), parts, reasons)


def saved_for_later(prefs: Preferences | None, save: dict[str, int] | None, game: int) -> set[str]:
    """Champions not to spend in this game: the coach's save list before game LATE_GAME, and the planner's save plan
    (champion -> first game we may pick it in)."""
    out = {c for c, first in (save or {}).items() if game < first}
    if prefs is not None and game < LATE_GAME:
        out |= set(prefs.strategy.save_for_late_games)
    return out


def coach_for_opponent(table: dict[str, list[str]], *names: str) -> set[str]:
    """Coach entries keyed by a team name, matched case-insensitively to the opponent's name or id, or as a prefix
    of it ("Team Liquid" matches "Team Liquid Alienware")."""
    keys = [n.strip().lower() for n in names if n.strip()]
    return {
        c
        for team, champs in table.items()
        if team.strip() and any(k.startswith(team.strip().lower()) for k in keys)
        for c in champs
    }


def recommend_pick(
    m: Matchup, s: DraftState, prefs: Preferences | None = None, mode: Mode = "best", save: dict[str, int] | None = None
) -> list[Option]:
    """mode "save" leaves saved champions out; "best" keeps them with a penalty; "comfort_only" keeps the coach's
    signature/comfortable picks only."""
    lv = m.live
    ours, theirs = s.picks(US), s.picks(THEM)
    probs = action_probs(m, [s])[0]
    free = open_roles(np.array([(_idx(lv, ours) + [-1] * 4)[:4]], np.int32), lv.roles)[0]
    saved = saved_for_later(prefs, save, m.game_number)
    never: set[str] = set(prefs.strategy.never_pick) if prefs else set()
    if mode == "save":
        never |= saved
    ctx = _PickContext(ours, theirs, assign_roles(lv, theirs), prefs, mode, saved)
    options: list[Option] = []
    for c in np.argsort(-probs):
        champ, p = str(lv.vocab[int(c)]), float(probs[c])
        rank = lv.roles[c]
        roles = [ROLES[int(k)] for k in np.argsort(rank, kind="stable") if rank[k] < state.UNTAGGED and free[k]]
        if p > 0 and roles and champ not in never and (opt := _score_pick(m, ctx, champ, roles[0], p)) is not None:
            options.append(opt)
        if len(options) >= SHORTLIST * 2:
            break
    options.sort(key=_by_score)
    base = win_prob(m, ours, theirs)
    for o in options[:SHORTLIST]:
        o.win_prob = _expected_after_reply(m, s.play(o.champion), [*ours, o.champion], theirs)
        edge = o.win_prob - base
        o.parts["edge"] = W["edge"] * edge
        o.score += o.parts["edge"]
        if abs(edge) >= 0.005:  # noqa: PLR2004
            o.reasons.append(f"draft edge {edge:+.1%} win probability after their likely answer (weak evidence)")
    return sorted(options[:SHORTLIST], key=_by_score)[:TOP_N]


def _expected_after_reply(m: Matchup, after: DraftState, ours: list[str], theirs: list[str]) -> float:
    """Depth-1 expectimax: if the enemy picks next, average our win probability over their REPLIES most likely
    answers (weighted by LambdaRank); otherwise just the win probability of the current picks."""
    if after.complete or after.who(after.slot) != THEM or after.kind(after.slot) != "pick":
        return win_prob(m, ours, theirs)
    probs = action_probs(m, [after])[0]
    top = np.argsort(-probs)[:REPLIES]
    weights = probs[top] / probs[top].sum()
    return float(sum(w * win_prob(m, ours, [*theirs, m.live.vocab[c]]) for c, w in zip(top, weights, strict=True)))


def recommend_ban(m: Matchup, s: DraftState, prefs: Preferences | None = None, enemy_name: str = "") -> list[Option]:
    lv = m.live
    threat = action_probs(m, [s], as_pick_for=THEM)[0]
    pro = action_probs(m, [s])[0]
    their_comfort = m.cand[US][:, 6]  # opponent players' recency-weighted pool (log1p games)
    weight = prefs.weight if prefs else 0.0
    their_now = lv.now_for(m.them)
    must: set[str] = (
        coach_for_opponent(prefs.strategy.must_ban_vs_opponent, enemy_name, m.them) if prefs and weight else set()
    )
    hated: set[str] = {c for p in prefs.players for c in p.hates_playing_against} if prefs and weight else set()
    ours, theirs = s.picks(US), s.picks(THEM)
    base = win_prob(m, ours, theirs)
    shortlist = [int(c) for c in np.argsort(-(threat + pro))[: SHORTLIST * 2] if threat[c] > 0 or pro[c] > 0]
    taken = s.taken()
    coach_idx = [lv.builder.index[c] for c in sorted(must | hated) if c in lv.builder.index and c not in taken]
    options: list[Option] = []
    for c in dict.fromkeys(shortlist + coach_idx):  # coach picks are scored even when the model ranks them low
        champ = str(lv.vocab[c])
        parts = {
            "threat": BAN_W["threat"] * np.log(threat[c] + 1e-4),
            "comfort": BAN_W["comfort"] * float(their_comfort[c]),
            "pro": BAN_W["pro"] * np.log(pro[c] + 1e-4),
        }
        reasons = [f"they pick it {threat[c]:.0%} of the time at their next pick (model)"]
        best = max(
            (p for p in m.their_players),
            key=lambda p: lv.builder.st.player_on(p.player_id, int(c), their_now)[2],
            default=None,
        )
        if best is not None and (n := lv.builder.st.player_on(best.player_id, int(c), their_now)[2]):
            reasons.append(f"denies {best.name}: {n} pro games on it")
        if champ in must or champ in hated:
            parts["coach"] = BAN_W["coach"] * weight / DEFAULT_WEIGHT
            reasons.append("coach: must-ban vs this opponent" if champ in must else "a player hates playing against it")
        loss = base - win_prob(m, ours, [*theirs, champ])
        parts["edge"] = BAN_W["edge"] * loss
        if loss >= 0.005:  # noqa: PLR2004 - only when their getting it hurts us
            reasons.append(f"if they get it: {-loss:+.1%} win probability for us (weak evidence)")
        options.append(Option(champ, None, sum(parts.values()), parts, reasons))
    ranked = sorted(options, key=_by_score)
    top = ranked[:TOP_N]
    missing = [o for o in ranked[TOP_N:] if o.champion in must]  # a must-ban is always on the list
    return [*top[: TOP_N - len(missing)], *missing] if missing else top


def recommend(
    m: Matchup,
    s: DraftState,
    prefs: Preferences | None = None,
    mode: Mode = "best",
    enemy_name: str = "",
    save: dict[str, int] | None = None,
) -> list[Option]:
    if s.complete or s.who(s.slot) != US:
        return []
    if s.kind(s.slot) == "ban":
        return recommend_ban(m, s, prefs, enemy_name)
    return recommend_pick(m, s, prefs, mode, save)
