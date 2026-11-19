"""Baselines (AGENT_PLAN.md §5.5, rungs L0–L1): the bar every later model has to beat.

Outcome models take outcome_frame rows and return P(blue wins). Action models return, for each draft action, a
probability over the champion vocabulary (unavailable champions get 0, the rest sum to 1).
"""

from typing import Protocol

import numpy as np
import numpy.typing as npt
import polars as pl

from fele.models.sk import Logistic
from fele.static.ddragon import patch_key

type Floats = npt.NDArray[np.float64]

GLOBAL_WINDOW = 3  # patches: global frequencies come from the latest patches in the training data
TEAM_PRIOR = 10.0  # pseudo-actions pulling a team's slot frequencies toward the global ones
PSEUDO = 0.5  # pseudo-count per champion, so a champion never seen still gets a small probability


class OutcomeModel(Protocol):
    def fit(self, train: pl.DataFrame) -> None: ...
    def predict(self, rows: pl.DataFrame) -> Floats: ...


class ActionModel(Protocol):
    def fit(self, train: pl.DataFrame, vocab: list[str]) -> None: ...
    def scores(self, rows: pl.DataFrame) -> Floats: ...  # rows x vocab, unnormalised, before availability masking


# --- outcome ----------------------------------------------------------------------------------------------------
class ConstantHalf:
    """L0: every game is a coin flip."""

    def fit(self, train: pl.DataFrame) -> None:
        pass

    @staticmethod
    def predict(rows: pl.DataFrame) -> Floats:
        return np.full(rows.height, 0.5)


class BlueSideRate:
    """L0: the blue-side win rate of the training games, for every game."""

    rate = 0.5

    def fit(self, train: pl.DataFrame) -> None:
        self.rate = float(train["y"].mean())  # pyright: ignore[reportArgumentType]

    def predict(self, rows: pl.DataFrame) -> Floats:
        return np.full(rows.height, self.rate)


class EloLogistic:
    """L1: logistic regression on the pre-game Elo difference; its intercept learns the blue-side edge."""

    def __init__(self) -> None:
        self.model = Logistic()

    @staticmethod
    def _x(rows: pl.DataFrame) -> Floats:
        return (rows["elo_diff"].to_numpy() / 400).reshape(-1, 1)

    def fit(self, train: pl.DataFrame) -> None:
        self.model.fit(self._x(train), train["y"].to_numpy())

    def predict(self, rows: pl.DataFrame) -> Floats:
        return self.model.predict(self._x(rows))


# --- actions ----------------------------------------------------------------------------------------------------
def _counts(rows: pl.DataFrame, keys: list[str], vocab: list[str]) -> dict[tuple[object, ...], Floats]:
    """Champion counts per key group, as vectors over the vocabulary."""
    index = {c: i for i, c in enumerate(vocab)}
    out: dict[tuple[object, ...], Floats] = {}
    for key, g in rows.group_by(keys):
        vec = np.zeros(len(vocab))
        for champ, n in g["champion"].value_counts().iter_rows():
            if champ in index:
                vec[index[champ]] += n
        out[tuple(key)] = vec
    return out


def recent_patches(train: pl.DataFrame) -> pl.DataFrame:
    """Training actions from the latest GLOBAL_WINDOW patches: older patches describe a different game."""
    recent = sorted(train["patch"].drop_nulls().unique().to_list(), key=patch_key)[-GLOBAL_WINDOW:]
    return train.filter(pl.col("patch").is_in(recent))


class GlobalFrequency:
    """L0: how often each champion was picked (or banned) in the latest training patches, the same for every team."""

    def __init__(self) -> None:
        self.dist: dict[object, Floats] = {}
        self.vocab: list[str] = []

    def fit(self, train: pl.DataFrame, vocab: list[str]) -> None:
        counts = _counts(recent_patches(train), ["action"], vocab)
        self.dist = {k[0]: (v + PSEUDO) / (v + PSEUDO).sum() for k, v in counts.items()}
        self.vocab = vocab

    def scores(self, rows: pl.DataFrame) -> Floats:
        uniform = np.full(len(self.vocab), 1 / len(self.vocab))
        return np.vstack([self.dist.get(a, uniform) for a in rows["action"].to_list()])


class TeamSlotFrequency:
    """L1: the team's own frequencies for this action and draft phase in the same recent patches, shrunk toward the
    global frequencies (a first version counted the team's whole history and lost to L0: stale champions)."""

    def __init__(self) -> None:
        self.base = GlobalFrequency()
        self.team: dict[tuple[object, ...], Floats] = {}

    def fit(self, train: pl.DataFrame, vocab: list[str]) -> None:
        self.base.fit(train, vocab)
        self.team = _counts(recent_patches(train), ["team_id", "action", "phase"], vocab)

    def scores(self, rows: pl.DataFrame) -> Floats:
        base = self.base.scores(rows)
        keys = rows.select("team_id", "action", "phase").rows()
        zero = np.zeros(base.shape[1])
        team = np.vstack([self.team.get(k, zero) for k in keys])
        return team + TEAM_PRIOR * base


OUTCOME_MODELS: dict[str, type[OutcomeModel]] = {
    "baseline_constant": ConstantHalf,
    "baseline_blue": BlueSideRate,
    "baseline_elo": EloLogistic,
}
ACTION_MODELS: dict[str, type[ActionModel]] = {
    "action_global": GlobalFrequency,
    "action_team_slot": TeamSlotFrequency,
}
