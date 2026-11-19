"""Role inference per team-game (GRID has no role column and roster order is unreliable).

Signals (all from the game itself):
- jungle: the player's share of the team's neutral-monster kills;
- support: bought an item of the support quest line (World Atlas → …), fallback lowest minion kills;
- mid: share of early position snapshots on the mid lane;
- bot vs top: share of early snapshots in the *support's* side lane vs the other side lane. This keeps
  lane swaps (top laner sent bot, duo sent top) from swapping top and bot;
- roster order: weak prior.
All 5! = 120 assignments are scored, so `role_confidence` is the exact posterior of the chosen one.
"""

import math
from collections import Counter, defaultdict
from itertools import permutations
from typing import Any

import polars as pl

from fele.prefs import Role

ROLES = (Role.top, Role.jungle, Role.mid, Role.bot, Role.support)
SUPPORT_ITEMS = frozenset(
    {
        "World Atlas",
        "Runic Compass",
        "Bounty of Worlds",
        "Celestial Opposition",
        "Dream Maker",
        "Solstice Sleigh",
        "Bloodsong",
        "Zaz'Zak's Realmspike",
    }
)
EARLY = (90, 600)  # seconds: laning phase snapshots
SHOP_SOURCES = ("player-purchased-item", "player-sold-item")
LANE_EDGE = 3000  # map units from the map edge that count as a side lane
MID_WIDTH = 1800
MAP_MAX = 15000
ROSTER_PRIOR = (0.6, 0.1)  # (same index as role, other) — roster order is right ~50-60% of the time
LOW_CONFIDENCE = 0.9
SWAP_PRIOR = (0.8, 0.2)  # normal lanes vs lane swap
EM_ROUNDS = 2  # re-score with champion priors learned from confident games


def lane(x: float, y: float) -> str | None:
    """'top' / 'bot' side lane, 'mid', or None (jungle, river, base)."""
    if abs(x - y) < MID_WIDTH and LANE_EDGE < x < MAP_MAX - LANE_EDGE:
        return "mid"
    if (x < LANE_EDGE and y > LANE_EDGE + 1000) or (y > MAP_MAX - LANE_EDGE and x < MAP_MAX - LANE_EDGE - 1000):
        return "top"
    if (y < LANE_EDGE and x > LANE_EDGE + 1000) or (x > MAP_MAX - LANE_EDGE and y < MAP_MAX - LANE_EDGE - 1000):
        return "bot"
    return None


def _log(p: float) -> float:
    return math.log(min(max(p, 1e-4), 1.0))


def _team_scores(
    players: list[dict[str, Any]], lanes: dict[str, Counter[str]], champ_prior: dict[str, list[float]]
) -> list[list[list[float]]]:
    """Log-score matrices [hypothesis][player][role]; hypotheses = normal lanes, lane swap."""
    neutral_total = sum(p["neutral_killed"] or 0 for p in players) or 1
    has_sup_item = any(p["support_item"] for p in players)
    min_cs = min((p["minions_killed"] or 0) for p in players)
    out: list[list[list[float]]] = []
    for solo, duo in (("top", "bot"), ("bot", "top")):
        rows: list[list[float]] = []
        for p in players:
            jg = 0.02 + 0.96 * (p["neutral_killed"] or 0) / neutral_total
            sup = p["support_item"] or (not has_sup_item and (p["minions_killed"] or 0) == min_cs)
            sup_ev = 0.95 if sup else 0.05
            c = lanes[p["player_id"]]
            n = sum(c.values()) + 1.5
            f = {k: (c.get(k, 0) + 0.5) / n for k in ("mid", "top", "bot")}
            laner = _log(1 - jg) + _log(1 - sup_ev)
            by_role = {
                Role.top: _log(f[solo]) + laner,
                Role.jungle: _log(jg),
                Role.mid: _log(f["mid"]) + laner,
                Role.bot: _log(f[duo]) + laner,
                Role.support: _log(sup_ev) + _log(1 - jg) + _log(f[duo]),
            }
            prior = champ_prior.get(p["champion"] or "", [1 / len(ROLES)] * len(ROLES))
            rows.append(
                [
                    by_role[r] + _log(prior[k]) + _log(ROSTER_PRIOR[0] if p["roster_index"] == k else ROSTER_PRIOR[1])
                    for k, r in enumerate(ROLES)
                ]
            )
        out.append(rows)
    return out


def _assign(hypotheses: list[list[list[float]]]) -> tuple[tuple[int, ...], float, bool]:
    """Best role index per player, its posterior over all assignments, and whether lanes were swapped."""
    n = len(hypotheses[0])
    totals: dict[tuple[int, ...], float] = {}
    swapped: dict[tuple[int, ...], bool] = {}
    for perm in permutations(range(len(ROLES)), n):
        per_h = [_log(w) + sum(m[i][perm[i]] for i in range(n)) for w, m in zip(SWAP_PRIOR, hypotheses, strict=True)]
        hi = max(per_h)
        totals[perm] = hi + math.log(sum(math.exp(v - hi) for v in per_h))
        swapped[perm] = per_h[1] > per_h[0]
    best = max(totals, key=totals.__getitem__)
    top = totals[best]
    z = sum(math.exp(v - top) for v in totals.values())
    return best, 1 / z, swapped[best]


def _pass(
    teams: list[list[dict[str, Any]]], lanes: dict[str, Counter[str]], champ_prior: dict[str, list[float]]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for players in teams:
        perm, conf, swap = _assign(_team_scores(players, lanes, champ_prior))
        for i, p in enumerate(players):
            c = lanes[p["player_id"]]
            out.append(
                {
                    "game_id": p["game_id"],
                    "player_id": p["player_id"].split("|")[1],
                    "champion": p["champion"],
                    "inferred_role": str(ROLES[perm[i]]),
                    "role_confidence": conf,
                    "lane_swap": swap,
                    "support_item": p["support_item"],
                    "early_top": c.get("top", 0),
                    "early_mid": c.get("mid", 0),
                    "early_bot": c.get("bot", 0),
                }
            )
    return out


def champion_prior(rows: list[dict[str, Any]], min_conf: float = LOW_CONFIDENCE) -> dict[str, list[float]]:
    """P(role | champion) from confident assignments, Laplace-smoothed."""
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for r in rows:
        if r["role_confidence"] >= min_conf:
            counts[r["champion"]][r["inferred_role"]] += 1
    return {ch: [(c.get(str(r), 0) + 1) / (c.total() + len(ROLES)) for r in ROLES] for ch, c in counts.items()}


def infer_roles(participants: pl.DataFrame, positions: pl.DataFrame, item_events: pl.DataFrame) -> pl.DataFrame:
    """One row per (game_id, player_id): inferred_role, role_confidence, plus the signals used."""
    sup_buyers = set(
        item_events.filter(pl.col("action") == "purchased", pl.col("item").is_in(list(SUPPORT_ITEMS)))
        .select(pl.concat_str("game_id", "player_id", separator="|"))
        .to_series()
        .to_list()
    )
    early = positions.filter(pl.col("t_s").is_between(*EARLY), ~pl.col("source").is_in(SHOP_SOURCES))
    lanes: dict[str, Counter[str]] = defaultdict(Counter)
    for gid, pid, x, y in early.select("game_id", "player_id", "x", "y").iter_rows():
        if (ln := lane(x, y)) is not None:
            lanes[f"{gid}|{pid}"][ln] += 1

    teams: list[list[dict[str, Any]]] = []
    skipped: list[dict[str, Any]] = []
    for (gid, _tid), grp in participants.sort("roster_index").group_by(["game_id", "team_id"], maintain_order=True):
        members = list(grp.iter_rows(named=True))
        if len(members) != len(ROLES):
            skipped += [{"game_id": gid, "player_id": p["player_id"]} for p in members]
            continue
        teams.append(
            [
                {**p, "support_item": f"{gid}|{p['player_id']}" in sup_buyers, "player_id": f"{gid}|{p['player_id']}"}
                for p in members
            ]
        )
    rows: list[dict[str, Any]] = _pass(teams, lanes, {})
    for _ in range(EM_ROUNDS):
        rows = _pass(teams, lanes, champion_prior(rows))
    return pl.DataFrame(rows + skipped, infer_schema_length=None).drop("champion")


__all__ = ["LOW_CONFIDENCE", "ROLES", "champion_prior", "infer_roles", "lane"]
