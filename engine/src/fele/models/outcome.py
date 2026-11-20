"""Outcome model ladder (problem A, AGENT_PLAN.md §5.5). Every model: fit(train rows) / predict(rows) -> P(blue wins).

Anti-overfitting rules built in:
- hyperparameters are chosen by `tune()` on walk-forward *inner* folds of the training rows only;
- everything learnt from champions (one-hot effects, SVD embeddings, archetype clusters) is fitted inside fit();
- calibration (Platt / isotonic) is fitted on cross-fitted inner-fold predictions, never on the test month;
- small, fixed search spaces; LightGBM is monotone in the Elo difference and heavily regularised.
"""

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import numpy.typing as npt
import polars as pl
from scipy import optimize

from fele.eval.metrics import log_losses
from fele.eval.splits import inner_masks
from fele.features.state import TAG_COLS
from fele.models.sk import Classifier, Isotonic, Logistic, kmeans, svd_embedding

type Floats = npt.NDArray[np.float64]

L2 = ("d_elo", "d_form", "d_champ_wr", "d_champ_presence", "d_comfort", "d_comfort_wr", "d_first_time", "d_delta")
L3 = (*L2, *(f"d_{t}" for t in TAG_COLS), "d_scaling", "d_damage_balance", "series_score_diff", "late", "late_comfort")
LAMBDA_GRID = (1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0)  # L2 penalty on draft features, in log-loss units
FREE = ("d_elo",)  # never shrunk: Elo is the strong, already-validated signal (Phase 7)
LATE_GAME = 3


def matrix(rows: pl.DataFrame, cols: Sequence[str]) -> Floats:
    late = (pl.col("game_number") >= LATE_GAME).cast(pl.Float64)
    rows = rows.with_columns(late=late, late_comfort=late * pl.col("d_comfort"))
    return rows.select(cols).to_numpy().astype(float)


def champion_onehot(rows: pl.DataFrame, vocab: list[str]) -> Floats:
    """+1 for each blue champion, -1 for each red one (a Bradley-Terry style champion-strength design)."""
    index = {c: i for i, c in enumerate(vocab)}
    x = np.zeros((rows.height, len(vocab)))
    for r, (blue, red) in enumerate(rows.select("blue_champs", "red_champs").rows()):
        x[r, [index[c] for c in blue if c in index]] += 1
        x[r, [index[c] for c in red if c in index]] -= 1
    return x


class PenalizedLogistic:
    """Logistic regression on standardised features where only *some* coefficients are L2-shrunk.

    Uniform shrinkage (scikit-learn's single C) also shrinks the strong Elo coefficient toward 0 when noisy draft
    features are added — the first L2 rung lost to Elo alone that way. Here the intercept and FREE columns are
    unpenalised; the penalty `lam` applies to the rest.
    """

    def __init__(self, lam: float, free: Sequence[bool]) -> None:
        self.lam = lam
        self.free = np.array(free, bool)
        self.mean: Floats = np.zeros(0)
        self.std: Floats = np.ones(0)
        self.w: Floats = np.zeros(0)

    def fit(self, x: Floats, y: Floats) -> None:
        self.mean, self.std = x.mean(axis=0), x.std(axis=0) + 1e-9
        z = np.hstack([np.ones((len(x), 1)), (x - self.mean) / self.std])
        pen = np.concatenate([[0.0], np.where(self.free, 0.0, self.lam)])

        def loss(w: Floats) -> tuple[float, Floats]:
            eta = z @ w
            p = 1 / (1 + np.exp(-eta))
            ll = np.logaddexp(0, eta).sum() - y @ eta
            return float(ll + 0.5 * (pen * w * w).sum()), z.T @ (p - y) + pen * w

        res = optimize.minimize(loss, np.zeros(z.shape[1]), jac=True, method="L-BFGS-B")
        self.w = np.asarray(res.x, dtype=float)

    def predict(self, x: Floats) -> Floats:
        z = np.hstack([np.ones((len(x), 1)), (x - self.mean) / self.std])
        return 1 / (1 + np.exp(-(z @ self.w)))

    def coefficients(self) -> Floats:
        """Per standardised feature (intercept excluded)."""
        return self.w[1:]


class Model:
    """Base: subclasses implement _fit / _predict on prepared matrices; fit() may tune first."""

    def fit(self, train: pl.DataFrame) -> None:
        raise NotImplementedError

    def predict(self, rows: pl.DataFrame) -> Floats:
        raise NotImplementedError


def tune(
    make: Callable[[dict[str, Any]], Model], grid: Sequence[dict[str, Any]], train: pl.DataFrame
) -> dict[str, Any]:
    """The grid point with the lowest mean log loss over walk-forward inner folds of `train`."""
    folds = inner_masks(train)
    best, best_loss = grid[0], float("inf")
    for params in grid:
        losses: list[float] = []
        for tr, va in folds:
            m = make(params)
            m.fit(train.filter(tr))
            valid = train.filter(va)
            losses.append(float(log_losses(valid["y"].to_numpy(), m.predict(valid)).mean()))
        if (loss := float(np.mean(losses))) < best_loss:
            best, best_loss = params, loss
    return best


# --- linear ------------------------------------------------------------------------------------------------------
def _free(n_extra: int, cols: Sequence[str]) -> list[bool]:
    return [c in FREE for c in cols] + [False] * n_extra


class LogisticFeatures(Model):
    """Penalised logistic regression on a fixed feature set (Elo free, the rest shrunk; lambda tuned on inner folds)."""

    def __init__(self, cols: Sequence[str], lam: float | None = None) -> None:
        self.cols, self.lam = tuple(cols), lam
        self.clf = PenalizedLogistic(lam or 10.0, _free(0, self.cols))

    def fit(self, train: pl.DataFrame) -> None:
        if self.lam is None:
            best = tune(lambda p: LogisticFeatures(self.cols, p["lam"]), [{"lam": v} for v in LAMBDA_GRID], train)
            self.clf = PenalizedLogistic(best["lam"], _free(0, self.cols))
        self.clf.fit(matrix(train, self.cols), train["y"].to_numpy())

    def predict(self, rows: pl.DataFrame) -> Floats:
        return self.clf.predict(matrix(rows, self.cols))


class LogisticChampions(Model):
    """L3 features + signed champion one-hot (champion strengths), one regularisation strength tuned on inner folds."""

    def __init__(self, lam: float | None = None) -> None:
        self.lam = lam
        self.vocab: list[str] = []
        self.clf = PenalizedLogistic(lam or 10.0, [])

    def _x(self, rows: pl.DataFrame) -> Floats:
        return np.hstack([matrix(rows, L3), champion_onehot(rows, self.vocab)])

    def fit(self, train: pl.DataFrame) -> None:
        self.vocab = sorted({c for col in ("blue_champs", "red_champs") for cs in train[col].to_list() for c in cs})
        if self.lam is None:
            best = tune(lambda p: LogisticChampions(p["lam"]), [{"lam": v} for v in LAMBDA_GRID], train)
            self.lam = best["lam"]
        self.clf = PenalizedLogistic(self.lam or 10.0, _free(len(self.vocab), L3))
        self.clf.fit(self._x(train), train["y"].to_numpy())

    def predict(self, rows: pl.DataFrame) -> Floats:
        return self.clf.predict(self._x(rows))


class LogisticArchetypes(Model):
    """L3 + unsupervised composition archetypes, fitted on the training drafts only:
    TruncatedSVD of the team x champion matrix -> champion embeddings; a team's composition = mean embedding;
    k-means on training compositions -> archetype; features = embedding difference + archetype one-hot difference.
    """

    DIMS = 6
    CLUSTERS = 6

    def __init__(self, lam: float | None = None) -> None:
        self.lam = lam
        self.vocab: list[str] = []
        self.emb: Floats = np.zeros((0, self.DIMS))
        self.centres: Floats = np.zeros((self.CLUSTERS, self.DIMS))
        self.clf = PenalizedLogistic(lam or 10.0, [])

    def _comp(self, champs: list[list[str]]) -> Floats:
        index = {c: i for i, c in enumerate(self.vocab)}
        out = np.zeros((len(champs), self.DIMS))
        for r, cs in enumerate(champs):
            ids = [index[c] for c in cs if c in index]
            if ids:
                out[r] = self.emb[ids].mean(axis=0)
        return out

    def _arch(self, comp: Floats) -> Floats:
        d = ((comp[:, None, :] - self.centres[None]) ** 2).sum(axis=2)
        return np.eye(self.CLUSTERS)[d.argmin(axis=1)]

    def _x(self, rows: pl.DataFrame) -> Floats:
        blue, red = self._comp(rows["blue_champs"].to_list()), self._comp(rows["red_champs"].to_list())
        return np.hstack([matrix(rows, L3), blue - red, self._arch(blue) - self._arch(red)])

    def fit(self, train: pl.DataFrame) -> None:
        teams = train["blue_champs"].to_list() + train["red_champs"].to_list()
        self.vocab = sorted({c for cs in teams for c in cs})
        index = {c: i for i, c in enumerate(self.vocab)}
        m = np.zeros((len(teams), len(self.vocab)))
        for r, cs in enumerate(teams):
            m[r, [index[c] for c in cs]] = 1
        self.emb = svd_embedding(m, self.DIMS)
        self.centres, _ = kmeans(self._comp(teams), self.CLUSTERS)
        if self.lam is None:
            best = tune(lambda p: LogisticArchetypes(p["lam"]), [{"lam": v} for v in LAMBDA_GRID], train)
            self.lam = best["lam"]
        self.clf = PenalizedLogistic(self.lam or 10.0, _free(self.DIMS + self.CLUSTERS, L3))
        self.clf.fit(self._x(train), train["y"].to_numpy())

    def predict(self, rows: pl.DataFrame) -> Floats:
        return self.clf.predict(self._x(rows))


# --- non-parametric / tree ensembles -----------------------------------------------------------------------------
class Sk(Model):
    """Any adapter classifier on a fixed feature set, one hyperparameter tuned on inner folds."""

    def __init__(
        self, kind: str, cols: Sequence[str], grid: Sequence[dict[str, Any]], params: dict[str, Any] | None = None
    ) -> None:
        self.kind = kind
        self.cols: tuple[str, ...] = tuple(cols)
        self.grid: tuple[dict[str, Any], ...] = tuple(grid)
        self.params = params
        self.clf = Classifier(kind, **(params or self.grid[0]))

    def fit(self, train: pl.DataFrame) -> None:
        params = self.params
        if params is None:
            single = len(self.grid) == 1
            params = (
                self.grid[0] if single else tune(lambda p: Sk(self.kind, self.cols, self.grid, p), self.grid, train)
            )
        self.clf = Classifier(self.kind, **params)
        self.clf.fit(matrix(train, self.cols), train["y"].to_numpy())

    def predict(self, rows: pl.DataFrame) -> Floats:
        return self.clf.predict(matrix(rows, self.cols))


LGBM_GRID = tuple(
    {
        "n_estimators": n,
        "learning_rate": 0.03,
        "num_leaves": leaves,
        "min_child_samples": 60,
        "subsample": 0.8,
        "subsample_freq": 1,
        "colsample_bytree": 0.7,
        "reg_lambda": 5.0,
        "monotone_constraints": [1] + [0] * (len(L3) - 1),  # higher Elo difference never lowers P(blue)
    }
    for n in (100, 250)
    for leaves in (4, 8)
)


# --- calibration & ensembles -------------------------------------------------------------------------------------
class Calibrated(Model):
    """Platt or isotonic calibration fitted on cross-fitted inner-fold predictions of the base model."""

    def __init__(self, make: Callable[[], Model], method: str = "platt") -> None:
        self.make, self.method = make, method
        self.cal: Logistic | Isotonic = Isotonic() if method == "isotonic" else Logistic()
        self.base = make()

    def fit(self, train: pl.DataFrame) -> None:
        preds: list[Floats] = []
        ys: list[Floats] = []
        for tr, va in inner_masks(train):
            m = self.make()
            m.fit(train.filter(tr))
            valid = train.filter(va)
            preds.append(m.predict(valid))
            ys.append(valid["y"].to_numpy())
        p, y = np.concatenate(preds), np.concatenate(ys)
        self.cal.fit(_logit(p).reshape(-1, 1) if self.method == "platt" else p, y)
        self.base = self.make()
        self.base.fit(train)

    def predict(self, rows: pl.DataFrame) -> Floats:
        p = self.base.predict(rows)
        return self.cal.predict(_logit(p).reshape(-1, 1) if self.method == "platt" else p)


def _logit(p: Floats) -> Floats:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


class Average(Model):
    """Mean of member probabilities (an ensemble of two or more rungs)."""

    def __init__(self, makers: Sequence[Callable[[], Model]]) -> None:
        self.makers = makers
        self.members: list[Model] = []

    def fit(self, train: pl.DataFrame) -> None:
        self.members = [m() for m in self.makers]
        for m in self.members:
            m.fit(train)

    def predict(self, rows: pl.DataFrame) -> Floats:
        return np.mean([m.predict(rows) for m in self.members], axis=0)


def _lgbm_optuna() -> Model:
    from fele.models.hpo import LgbmOptuna  # noqa: PLC0415 - Optuna is optional (ml extra)

    return LgbmOptuna()


def _bayes() -> Model:
    from fele.models.bayes import BayesHierarchical  # noqa: PLC0415 - PyMC is optional (ml extra)

    return BayesHierarchical()


OUTCOME_LADDER: dict[str, Callable[[], Model]] = {
    "logit_l2": lambda: LogisticFeatures(L2),
    "logit_l3": lambda: LogisticFeatures(L3),
    "logit_champions": LogisticChampions,
    "logit_archetypes": LogisticArchetypes,
    "naive_bayes": lambda: Sk("naive_bayes", L2, [{}]),
    "knn": lambda: Sk("knn", L2, [{"k": k} for k in (50, 100, 200, 400)]),
    "random_forest": lambda: Sk("random_forest", L3, [{"leaf": leaf} for leaf in (10, 30, 60)]),
    "extra_trees": lambda: Sk("extra_trees", L3, [{"leaf": leaf} for leaf in (10, 30, 60)]),
    "svm_rbf": lambda: Sk("svm", L2, [{"C": c} for c in (0.1, 1.0)]),
    "gaussian_process": lambda: Sk("gp", L2, [{"dims": len(L2)}]),
    "lgbm": lambda: Sk("lgbm", L3, LGBM_GRID),
    "lgbm_platt": lambda: Calibrated(lambda: Sk("lgbm", L3, LGBM_GRID), "platt"),
    "logit_l3_isotonic": lambda: Calibrated(lambda: LogisticFeatures(L3), "isotonic"),
    "avg_logit_lgbm": lambda: Average([lambda: LogisticFeatures(L3), lambda: Sk("lgbm", L3, LGBM_GRID)]),
    "lgbm_optuna": _lgbm_optuna,
    "bayes_hier": _bayes,
}
