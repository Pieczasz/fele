"""Metrics for the outcome model (problem A) and the draft-action model (problem B), plus paired bootstrap CIs.

Bootstraps resample series, not games: games of one series share teams, patch and form, so they aren't independent.
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from fele.models.sk import roc_auc

type Floats = npt.NDArray[np.float64]

EPS = 1e-12
ECE_BINS = 10
HALF = 0.5  # a prediction above this calls a blue win
BOOTSTRAP = 2000
TOP_K = (1, 5, 10)


def log_losses(y: Floats, p: Floats) -> Floats:
    """Per-game log loss (natural log)."""
    p = np.clip(p, EPS, 1 - EPS)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def reliability(y: Floats, p: Floats, bins: int = ECE_BINS) -> list[dict[str, float]]:
    """Equal-width bins of predicted probability: mean prediction vs observed rate, with counts."""
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, bins - 1)
    return [
        {
            "lo": float(edges[b]),
            "hi": float(edges[b + 1]),
            "n": int(m.sum()),
            "mean_p": float(p[m].mean()),
            "rate": float(y[m].mean()),
        }
        for b in range(bins)
        if (m := idx == b).any()
    ]


def ece(y: Floats, p: Floats, bins: int = ECE_BINS) -> float:
    """Expected calibration error: count-weighted |mean prediction - observed rate| over the bins."""
    return sum(r["n"] * abs(r["mean_p"] - r["rate"]) for r in reliability(y, p, bins)) / len(y)


def outcome_metrics(y: Floats, p: Floats) -> dict[str, float]:
    both = len(np.unique(y)) > 1
    return {
        "n": float(len(y)),
        "log_loss": float(log_losses(y, p).mean()),
        "brier": float(np.mean((p - y) ** 2)),
        "auc": roc_auc(y, p) if both else float("nan"),
        "accuracy": float(np.equal(p > HALF, y == 1).mean()),
        "ece": ece(y, p),
    }


def action_metrics(p_true: Floats, rank: npt.NDArray[np.int64]) -> dict[str, float]:
    """p_true = probability of the champion actually chosen; rank = its rank among available champions (1 = top)."""
    out = {
        "n": float(len(rank)),
        "log_loss": float(-np.log(np.clip(p_true, EPS, 1)).mean()),
        "mrr": float(np.mean(1 / rank)),
    }
    out |= {f"top{k}": float(np.mean(rank <= k)) for k in TOP_K}
    return out


@dataclass(frozen=True)
class Interval:
    mean: float
    lo: float
    hi: float


def paired_bootstrap(
    loss_a: Floats, loss_b: Floats, groups: npt.NDArray[np.str_], n: int = BOOTSTRAP, seed: int = 0
) -> Interval:
    """Mean per-row difference (a - b) with a 95% CI from resampling groups (series) with replacement.

    Negative = model a has lower loss. Rows of a resampled series count as often as the series is drawn.
    """
    _, inverse = np.unique(groups, return_inverse=True)
    diff_sum = np.bincount(inverse, weights=loss_a - loss_b)
    count = np.bincount(inverse).astype(float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(count), size=(n, len(count)))
    boot = diff_sum[draws].sum(axis=1) / count[draws].sum(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return Interval(mean=float(diff_sum.sum() / count.sum()), lo=float(lo), hi=float(hi))


def bootstrap_mean(values: Floats, groups: npt.NDArray[np.str_], n: int = BOOTSTRAP, seed: int = 0) -> Interval:
    """Series-resampled 95% CI of a per-row mean (e.g. log loss of one model)."""
    return paired_bootstrap(values, np.zeros_like(values), groups, n, seed)
