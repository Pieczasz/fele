"""Draft-action rows for the action model (problem B: which champion will this team pick/ban now?).

One row per pick or ban of a standard-order draft, with the champions that weren't available at that moment:
picked or banned earlier in the same game, or locked by hard Fearless (picked in an earlier game of the series).
"""

import polars as pl


def action_frame(draft: pl.DataFrame, games: pl.DataFrame, fearless: pl.DataFrame) -> pl.DataFrame:
    """game_id, series_id, started_at, patch, team_id, action, phase, slot, champion, unavailable[]."""
    d = (
        draft.drop_nulls("slot")
        .join(games.select("game_id", "series_id", "started_at", "patch"), on="game_id")
        .join(fearless.select("game_id", "locked_champions"), on="game_id", how="left")
        .sort("game_id", "slot")
    )
    in_order = d.group_by("game_id").agg(game_champions=pl.col("champion").sort_by("slot"))
    return (
        d.join(in_order, on="game_id")
        .with_columns(position=pl.int_range(pl.len()).over("game_id", order_by="slot"))
        .with_columns(
            unavailable=pl.concat_list(
                pl.col("game_champions").list.slice(0, pl.col("position")),
                pl.col("locked_champions").fill_null([]),
            ).list.unique()
        )
        .select(
            "game_id",
            "series_id",
            "started_at",
            "patch",
            "team_id",
            "action",
            "phase",
            "slot",
            "champion",
            "unavailable",
        )
    )
