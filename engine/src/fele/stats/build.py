"""`fele stats`: every Phase 5 table → data_local/aggregates/stats_*.parquet (DuckDB schema `aggregates`).

Needs `fele ingest` and `fele static` (and optionally `fele soloq-aggregate` for the live meta).
Team tables come in two periods: `all` games and `recent` (the last 120 days before `as_of`).
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import polars as pl

from fele.config import settings
from fele.static.build import read_tags, static_dir
from fele.static.ddragon import patch_key
from fele.stats import data, draft, elo, macro, meta, pools

RECENT_DAYS = 120


def _live_patch() -> str | None:
    path = settings().local("ddragon") / "versions.json"
    return ".".join(json.loads(path.read_text())[0].split(".")[:2]) if path.exists() else None


def _meta_inputs(windows: pl.DataFrame, last_grid: str) -> tuple[pl.DataFrame, pl.DataFrame | None, pl.DataFrame]:
    """Windows incl. `live`, solo-queue rows of the live patch, Data Dragon deltas per window."""
    live = _live_patch()
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
        soloq = (
            pl.read_parquet(soloq_path)
            .filter(pl.col("patch") == live)
            .group_by("champion")
            .agg(pl.col("games").sum(), pl.col("wins").sum())
            .with_columns(window=pl.lit("live"))
        )
    return windows, soloq, deltas


def _meta_by_role(meta_table: pl.DataFrame, top_n: int = pools.META_TOP_N) -> dict[str, list[str]]:
    roles = read_tags().select("champion", pl.col("roles").str.split("|"))
    live = meta_table.filter(pl.col("window") == "live").join(roles, on="champion").explode("roles")
    return {
        str(role): g.sort("meta_score", descending=True)["grid"].head(top_n).to_list()
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
    windows, soloq, deltas = _meta_inputs(data.trailing_windows(grid_patches), grid_patches[-1])
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

    tables = {
        "stats_meta": meta_table,
        "stats_champion_roles": meta.champion_role_winrates(parts_ctx, windows),
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
    out = settings().local("aggregates")
    counts: dict[str, int] = {}
    for name, df in tables.items():
        df.write_parquet(out / f"{name}.parquet")
        counts[name] = df.height
    counts["as_of"] = int(as_of.replace(tzinfo=as_of.tzinfo or UTC).timestamp())
    return counts
