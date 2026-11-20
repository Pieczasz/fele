"""Draft-action ladder (problem B): P(next pick/ban = champion c | draft state), over available champions only.

Candidate features (all time-respecting, from fele.features.state): pick/ban presence, shrunk win rate, this
team's pick/ban habits, own/opponent player comfort, patch delta, synergy with own / opponent picks so far, and
whether the champion fills a role this team (or the opponent) still needs. Weights differ for picks and bans, with an
extra interaction for phase-2 bans (targeted bans).

Anti-overfitting: L2 strength / softmax temperature are fitted on walk-forward inner folds of the training actions;
training uses the most recent MAX_TRAIN actions (recent drafts describe the current game best, and it bounds memory).
"""

from collections.abc import Callable, Iterable

import numpy as np
import numpy.typing as npt
import polars as pl
from scipy import optimize

from fele.eval.splits import inner_masks
from fele.features.state import UNTAGGED, ActionData
from fele.models.sk import Ranker

type Floats = npt.NDArray[np.float64]
type F32 = npt.NDArray[np.float32]

MAX_TRAIN = 8000
LAMBDA_GRID = (1.0, 10.0, 100.0)
TEMPERATURES = np.linspace(0.3, 3.0, 28)
EPS = 1e-3
BASE_NAMES = (
    "log_pick_presence", "log_ban_presence", "champ_wr", "log_team_pick", "log_team_ban", "own_pool", "opp_pool",
    "delta", "synergy", "opp_synergy", "role_fit", "opp_role_fit",
)  # fmt: skip
FEATURE_NAMES = (
    *(f"pick:{n}" for n in BASE_NAMES),
    *(f"ban:{n}" for n in BASE_NAMES),
    "ban2:opp_pool",
    "ban2:opp_role_fit",
)


def role_assignment(picks: Iterable[int], role_rank: npt.NDArray[np.int8]) -> list[int]:
    """Role index per pick, in pick order: its highest-ranked tagged role still free, else any free role."""
    free = np.ones(role_rank.shape[1], bool)
    out: list[int] = []
    for c in picks:
        if c < 0:
            break
        k = int(np.argmin(np.where(free, role_rank[c], np.iinfo(np.int8).max)))
        free[k] = False
        out.append(k)
    return out


def open_roles(picks: npt.NDArray[np.int32], role_rank: npt.NDArray[np.int8]) -> npt.NDArray[np.bool_]:
    """Roles still free after `role_assignment` of each row's earlier picks. (actions, 5)."""
    free = np.ones((len(picks), role_rank.shape[1]), bool)
    for r, row in enumerate(picks):
        free[r, role_assignment(row, role_rank)] = False
    return free


def features(rows: pl.DataFrame, act: ActionData) -> F32:
    """(actions, V, len(FEATURE_NAMES)) candidate features for the given action rows."""
    idx = rows["idx"].to_numpy()
    base = act.team_x[rows["gt"].to_numpy()]  # (n, V, 8)
    tagged = (act.role_rank < UNTAGGED).astype(np.float32)
    own_open = open_roles(act.own_picks[idx], act.role_rank)
    opp_open = open_roles(act.opp_picks[idx], act.role_rank)
    fit_own = (tagged[None] * own_open[:, None, :]).max(axis=2)
    fit_opp = (tagged[None] * opp_open[:, None, :]).max(axis=2)
    x = np.stack(
        [
            np.log(base[..., 0] + EPS),
            np.log(base[..., 1] + EPS),
            (base[..., 2] - 0.5) * 10,
            np.log(base[..., 3] + EPS),
            np.log(base[..., 4] + EPS),
            base[..., 5],
            base[..., 6],
            base[..., 7],
            act.synergy[idx],
            act.opp_synergy[idx],
            fit_own,
            fit_opp,
        ],
        axis=2,
    ).astype(np.float32)
    is_pick = (rows["action"] == "pick").to_numpy()[:, None, None]
    ban2 = (rows["phase"] == "ban2").to_numpy()[:, None, None].astype(np.float32)
    return np.concatenate([x * is_pick, x * ~is_pick, ban2 * x[..., 6:7], ban2 * x[..., 11:12]], axis=2)


def _recent(train: pl.DataFrame) -> pl.DataFrame:
    return train.sort("started_at", "idx").tail(MAX_TRAIN)


def _softmax_logits(logits: Floats, mask: npt.NDArray[np.bool_]) -> Floats:
    z = np.where(mask, -np.inf, logits)
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


class ConditionalLogit:
    """Multinomial (conditional) logit over the available champions: P(c) ∝ exp(w · x_c), L2 on w."""

    def __init__(self, lam: float | None = None) -> None:
        self.lam = lam
        self.w: Floats = np.zeros(len(FEATURE_NAMES))
        self.act: ActionData | None = None
        self.lam_used = lam

    @staticmethod
    def _fit_w(x: F32, y: npt.NDArray[np.int64], mask: npt.NDArray[np.bool_], lam: float) -> Floats:
        rows = np.arange(len(y))
        x_true = x[rows, y].astype(np.float64)

        def loss(w: Floats) -> tuple[float, Floats]:
            logits = np.where(mask, -np.inf, x @ w.astype(np.float32)).astype(np.float64)
            top = logits.max(axis=1, keepdims=True)
            e = np.exp(logits - top)
            z = e.sum(axis=1, keepdims=True)
            p = e / z
            ll = (np.log(z[:, 0]) + top[:, 0] - logits[rows, y]).sum()
            grad = np.einsum("nv,nvf->f", p, x, optimize=True) - x_true.sum(axis=0)
            return float(ll + 0.5 * lam * w @ w), grad + lam * w

        res = optimize.minimize(loss, np.zeros(x.shape[2]), jac=True, method="L-BFGS-B")
        return np.asarray(res.x, dtype=float)

    @staticmethod
    def _data(rows: pl.DataFrame, act: ActionData) -> tuple[F32, npt.NDArray[np.int64], npt.NDArray[np.bool_]]:
        return features(rows, act), rows["y"].to_numpy().astype(np.int64), act.unavailable[rows["idx"].to_numpy()]

    def fit(self, train: pl.DataFrame, act: ActionData) -> None:
        self.act = act
        train = _recent(train)
        lam = self.lam
        if lam is None:
            losses = dict.fromkeys(LAMBDA_GRID, 0.0)
            for tr, va in inner_masks(train):
                xt, yt, mt = self._data(train.filter(tr), act)
                xv, yv, mv = self._data(train.filter(va), act)
                for cand in LAMBDA_GRID:
                    w = self._fit_w(xt, yt, mt, cand)
                    p = _softmax_logits((xv @ w.astype(np.float32)).astype(np.float64), mv)
                    losses[cand] += float(-np.log(p[np.arange(len(yv)), yv] + 1e-12).mean())
            lam = min(losses, key=lambda k: losses[k])
        self.lam_used = lam
        x, y, m = self._data(train, act)
        self.w = self._fit_w(x, y, m, lam)

    def scores(self, rows: pl.DataFrame) -> Floats:
        if self.act is None:
            raise RuntimeError("fit() first")
        return self.scores_for(rows, self.act)

    def scores_for(self, rows: pl.DataFrame, act: ActionData) -> Floats:
        """Probabilities for actions described by any ActionData (e.g. a live draft), with the fitted weights."""
        x = features(rows, act)
        return _softmax_logits(
            (x @ self.w.astype(np.float32)).astype(np.float64), act.unavailable[rows["idx"].to_numpy()]
        )


class LambdaRank:
    """LightGBM LambdaRank over (action, available candidate) pairs; softmax temperature fitted on an inner fold."""

    def __init__(self, n_estimators: int = 300) -> None:
        self.n_estimators = n_estimators
        self.act: ActionData | None = None
        self.temperature = 1.0
        self.model = self._model()

    @staticmethod
    def _flat(
        rows: pl.DataFrame, act: ActionData
    ) -> tuple[F32, npt.NDArray[np.int32], npt.NDArray[np.int64], npt.NDArray[np.bool_]]:
        x = features(rows, act)
        avail = ~act.unavailable[rows["idx"].to_numpy()]
        label = np.zeros(avail.shape, np.int32)
        label[np.arange(len(rows)), rows["y"].to_numpy()] = 1
        return x[avail], label[avail], avail.sum(axis=1).astype(np.int64), avail

    def _model(self) -> Ranker:
        return Ranker(
            objective="lambdarank",
            n_estimators=self.n_estimators,
            learning_rate=0.05,
            num_leaves=15,
            min_child_samples=200,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.8,
            reg_lambda=5.0,
            lambdarank_truncation_level=20,
        )

    @staticmethod
    def _scores(model: Ranker, rows: pl.DataFrame, act: ActionData) -> Floats:
        x = features(rows, act)
        return model.predict(x.reshape(-1, x.shape[2])).reshape(x.shape[:2])

    def fit(self, train: pl.DataFrame, act: ActionData) -> None:
        self.act = act
        train = _recent(train)
        tr, va = inner_masks(train)[-1]
        inner = self._model()
        xi, li, gi, _ = self._flat(train.filter(tr), act)
        inner.fit(xi, li, group=gi)
        valid = train.filter(va)
        s = self._scores(inner, valid, act)
        mask, y = act.unavailable[valid["idx"].to_numpy()], valid["y"].to_numpy()
        losses = [
            float(-np.log(_softmax_logits(s / t, mask)[np.arange(len(y)), y] + 1e-12).mean()) for t in TEMPERATURES
        ]
        self.temperature = float(TEMPERATURES[int(np.argmin(losses))])
        self.model = self._model()
        x, label, groups, _ = self._flat(train, act)
        self.model.fit(x, label, group=groups)

    def scores(self, rows: pl.DataFrame) -> Floats:
        if self.act is None:
            raise RuntimeError("fit() first")
        return self.scores_for(rows, self.act)

    def scores_for(self, rows: pl.DataFrame, act: ActionData) -> Floats:
        """Probabilities for actions described by any ActionData (e.g. a live draft or a simulated one)."""
        s = self._scores(self.model, rows, act)
        return _softmax_logits(s / self.temperature, act.unavailable[rows["idx"].to_numpy()])


ACTION_LADDER: dict[str, Callable[[], ConditionalLogit | LambdaRank]] = {
    "action_clogit": ConditionalLogit,
    "action_lambdarank": LambdaRank,
}
