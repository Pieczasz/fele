"""Full GRID ingest: replay every series in parallel, infer roles, write Parquet to data_local/parquet/.

Idempotent: every run rewrites all tables from the raw feeds.
"""

import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import polars as pl

from fele.config import settings
from fele.db import write_tables
from fele.ingest.grid import series_index, series_path
from fele.ingest.replay import EVENT_TABLES, replay
from fele.ingest.roles import infer_roles

TABLES = ("series", "games", "draft_actions", "participants", *EVENT_TABLES)


def parquet_dir() -> Path:
    return settings().local("parquet")


def _replay_one(series_id: str) -> dict[str, pl.DataFrame]:
    """Runs in a worker: replay one series and build its frames there (pickling frames is ~8x cheaper than dicts)."""
    tables = replay(series_id, series_path(series_id))
    return {t: pl.DataFrame(tables[t], infer_schema_length=None) for t in TABLES}


def _utc(*cols: str) -> list[pl.Expr]:
    return [pl.col(c).str.to_datetime(time_zone="UTC") for c in cols]


def fearless_state(games: pl.DataFrame, draft: pl.DataFrame) -> pl.DataFrame:
    """Champions picked (by either team) in earlier games of the same series — locked under hard Fearless."""
    keys = games.select("game_id", "series_id", "game_number")
    picks = draft.filter(pl.col("action") == "pick").join(keys, on="game_id")
    pairs = keys.join(
        picks.select("series_id", pl.col("game_number").alias("earlier"), "champion"), on="series_id", how="left"
    )
    earlier = pl.when(pl.col("earlier") < pl.col("game_number")).then(pl.col("champion"))
    locked = (
        pairs.with_columns(earlier.alias("champion"))
        .group_by("game_id", "series_id", "game_number")
        .agg(pl.col("champion").drop_nulls().unique().sort().alias("locked_champions"))
    )
    count = pl.col("locked_champions").list.len().alias("locked_count")
    return locked.with_columns(count).sort("series_id", "game_number")


def build(workers: int | None = None) -> dict[str, int]:
    """Run the ingest and return row counts per table."""
    t0 = time.monotonic()
    index = {r["series_id"]: r for r in series_index()}
    with ProcessPoolExecutor(workers) as ex:
        parts = list(ex.map(_replay_one, list(index), chunksize=4))
    # relaxed: a series where a column is all null infers Null (or list[null]) and must upcast
    frames = {t: pl.concat([p[t] for p in parts if p[t].height], how="diagonal_relaxed") for t in TABLES}
    del parts
    meta = pl.DataFrame(list(index.values())).select("series_id", "event", "stage", "scheduled_start")
    frames["series"] = (
        frames["series"]
        .join(meta, on="series_id", how="left")
        .join(frames["games"].group_by("series_id").agg(pl.len().alias("games_played")), on="series_id", how="left")
        .with_columns(pl.col("event").str.split(" - ").list.first().alias("league"))
        .with_columns(*_utc("started_at", "scheduled_start"))
    )
    frames["games"] = frames["games"].with_columns(*_utc("started_at"))
    roles = infer_roles(frames["participants"], frames["positions"], frames["item_events"])
    frames["participants"] = frames["participants"].join(roles, on=["game_id", "player_id"], how="left")
    frames["fearless_state"] = fearless_state(frames["games"], frames["draft_actions"])

    counts = write_tables(parquet_dir(), frames)
    counts["seconds"] = round(time.monotonic() - t0)
    return counts
