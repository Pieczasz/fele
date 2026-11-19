# pyright: basic
"""Typed wrappers around scikit-learn. It ships no type stubs, so this one file is checked in basic mode and the
rest of the package stays strict."""

import numpy as np
import numpy.typing as npt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

type Floats = npt.NDArray[np.float64]


class Logistic:
    """L2-regularised logistic regression (scikit-learn defaults)."""

    def __init__(self) -> None:
        self._model = LogisticRegression()

    def fit(self, x: Floats, y: Floats) -> None:
        self._model.fit(x, y)

    def predict(self, x: Floats) -> Floats:
        return np.asarray(self._model.predict_proba(x)[:, 1], dtype=float)


def roc_auc(y: Floats, p: Floats) -> float:
    return float(roc_auc_score(y, p))
