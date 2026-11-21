"""Does the champ-select scorer put a player's actual pick near the top? Checked on the high-elo solo-queue sample.

For every sampled ladder player with enough games (from the cached match-v5 JSON), in time order: the pool is built
from that player's *earlier* games only, the champ select shows the match's bans and the enemy laner's pick, and we
record where the real pick ranks. Methods: the scorer, its parts alone, and "most played". Output is aggregate hit
rates only; no player ids leave this module. Caveats: Challenger/Grandmaster players, and the meta aggregates include
the evaluated matches (one game in ~1,800 per champion-position cell).
"""

import gzip
import json
import math
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fele.config import settings
from fele.engine import solo
from fele.external.riot import RANKED_SOLO_QUEUE
from fele.jsontypes import JsonObj
from fele.lcu.history import Game, pool_of
from fele.lcu.state import Ally, ChampSelect

MIN_HISTORY = 5
TOPS = (1, 5, 10)
METHODS: dict[str, dict[str, float]] = {  # weight overrides on top of solo.W
    "scorer": {},
    "meta only": {"comfort": 0.0, "form": 0.0},
    "comfort only": {"meta": 0.0, "presence": 0.0, "lane": 0.0, "comp": 0.0, "form": 0.0},
    "presence only": {"meta": 0.0, "lane": 0.0, "comp": 0.0, "comfort": 0.0, "form": 0.0},
}
SWEEP = {"comfort": (0.8, 1.6, 3.2), "presence": (0.25, 0.5, 1.0)}
RANK_ALL = 400
ROLE_OF = solo.ROLE_OF


@dataclass(frozen=True)
class PlayerGame:
    start_ms: int
    champion: int
    role: str
    win: bool
    bans: tuple[int, ...]
    enemy_laner: int | None


def cached_matches(cache: Path | None = None) -> Iterator[JsonObj]:
    """Ranked solo-queue match JSON from data_local/riot_cache (timelines and other replies skipped)."""
    seen: set[str] = set()
    for f in sorted((cache or settings().local("riot_cache")).glob("*/*.json.gz")):
        m: JsonObj | list[Any] = json.loads(gzip.decompress(f.read_bytes()))
        if isinstance(m, list):
            continue  # match-id lists
        info: JsonObj = m.get("info") or {}
        meta: JsonObj = m.get("metadata") or {}
        mid = str(meta.get("matchId", f.name))
        if "frames" in info or info.get("queueId") != RANKED_SOLO_QUEUE or mid in seen:
            continue
        seen.add(mid)
        yield m


def player_games(matches: Iterator[JsonObj]) -> list[list[PlayerGame]]:
    """Per player (anonymous), their games in time order."""
    by_player: defaultdict[str, list[PlayerGame]] = defaultdict(list)
    for m in matches:
        info = m["info"]
        parts = info["participants"]
        bans = tuple(b["championId"] for t in info.get("teams", []) for b in t.get("bans", []) if b["championId"] > 0)
        lane = {(p["teamId"], p.get("teamPosition")): p["championId"] for p in parts}
        for p in parts:
            role = ROLE_OF.get(p.get("teamPosition") or "")
            if role and p.get("puuid"):
                enemy = lane.get((300 - p["teamId"], p["teamPosition"]))  # team ids are 100 and 200
                game = PlayerGame(info["gameStartTimestamp"], p["championId"], role, p["win"], bans, enemy)
                by_player[p["puuid"]].append(game)
    return [sorted(g, key=lambda x: x.start_ms) for g in by_player.values()]


def _champ_select(g: PlayerGame) -> ChampSelect:
    me = Ally(cell=2, position=g.role, champion=0, intent=0, puuid="p", name=None, me=True)
    enemy = (g.enemy_laner,) if g.enemy_laner else ()
    return ChampSelect(
        queue=420,
        custom=False,
        me=2,
        allies=(me,),
        enemy_picks=enemy,
        ally_bans=g.bans,
        enemy_bans=(),
        actions=(),
        phase="BAN_PICK",
        time_left_ms=0,
    )


def ranks(data: solo.SoloData, players: list[list[PlayerGame]], weights: dict[str, float]) -> list[int | None]:
    """Rank (1 = top) of the actual pick for every evaluable player-game; None = not offered (off-role filter)."""
    out: list[int | None] = []
    for games in players:
        for k in range(MIN_HISTORY, len(games)):
            g = games[k]
            past = [Game(x.champion, x.role, x.win, x.start_ms, 420) for x in games[:k]]
            opts = solo.pick_options(
                data, _champ_select(g), 2, pool_of(past, now_ms=g.start_ms), top_n=RANK_ALL, weights=weights
            )
            names = [o.champion for o in opts]
            actual = data.names.get(g.champion)
            out.append(names.index(actual) + 1 if actual in names else None)
    return out


def hit_rates(r: list[int | None]) -> dict[int, tuple[float, float]]:
    """top-k -> (rate, 95% half-width)."""
    n = len(r)
    res: dict[int, tuple[float, float]] = {}
    for k in TOPS:
        p = sum(1 for x in r if x is not None and x <= k) / n if n else 0.0
        res[k] = (p, 1.96 * math.sqrt(p * (1 - p) / n) if n else 0.0)
    return res


def report(data: solo.SoloData | None = None, players: list[list[PlayerGame]] | None = None) -> str:
    data = data or solo.load_solo()
    players = players if players is not None else player_games(cached_matches())
    evaluable = [p for p in players if len(p) > MIN_HISTORY]
    lines = [
        "# Champ-select scorer check (high-elo solo queue)",
        "",
        (
            f"Sample: {data.patch_label}, {data.matches} matches; {len(evaluable)} players with more than "
            f"{MIN_HISTORY} games; pool from each player's earlier games only; bans and the enemy laner visible."
        ),
        "",
        "| Method | n | top-1 | top-5 | top-10 | not offered |",
        "|---|---|---|---|---|---|",
    ]
    for name, weights in METHODS.items():
        r = ranks(data, evaluable, weights)
        h = hit_rates(r)
        cells = " | ".join(f"{h[k][0]:.1%} ± {h[k][1]:.1%}" for k in TOPS)
        lines.append(f"| {name} | {len(r)} | {cells} | {sum(x is None for x in r) / max(len(r), 1):.1%} |")
    tune, test = evaluable[::2], evaluable[1::2]
    best = max(
        ({"comfort": c, "presence": p} for c in SWEEP["comfort"] for p in SWEEP["presence"]),
        key=lambda w: hit_rates(ranks(data, tune, w))[5][0],
    )
    h_best, h_default = hit_rates(ranks(data, test, best)), hit_rates(ranks(data, test, {}))
    lines += [
        "",
        (
            f"Weight sweep (comfort x presence, chosen on half the players by top-5, reported on the other half): "
            f"best {best} → top-5 {h_best[5][0]:.1%} vs the default weights {h_default[5][0]:.1%} on the same players."
        ),
    ]
    return "\n".join(lines) + "\n"
