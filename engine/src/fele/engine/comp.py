"""Composition analyzer: what a team's picks bring (from the reviewed champion tags) and each pick's share of the
outcome model's win probability (leave-one-out). Tags are 0-3 (3 = a defining strength) except ap_share (0-1) and
hard_cc (count of hard-CC abilities)."""

from dataclasses import dataclass, field

import numpy as np

from fele.engine.recommend import Matchup, win_prob
from fele.features import state

SCALING = {0.0: "early", 1.0: "mid", 2.0: "late"}


@dataclass
class Comp:
    champions: list[str]
    ap_share: float
    damage: str
    totals: dict[str, float]
    scaling: str
    warnings: list[str] = field(default_factory=list[str])
    contribution: dict[str, float] = field(default_factory=dict[str, float])  # pick -> win prob it adds (pp)


def analyze(m: Matchup, ours: list[str], theirs: list[str]) -> Comp:
    tags = [m.live.tags[c] for c in ours if c in m.live.tags]
    if not tags:
        return Comp(ours, 0.5, "—", {}, "—")
    ap = float(np.mean([t["ap_share"] for t in tags]))
    totals = {k: float(sum(t[k] for t in tags)) for k in state.TAG_COLS if k != "ap_share"}
    scaling = SCALING[float(round(np.mean([t["scaling"] for t in tags])))]
    damage = "AP-heavy" if ap > 0.65 else "AD-heavy" if ap < 0.35 else "mixed"  # noqa: PLR2004
    warnings: list[str] = []
    full = len(tags) == 5  # noqa: PLR2004
    if full and (ap < 0.2 or ap > 0.8):  # noqa: PLR2004
        warnings.append(f"almost all {'magic' if ap > 0.5 else 'physical'} damage: easy to itemise against")  # noqa: PLR2004
    for key, label, low in (("frontline", "frontline", 3), ("engage", "engage", 3), ("waveclear", "waveclear", 5)):
        if full and totals[key] < low:
            warnings.append(f"little {label} ({totals[key]:.0f} on the 0-15 team scale)")
    base = win_prob(m, ours, theirs)
    contribution = {c: base - win_prob(m, [x for x in ours if x != c], theirs) for c in ours}
    return Comp(ours, ap, damage, totals, scaling, warnings, contribution)
