"""Champion strength per trailing patch window: shrunk pro win rates per role and a combined meta score.

Window `P` = GRID games on patch P and the 2 patches before it (fele.stats.data.trailing_windows). It includes P
itself, so features for a game on patch P must use window P-1 (Phase 7 leakage rule).

meta_score = 0.50·z(pro presence) + 0.25·z(shrunk pro win rate) + 0.15·z(shrunk solo-queue win rate)
           + 0.10·z(patch delta score)
z = standardised within the window; a missing component (no solo-queue sample for that patch, champion not picked in
pro, no Data Dragon change) contributes 0, i.e. "average". The weights are a readable heuristic for the meta view;
the models in Phase 8 learn their own weights from these components.
"""

import polars as pl

from fele.stats.core import with_rate, with_shrunk

WEIGHTS = {"presence": 0.50, "pro_wr": 0.25, "soloq_wr": 0.15, "delta": 0.10}


def champion_role_winrates(parts: pl.DataFrame, windows: pl.DataFrame) -> pl.DataFrame:
    """Window × role × champion: pro wins k of n games, Wilson interval, shrunk win rate.

    One prior per role, fitted over all windows: a single window has ~20 games per champion, too few to fit a
    stable prior (fits swing between no shrinkage and complete pooling).
    """
    d = parts.drop_nulls("inferred_role").join(windows, on="patch")
    agg = d.group_by("window", pl.col("inferred_role").alias("role"), "champion").agg(n=pl.len(), k=pl.col("win").sum())
    return with_shrunk(with_rate(agg), prior_by=("role",)).sort("window", "role", "n", descending=[False, False, True])


def _z(col: str) -> pl.Expr:
    c = pl.col(col)
    std = c.std().over("window")
    return pl.when(std > 0).then((c - c.mean().over("window")) / std).otherwise(0.0).fill_null(0.0)


def meta_scores(  # noqa: PLR0913 - one input per score component
    draft: pl.DataFrame,
    parts: pl.DataFrame,
    games: pl.DataFrame,
    windows: pl.DataFrame,
    cmap: pl.DataFrame,
    *,
    soloq: pl.DataFrame | None = None,
    deltas: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Window × champion (Data Dragon key): presence, shrunk pro win rate, solo-queue win rate, delta, meta_score.

    `games`: game_id, patch. `windows`: window, patch. `cmap`: grid_name -> champion (key).
    `soloq`: window, champion (key), games, wins. `deltas`: window, champion (key), score.
    """
    names = cmap.select(pl.col("grid_name").alias("grid"), "champion", "name")
    gw = games.select("game_id", "patch").join(windows, on="patch")
    n_games = gw.group_by("window").agg(n=pl.len())
    presence = (
        draft.join(gw, on="game_id")
        .group_by("window", pl.col("champion").alias("grid"))
        .agg(
            k=pl.col("game_id").n_unique(),
            picks=(pl.col("action") == "pick").sum(),
            bans=(pl.col("action") == "ban").sum(),
        )
        .join(n_games, on="window")
    )
    presence = with_rate(presence).rename({"rate": "presence", "lo": "presence_lo", "hi": "presence_hi", "n": "games"})
    pro = parts.join(gw.select("game_id", "window"), on="game_id").group_by("window", pl.col("champion").alias("grid"))
    # one prior over all windows (a single window is too small to fit one)
    pro_wr = with_shrunk(pro.agg(n=pl.len(), k=pl.col("win").sum())).select(
        "window", "grid", pro_n="n", pro_wins="k", pro_wr="shrunk", pro_wr_lo="shrunk_lo", pro_wr_hi="shrunk_hi"
    )
    out = presence.join(pro_wr, on=["window", "grid"], how="left").join(names, on="grid", how="left")

    if soloq is not None and not soloq.is_empty():
        sq = with_shrunk(soloq.rename({"games": "n", "wins": "k"}), prior_by=("window",)).select(
            "window", "champion", soloq_n="n", soloq_wr="shrunk", soloq_wr_lo="shrunk_lo", soloq_wr_hi="shrunk_hi"
        )
        out = out.join(sq, on=["window", "champion"], how="left")
    else:
        empty = ("soloq_n", "soloq_wr", "soloq_wr_lo", "soloq_wr_hi")
        out = out.with_columns(*(pl.lit(None, pl.Float64).alias(c) for c in empty))
    if deltas is not None and not deltas.is_empty():
        out = out.join(deltas.select("window", "champion", delta="score"), on=["window", "champion"], how="left")
    else:
        out = out.with_columns(delta=pl.lit(None, pl.Float64))

    score = sum((w * _z(c) for c, w in WEIGHTS.items()), start=pl.lit(0.0))
    return out.with_columns(meta_score=score).sort("window", "meta_score", descending=[False, True])
