"""Load the ingested GRID tables (data_local/parquet) with the game context every stats module needs."""

import polars as pl

from fele.ingest.build import parquet_dir
from fele.static.ddragon import patch_key

WINDOW_PATCHES = 3  # trailing patch window: the patch itself + the 2 previous patches played in GRID


def read(table: str) -> pl.DataFrame:
    return pl.read_parquet(parquet_dir() / f"{table}.parquet")


def game_context(games: pl.DataFrame, series: pl.DataFrame) -> pl.DataFrame:
    """One row per game: league, date, patch, game number bucket (G1 / G2 / G3+), sides, winner."""
    return games.join(series.select("series_id", "league", "event", "format"), on="series_id", how="left").select(
        "game_id",
        "series_id",
        "league",
        "event",
        "format",
        "started_at",
        "patch",
        "game_number",
        pl.when(pl.col("game_number") >= 3)  # noqa: PLR2004 - G3+ = Fearless late games
        .then(pl.lit("G3+"))
        .otherwise(pl.format("G{}", pl.col("game_number")))
        .alias("game_bucket"),
        "blue_team_id",
        "red_team_id",
        "winner_team_id",
        "first_pick_team_id",
    )


def team_games(ctx: pl.DataFrame) -> pl.DataFrame:
    """One row per team-game: team_id, opponent_id, side, win + game context."""
    sides = [("blue", "blue_team_id", "red_team_id"), ("red", "red_team_id", "blue_team_id")]
    return pl.concat(
        [
            ctx.with_columns(
                team_id=pl.col(me),
                opponent_id=pl.col(opp),
                side=pl.lit(side),
                win=pl.col("winner_team_id") == pl.col(me),
            )
            for side, me, opp in sides
        ]
    ).drop("blue_team_id", "red_team_id", "winner_team_id")


def patches(ctx: pl.DataFrame) -> list[str]:
    """GRID patches, oldest first."""
    return sorted(ctx["patch"].drop_nulls().unique().to_list(), key=patch_key)


def trailing_windows(all_patches: list[str], size: int = WINDOW_PATCHES) -> pl.DataFrame:
    """(window, patch) pairs: window `P` contains P and the `size - 1` patches before it."""
    return pl.DataFrame(
        [
            {"window": p, "patch": q}
            for i, p in enumerate(all_patches)
            for q in all_patches[max(0, i - size + 1) : i + 1]
        ]
    )
