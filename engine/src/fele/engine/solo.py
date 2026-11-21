"""Champ-select advice for the user's own games (solo/duo, flex, Clash): ranked options with reasons, never orders.

No GRID data: everything comes from the live-patch high-elo solo-queue sample (Riot API), the reviewed champion
tags, and the recent games of the user and their party members (the client's match history).

  picks: meta     = shrunk win rate at the position, last META_PATCHES patches            n shown
         presence = how often high-elo players pick it at the position (viability)
         comfort  = the player's recency-weighted games on it                           n shown
         form     = the player's shrunk win rate on it vs their own average             n shown
         lane     = shrunk matchup vs the enemy pick most likely in the same lane       n shown
         comp     = fills a damage / frontline / engage / peel gap                     tags
  bans:  threat   = shrunk win rate at its best position + pick/ban presence           n shown
         counter  = beats one of the party's comfort picks in lane                     n shown
Weights are fixed by design and checked by `fele eval solo` (docs/MODEL_CARD.md).
"""

import math
from collections import defaultdict
from dataclasses import dataclass
from functools import cache

import polars as pl

from fele.config import settings
from fele.engine.recommend import TOP_N, Option, comp_fit
from fele.features import state
from fele.lcu.history import Pool
from fele.lcu.state import ChampSelect
from fele.static.ddragon import patch_key

META_PATCHES = 2
META_PRIOR = 60.0  # pseudo-games shrinking a champion's win rate at a position toward 50%
MATCHUP_PRIOR = 20.0
MIN_POSITION_GAMES = 3  # high-elo games at a position that make a champion "played there"
EVIDENCE_GAMES = 20  # meta/matchup reasons are shown from this many games on
POOL_EVIDENCE = 3
W = {"meta": 6.0, "presence": 0.5, "comfort": 1.6, "form": 3.0, "lane": 4.0, "comp": 0.6}  # eval-solo sweep
BAN_W = {"threat": 6.0, "presence": 0.4, "counter": 4.0}
ROLE_OF = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "mid", "BOTTOM": "bot", "UTILITY": "support"}
COMFORT_PICKS = 3  # a party member's top champions: checked for counters, never suggested as bans
COUNTER_EDGE = 0.02  # shrunk lane edge needed to call a champion a counter


@dataclass(frozen=True)
class SoloData:
    names: dict[int, str]  # champion id -> display name
    keys: dict[int, str]  # champion id -> Data Dragon key (icons)
    roles: dict[int, tuple[str, ...]]  # tagged roles, primary first
    tags: dict[str, dict[str, float]]  # str(champion id) -> tag values
    meta: dict[tuple[str, int], tuple[int, int]]  # (role, champion) -> (games, wins)
    bans: dict[int, int]
    matches: int
    patches: tuple[str, ...]
    matchups: dict[tuple[str, int, int], tuple[int, int]]  # (role, champion, opponent) -> (games, wins)

    def meta_rate(self, role: str, champion: int) -> tuple[float, int]:
        games, wins = self.meta.get((role, champion), (0, 0))
        return (wins + 0.5 * META_PRIOR) / (games + META_PRIOR), games

    def matchup(self, role: str, champion: int, opponent: int) -> tuple[float, int]:
        games, wins = self.matchups.get((role, champion, opponent), (0, 0))
        return (wins + 0.5 * MATCHUP_PRIOR) / (games + MATCHUP_PRIOR), games

    def plays(self, role: str, champion: int) -> bool:
        return role in self.roles.get(champion, ()) or self.meta.get((role, champion), (0, 0))[0] >= MIN_POSITION_GAMES

    @property
    def patch_label(self) -> str:
        return "–".join(sorted(self.patches, key=patch_key)) if self.patches else "no sample"


def build_solo(champions: pl.DataFrame, champ_patch: pl.DataFrame, matchups: pl.DataFrame) -> SoloData:
    names: dict[int, str] = {}
    keys: dict[int, str] = {}
    roles: dict[int, tuple[str, ...]] = {}
    tags: dict[str, dict[str, float]] = {}
    for r in champions.iter_rows(named=True):
        cid = int(r["riot_id"])
        names[cid], keys[cid] = r["name"], r["champion"]
        roles[cid] = tuple(str(r["roles"] or "").split("|")) if r["roles"] else ()
        if r["scaling"] is not None:
            tags[str(cid)] = {c: float(r[c]) for c in state.TAG_COLS} | {
                "scaling": state.SCALING.get(r["scaling"], 1.0)
            }
    patches = (
        tuple(sorted(champ_patch["patch"].unique().to_list(), key=patch_key)[-META_PATCHES:])
        if len(champ_patch)
        else ()
    )
    recent = champ_patch.filter(pl.col("patch").is_in(patches))
    meta = {
        (ROLE_OF[p], int(c)): (int(g), int(w))
        for p, c, g, w in recent.group_by("position", "champion_id")
        .agg(pl.col("games").sum(), pl.col("wins").sum())
        .iter_rows()
        if p in ROLE_OF
    }
    per_patch = recent.group_by("patch", "champion_id").agg(pl.col("bans").first(), pl.col("matches").first())
    bans = {int(c): int(b) for c, b in per_patch.group_by("champion_id").agg(pl.col("bans").sum()).iter_rows()}
    matches = int(recent.group_by("patch").agg(pl.col("matches").first())["matches"].sum()) if len(recent) else 0
    mu = {
        (ROLE_OF[p], int(c), int(o)): (int(g), int(w))
        for p, c, o, g, w in matchups.group_by("position", "champion_id", "opponent_id")
        .agg(pl.col("games").sum(), pl.col("wins").sum())
        .iter_rows()
        if p in ROLE_OF
    }
    return SoloData(names, keys, roles, tags, meta, bans, matches, patches, mu)


@cache
def load_solo() -> SoloData:
    """From data_local/static and data_local/aggregates (cached for the process)."""
    static, agg = settings().local("static"), settings().local("aggregates")
    empty_patch = pl.DataFrame(
        schema={
            "patch": pl.String,
            "champion_id": pl.Int64,
            "position": pl.String,
            "games": pl.Int64,
            "wins": pl.Int64,
            "bans": pl.Int64,
            "matches": pl.Int64,
        }
    )
    empty_mu = pl.DataFrame(
        schema={
            "position": pl.String,
            "champion_id": pl.Int64,
            "opponent_id": pl.Int64,
            "games": pl.Int64,
            "wins": pl.Int64,
        }
    )
    cp, mu = agg / "soloq_champion_patch.parquet", agg / "soloq_matchups.parquet"
    return build_solo(
        pl.read_parquet(static / "champions.parquet"),
        pl.read_parquet(cp) if cp.exists() else empty_patch,
        pl.read_parquet(mu) if mu.exists() else empty_mu,
    )


def enemy_lanes(data: SoloData, picks: list[int]) -> dict[str, int]:
    """Most likely lane of each enemy pick: primary tagged role first, then the role it is most played in."""
    out: dict[str, int] = {}
    for c in picks:
        by_games = sorted(ROLE_OF.values(), key=lambda r: -data.meta.get((r, c), (0, 0))[0])
        for role in (*data.roles.get(c, ()), *by_games):
            if role not in out:
                out[role] = c
                break
    return out


def _who(name: str | None) -> str:
    """None = the local player."""
    return name.split("#")[0] if name else "you"


def _whose(name: str | None) -> str:
    return f"{name.split('#')[0]}'s" if name else "your"


def pick_options(  # noqa: PLR0913 - weights are overridable for `fele eval-solo` only
    data: SoloData,
    cs: ChampSelect,
    cell: int,
    pool: Pool | None,
    name: str | None = None,
    *,
    top_n: int = TOP_N,
    weights: dict[str, float] | None = None,
) -> list[Option]:
    """Ranked picks for one of our cells. `pool` only for the local player and party members (privacy rule)."""
    ally = cs.ally(cell)
    role = ally.position if ally else None
    others = {a.champion or a.intent for a in cs.allies if a.cell != cell} - {0}
    blocked = cs.unavailable | others
    ours = [str(c) for c in cs.ally_picks if c and (not ally or c != ally.champion)]
    lanes = enemy_lanes(data, list(cs.enemy_picks))
    w = W | (weights or {})
    options: list[Option] = []
    for c, cname in data.names.items():
        if c in blocked:
            continue
        own = pool.champions.get(c) if pool else None
        if role and not (data.plays(role, c) or (own and own.positions[role] >= 2)):  # noqa: PLR2004
            continue
        parts: dict[str, float] = {}
        reasons: list[str] = []
        if role:
            wr, n = data.meta_rate(role, c)
            parts["meta"] = w["meta"] * (wr - 0.5)
            parts["presence"] = w["presence"] * math.log1p(n)
            if n >= EVIDENCE_GAMES:
                reasons.append(f"{wr:.0%} adj. win rate at {role} in {n} high-elo games ({data.patch_label})")
            enemy = lanes.get(role)
            if enemy:
                mwr, mn = data.matchup(role, c, enemy)
                parts["lane"] = w["lane"] * (mwr - 0.5)
                if mn >= EVIDENCE_GAMES // 2:
                    reasons.append(f"vs {data.names.get(enemy, enemy)} in lane: {mwr:.0%} adj. in {mn} games")
        if pool and own:
            parts["comfort"] = w["comfort"] * math.log1p(own.weight)
            swr, sn = pool.shrunk(c)
            parts["form"] = w["form"] * (swr - pool.win_rate)
            if sn >= POOL_EVIDENCE:
                reasons.append(f"{_who(name)}: {sn} of the last {pool.games} games on it, {own.wins / sn:.0%} won")
        fit, why = comp_fit(data.tags, ours, str(c))
        parts["comp"] = w["comp"] * fit
        reasons += why
        options.append(Option(cname, role, sum(parts.values()), parts, reasons))
    options.sort(key=lambda o: -o.score)
    return options[:top_n]


def _counters(
    data: SoloData, cs: ChampSelect, pools: dict[int, tuple[Pool, str | None]]
) -> defaultdict[int, list[tuple[float, str]]]:
    """Enemy champions that beat one of our likely picks (the party's comfort picks at their positions) in lane."""
    comfort: list[tuple[str, int, str | None]] = []  # (role, champion, owner) of our likely picks
    for cell, (pool, name) in pools.items():
        ally = cs.ally(cell)
        if ally and ally.position:
            comfort += [(ally.position, c, name) for c, _ in pool.top(COMFORT_PICKS, ally.position)]
    counters: defaultdict[int, list[tuple[float, str]]] = defaultdict(list)
    for role, ours, owner in comfort:
        for enemy in data.names:
            wr, n = data.matchup(role, ours, enemy)  # our win rate when they pick `enemy`
            if wr < 0.5 - COUNTER_EDGE and n >= EVIDENCE_GAMES // 2:
                why = f"counters {_whose(owner)} {data.names.get(ours, ours)} ({role}): {1 - wr:.0%} adj. in {n} games"
                counters[enemy].append((0.5 - wr, why))
    return counters


def ban_options(
    data: SoloData, cs: ChampSelect, pools: dict[int, tuple[Pool, str | None]], top_n: int = TOP_N
) -> list[Option]:
    """Ranked bans. `pools`: our cell -> (pool, name) for the local player and party members only."""
    keep = {a.champion or a.intent for a in cs.allies} - {0}  # never ban what a teammate shows
    keep |= {c for pool, _ in pools.values() for c, _ in pool.top(COMFORT_PICKS)}  # or a party member's best picks
    blocked = cs.unavailable | keep
    counters = _counters(data, cs, pools)
    options: list[Option] = []
    for c, cname in data.names.items():
        if c in blocked:
            continue
        best = max(ROLE_OF.values(), key=lambda r: data.meta.get((r, c), (0, 0))[0])  # its main position
        wr, n = data.meta_rate(best, c)
        picks = sum(data.meta.get((r, c), (0, 0))[0] for r in ROLE_OF.values())
        bans = data.bans.get(c, 0)
        presence = (picks + bans) / data.matches if data.matches else 0.0
        parts = {"threat": BAN_W["threat"] * (wr - 0.5), "presence": BAN_W["presence"] * math.log1p(100 * presence)}
        reasons: list[str] = []
        if data.matches:
            reasons.append(f"picked or banned in {presence:.0%} of {data.matches} high-elo games ({data.patch_label})")
        if n >= EVIDENCE_GAMES:
            reasons.append(f"{wr:.0%} adj. win rate at {best} in {n} games")
        if counters[c]:
            parts["counter"] = BAN_W["counter"] * sum(edge for edge, _ in counters[c])
            reasons += [why for _, why in counters[c]]
        options.append(Option(cname, None, sum(parts.values()), parts, reasons))
    options.sort(key=lambda o: -o.score)
    return options[:top_n]
