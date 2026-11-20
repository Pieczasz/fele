"""Phase 8 model building blocks on synthetic data with known answers."""

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from fele.features.state import UNTAGGED, ActionData
from fele.models.action import ConditionalLogit, LambdaRank, open_roles, role_assignment
from fele.models.outcome import L3, OUTCOME_LADDER, PenalizedLogistic, tune


def test_penalized_logistic_keeps_free_coefficient_and_shrinks_the_rest():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(2000, 3))
    y = (rng.random(2000) < 1 / (1 + np.exp(-(1.5 * x[:, 0] + 0.8 * x[:, 1])))).astype(float)
    free = PenalizedLogistic(1e6, [True, False, False])
    free.fit(x, y)
    w = free.coefficients()
    alone = PenalizedLogistic(1e-6, [False])
    alone.fit(x[:, :1], y)
    # the free coefficient is estimated without shrinkage: it equals the unpenalised fit on x0 alone (smaller than
    # the true 1.5 because the dropped x1 effect attenuates a logistic coefficient)
    assert w[0] == pytest.approx(alone.coefficients()[0], abs=1e-3)
    assert np.abs(w[1:]).max() < 0.01  # the penalised ones are shrunk to ~0
    loose = PenalizedLogistic(1e-6, [False, False, False])
    loose.fit(x, y)
    assert loose.coefficients()[1] == pytest.approx(0.8, abs=0.15)


def test_conditional_logit_gradient_matches_finite_differences():
    rng = np.random.default_rng(1)
    x = rng.normal(size=(40, 6, 3)).astype(np.float32)
    y = rng.integers(0, 6, size=40)
    mask = np.zeros((40, 6), bool)
    mask[:, 5] = True
    y[y == 5] = 0  # the true champion is always available
    model = ConditionalLogit(lam=0.5)
    w = model._fit_w(x, y, mask, 0.5)  # noqa: SLF001 - checking the optimiser's objective directly
    rows = np.arange(40)

    def nll(v: np.ndarray) -> float:
        logits = np.where(mask, -np.inf, x.astype(float) @ v)
        logz = np.log(np.exp(logits - logits.max(axis=1, keepdims=True)).sum(axis=1)) + logits.max(axis=1)
        return float((logz - logits[rows, y]).sum() + 0.25 * v @ v)

    eps = 1e-5
    grad = np.array([(nll(w + eps * e) - nll(w - eps * e)) / (2 * eps) for e in np.eye(3)])
    assert np.abs(grad).max() < 0.05  # the optimum: gradient ~ 0


def test_role_assignment_prefers_primary_role_and_always_assigns():
    u = UNTAGGED
    rank = np.array(
        [
            [0, u, u, u, u],  # top only
            [1, 0, u, u, u],  # jungle first, top second (e.g. Wukong)
            [u, u, 0, u, u],  # mid only
            [0, u, u, u, u],  # top only: second top laner has no free tagged role
        ],
        np.int8,
    )
    assert role_assignment([1, 0], rank) == [1, 0]  # Wukong goes jungle (primary), not top (first in role order)
    assert role_assignment([0, 3], rank) == [0, 1]  # a pick with no free tagged role still gets a role
    picks = np.array([[1, 0, -1, -1], [-1, -1, -1, -1]], np.int32)
    free = open_roles(picks, rank)
    assert free[0].tolist() == [False, False, True, True, True]
    assert free[1].all()


def test_tune_picks_the_better_setting_on_inner_folds():
    t0 = datetime(2025, 1, 1, tzinfo=UTC)
    rng = np.random.default_rng(2)
    n = 400
    x = rng.normal(size=n)
    train = pl.DataFrame(
        {
            "series_id": [f"s{i // 2}" for i in range(n)],
            "started_at": [t0 + timedelta(hours=i) for i in range(n)],
            "x": x,
            "y": (rng.random(n) < 1 / (1 + np.exp(-2 * x))).astype(float),
        }
    )

    class Fixed:
        def __init__(self, *, use: bool) -> None:
            self.use = use

        def fit(self, rows: pl.DataFrame) -> None:
            pass

        def predict(self, rows: pl.DataFrame) -> np.ndarray:
            if not self.use:
                return np.full(rows.height, 0.5)
            return 1 / (1 + np.exp(-2 * rows["x"].to_numpy()))

    best = tune(lambda p: Fixed(use=p["use"]), [{"use": False}, {"use": True}], train)  # type: ignore[arg-type,return-value]
    assert best == {"use": True}


def _outcome_frame(n: int = 240) -> pl.DataFrame:
    rng = np.random.default_rng(3)
    t0 = datetime(2025, 1, 1, tzinfo=UTC)
    champs = ["A", "B", "C", "D", "E", "F", "G", "H"]
    data: dict[str, object] = {
        "series_id": [f"s{i // 2}" for i in range(n)],
        "started_at": [t0 + timedelta(hours=i) for i in range(n)],
        "game_number": [1 + i % 3 for i in range(n)],
        "blue_team_id": [f"t{i % 4}" for i in range(n)],
        "red_team_id": [f"t{(i + 1) % 4}" for i in range(n)],
        "blue_champs": [list(rng.choice(champs, 5, replace=False)) for _ in range(n)],
        "red_champs": [list(rng.choice(champs, 5, replace=False)) for _ in range(n)],
        "series_score_diff": rng.integers(-1, 2, n).astype(float),
    }
    for col in {*L3} - {"late", "late_comfort", "series_score_diff"}:
        data[col] = rng.normal(size=n)
    frame = pl.DataFrame(data)
    eta = 0.01 * frame["d_elo"].to_numpy() * 100
    return frame.with_columns(y=pl.Series((rng.random(n) < 1 / (1 + np.exp(-eta))).astype(float)))


@pytest.mark.parametrize(
    "name",
    [
        "logit_l2",
        "logit_l3",
        "logit_champions",
        "logit_archetypes",
        "knn",
        "random_forest",
        "lgbm",
        "lgbm_platt",
        "logit_l3_isotonic",
        "avg_logit_lgbm",
        "naive_bayes",
    ],
)
def test_outcome_rungs_fit_and_predict_probabilities(name: str):
    frame = _outcome_frame()
    train, test = frame.head(200), frame.tail(40).with_columns(blue_champs=pl.lit(["Z", "A"]))  # unseen champion "Z"
    model = OUTCOME_LADDER[name]()
    model.fit(train)
    p = model.predict(test)
    assert p.shape == (40,)
    assert np.all((p > 0) & (p < 1))


def _action_data(n_games: int = 60, v: int = 12) -> tuple[pl.DataFrame, ActionData]:
    rng = np.random.default_rng(4)
    t0 = datetime(2025, 1, 1, tzinfo=UTC)
    rows, unavailable, own, opp = [], [], [], []
    for g in range(n_games):
        taken: list[int] = []
        for slot in range(1, 7):
            choice = int(rng.choice([c for c in range(v) if c not in taken]))
            rows.append(
                {
                    "gt": g,
                    "game_id": f"g{g}",
                    "series_id": f"s{g}",
                    "started_at": t0 + timedelta(hours=g),
                    "team_id": "A",
                    "patch": "15.1",
                    "champion": f"c{choice}",
                    "action": "ban" if slot < 4 else "pick",
                    "phase": "ban1" if slot < 4 else "pick1",
                    "slot": slot,
                    "game_number": 1,
                    "y": choice,
                }
            )
            mask = np.zeros(v, bool)
            mask[taken] = True
            unavailable.append(mask)
            own.append([-1] * 4)
            opp.append([-1] * 5)
            taken.append(choice)
    team_x = rng.random((n_games, v, 8)).astype(np.float32)
    team_x[:, 3, 3] += 2.0  # champion 3 is this team's favourite pick
    act = ActionData(
        vocab=[f"c{i}" for i in range(v)],
        role_rank=np.where(np.eye(v, 5, dtype=bool), 0, UNTAGGED).astype(np.int8),
        team_x=team_x,
        rows=pl.DataFrame(rows),
        unavailable=np.stack(unavailable),
        own_picks=np.array(own, np.int32),
        opp_picks=np.array(opp, np.int32),
        synergy=np.zeros((len(rows), v), np.float32),
        opp_synergy=np.zeros((len(rows), v), np.float32),
    )
    return act.rows.with_row_index("idx"), act


@pytest.mark.parametrize("model", [ConditionalLogit, LambdaRank])
def test_action_rungs_give_distributions_over_available_champions(model: type):
    rows, act = _action_data()
    m = model()
    m.fit(rows.head(300), act)
    test = rows.tail(60)
    s = m.scores(test)
    assert s.shape == (60, len(act.vocab))
    assert np.allclose(s.sum(axis=1), 1.0)
    assert np.all(s[act.unavailable[test["idx"].to_numpy()]] == 0)  # taken champions get no probability
