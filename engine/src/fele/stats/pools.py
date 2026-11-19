"""Player champion pools from pro games: comfort, effective pool size, depth, overlap with the meta."""

from datetime import datetime

import numpy as np
import polars as pl
from scipy import stats

from fele.stats.core import with_rate, with_shrunk

HALF_LIFE_DAYS = 90.0
DEPTH_MIN_RECENT = 1.0  # a champion counts toward depth with ≥ 1 recency-weighted game
META_TOP_N = 10
OVERLAP_MIN_GAMES = 2
BOOTSTRAP = 400


def player_champions(parts: pl.DataFrame, as_of: datetime, half_life_days: float = HALF_LIFE_DAYS) -> pl.DataFrame:
    """Player × champion (games strictly before `as_of`): games, wins, shrunk win rate, recency-weighted games, comfort.

    recent_games = Σ 0.5^(age_days / half_life) — a game today counts 1, one half-life ago 0.5.
    comfort = recent_games × shrunk_win_rate / 0.5: recency-weighted games, scaled up or down by how well it went.
    The win-rate prior is fitted per role over all player-champion pairs.
    """
    past = parts.filter(pl.col("started_at") < as_of)
    role = past.group_by("player_id").agg(role=pl.col("inferred_role").drop_nulls().mode().sort().first())
    age = (pl.lit(as_of) - pl.col("started_at")).dt.total_seconds() / 86400
    pc = (
        past.group_by("player_id", "champion")
        .agg(
            n=pl.len(),
            k=pl.col("win").sum(),
            last_played=pl.col("started_at").max(),
            recent_games=(0.5 ** (age / half_life_days)).sum(),
        )
        .join(role, on="player_id")
    )
    pc = with_shrunk(with_rate(pc), prior_by=("role",))
    return pc.with_columns(comfort=pl.col("recent_games") * pl.col("shrunk") / 0.5).sort(
        "player_id", "comfort", descending=[False, True]
    )


def effective_pool(counts: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    """exp(entropy) of the champion distribution + basic-bootstrap 95% interval (resampling the player's games)."""
    n = int(counts.sum())
    value = float(np.exp(stats.entropy(counts)))
    draws = rng.multinomial(n, counts / n, size=BOOTSTRAP)
    q_lo, q_hi = np.percentile(np.exp(stats.entropy(draws, axis=1)), [2.5, 97.5])
    # basic bootstrap: resampling loses rare champions, so the plug-in estimate is biased low; reflect around it,
    # widened to contain the estimate (an even pool can't look more even when resampled)
    lo, hi = min(value, 2 * value - q_hi), max(value, 2 * value - q_lo)
    return value, max(1.0, float(lo)), float(hi)


def player_summary(pc: pl.DataFrame, meta_by_role: dict[str, list[str]]) -> pl.DataFrame:
    """Per player: games (n), unique champions, effective pool size (+ interval), depth, meta overlap (k of top N).

    meta_by_role: role -> current top-N meta champions (GRID names); overlap counts those with ≥ 2 games.
    """
    rng = np.random.default_rng(0)  # fixed: the same data gives the same intervals
    rows: list[dict[str, object]] = []
    for (player_id, role), g in pc.group_by("player_id", "role", maintain_order=True):
        eff, lo, hi = effective_pool(g["n"].to_numpy().astype(float), rng)
        played = set(g.filter(pl.col("n") >= OVERLAP_MIN_GAMES)["champion"].to_list())
        meta = meta_by_role.get(str(role), [])
        rows.append(
            {
                "player_id": player_id,
                "role": role,
                "n": int(g["n"].sum()),
                "unique_champions": g.height,
                "effective_pool": eff,
                "effective_pool_lo": lo,
                "effective_pool_hi": hi,
                "depth": int((g["recent_games"] >= DEPTH_MIN_RECENT).sum()),
                "meta_k": len(played & set(meta)),
                "meta_n": len(meta),
            }
        )
    return with_rate(pl.DataFrame(rows), k="meta_k", n="meta_n", prefix="meta_overlap_")
