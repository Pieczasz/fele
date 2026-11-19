"""Macro context per team: jungle start side, first scuttle, grubs vs drake priority, objective timings, early kills.

Limits (say so wherever these are shown): positions are snapshots at event times, not continuous tracking, and the
feed has no normal jungle camp events, so "start side" = the map half where the jungler reached level 2 (≈ 1:47).
Map halves are split by the mid-lane diagonal: `top` = y > x (top-lane side), `bot` otherwise.
"""

import polars as pl

from fele.stats.core import with_rate, with_tendency
from fele.stats.draft import team_league

EARLY_S = 900  # "early" kills: first 15 minutes
CELL = 1000  # heatmap cell size in map units
DRAKES = ("Infernal", "Ocean", "Mountain", "Cloud", "Hextech", "Chemtech")
FIRSTS = {
    "grubs": pl.col("kind") == "slayVoidGrub",
    "drake": pl.col("kind").is_in([f"slay{d}Drake" for d in DRAKES]),
    "herald": pl.col("kind") == "slayRiftHerald",
    "tower": pl.col("kind") == "destroyTower",
    "scuttle": pl.col("kind").str.starts_with("slayRiftScuttler"),
}


HALF = pl.when(pl.col("y") > pl.col("x")).then(pl.lit("top")).otherwise(pl.lit("bot"))


def _first_per_game(df: pl.DataFrame) -> pl.DataFrame:
    """The earliest row of each game."""
    return df.sort("t_s").unique("game_id", keep="first")


def team_game_macro(
    tg: pl.DataFrame, parts: pl.DataFrame, levelups: pl.DataFrame, objectives: pl.DataFrame, kills: pl.DataFrame
) -> pl.DataFrame:
    """One row per team-game with the raw macro facts (sides, times, who got which first)."""
    jungler = parts.filter(pl.col("inferred_role") == "jungle").select("game_id", "team_id", "player_id")
    lv = levelups.join(jungler, on=["game_id", "player_id"])
    start = (
        lv.filter(pl.col("level") == 2)  # noqa: PLR2004
        .select("game_id", "team_id", jungle_l2_s="t_s", jungle_start=HALF)
        .join(
            lv.filter(pl.col("level") == 3).select("game_id", "team_id", jungle_l3_side=HALF),  # noqa: PLR2004
            on=["game_id", "team_id"],
            how="left",
        )
    )
    out = tg.select("game_id", "team_id", "opponent_id", "side", "league", "game_bucket", "started_at").join(
        start, on=["game_id", "team_id"], how="left"
    )
    for name, cond in FIRSTS.items():
        ev = objectives.filter(cond)
        mine = ev.group_by("game_id", "team_id").agg(pl.col("t_s").min().alias(f"{name}_s"))
        game_first = _first_per_game(ev).select("game_id", pl.col("team_id").alias(f"first_{name}_team"))
        out = out.join(mine, on=["game_id", "team_id"], how="left").join(game_first, on="game_id", how="left")
        got = (pl.col(f"first_{name}_team") == pl.col("team_id")).alias(f"got_first_{name}")  # null if nobody did
        out = out.with_columns(got).drop(f"first_{name}_team")
    scuttle_side = pl.col("kind").str.strip_prefix("slayRiftScuttler").str.to_lowercase()
    first_scuttle = _first_per_game(objectives.filter(FIRSTS["scuttle"])).select(
        "game_id", first_scuttle_side=scuttle_side
    )
    blood = _first_per_game(kills).select("game_id", fb_team="killer_team_id", fb_s="t_s")
    return (
        out.join(first_scuttle, on="game_id", how="left")
        .join(blood, on="game_id", how="left")
        .with_columns(
            got_first_blood=pl.col("fb_team") == pl.col("team_id"),
            grubs_before_drake=pl.when(pl.col("grubs_s").is_not_null() | pl.col("drake_s").is_not_null()).then(
                pl.col("grubs_s").fill_null(10**9) < pl.col("drake_s").fill_null(10**9)
            ),
            jungle_top_start=pl.col("jungle_start") == "top",
        )
        .drop("fb_team")
    )


RATE_METRICS = (
    "jungle_top_start",
    "got_first_scuttle",
    "got_first_blood",
    "got_first_tower",
    "got_first_drake",
    "got_first_grubs",
    "got_first_herald",
    "grubs_before_drake",
)
TIME_METRICS = ("jungle_l2_s", "scuttle_s", "grubs_s", "drake_s", "herald_s", "tower_s")


def team_macro_rates(tgm: pl.DataFrame) -> pl.DataFrame:
    """Team × metric × side split: k of n team-games, Wilson interval, league base rate, tendency label."""
    tgm = tgm.drop("league").join(team_league(tgm), on="team_id")
    long = tgm.unpivot(
        index=["team_id", "league", "side"], on=list(RATE_METRICS), variable_name="metric", value_name="hit"
    ).drop_nulls("hit")
    frames: list[pl.DataFrame] = []
    for split in (None, "side"):
        s = [split] if split else []
        agg = long.group_by("team_id", "league", "metric", *s).agg(k=pl.col("hit").sum(), n=pl.len())
        base = long.group_by("league", "metric", *s).agg(base_rate=pl.col("hit").mean())
        frames.append(
            agg.join(base, on=["league", "metric", *s])
            .with_columns(split=pl.col(split) if split else pl.lit("all"))
            .drop(*s)
        )
    return with_tendency(with_rate(pl.concat(frames, how="diagonal"))).sort("team_id", "metric", "split")


def team_macro_timings(tgm: pl.DataFrame) -> pl.DataFrame:
    """Team × metric: median time (s) of the team's own first objective, with quartiles and n."""
    long = tgm.unpivot(index=["team_id"], on=list(TIME_METRICS), variable_name="metric", value_name="t_s").drop_nulls()
    return (
        long.group_by("team_id", "metric")
        .agg(
            n=pl.len(),
            median_s=pl.col("t_s").median(),
            q25_s=pl.col("t_s").quantile(0.25),
            q75_s=pl.col("t_s").quantile(0.75),
        )
        .sort("team_id", "metric")
    )


def early_kill_cells(kills: pl.DataFrame, tg: pl.DataFrame) -> pl.DataFrame:
    """Heatmap data: team × side × kind (kill/death) × map cell, counts in the first 15 minutes (n = team-games)."""
    early = kills.filter(pl.col("t_s") < EARLY_S).drop_nulls(["x", "y"])
    cell = [(pl.col("x") // CELL).cast(pl.Int32).alias("cx"), (pl.col("y") // CELL).cast(pl.Int32).alias("cy")]
    sides = tg.select("game_id", "team_id", "side")
    rows = pl.concat(
        [
            early.select("game_id", pl.col(col).alias("team_id"), *cell).with_columns(kind=pl.lit(kind))
            for col, kind in (("killer_team_id", "kill"), ("victim_team_id", "death"))
        ]
    ).join(sides, on=["game_id", "team_id"])
    games = sides.group_by("team_id", "side").agg(n=pl.len())
    return rows.group_by("team_id", "side", "kind", "cx", "cy").agg(count=pl.len()).join(games, on=["team_id", "side"])
