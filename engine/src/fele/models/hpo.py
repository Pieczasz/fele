# pyright: basic, reportMissingImports=false
"""LightGBM tuned by Optuna (TPE, small budget) on walk-forward inner folds only — nested inside each outer fold.

Optuna is in the `ml` extra; without it the same search space is sampled at random (seeded), so the model still
runs in CI-like environments.
"""

import random
from importlib.util import find_spec
from typing import Any

import numpy as np
import polars as pl

from fele.eval.metrics import log_losses
from fele.eval.splits import inner_masks
from fele.models.outcome import L3, Model, Sk

TRIALS = 25


def _space(trial_or_rng: Any) -> dict[str, Any]:  # noqa: ANN401 - optuna Trial or random.Random
    def pick(name: str, lo: float, hi: float, *, log: bool = False, integer: bool = False) -> float | int:
        if hasattr(trial_or_rng, "suggest_float"):
            if integer:
                return trial_or_rng.suggest_int(name, int(lo), int(hi), log=log)
            return trial_or_rng.suggest_float(name, lo, hi, log=log)
        v = float(np.exp(trial_or_rng.uniform(np.log(lo), np.log(hi)))) if log else trial_or_rng.uniform(lo, hi)
        return round(v) if integer else v

    return {
        "n_estimators": pick("n_estimators", 50, 400, integer=True),
        "learning_rate": pick("learning_rate", 0.01, 0.1, log=True),
        "num_leaves": pick("num_leaves", 3, 16, integer=True),
        "min_child_samples": pick("min_child_samples", 30, 150, integer=True),
        "reg_lambda": pick("reg_lambda", 0.1, 50.0, log=True),
        "colsample_bytree": pick("colsample_bytree", 0.4, 1.0),
        "subsample": 0.8,
        "subsample_freq": 1,
        "monotone_constraints": [1] + [0] * (len(L3) - 1),
    }


def _inner_loss(params: dict[str, Any], train: pl.DataFrame) -> float:
    losses = []
    for tr, va in inner_masks(train):
        m = Sk("lgbm", L3, [params], params)
        m.fit(train.filter(tr))
        valid = train.filter(va)
        losses.append(float(log_losses(valid["y"].to_numpy(), m.predict(valid)).mean()))
    return float(np.mean(losses))


class LgbmOptuna(Model):
    def __init__(self) -> None:
        self.params: dict[str, Any] = {}
        self.model = Sk("lgbm", L3, [{}], {})

    def fit(self, train: pl.DataFrame) -> None:
        if find_spec("optuna") is not None:
            import optuna  # noqa: PLC0415 - optional

            optuna.logging.set_verbosity(optuna.logging.WARNING)
            study = optuna.create_study(sampler=optuna.samplers.TPESampler(seed=0))
            study.optimize(lambda t: _inner_loss(_space(t), train), n_trials=TRIALS)
            best = _space(optuna.trial.FixedTrial(study.best_params))
        else:
            rng = random.Random(0)  # noqa: S311 - search order, not security
            candidates = [_space(rng) for _ in range(TRIALS)]
            best = min(candidates, key=lambda p: _inner_loss(p, train))
        self.params = best
        self.model = Sk("lgbm", L3, [best], best)
        self.model.fit(train)

    def predict(self, rows: pl.DataFrame) -> np.ndarray:
        return self.model.predict(rows)
