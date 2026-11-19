"""Full GRID ingest: replay every series in parallel, infer roles, write Parquet to data_local/parquet/.

Idempotent: every run rewrites all tables from the raw feeds.
"""

import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import polars as pl

from fele.config import settings
from fele.ingest.grid import series_index, series_path
from fele.ingest.replay import Tables, replay
from fele.ingest.roles import infer_roles

TABLES = (
    "series",
    "games",
    "draft_actions",
    "participants",
    "kills",
    "objectives",
    "levelups",
    "item_events",
    "positions",
)


def parquet_dir() -> Path:
    return settings().local("parquet")


def _replay_one(series_id: str) -> Tables:
    return replay(series_id, series_path(series_id))


def _frame(rows: list[dict[str, object]]) -> pl.DataFrame:
    return pl.DataFrame(rows, infer_schema_length=None)


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
    acc: dict[str, list[dict[str, object]]] = {t: [] for t in TABLES}
    with ProcessPoolExecutor(workers) as ex:
        for tables in ex.map(_replay_one, list(index), chunksize=4):
            for t in TABLES:
                acc[t] += tables[t]

    frames = {t: _frame(acc.pop(t)) for t in TABLES}
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

    out = parquet_dir()
    counts: dict[str, int] = {}
    for name, df in frames.items():
        df.write_parquet(out / f"{name}.parquet")
        counts[name] = df.height
    counts["seconds"] = round(time.monotonic() - t0)
    return counts
