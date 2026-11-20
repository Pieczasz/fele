# pyright: basic, reportMissingImports=false
"""Hierarchical Bayesian outcome model (rung L5) in PyMC. PyMC is in the `ml` extra (not installed in CI), so this
module is imported lazily and type-checked in basic mode.

logit P(blue wins) = a + b_elo * z_elo + sum_j b_j * z_j                (draft features, shared scale s_b)
                   + sum_c theta_c * (+1 blue pick / -1 red pick)        (champion effects, partially pooled)
                   + u_blue - u_red                                      (team effects beyond Elo, partially pooled)

Every scale has a half-normal prior, so the data decides how much each block is shrunk toward zero; random effects
use the non-centred form. Fitted with ADVI (variational) for speed; predictions average 400 posterior draws.
Unseen champions/teams at prediction time get effect 0 (the population mean).
"""

import numpy as np
import polars as pl

from fele.models.outcome import L2, Model, champion_onehot, matrix

ADVI_STEPS = 15_000
DRAWS = 400


class BayesHierarchical(Model):
    def __init__(self) -> None:
        self.mean = self.std = np.zeros(0)
        self.vocab: list[str] = []
        self.teams: list[str] = []
        self.a = self.b_elo = np.zeros(DRAWS)
        self.b = self.theta = self.u = np.zeros((DRAWS, 0))
        self.scales: dict[str, float] = {}

    def fit(self, train: pl.DataFrame) -> None:
        import pymc as pm  # noqa: PLC0415 - heavy, optional

        x = matrix(train, L2)
        self.mean, self.std = x.mean(axis=0), x.std(axis=0) + 1e-9
        z = (x - self.mean) / self.std
        self.vocab = sorted({c for col in ("blue_champs", "red_champs") for cs in train[col].to_list() for c in cs})
        champs = champion_onehot(train, self.vocab)
        self.teams = sorted(set(train["blue_team_id"].to_list()) | set(train["red_team_id"].to_list()))
        t_index = {t: i for i, t in enumerate(self.teams)}
        blue = np.array([t_index[t] for t in train["blue_team_id"].to_list()])
        red = np.array([t_index[t] for t in train["red_team_id"].to_list()])
        with pm.Model():
            a = pm.Normal("a", 0, 1)
            b_elo = pm.Normal("b_elo", 0, 1)
            s_b = pm.HalfNormal("s_b", 0.3)
            b = pm.Normal("b_raw", 0, 1, shape=z.shape[1] - 1) * s_b
            s_theta = pm.HalfNormal("s_theta", 0.2)
            theta = pm.Normal("theta_raw", 0, 1, shape=len(self.vocab)) * s_theta
            s_u = pm.HalfNormal("s_u", 0.3)
            u = pm.Normal("u_raw", 0, 1, shape=len(self.teams)) * s_u
            eta = a + b_elo * z[:, 0] + pm.math.dot(z[:, 1:], b) + pm.math.dot(champs, theta) + u[blue] - u[red]
            pm.Bernoulli("y", logit_p=eta, observed=train["y"].to_numpy())
            approx = pm.fit(ADVI_STEPS, method="advi", random_seed=0, progressbar=False)
            post = approx.sample(DRAWS, random_seed=0).posterior
        flat = {k: post[k].values.reshape(DRAWS, -1) for k in ("a", "b_elo", "s_b", "s_theta", "s_u")}
        self.a, self.b_elo = flat["a"][:, 0], flat["b_elo"][:, 0]
        self.b = post["b_raw"].values.reshape(DRAWS, -1) * flat["s_b"]
        self.theta = post["theta_raw"].values.reshape(DRAWS, -1) * flat["s_theta"]
        self.u = post["u_raw"].values.reshape(DRAWS, -1) * flat["s_u"]
        self.scales = {k: float(flat[k].mean()) for k in ("s_b", "s_theta", "s_u")}

    def predict(self, rows: pl.DataFrame) -> np.ndarray:
        z = (matrix(rows, L2) - self.mean) / self.std
        champs = champion_onehot(rows, self.vocab)
        t_index = {t: i for i, t in enumerate(self.teams)}
        u = np.hstack([self.u, np.zeros((DRAWS, 1))])  # last column = unseen team
        blue = np.array([t_index.get(t, len(self.teams)) for t in rows["blue_team_id"].to_list()])
        red = np.array([t_index.get(t, len(self.teams)) for t in rows["red_team_id"].to_list()])
        eta = (
            self.a[:, None]
            + self.b_elo[:, None] * z[:, 0][None]
            + self.b @ z[:, 1:].T
            + self.theta @ champs.T
            + u[:, blue]
            - u[:, red]
        )
        return (1 / (1 + np.exp(-eta))).mean(axis=0)
