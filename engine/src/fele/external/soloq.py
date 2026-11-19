"""High-elo ranked solo queue sampler (current-patch meta signal).

Ladder (Challenger/GM) -> PUUIDs -> ranked match ids -> match details (+ a deterministic share of timelines for
item builds) -> compact participant rows in data_local/soloq/<platform>/ (no PUUIDs or names kept).
Resumable: every match/timeline response is cached on disk by the client, so re-runs don't repeat those requests,
and rows parsed so far are written even when a run is interrupted. Only aggregates leave data_local/.
"""

import asyncio
import hashlib
import random
import time
from functools import cache
from typing import Any

import polars as pl

from fele.config import settings
from fele.external.riot import PLATFORM_TO_REGION, RANKED_SOLO_QUEUE, RiotClient
from fele.jsontypes import JsonObj
from fele.static.ddragon import cached, cached_versions, patch_of

APEX_TIERS = ("challenger", "grandmaster")
PER_PLAYER = 20  # recent match ids requested per ladder player
SEED = 0  # ladder shuffle, so re-runs walk players in the same order
CORE_ITEMS = 3  # first N completed items = the "build"
COMPLETED_MIN_GOLD = 1000

type Row = dict[str, Any]
ROW_TYPES = {"core_items": pl.List(pl.Int64)}  # all-None when no timeline was sampled → keep the list type


def completed_items(item_json: JsonObj) -> set[int]:
    """Finished Summoner's Rift items: buyable, nothing builds out of them, ≥ 1000 gold, not consumables."""
    data: dict[str, JsonObj] = item_json["data"]
    return {
        int(i)
        for i, it in data.items()
        if not it.get("into")
        and it["gold"]["purchasable"]
        and it["gold"]["total"] >= COMPLETED_MIN_GOLD
        and it.get("maps", {}).get("11")
        and "Consumable" not in it.get("tags", [])
    }


@cache
def completed_for_patch(patch: str) -> frozenset[int]:
    """Completed items of a patch from the cached Data Dragon item.json (latest cached patch as fallback)."""
    vs = cached_versions()
    for version in [v for v in vs if patch_of(v) == patch] + vs[:1]:
        try:
            return frozenset(completed_items(cached(version, "item")))
        except FileNotFoundError:
            continue
    return frozenset()


def item_order(timeline: JsonObj, completed: frozenset[int]) -> dict[int, list[int]]:
    """participantId -> completed items in purchase order (undone purchases removed, duplicates kept once)."""
    bought: dict[int, list[int]] = {}
    for frame in timeline["info"]["frames"]:
        for e in frame["events"]:
            pid = e.get("participantId")
            if e["type"] == "ITEM_PURCHASED" and e["itemId"] in completed:
                bought.setdefault(pid, []).append(e["itemId"])
            elif e["type"] == "ITEM_UNDO" and (undone := e.get("beforeId")) in (items := bought.get(pid, [])):
                del items[len(items) - 1 - items[::-1].index(undone)]  # the latest purchase of that item
    return {pid: list(dict.fromkeys(items)) for pid, items in bought.items()}


def participant_rows(m: JsonObj, platform: str, builds: dict[int, list[int]] | None = None) -> list[Row]:
    info: JsonObj = m["info"]
    bans = {t["teamId"]: [b["championId"] for b in t.get("bans", [])] for t in info["teams"]}
    return [
        {
            "match_id": m["metadata"]["matchId"],
            "platform": platform,
            "game_version": info["gameVersion"],
            "patch": patch_of(info["gameVersion"]),
            "game_start_ms": info["gameStartTimestamp"],
            "duration_s": info["gameDuration"],
            "team_id": p["teamId"],
            "win": p["win"],
            "champion_id": p["championId"],
            "champion": p["championName"],
            "position": p.get("teamPosition") or "",
            "team_bans": bans.get(p["teamId"], []),
            "core_items": builds.get(p["participantId"], [])[:CORE_ITEMS] if builds is not None else None,
        }
        for p in info["participants"]
    ]


def wants_timeline(match_id: str, share: float) -> bool:
    """Deterministic per match, so re-runs pick the same (already cached) timelines."""
    return int(hashlib.sha256(match_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF < share


async def _apex_puuids(rc: RiotClient, platform: str) -> list[str]:
    puuids: list[str] = []
    for tier in APEX_TIERS:
        league = await rc.apex_league(platform, tier) or {}
        puuids += [e["puuid"] for e in league.get("entries", []) if e.get("puuid")]
    return puuids


def _read_batches(pattern: str) -> pl.DataFrame | None:
    """Sampled batches under data_local/soloq/ (relaxed: early batches lack or null-type some columns)."""
    files = sorted(settings().local("soloq").glob(pattern))
    return pl.concat([pl.read_parquet(f) for f in files], how="diagonal_relaxed") if files else None


def _start_time(df: pl.DataFrame | None, patch: str | None, days: int) -> int:
    """Earliest sampled game of `patch` (≈ its release) if we've seen it, else `days` ago."""
    fallback = int(time.time()) - days * 86400
    if patch and df is not None and not (seen := df.filter(pl.col("patch") == patch)).is_empty():
        return max(fallback, int(seen["game_start_ms"].min()) // 1000)  # pyright: ignore[reportArgumentType]
    return fallback


async def sample(
    rc: RiotClient,
    platform: str,
    max_matches: int,
    days: int = 14,
    *,
    patch: str | None = None,
    timeline_share: float = 0.25,
) -> dict[str, int]:
    """Collect up to `max_matches` new ranked matches (on `patch`, if given). Returns counters.

    Pass one shared RiotClient for all platforms: rate limits are per routing host, and platforms share regional
    hosts for match-v5 (euw1 and eun1 both use `europe`).
    """
    region = PLATFORM_TO_REGION[platform]
    prev = _read_batches(f"{platform}/*.parquet")
    seen: set[str] = set(prev["match_id"].unique().to_list()) if prev is not None else set()
    start = _start_time(prev, patch, days)
    rows: list[Row] = []
    stats = {"matches": 0, "on_patch": 0, "timelines": 0}
    try:
        puuids = await _apex_puuids(rc, platform)
        random.Random(SEED).shuffle(puuids)  # noqa: S311 - sampling order, not security
        for puuid in puuids:
            if stats["on_patch"] >= max_matches:
                break
            ids = await rc.match_ids(region, puuid, start_time=start, count=PER_PLAYER) or []
            new = [i for i in ids if i not in seen]
            seen.update(new)
            matches = await asyncio.gather(*(rc.match(region, i) for i in new))
            ranked = [
                (i, m) for i, m in zip(new, matches, strict=True) if m and m["info"].get("queueId") == RANKED_SOLO_QUEUE
            ]
            wanted = [i for i, _ in ranked if wants_timeline(i, timeline_share)]
            timelines = dict(zip(wanted, await asyncio.gather(*(rc.timeline(region, i) for i in wanted)), strict=True))
            for mid, m in ranked:
                game_patch = patch_of(m["info"]["gameVersion"])
                builds = None
                if tl := timelines.get(mid):
                    builds = item_order(tl, completed_for_patch(game_patch))
                    stats["timelines"] += 1
                rows += participant_rows(m, platform, builds)
                stats["matches"] += 1
                stats["on_patch"] += patch is None or game_patch == patch
    finally:
        if rows:
            out = settings().local("soloq", platform) / f"batch_{int(time.time())}.parquet"
            pl.DataFrame(rows, infer_schema_length=None, schema_overrides=ROW_TYPES).write_parquet(out)
    return stats


def sample_rows() -> pl.DataFrame:
    """Every sampled participant row (all platforms), deduplicated; empty if nothing was sampled."""
    df = _read_batches("*/*.parquet")
    return pl.DataFrame() if df is None else df.unique(["match_id", "champion_id", "team_id"])


def champion_patch_table(df: pl.DataFrame) -> pl.DataFrame:
    """Champion x position x patch: games, wins, win rate, pick rate, bans, average game length (all platforms).

    Keyed by `champion_id`: match-v5 `championName` isn't always the Data Dragon key (e.g. "FiddleSticks").
    """
    if df.is_empty():
        return df
    picks = df.group_by("patch", "champion", "champion_id", "position").agg(
        games=pl.len(),
        wins=pl.col("win").sum(),
        platforms=pl.col("platform").n_unique(),
        avg_duration_s=pl.col("duration_s").mean(),
    )
    n_matches = df.group_by("patch").agg(matches=pl.col("match_id").n_unique())
    bans = (
        df.unique(["match_id", "team_id"])
        .explode("team_bans")
        .group_by("patch", "team_bans")
        .agg(bans=pl.len())
        .rename({"team_bans": "champion_id"})
    )
    return (
        picks.join(n_matches, on="patch")
        .join(bans, on=["patch", "champion_id"], how="left")
        .with_columns(win_rate=pl.col("wins") / pl.col("games"), pick_rate=pl.col("games") / pl.col("matches"))
        .sort("patch", "games", descending=[True, True])
    )


def matchup_table(df: pl.DataFrame) -> pl.DataFrame:
    """Lane matchups (same position, opposite teams): champion vs opponent x position x patch, games and wins."""
    if df.is_empty():
        return df
    cols = ("match_id", "patch", "position", "team_id", "champion", "champion_id", "win")
    lane = df.filter(pl.col("position") != "").select(cols)
    pairs = lane.join(
        lane.select("match_id", "position", "team_id", opponent="champion", opponent_id="champion_id"),
        on=["match_id", "position"],
    ).filter(pl.col("team_id") != pl.col("team_id_right"))
    return (
        pairs.group_by("patch", "position", "champion", "champion_id", "opponent", "opponent_id")
        .agg(games=pl.len(), wins=pl.col("win").sum())
        .with_columns(win_rate=pl.col("wins") / pl.col("games"))
        .sort("patch", "games", descending=[True, True])
    )


def items_table(df: pl.DataFrame) -> pl.DataFrame:
    """Most common completed-item orders (first 3) per champion x position x patch, from sampled timelines."""
    if df.is_empty() or "core_items" not in df.columns:
        return pl.DataFrame()
    items = pl.col("core_items").cast(pl.List(pl.Int64))  # older batches may hold an all-null column
    builds = df.with_columns(items).filter(items.list.len() > 0)
    return (
        builds.group_by("patch", "champion", "champion_id", "position", "core_items")
        .agg(games=pl.len(), wins=pl.col("win").sum())
        .with_columns(
            share=pl.col("games") / pl.col("games").sum().over("patch", "champion", "position"),
            win_rate=pl.col("wins") / pl.col("games"),
        )
        .sort("patch", "champion", "games", descending=[True, False, True])
    )
