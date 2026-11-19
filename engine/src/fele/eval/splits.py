"""Validation protocol (AGENT_PLAN.md §5.4): series-grouped, time-ordered splits with a locked final holdout.

- Series are sorted by start time. The most recent `HOLDOUT_SHARE` of series is the final holdout: no fold ever
  trains or tests on it. Using it needs `holdout_split(confirm=True)`, which records the use, and it may happen once.
- Outer walk-forward folds: each of the last `OUTER_MONTHS` calendar months that have games (before the holdout) is a
  test fold; its training set is every series that started before that month.
- Splits are by series, never by game, so games of one series never sit on both sides.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import polars as pl

from fele.config import settings

HOLDOUT_SHARE = 0.15
OUTER_MONTHS = 8
INNER_FOLDS = 3


@dataclass(frozen=True)
class Fold:
    name: str
    train: frozenset[str]  # series ids
    test: frozenset[str]


def series_order(series: pl.DataFrame) -> pl.DataFrame:
    """series_id, started_at, month — sorted by start time (ties by id, so the order is deterministic)."""
    return (
        series.drop_nulls("started_at")
        .select("series_id", "started_at")
        .sort("started_at", "series_id")
        .with_columns(month=pl.col("started_at").dt.strftime("%Y-%m"))
    )


def holdout_ids(series: pl.DataFrame, share: float = HOLDOUT_SHARE) -> frozenset[str]:
    ordered = series_order(series)
    n_holdout = round(ordered.height * share)
    return frozenset(ordered.tail(n_holdout)["series_id"].to_list())


def outer_folds(series: pl.DataFrame, months: int = OUTER_MONTHS) -> list[Fold]:
    """Walk-forward folds over the last `months` months with games, holdout excluded."""
    holdout = holdout_ids(series)
    dev = series_order(series).filter(~pl.col("series_id").is_in(list(holdout)))
    test_months = dev["month"].unique().sort().to_list()[-months:]
    folds: list[Fold] = []
    for m in test_months:
        train = dev.filter(pl.col("month") < m)["series_id"].to_list()
        test = dev.filter(pl.col("month") == m)["series_id"].to_list()
        folds.append(Fold(name=m, train=frozenset(train), test=frozenset(test)))
    return folds


def inner_folds(series: pl.DataFrame, train: frozenset[str], k: int = INNER_FOLDS) -> list[Fold]:
    """Walk-forward folds inside one training set (for tuning and calibration in Phase 8): the last k equal chunks."""
    ordered = series_order(series).filter(pl.col("series_id").is_in(list(train)))["series_id"].to_list()
    size = len(ordered) // (k + 1)
    return [
        Fold(
            name=f"inner{i + 1}",
            train=frozenset(ordered[: size * (i + 1)]),
            test=frozenset(ordered[size * (i + 1) : size * (i + 2)]),
        )
        for i in range(k)
    ]


class HoldoutLockedError(RuntimeError):
    pass


def holdout_split(series: pl.DataFrame, *, confirm: bool, note: str = "") -> Fold:
    """The one-time final evaluation: train on everything before the holdout, test on it. Recorded on first use."""
    marker = settings().local() / "holdout_used.json"
    if not confirm:
        raise HoldoutLockedError("The final holdout is locked until the end of Phase 8 (pass confirm=True)")
    if marker.exists():
        used = json.loads(marker.read_text())
        msg = f"The final holdout was already used on {used['at']} ({used['note']}); it may be touched once."
        raise HoldoutLockedError(msg)
    holdout = holdout_ids(series)
    dev = series_order(series).filter(~pl.col("series_id").is_in(list(holdout)))["series_id"].to_list()
    marker.write_text(json.dumps({"at": datetime.now(UTC).isoformat(), "note": note}))
    return Fold(name="holdout", train=frozenset(dev), test=holdout)
