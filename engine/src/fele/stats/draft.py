"""Draft priority per team: presence, first-rotation priority, side / game-number splits, ban targeting."""

import polars as pl

from fele.stats.core import with_rate, with_tendency

SPLITS = (None, "side", "game_bucket")
FIRST_ROTATION = ("ban1", "pick1")


def team_league(tg: pl.DataFrame) -> pl.DataFrame:
    """A team's league = where it played most of its games (international events don't change it)."""
    return tg.group_by("team_id").agg(pl.col("league").mode().sort().first())


def team_draft(draft: pl.DataFrame, tg: pl.DataFrame) -> pl.DataFrame:
    """Team × champion × split: presence (k of n team-games picked or banned by the team), picks, bans,
    first-rotation share, average template slot, and the league's presence rate as the tendency baseline.

    `split_type` is `all`, `side` (blue/red) or `game_bucket` (G1/G2/G3+); `split` holds its value.
    """
    keyed = tg.select("game_id", "team_id", "side", "game_bucket").join(team_league(tg), on="team_id")
    d = draft.join(keyed, on=["game_id", "team_id"])
    frames: list[pl.DataFrame] = []
    for split in SPLITS:
        s = [split] if split else []
        n = keyed.group_by("team_id", *s).agg(n=pl.len())
        agg = d.group_by("team_id", "league", *s, "champion").agg(
            picks=(pl.col("action") == "pick").sum(),
            bans=(pl.col("action") == "ban").sum(),
            k=pl.col("game_id").n_unique(),
            first_rotation=pl.col("game_id").filter(pl.col("phase").is_in(FIRST_ROTATION)).n_unique(),
            avg_slot=pl.col("slot").mean(),
        )
        league_n = keyed.group_by("league", *s).agg(league_n=pl.len())
        league_k = d.group_by("league", *s, "champion").agg(league_k=pl.struct("game_id", "team_id").n_unique())
        base = league_k.join(league_n, on=["league", *s]).with_columns(
            base_rate=pl.col("league_k") / pl.col("league_n")
        )
        frames.append(
            agg.join(n, on=["team_id", *s])
            .join(base.select("league", *s, "champion", "base_rate"), on=["league", *s, "champion"])
            .with_columns(split_type=pl.lit(split or "all"), split=pl.col(split) if split else pl.lit("all"))
            .drop(*s)
        )
    out = with_rate(pl.concat(frames, how="diagonal"))
    out = with_rate(out, k="first_rotation", prefix="first_rotation_")
    return with_tendency(out).sort("team_id", "split_type", "split", "k", descending=[False, False, False, True])


def ban_targets(draft: pl.DataFrame, parts: pl.DataFrame, tg: pl.DataFrame) -> pl.DataFrame:
    """One row per ban: the opponent player whose earlier pro games (before this game) include the champion most.

    `target_player_id` is null when no opponent player had played the champion before (a meta/comfort-free ban).
    """
    started = tg.select("game_id", "started_at").unique()
    bans = (
        draft.filter(pl.col("action") == "ban")
        .select("game_id", "team_id", "champion", "slot", "phase")
        .join(tg.select("game_id", "team_id", "opponent_id"), on=["game_id", "team_id"])
        .join(started, on="game_id")
    )
    roster = parts.select(
        "game_id", pl.col("team_id").alias("opponent_id"), "player_id", "player_name", "inferred_role"
    )
    history = parts.join(started, on="game_id").select("player_id", "champion", pl.col("started_at").alias("played_at"))
    hits = (
        bans.join(roster, on=["game_id", "opponent_id"])
        .join(history, on=["player_id", "champion"])
        .filter(pl.col("played_at") < pl.col("started_at"))
        .group_by("game_id", "team_id", "champion", "player_id", "player_name", "inferred_role")
        .agg(prior_games=pl.len())
        .sort("prior_games", "player_id", descending=[True, False])
        .unique(["game_id", "team_id", "champion"], keep="first")
    )
    return bans.join(hits, on=["game_id", "team_id", "champion"], how="left").rename(
        {"player_id": "target_player_id", "player_name": "target_player", "inferred_role": "target_role"}
    )


def ban_targeting_by_player(bans: pl.DataFrame) -> pl.DataFrame:
    """Per targeted team and player: k bans aimed at the player out of n bans the team faced."""
    faced = bans.group_by(pl.col("opponent_id").alias("team_id")).agg(n=pl.len())
    k = (
        bans.drop_nulls("target_player_id")
        .group_by(pl.col("opponent_id").alias("team_id"), "target_player_id")
        .agg(
            k=pl.len(),
            target_player=pl.col("target_player").mode().sort().first(),
            target_role=pl.col("target_role").drop_nulls().mode().sort().first(),  # one row per player
            champions=pl.col("champion").value_counts(sort=True).head(5),
        )
    )
    return with_rate(k.join(faced, on="team_id")).sort("team_id", "k", descending=[False, True])
