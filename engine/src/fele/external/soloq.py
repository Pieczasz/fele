"""High-elo ranked solo queue sampler (current-patch meta signal).

Ladder (Challenger/GM) -> PUUIDs -> ranked match ids -> match details -> compact participant rows.
Resumable: every response is cached on disk by the client, so re-runs don't repeat requests.
Only aggregates leave data_local/.
"""

import asyncio
import random
import time
from typing import Any

import polars as pl

from fele.config import settings
from fele.external.riot import PLATFORM_TO_REGION, RANKED_SOLO_QUEUE, RiotClient
from fele.jsontypes import JsonObj

DEFAULT_TIERS = ("challenger", "grandmaster")


def participant_rows(m: JsonObj, platform: str) -> list[dict[str, Any]]:
    info: JsonObj = m["info"]
    bans = {t["teamId"]: [b["championId"] for b in t.get("bans", [])] for t in info["teams"]}
    return [
        {
            "match_id": m["metadata"]["matchId"],
            "platform": platform,
            "game_version": info["gameVersion"],
            "patch": ".".join(info["gameVersion"].split(".")[:2]),
            "game_start_ms": info["gameStartTimestamp"],
            "duration_s": info["gameDuration"],
            "team_id": p["teamId"],
            "win": p["win"],
            "champion_id": p["championId"],
            "champion": p["championName"],
            "position": p.get("teamPosition") or "",
            "team_bans": bans.get(p["teamId"], []),
        }
        for p in info["participants"]
    ]


async def _apex_puuids(rc: RiotClient, platform: str, tiers: tuple[str, ...]) -> list[str]:
    puuids: list[str] = []
    for tier in tiers:
        league = await rc.apex_league(platform, tier) or {}
        puuids += [e["puuid"] for e in league.get("entries", []) if e.get("puuid")]
    return puuids


def _seen_match_ids(out_dir: str) -> set[str]:
    seen: set[str] = set()
    for f in settings().local(out_dir).glob("*.parquet"):
        seen |= set(pl.read_parquet(f, columns=["match_id"])["match_id"].unique().to_list())
    return seen


async def sample(
    platform: str,
    max_matches: int,
    days: int = 14,
    tiers: tuple[str, ...] = DEFAULT_TIERS,
    per_player: int = 20,
    seed: int = 0,
) -> int:
    region = PLATFORM_TO_REGION[platform]
    out_dir = settings().local("soloq", platform)
    start = int(time.time()) - days * 86400
    async with RiotClient() as rc:
        puuids = await _apex_puuids(rc, platform, tiers)
        random.Random(seed).shuffle(puuids)  # noqa: S311 - sampling order, not security
        seen = _seen_match_ids(f"soloq/{platform}")
        rows: list[dict[str, Any]] = []
        fetched = 0
        for puuid in puuids:
            if fetched >= max_matches:
                break
            ids = await rc.match_ids(region, puuid, start_time=start, count=per_player) or []
            new = [i for i in ids if i not in seen][: max_matches - fetched]
            matches = await asyncio.gather(*(rc.match(region, i) for i in new))
            for mid, m in zip(new, matches, strict=True):
                seen.add(mid)
                if m and m["info"].get("queueId") == RANKED_SOLO_QUEUE:
                    rows += participant_rows(m, platform)
                    fetched += 1
        if rows:
            pl.DataFrame(rows).write_parquet(out_dir / f"batch_{int(time.time())}.parquet")
        return fetched


def champion_patch_table() -> pl.DataFrame:
    """Champion x position x patch: games, wins, win rate, ban count (across all sampled platforms)."""
    files = list(settings().local("soloq").glob("*/*.parquet"))
    if not files:
        return pl.DataFrame()
    df = pl.concat([pl.read_parquet(f) for f in files]).unique(["match_id", "champion_id", "team_id"])
    picks = df.group_by("patch", "champion", "position").agg(
        games=pl.len(), wins=pl.col("win").sum(), platforms=pl.col("platform").n_unique()
    )
    n_matches = df.group_by("patch").agg(matches=pl.col("match_id").n_unique())
    bans = (
        df.unique(["match_id", "team_id"])
        .explode("team_bans")
        .group_by("patch", "team_bans")
        .agg(bans=pl.len())
        .rename({"team_bans": "champion_id"})
    )
    ids = df.select("champion", "champion_id").unique()
    bans = bans.join(ids, on="champion_id").drop("champion_id")
    return (
        picks.join(n_matches, on="patch")
        .join(bans.group_by("patch", "champion").agg(pl.col("bans").sum()), on=["patch", "champion"], how="left")
        .with_columns(win_rate=pl.col("wins") / pl.col("games"), pick_rate=pl.col("games") / pl.col("matches"))
        .sort("patch", "games", descending=[True, True])
    )
