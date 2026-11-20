"""Time-respecting team Elo: each game's ratings use only earlier games. Internal model feature, never displayed.

One rating per team. Leagues barely play each other (only international events and LTA Cross-Conference), so
ratings are comparable within a region only — don't rank teams across leagues with them.
"""

import polars as pl

INITIAL = 1500.0
K = 32.0


def expected(r_a: float, r_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400))


def current_ratings(ctx: pl.DataFrame) -> dict[str, float]:
    """Every team's rating after the last game in `ctx` (for live drafts)."""
    ratings: dict[str, float] = {}
    for g in (
        ctx.drop_nulls(["blue_team_id", "red_team_id", "winner_team_id"])
        .sort("started_at", "game_id")
        .iter_rows(named=True)
    ):
        blue, red = g["blue_team_id"], g["red_team_id"]
        rb, rr = ratings.get(blue, INITIAL), ratings.get(red, INITIAL)
        s = 1.0 if g["winner_team_id"] == blue else 0.0
        e = expected(rb, rr)
        ratings[blue], ratings[red] = rb + K * (s - e), rr - K * (s - e)
    return ratings


def game_elo(ctx: pl.DataFrame) -> pl.DataFrame:
    """Per game: blue/red pre-game rating, number of earlier rated games for each team (n), expected blue win."""
    ratings: dict[str, float] = {}
    played: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    ordered = ctx.drop_nulls(["blue_team_id", "red_team_id", "winner_team_id"]).sort("started_at", "game_id")
    for g in ordered.iter_rows(named=True):
        blue, red = g["blue_team_id"], g["red_team_id"]
        rb, rr = ratings.get(blue, INITIAL), ratings.get(red, INITIAL)
        e = expected(rb, rr)
        rows.append(
            {
                "game_id": g["game_id"],
                "blue_elo": rb,
                "red_elo": rr,
                "blue_n": played.get(blue, 0),
                "red_n": played.get(red, 0),
                "expected_blue": e,
            }
        )
        s = 1.0 if g["winner_team_id"] == blue else 0.0
        ratings[blue] = rb + K * (s - e)
        ratings[red] = rr - K * (s - e)
        played[blue] = played.get(blue, 0) + 1
        played[red] = played.get(red, 0) + 1
    return pl.DataFrame(rows)
