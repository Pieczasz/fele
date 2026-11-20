# pyright: basic, reportArgumentType=false, reportOptionalMemberAccess=false
"""Typed wrappers around scikit-learn and LightGBM. Neither ships complete type stubs, so this one file is checked
in basic mode and the rest of the package stays strict."""

from typing import Any

import lightgbm as lgb
import numpy as np
import numpy.typing as npt
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

type Floats = npt.NDArray[np.float64]


class Classifier:
    """fit(X, y) / predict(X) -> P(y = 1) for any scikit-learn-style binary classifier."""

    def __init__(self, kind: str, **params: Any) -> None:  # noqa: ANN401 - estimator-specific hyperparameters
        self.kind = kind
        self.params = params
        self._model = _make(kind, params)

    def fit(self, x: Floats, y: Floats) -> None:
        if self.kind == "knn":  # early inner folds can be smaller than k
            self._model.set_params(kneighborsclassifier__n_neighbors=min(self.params.get("k", 100), len(x)))
        self._model.fit(x, y)

    def predict(self, x: Floats) -> Floats:
        return np.asarray(self._model.predict_proba(x)[:, 1], dtype=float)

    def coefficients(self) -> Floats | None:
        """Standardised coefficients of a logistic pipeline (None for other models)."""
        last = self._model[-1] if hasattr(self._model, "__getitem__") else self._model
        return np.asarray(last.coef_[0], dtype=float) if hasattr(last, "coef_") else None

    def booster(self) -> Any:  # noqa: ANN401 - LightGBM model for SHAP
        return self._model if self.kind == "lgbm" else None


def _make(kind: str, p: dict[str, Any]) -> Any:  # noqa: ANN401, PLR0911 - one constructor per model family
    if kind == "logistic":
        return make_pipeline(StandardScaler(), LogisticRegression(C=p.get("C", 1.0), max_iter=2000))
    if kind == "random_forest":
        return RandomForestClassifier(
            n_estimators=400, min_samples_leaf=p.get("leaf", 20), max_features="sqrt", n_jobs=-1, random_state=0
        )
    if kind == "extra_trees":
        return ExtraTreesClassifier(
            n_estimators=400, min_samples_leaf=p.get("leaf", 20), max_features="sqrt", n_jobs=-1, random_state=0
        )
    if kind == "knn":
        return make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=p.get("k", 100), weights="distance"))
    if kind == "gp":
        kernel = ConstantKernel(1.0) * RBF(length_scale=np.ones(p["dims"]) * 3.0) + WhiteKernel(1.0)
        return make_pipeline(StandardScaler(), GaussianProcessClassifier(kernel=kernel, random_state=0))
    if kind == "svm":
        return make_pipeline(StandardScaler(), SVC(C=p.get("C", 1.0), gamma="scale", probability=True, random_state=0))
    if kind == "naive_bayes":
        return GaussianNB()
    if kind == "lgbm":
        return lgb.LGBMClassifier(verbose=-1, random_state=0, **p)
    raise ValueError(kind)


class Isotonic:
    def __init__(self) -> None:
        self._model = IsotonicRegression(out_of_bounds="clip", y_min=0.01, y_max=0.99)

    def fit(self, p: Floats, y: Floats) -> None:
        self._model.fit(p, y)

    def predict(self, p: Floats) -> Floats:
        return np.asarray(self._model.predict(p), dtype=float)


class Logistic:
    """L2-regularised logistic regression on raw features (scikit-learn defaults)."""

    def __init__(self) -> None:
        self._model = LogisticRegression()

    def fit(self, x: Floats, y: Floats) -> None:
        self._model.fit(x, y)

    def predict(self, x: Floats) -> Floats:
        return np.asarray(self._model.predict_proba(x)[:, 1], dtype=float)


def svd_embedding(matrix: Floats, dims: int) -> Floats:
    """Rows of `matrix` (team compositions x champions) -> champion embeddings (champions x dims)."""
    svd = TruncatedSVD(n_components=dims, random_state=0)
    svd.fit(matrix)
    return np.asarray(svd.components_.T, dtype=float)


def kmeans(points: Floats, k: int) -> tuple[Floats, npt.NDArray[np.int64]]:
    """(centres, labels) of k-means on the rows of `points`."""
    km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(points)
    return np.asarray(km.cluster_centers_, dtype=float), np.asarray(km.labels_, dtype=np.int64)


class Ranker:
    """LightGBM LambdaRank: fit(features, relevance labels, group sizes) / predict(features) -> scores."""

    def __init__(self, **params: Any) -> None:  # noqa: ANN401 - LightGBM hyperparameters
        self._model = lgb.LGBMRanker(verbose=-1, random_state=0, **params)

    def fit(self, x: Any, label: Any, group: Any) -> None:  # noqa: ANN401 - numpy arrays of any dtype
        self._model.fit(x, label, group=group)

    def predict(self, x: Any) -> Floats:  # noqa: ANN401
        return np.asarray(self._model.predict(x), dtype=float)


def roc_auc(y: Floats, p: Floats) -> float:
    return float(roc_auc_score(y, p))
