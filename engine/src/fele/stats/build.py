"""`fele stats`: every Phase 5 table → data_local/aggregates/stats_*.parquet (DuckDB schema `aggregates`).

Needs `fele ingest` and `fele static` (and optionally `fele soloq-aggregate` for the live meta).
Team tables come in two periods: `all` games and `recent` (the last 120 days before `as_of`).
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import polars as pl

from fele.config import settings
from fele.db import write_tables
from fele.ingest.grid import read_meta
from fele.static.build import read_tags, static_dir
from fele.static.ddragon import live_patch, patch_key
from fele.stats import data, draft, elo, macro, meta, pools

RECENT_DAYS = 120


def _meta_inputs(windows: pl.DataFrame, last_grid: str) -> tuple[pl.DataFrame, pl.DataFrame | None, pl.DataFrame]:
    """Windows incl. `live`, solo-queue rows of the live patch, Data Dragon deltas per window."""
    live = live_patch()
    windows = pl.concat([windows, windows.filter(pl.col("window") == last_grid).with_columns(window=pl.lit("live"))])
    deltas = pl.read_parquet(static_dir() / "patch_deltas.parquet").select("champion", "patch", "score")
    after = [p for p in deltas["patch"].unique().to_list() if patch_key(p) > patch_key(last_grid)]
    live_delta = (
        deltas.filter(pl.col("patch").is_in(after))
        .group_by("champion")
        .agg(pl.col("score").sum())
        .with_columns(window=pl.lit("live"))
    )
    deltas = pl.concat(
        [
            deltas.select(window="patch", champion="champion", score="score"),
            live_delta.select("window", "champion", "score"),
        ]
    )
    soloq_path = settings().local("aggregates") / "soloq_champion_patch.parquet"
    soloq = None
    if live and soloq_path.exists():
        # match-v5 championName isn't always the Data Dragon key (e.g. "FiddleSticks"): map by numeric id
        keys = pl.read_parquet(static_dir() / "champions.parquet").select(champion_id="riot_id", key="champion")
        soloq = (
            pl.read_parquet(soloq_path)
            .filter(pl.col("patch") == live)
            .join(keys, on="champion_id")
            .group_by(champion="key")
            .agg(pl.col("games").sum(), pl.col("wins").sum())
            .with_columns(window=pl.lit("live"))
        )
    return windows, soloq, deltas


def _meta_by_role(meta_table: pl.DataFrame) -> dict[str, list[str]]:
    roles = read_tags().select("champion", pl.col("roles").str.split("|"))
    live = meta_table.filter(pl.col("window") == "live").join(roles, on="champion").explode("roles")
    return {
        str(role): g.sort("meta_score", descending=True)["grid"].head(pools.META_TOP_N).to_list()
        for (role,), g in live.drop_nulls("grid").group_by("roles")
    }


def build(as_of: datetime | None = None) -> dict[str, int]:
    ctx = data.game_context(data.read("games"), data.read("series"))
    tg = data.team_games(ctx)
    draft_actions, parts = data.read("draft_actions"), data.read("participants")
    parts_ctx = parts.join(ctx.select("game_id", "started_at", "patch", "league"), on="game_id")
    if as_of is None:
        latest = ctx["started_at"].max()
        if not isinstance(latest, datetime):
            raise TypeError("games.started_at must be a datetime column")
        as_of = latest + timedelta(days=1)
    periods = {"all": tg, "recent": tg.filter(pl.col("started_at") >= as_of - timedelta(days=RECENT_DAYS))}

    grid_patches = data.patches(ctx)
    grid_windows = data.trailing_windows(grid_patches)
    windows, soloq, deltas = _meta_inputs(grid_windows, grid_patches[-1])
    cmap = pl.read_parquet(static_dir() / "champion_map.parquet")
    meta_table = meta.meta_scores(
        draft_actions, parts, ctx.select("game_id", "patch"), windows, cmap, soloq=soloq, deltas=deltas
    )

    pc = pools.player_champions(parts_ctx, as_of)
    latest = parts_ctx.sort("started_at").unique("player_id", keep="last").select("player_id", "player_name", "team_id")
    players = pools.player_summary(pc, _meta_by_role(meta_table)).join(latest, on="player_id")

    bans = draft.ban_targets(draft_actions, parts, tg)
    tgm = macro.team_game_macro(tg, parts, data.read("levelups"), data.read("objectives"), data.read("kills"))

    def per_period(fn: Callable[[pl.DataFrame, pl.DataFrame], pl.DataFrame], frame: pl.DataFrame) -> pl.DataFrame:
        """fn(frame rows of the period's games, the period's team-games), stacked with a `period` column."""
        return pl.concat(
            [
                fn(frame.join(t.select("game_id").unique(), on="game_id"), t).with_columns(period=pl.lit(p))
                for p, t in periods.items()
            ]
        )

    names = pl.DataFrame(read_meta("teams")).select("team_id", "name")
    tables = {
        "stats_teams": data.team_summary(tg, names),
        "stats_windows": windows,
        "stats_meta": meta_table,
        # grid windows only: the `live` copy of the last window would count its games twice
        "stats_champion_roles": meta.champion_role_winrates(parts_ctx, grid_windows),
        "stats_player_champions": pc,
        "stats_players": players,
        "stats_team_draft": per_period(draft.team_draft, draft_actions),
        "stats_bans": bans,
        "stats_ban_targets": per_period(lambda b, _: draft.ban_targeting_by_player(b), bans),
        "stats_elo": elo.game_elo(ctx),
        "stats_team_game_macro": tgm,
        "stats_macro_rates": per_period(lambda m, _: macro.team_macro_rates(m), tgm),
        "stats_macro_timings": per_period(lambda m, _: macro.team_macro_timings(m), tgm),
        "stats_early_kills": per_period(macro.early_kill_cells, data.read("kills")),
    }
    counts = write_tables(settings().local("aggregates"), tables)
    counts["as_of"] = int(as_of.replace(tzinfo=as_of.tzinfo or UTC).timestamp())
    return counts
