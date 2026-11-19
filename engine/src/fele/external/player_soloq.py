"""Recent ranked solo-queue champion pools for the coach's own players. Off by default.

Only Riot IDs the coach typed into config/preferences.yaml (`riot_ids: ["Name#TAG@na1"]`) are looked up, never IDs
found elsewhere (docs/COMPLIANCE.md). Accounts or matches the API doesn't return are skipped. Only the player's own
row of each match is used, and the output is champion-level (no PUUIDs, no other players). It is kept separate from
GRID tables: nothing joins them in code.
"""

import time
from typing import Any

import polars as pl

from fele.external.riot import PLATFORM_TO_REGION, RANKED_SOLO_QUEUE, RiotClient
from fele.external.soloq import patch_of
from fele.prefs import Preferences

type Row = dict[str, Any]


def parse_riot_id(riot_id: str) -> tuple[str, str, str]:
    """'Game Name#TAG@na1' -> ('Game Name', 'TAG', 'na1')."""
    name_tag, _, platform = riot_id.rpartition("@")
    name, _, tag = name_tag.rpartition("#")
    if not (name and tag and platform in PLATFORM_TO_REGION):
        msg = f"Riot ID must look like 'GameName#TAG@platform' (platforms: {', '.join(PLATFORM_TO_REGION)})"
        raise ValueError(msg)
    return name, tag, platform


def account_region(platform: str) -> str:
    region = PLATFORM_TO_REGION[platform]
    return "asia" if region == "sea" else region  # account-v1 has no SEA routing


async def player_rows(rc: RiotClient, player: str, riot_id: str, days: int, max_matches: int) -> list[Row]:
    name, tag, platform = parse_riot_id(riot_id)
    account = await rc.account_by_riot_id(account_region(platform), name, tag)
    if not account:
        return []
    region = PLATFORM_TO_REGION[platform]
    start = int(time.time()) - days * 86400
    ids = await rc.match_ids(region, account["puuid"], start_time=start, count=max_matches) or []
    rows: list[Row] = []
    for mid in ids:
        m = await rc.match(region, mid)
        if not m or m["info"].get("queueId") != RANKED_SOLO_QUEUE:
            continue
        me = next((p for p in m["info"]["participants"] if p["puuid"] == account["puuid"]), None)
        if me:
            rows.append(
                {
                    "player": player,
                    "champion": me["championName"],
                    "position": me.get("teamPosition") or "",
                    "patch": patch_of(m["info"]["gameVersion"]),
                    "game_start_ms": m["info"]["gameStartTimestamp"],
                    "win": me["win"],
                }
            )
    return rows


def pool_table(rows: list[Row]) -> pl.DataFrame:
    """Player x champion: games, wins, win rate, last played, patches."""
    if not rows:
        return pl.DataFrame()
    return (
        pl.DataFrame(rows)
        .group_by("player", "champion")
        .agg(
            games=pl.len(),
            wins=pl.col("win").sum(),
            last_played=pl.from_epoch(pl.col("game_start_ms").max(), time_unit="ms").dt.replace_time_zone("UTC"),
            patches=pl.col("patch").unique().sort(),
        )
        .with_columns(win_rate=pl.col("wins") / pl.col("games"))
        .sort("player", "games", descending=[False, True])
    )


async def pools(prefs: Preferences, days: int = 30, max_matches: int = 100) -> pl.DataFrame:
    rows: list[Row] = []
    async with RiotClient() as rc:
        for p in prefs.players:
            for riot_id in p.riot_ids:
                rows += await player_rows(rc, p.name, riot_id, days, max_matches)
    return pool_table(rows)
