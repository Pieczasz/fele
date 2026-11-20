"""Every evaluable model by name: baselines (Phase 7) + the Phase 8 ladders."""

from collections.abc import Callable

from fele.models import action, baselines, outcome
from fele.models.baselines import ActionModel, OutcomeModel

OUTCOME: dict[str, Callable[[], OutcomeModel]] = {**baselines.OUTCOME_MODELS, **outcome.OUTCOME_LADDER}
ACTION: dict[str, Callable[[], ActionModel]] = {**baselines.ACTION_MODELS, **action.ACTION_LADDER}
GROUPS = {"ladder": list(outcome.OUTCOME_LADDER), "action_ladder": list(action.ACTION_LADDER)}


def resolve(spec: str) -> list[str]:
    """'baseline_elo', 'logit_l2,lgbm' or a group name ('ladder') -> model names; unknown names raise."""
    names: list[str] = []
    for part in (p.strip() for p in spec.split(",")):
        names += GROUPS.get(part, [part])
    unknown = [n for n in names if n not in OUTCOME and n not in ACTION]
    if unknown:
        msg = f"Unknown model(s) {unknown}; choose from {sorted({*OUTCOME, *ACTION, *GROUPS})}"
        raise ValueError(msg)
    return names
