"""Rates with intervals, empirical-Bayes beta-binomial shrinkage, tendency significance.

Conventions used by every stats table: `k` successes out of `n` trials, `rate` = k/n with a Wilson 95% interval
(`lo`, `hi`). Shrunk rates add `shrunk` (posterior mean) and `shrunk_lo`/`shrunk_hi` (95% credible interval) under a
Beta prior fitted to all groups of the same kind (e.g. all champions of one role in one patch window).
"""

import math

import numpy as np
import numpy.typing as npt
import polars as pl
from scipy import optimize, special, stats

Z95 = 1.959963984540054
LOG_BOUNDS = (math.log(0.5), math.log(5000.0))  # prior strength between ~1 and ~10,000 pseudo-games
STRONG_Q, WEAK_P = 0.05, 0.05


def with_rate(df: pl.DataFrame, k: str = "k", n: str = "n", prefix: str = "") -> pl.DataFrame:
    """Add `{prefix}rate`, `{prefix}lo`, `{prefix}hi` (Wilson score interval, 95%)."""
    kk, nn = pl.col(k).cast(pl.Float64), pl.col(n).cast(pl.Float64)
    p = kk / nn
    z2 = Z95**2
    centre = (p + z2 / (2 * nn)) / (1 + z2 / nn)
    half = Z95 * (p * (1 - p) / nn + z2 / (4 * nn**2)).sqrt() / (1 + z2 / nn)
    ok = nn > 0
    return df.with_columns(
        pl.when(ok).then(p).alias(f"{prefix}rate"),
        pl.when(ok).then(centre - half).alias(f"{prefix}lo"),
        pl.when(ok).then(centre + half).alias(f"{prefix}hi"),
    )


def fit_beta_prior(k: np.ndarray, n: np.ndarray) -> tuple[float, float]:
    """Beta(a, b) prior maximising the beta-binomial likelihood of k successes out of n (groups with n > 0)."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    keep = n > 0
    k, n = k[keep], n[keep]
    if len(k) == 0:
        return 1.0, 1.0
    mean = np.clip(k.sum() / n.sum(), 0.01, 0.99)
    if len(k) == 1:
        return 2 * mean, 2 * (1 - mean)  # one group: weak prior at its own mean

    def nll(log_ab: npt.NDArray[np.float64]) -> float:
        a, b = math.exp(log_ab[0]), math.exp(log_ab[1])
        return -float(np.sum(special.betaln(k + a, n - k + b) - special.betaln(a, b)))

    start = np.clip(np.log([10 * mean, 10 * (1 - mean)]), *LOG_BOUNDS)  # all-win/all-loss data starts off-bounds
    # Nelder-Mead: L-BFGS-B's finite-difference gradient stalls on this likelihood's flat ridge
    res = optimize.minimize(nll, start, method="Nelder-Mead", bounds=[LOG_BOUNDS, LOG_BOUNDS])
    a, b = np.exp(res.x)
    return float(a), float(b)


def _shrink_group(df: pl.DataFrame, k: str, n: str) -> pl.DataFrame:
    a, b = fit_beta_prior(df[k].to_numpy(), df[n].to_numpy())
    post_a = df[k].to_numpy().astype(float) + a
    post_b = df[n].to_numpy().astype(float) - df[k].to_numpy() + b
    return df.with_columns(
        pl.Series("shrunk", post_a / (post_a + post_b)),
        pl.Series("shrunk_lo", np.asarray(stats.beta.ppf(0.025, post_a, post_b), dtype=float)),
        pl.Series("shrunk_hi", np.asarray(stats.beta.ppf(0.975, post_a, post_b), dtype=float)),
        prior_a=pl.lit(a),
        prior_b=pl.lit(b),
    )


def with_shrunk(df: pl.DataFrame, k: str = "k", n: str = "n", prior_by: tuple[str, ...] = ()) -> pl.DataFrame:
    """Add shrunk rate + credible interval; the prior is fitted separately within each `prior_by` group."""
    if df.is_empty():
        return df.with_columns(
            *(pl.lit(None, pl.Float64).alias(c) for c in ("shrunk", "shrunk_lo", "shrunk_hi", "prior_a", "prior_b"))
        )
    if not prior_by:
        return _shrink_group(df, k, n)
    return pl.concat([_shrink_group(g, k, n) for _, g in df.group_by(prior_by, maintain_order=True)])


def bh_qvalues(p: np.ndarray) -> np.ndarray:
    """Benjamini–Hochberg adjusted p-values (q-values)."""
    p = np.asarray(p, float)
    m = len(p)
    if m == 0:
        return p
    order = np.argsort(p)
    ranked = p[order] * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1].clip(max=1.0)
    out = np.empty(m)
    out[order] = q
    return out


def with_tendency(df: pl.DataFrame, base: str = "base_rate", k: str = "k", n: str = "n") -> pl.DataFrame:
    """Two-sided binomial test of k/n against `base`, BH across all rows → `p`, `q`, `tendency` strong/weak/noise.

    strong = BH q < 0.05 (survives testing every row of the table); weak = raw p < 0.05 only; noise = otherwise.
    """
    if df.is_empty():
        return df.with_columns(p=pl.lit(None, pl.Float64), q=pl.lit(None, pl.Float64), tendency=pl.lit(None, pl.String))
    ks, ns, bs = df[k].to_list(), df[n].to_list(), df[base].to_list()
    p = np.array(
        [
            stats.binomtest(int(kk), int(nn), float(min(max(bb, 1e-9), 1 - 1e-9))).pvalue
            if nn and bb is not None
            else 1.0
            for kk, nn, bb in zip(ks, ns, bs, strict=True)
        ]
    )
    q = bh_qvalues(p)
    label = np.where(q < STRONG_Q, "strong", np.where(p < WEAK_P, "weak", "noise"))
    return df.with_columns(pl.Series("p", p), pl.Series("q", q), pl.Series("tendency", label))
