"""Game-level rows for the outcome model (problem A: does blue win?). Every feature is known before the game starts.

FEATURES lists the model inputs; everything else is an id, the label, or a column for sub-reports. The leakage tests
check that no in-game statistic is ever a feature.
"""

import polars as pl

from fele.stats import elo
from fele.stats.data import game_context

FEATURES = ("elo_diff", "expected_blue", "blue_n", "red_n")
SUBREPORTS = ("league", "game_bucket", "patch_age")


def patch_age() -> pl.Expr:
    """Days since the first game on this patch in the data (time-respecting: that game is never later)."""
    first = pl.col("started_at").min().over("patch")
    days = (pl.col("started_at") - first).dt.total_days()
    return pl.when(days < 7).then(pl.lit("week 1")).when(days < 14).then(pl.lit("week 2")).otherwise(pl.lit("week 3+"))  # noqa: PLR2004


def outcome_frame(games: pl.DataFrame, series: pl.DataFrame) -> pl.DataFrame:
    ctx = game_context(games, series).drop_nulls(["blue_team_id", "red_team_id", "winner_team_id", "started_at"])
    ratings = elo.game_elo(ctx)
    return (
        ctx.join(ratings, on="game_id")
        .with_columns(
            y=(pl.col("winner_team_id") == pl.col("blue_team_id")).cast(pl.Float64),
            elo_diff=pl.col("blue_elo") - pl.col("red_elo"),
            patch_age=patch_age(),
        )
        .select(
            "game_id",
            "series_id",
            "started_at",
            "league",
            "game_bucket",
            "patch",
            "patch_age",
            "blue_team_id",
            "red_team_id",
            "y",
            *FEATURES,
        )
        .sort("started_at", "game_id")
    )
