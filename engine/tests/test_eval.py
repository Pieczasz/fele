"""Evaluation harness: splits, holdout lock, metrics, baselines, and leakage checks (AGENT_PLAN.md §5.3)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from fele.eval import metrics, splits
from fele.features.actions import action_frame
from fele.features.outcome import FEATURES, outcome_frame
from fele.models.baselines import EloLogistic, GlobalFrequency, TeamSlotFrequency

T0 = datetime(2025, 1, 1, tzinfo=UTC)
IN_GAME = {"kills", "deaths", "assists", "gold_earned", "net_worth", "damage_dealt", "vision_score", "duration_s"}


def _series(n: int = 40, per_month: int = 4) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "series_id": [f"s{i:02d}" for i in range(n)],
            "started_at": [T0 + timedelta(days=30 * (i // per_month) + i % per_month) for i in range(n)],
            "league": ["LCS"] * n,
            "event": ["LCS - Split 1"] * n,
            "format": ["best-of-3"] * n,
        }
    )


def _games(series: pl.DataFrame, rng: np.random.Generator) -> pl.DataFrame:
    teams = ["A", "B", "C", "D"]
    rows: list[dict[str, object]] = []
    for s, start in series.select("series_id", "started_at").iter_rows():
        blue, red = rng.choice(teams, size=2, replace=False)
        rows.extend(
            {
                "game_id": f"{s}g{g}",
                "series_id": s,
                "game_number": g + 1,
                "patch": "15.1",
                "started_at": start + timedelta(hours=g),
                "blue_team_id": blue,
                "red_team_id": red,
                "winner_team_id": blue if rng.random() < 0.6 else red,
                "first_pick_team_id": blue,
            }
            for g in range(2)
        )
    return pl.DataFrame(rows)


# --- splits -----------------------------------------------------------------------------------------------------
def test_walk_forward_folds_respect_time_series_and_holdout():
    series = _series()
    holdout = splits.holdout_ids(series)
    assert len(holdout) == 6  # 15% of 40
    assert holdout == frozenset(f"s{i}" for i in range(34, 40))  # the latest series
    folds = splits.outer_folds(series, months=3)
    assert [f.name for f in folds] == ["2025-06", "2025-07", "2025-08"]
    start = dict(series.select("series_id", "started_at").iter_rows())
    for f in folds:
        assert not f.train & f.test
        assert not (f.train | f.test) & holdout
        assert max(start[s] for s in f.train) < min(start[s] for s in f.test)
    inner = splits.inner_folds(series, folds[-1].train, k=2)
    assert all(max(start[s] for s in f.train) < min(start[s] for s in f.test) for f in inner)


def test_holdout_is_locked_and_single_use(tmp_settings: Path):
    series = _series()
    with pytest.raises(splits.HoldoutLockedError, match="locked"):
        splits.holdout_split(series, confirm=False)
    fold = splits.holdout_split(series, confirm=True, note="final Phase 8 check")
    assert fold.test == splits.holdout_ids(series)
    assert (tmp_settings / "data_local" / "holdout_used.json").exists()
    with pytest.raises(splits.HoldoutLockedError, match="already used"):
        splits.holdout_split(series, confirm=True)


# --- metrics ----------------------------------------------------------------------------------------------------
def test_outcome_metrics_known_values():
    y = np.array([1.0, 0.0, 1.0, 0.0])
    m = metrics.outcome_metrics(y, np.full(4, 0.5))
    assert m["log_loss"] == pytest.approx(np.log(2))
    assert (m["brier"], m["auc"], m["ece"]) == (0.25, 0.5, 0.0)
    perfect = metrics.outcome_metrics(y, np.array([0.9, 0.1, 0.9, 0.1]))
    assert (perfect["accuracy"], perfect["auc"]) == (1.0, 1.0)
    assert perfect["ece"] == pytest.approx(0.1)


def test_paired_bootstrap_resamples_series():
    groups = np.array(["a", "a", "b", "b", "c", "c"])
    same = metrics.paired_bootstrap(np.ones(6), np.ones(6), groups)
    assert (same.mean, same.lo, same.hi) == (0.0, 0.0, 0.0)
    better = metrics.paired_bootstrap(np.full(6, 0.5), np.ones(6), groups)
    assert better.hi < 0  # a has lower loss in every resample


def test_action_metrics():
    m = metrics.action_metrics(np.array([0.5, 0.1]), np.array([1, 7]))
    assert (m["top1"], m["top5"], m["top10"]) == (0.5, 0.5, 1.0)
    assert m["mrr"] == pytest.approx((1 + 1 / 7) / 2)


# --- leakage (§5.3) ---------------------------------------------------------------------------------------------
def test_outcome_features_ignore_the_future():
    """Changing the result of game i must not change the features of game i or any earlier game."""
    series = _series(20)
    games = _games(series, np.random.default_rng(0))
    base = outcome_frame(games, series)
    i = 15
    flipped_id = base["game_id"][i]
    g = games.with_columns(
        winner_team_id=pl.when(pl.col("game_id") == flipped_id)
        .then(pl.when(pl.col("winner_team_id") == pl.col("blue_team_id")).then("red_team_id").otherwise("blue_team_id"))
        .otherwise("winner_team_id")
    )
    after = outcome_frame(g, series)
    cols = list(FEATURES)
    assert base.head(i + 1).select(cols).equals(after.head(i + 1).select(cols))
    assert not base.tail(-(i + 1)).select(cols).equals(after.tail(-(i + 1)).select(cols))  # later games do react


def test_outcome_features_are_pre_game_only():
    assert not set(FEATURES) & IN_GAME
    frame = outcome_frame(_games(_series(8), np.random.default_rng(1)), _series(8))
    played = {}
    for row in frame.iter_rows(named=True):  # blue_n = earlier games of the blue team, strictly before
        assert row["blue_n"] == played.get(row["blue_team_id"], 0)
        for t in (row["blue_team_id"], row["red_team_id"]):
            played[t] = played.get(t, 0) + 1


def test_action_rows_only_know_earlier_actions_and_fearless_locks():
    draft = pl.DataFrame(
        {
            "game_id": ["g2"] * 3,
            "slot": [1, 2, 7],
            "action": ["ban", "ban", "pick"],
            "phase": ["ban1", "ban1", "pick1"],
            "team_id": ["A", "B", "A"],
            "champion": ["Azir", "Vi", "Ahri"],
        }
    )
    games = pl.DataFrame({"game_id": ["g2"], "series_id": ["s"], "started_at": [T0], "patch": ["15.1"]})
    fearless = pl.DataFrame({"game_id": ["g2"], "locked_champions": [["Jinx"]]})
    rows = action_frame(draft, games, fearless).sort("slot")
    assert [sorted(u) for u in rows["unavailable"].to_list()] == [["Jinx"], ["Azir", "Jinx"], ["Azir", "Jinx", "Vi"]]


# --- baselines --------------------------------------------------------------------------------------------------
def test_elo_logistic_learns_direction():
    train = pl.DataFrame({"elo_diff": [-200.0, -100.0, 100.0, 200.0] * 10, "y": [0.0, 0.0, 1.0, 1.0] * 10})
    model = EloLogistic()
    model.fit(train)
    p = model.predict(pl.DataFrame({"elo_diff": [-150.0, 150.0]}))
    assert p[0] < 0.5 < p[1]


def test_action_baselines_use_recent_patches_and_team_history():
    train = pl.DataFrame(
        {
            "patch": ["14.1"] * 5 + ["15.1", "15.2", "15.3"] * 2,
            "action": ["pick"] * 11,
            "phase": ["pick1"] * 11,
            "team_id": ["A"] * 5 + ["A", "B", "B", "B", "B", "B"],
            "champion": ["Old"] * 5 + ["Ahri"] * 3 + ["Azir"] * 3,
        }
    )
    vocab = ["Ahri", "Azir", "Old"]
    rows = pl.DataFrame({"action": ["pick"], "team_id": ["A"], "phase": ["pick1"]})
    glob = GlobalFrequency()
    glob.fit(train, vocab)
    g = glob.scores(rows)[0]
    assert g[2] < g[0]  # "Old" was only played on an old patch
    team = TeamSlotFrequency()
    team.fit(train, vocab)
    t = team.scores(rows)[0]
    assert t[0] / t.sum() > g[0]  # team A's own recent Ahri pick lifts Ahri above the global share


@pytest.mark.real_data
def test_protocol_and_leakage_on_real_data():
    """Phase 7 acceptance: run after `fele ingest`. Same checks as above on the real 745 series."""
    from fele.stats.data import read  # noqa: PLC0415 - real-data paths only

    series, games = read("series"), read("games")
    holdout = splits.holdout_ids(series)
    start = dict(series.select("series_id", "started_at").iter_rows())
    folds = splits.outer_folds(series)
    assert len(folds) == splits.OUTER_MONTHS
    assert max(start[s] for f in folds for s in f.test) < min(start[s] for s in holdout)
    for f in folds:
        assert not f.train & f.test
        assert not (f.train | f.test) & holdout
        assert max(start[s] for s in f.train) < min(start[s] for s in f.test)
    frame = outcome_frame(games, series)
    played: dict[str, int] = {}
    for row in frame.iter_rows(named=True):
        assert row["blue_n"] == played.get(row["blue_team_id"], 0)
        assert row["red_n"] == played.get(row["red_team_id"], 0)
        for t in (row["blue_team_id"], row["red_team_id"]):
            played[t] = played.get(t, 0) + 1
    actions = action_frame(read("draft_actions"), games, read("fearless_state"))
    assert actions.filter(pl.col("unavailable").list.contains(pl.col("champion"))).is_empty()
