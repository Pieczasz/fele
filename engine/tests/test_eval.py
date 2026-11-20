"""Evaluation harness: splits, holdout lock, metrics, baselines, and leakage checks (AGENT_PLAN.md §5.3)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import polars as pl
import pytest

from fele.eval import metrics, splits
from fele.eval.run import load
from fele.features import state
from fele.models.baselines import EloLogistic, GlobalFrequency, TeamSlotFrequency
from fele.prefs import Role
from fele.stats.data import game_context
from fele.stats.elo import game_elo

T0 = datetime(2025, 1, 1, tzinfo=UTC)
ROLES = [str(r) for r in Role]
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
CHAMPS = [f"Champ{i:02d}" for i in range(30)]


def _inputs(series: pl.DataFrame, games: pl.DataFrame, rng: np.random.Generator) -> state.Inputs:
    """A small but complete synthetic world for the feature store: 5 players and 5 picks per team, hard Fearless
    respected within each series (like the real data)."""
    draft_rows: list[dict[str, object]] = []
    part_rows: list[dict[str, object]] = []
    used: dict[str, set[str]] = {}
    for g in games.iter_rows(named=True):
        free = [c for c in CHAMPS if c not in used.setdefault(g["series_id"], set())]
        champs = [str(c) for c in rng.choice(free, 10, replace=False)]
        used[g["series_id"]].update(champs)
        teams = [g["blue_team_id"]] * 5 + [g["red_team_id"]] * 5
        part_rows.extend(
            {
                "game_id": g["game_id"],
                "team_id": t,
                "player_id": f"{t}p{k % 5}",
                "champion": c,
                "inferred_role": ROLES[k % 5],
            }
            for k, (t, c) in enumerate(zip(teams, champs, strict=True))
        )
        draft_rows.extend(
            {"game_id": g["game_id"], "slot": 7 + k, "action": "pick", "phase": "pick1", "team_id": t, "champion": c}
            for k, (t, c) in enumerate(zip(teams, champs, strict=True))
        )
    roles = "top|jungle|mid|bot|support"
    champions = pl.DataFrame(
        [{"champion": c, "roles": roles, "scaling": "mid", **dict.fromkeys(state.TAG_COLS, 1.0)} for c in CHAMPS]
    )
    ctx = game_context(games, series)
    return state.Inputs(
        games=games,
        series=series,
        draft=pl.DataFrame(draft_rows),
        parts=pl.DataFrame(part_rows),
        fearless=games.select("game_id", locked_count=pl.lit(0)),
        champions=champions,
        cmap=pl.DataFrame({"grid_name": CHAMPS, "champion": CHAMPS}),
        deltas=pl.DataFrame({"champion": CHAMPS, "patch": ["15.1"] * len(CHAMPS), "score": [0.0] * len(CHAMPS)}),
        elo=game_elo(ctx),
    )


def test_feature_store_ignores_the_future():
    """Changing the result of game i must not change the features of game i or any earlier game."""
    series = _series(20)
    games = _games(series, np.random.default_rng(0))
    inp = _inputs(series, games, np.random.default_rng(5))
    base, _ = state.build(inp)
    i = 15
    flipped_id = base["game_id"][i]
    g = games.with_columns(
        winner_team_id=pl.when(pl.col("game_id") == flipped_id)
        .then(pl.when(pl.col("winner_team_id") == pl.col("blue_team_id")).then("red_team_id").otherwise("blue_team_id"))
        .otherwise("winner_team_id")
    )
    after, _ = state.build(state.Inputs(**{**inp.__dict__, "games": g, "elo": game_elo(game_context(g, series))}))
    cols = [c for c in base.columns if c.startswith("d_")]
    assert base.head(i + 1).select(cols).equals(after.head(i + 1).select(cols))
    assert not base.tail(-(i + 1)).select(cols).equals(after.tail(-(i + 1)).select(cols))  # later games do react


def test_features_are_pre_game_only():
    assert not set(state.TEAM_FEATURES) & IN_GAME
    ctx = game_context(_games(_series(8), np.random.default_rng(1)), _series(8))
    played: dict[str, int] = {}
    for row in game_elo(ctx).join(ctx, on="game_id").sort("started_at", "game_id").iter_rows(named=True):
        assert row["blue_n"] == played.get(row["blue_team_id"], 0)  # Elo counts strictly earlier games
        for t in (row["blue_team_id"], row["red_team_id"]):
            played[t] = played.get(t, 0) + 1


def test_draft_rows_know_only_earlier_actions_and_fearless_locks():
    series = _series(1)
    games = _games(series, np.random.default_rng(2))  # one series, two games
    _, act = state.build(_inputs(series, games, np.random.default_rng(6)))
    rows = act.rows.with_row_index("idx")
    game1 = rows.filter(pl.col("game_number") == 1)
    game2 = rows.filter(pl.col("game_number") == 2)
    first_of_game2 = int(game2["idx"][0])
    locked = {act.vocab.index(c) for c in game1["champion"].to_list()}
    assert set(np.flatnonzero(act.unavailable[first_of_game2])) == locked  # Fearless: game-1 picks, nothing else
    second = int(game2["idx"][1])
    assert set(np.flatnonzero(act.unavailable[second])) == locked | {int(game2["y"][0])}
    assert not act.unavailable[rows["idx"].to_numpy(), rows["y"].to_numpy()].any()  # the chosen champion is free


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
    act = SimpleNamespace(vocab=vocab)  # the baselines only read the vocabulary
    glob = GlobalFrequency()
    glob.fit(train, act)
    g = glob.scores(rows)[0]
    assert g[2] < g[0]  # "Old" was only played on an old patch
    team = TeamSlotFrequency()
    team.fit(train, act)
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
    ctx = game_context(games, series)
    played: dict[str, int] = {}
    for row in game_elo(ctx).join(ctx, on="game_id").sort("started_at", "game_id").iter_rows(named=True):
        assert row["blue_n"] == played.get(row["blue_team_id"], 0)
        assert row["red_n"] == played.get(row["red_team_id"], 0)
        for t in (row["blue_team_id"], row["red_team_id"]):
            played[t] = played.get(t, 0) + 1
    data = load()
    rows = data.actions
    assert not data.act.unavailable[rows["idx"].to_numpy(), rows["y"].to_numpy()].any()


@pytest.mark.real_data
def test_feature_store_ignores_the_future_on_real_data():
    """Phase 8 leakage check (§5.3): flip every result and scramble every draft after a cutoff; the outcome features
    and the draft-candidate features of every game/action before the cutoff must not change at all."""
    from fele.config import settings  # noqa: PLC0415 - real-data paths only
    from fele.features import state  # noqa: PLC0415
    from fele.stats.data import game_context, read  # noqa: PLC0415
    from fele.stats.elo import game_elo  # noqa: PLC0415

    static = settings().local("static")
    games, series, draft = read("games"), read("series"), read("draft_actions")

    def run(g: pl.DataFrame, d: pl.DataFrame) -> tuple[pl.DataFrame, state.ActionData]:
        return state.build(
            state.Inputs(
                games=g,
                series=series,
                draft=d,
                parts=read("participants"),
                fearless=read("fearless_state"),
                champions=pl.read_parquet(static / "champions.parquet"),
                cmap=pl.read_parquet(static / "champion_map.parquet"),
                deltas=pl.read_parquet(static / "patch_deltas.parquet"),
                elo=game_elo(game_context(g, series)),
            )
        )

    cutoff = games["started_at"].sort()[games.height // 2]
    later = games.filter(pl.col("started_at") > cutoff)["game_id"]
    flipped = games.with_columns(
        winner_team_id=pl.when(pl.col("game_id").is_in(later.implode()))
        .then(pl.when(pl.col("winner_team_id") == pl.col("blue_team_id")).then("red_team_id").otherwise("blue_team_id"))
        .otherwise("winner_team_id")
    )
    shuffled = draft.with_columns(
        champion=pl.when(pl.col("game_id").is_in(later.implode()))
        .then(pl.col("champion").shuffle(seed=1))
        .otherwise("champion")
    )
    base_out, base_act = run(games, draft)
    new_out, new_act = run(flipped, shuffled)
    feats = [c for c in base_out.columns if c.startswith("d_")]
    early = pl.col("started_at") <= cutoff
    assert base_out.filter(early).select(feats).equals(new_out.filter(early).select(feats))
    n_early = base_act.rows.filter(early).height
    assert n_early > 0
    gt_early = base_act.rows.filter(early)["gt"].unique().to_numpy()
    assert np.array_equal(base_act.team_x[gt_early], new_act.team_x[gt_early])
    assert np.array_equal(base_act.synergy[:n_early], new_act.synergy[:n_early])
    # and the future does matter for later games (the test would catch a frozen feature store)
    assert not base_out.filter(~early).select(feats).equals(new_out.filter(~early).select(feats))
