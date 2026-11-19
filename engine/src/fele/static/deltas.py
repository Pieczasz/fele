"""Patch deltas: per champion per patch, how its Data Dragon numbers changed since the previous patch.

Derived from numbers only (patch-note text is copyrighted). Data Dragon keeps base stats and spell
cooldowns/costs/ranges up to date, but not spell damage values (their `effect` arrays are mostly zeros),
so damage-only changes are invisible here.

Score = sum of signed relative changes (positive = buff):
- base stats compared at level 9 (base + 8 x per-level growth), so a per-level change counts by its real size;
- each Q/W/E/R cooldown, cost and range: mean relative change over the ranks (lower cooldown/cost = buff);
  cost and range count half as much as cooldowns.
A raw stat field that changes for more than half of all champions in one patch is a game-wide change
(e.g. 16.5.1 set `attackdamageperlevel` to 0 for everyone); it is reported in `systemic` and left out of the score.
"""

from itertools import pairwise
from typing import Any

from fele.jsontypes import JsonObj

LEVEL = 9
GROWING = ("hp", "mp", "armor", "spellblock", "attackdamage", "hpregen", "mpregen")
FLAT = ("movespeed", "attackrange")
SPELL_FIELDS = {"cooldown": -1.0, "cost": -0.5, "range": 0.5}  # sign = direction (+ = higher is better), size = weight
SPELL_KEYS = "QWER"
SYSTEMIC_SHARE = 0.5
CAP = 0.5  # one component can't move the score by more than ±50 % (also tames data quirks such as 0 → 22 s)

type Row = dict[str, Any]


def is_champion(key: str) -> bool:
    """False for mode variants such as `Jade_Ahri` (16.15.1)."""
    return "_" not in key


def level_stats(stats: dict[str, float]) -> dict[str, float]:
    out = {s: stats.get(s, 0) + stats.get(f"{s}perlevel", 0) * (LEVEL - 1) for s in GROWING}
    out |= {s: stats.get(s, 0) for s in FLAT}
    out["attackspeed"] = stats.get("attackspeed", 0) * (1 + stats.get("attackspeedperlevel", 0) / 100 * (LEVEL - 1))
    return out


def _rel(old: float, new: float) -> float:
    return max(-CAP, min(CAP, (new - old) / max(abs(old), 1)))


def systemic_fields(prev: dict[str, JsonObj], cur: dict[str, JsonObj]) -> set[str]:
    both = [k for k in cur if k in prev and is_champion(k)]
    changed: dict[str, int] = {}
    for k in both:
        for f, v in cur[k]["stats"].items():
            if prev[k]["stats"].get(f) != v:
                changed[f] = changed.get(f, 0) + 1
    return {f for f, n in changed.items() if n > SYSTEMIC_SHARE * len(both)}


def _fmt(values: list[float]) -> str:
    return "/".join(f"{v:g}" for v in values)


def champion_delta(prev: JsonObj, cur: JsonObj, systemic: set[str]) -> tuple[float, float, bool, list[str]]:
    """(stat_score, spell_score, rework, changes) for one champion between two versions."""
    changes: list[str] = []
    old_raw = dict(prev["stats"])
    new_raw = {f: (old_raw.get(f, v) if f in systemic else v) for f, v in cur["stats"].items()}
    changes += [f"{f} {old_raw.get(f)}→{v}" for f, v in new_raw.items() if old_raw.get(f) != v]
    old_lv, new_lv = level_stats(old_raw), level_stats(new_raw)
    stat_score = sum(_rel(old_lv[s], new_lv[s]) for s in new_lv if old_lv[s] != new_lv[s])

    spell_score, rework = 0.0, False
    for key, a, b in zip(SPELL_KEYS, prev["spells"], cur["spells"], strict=False):
        if a["id"] != b["id"] or a["maxrank"] != b["maxrank"]:
            rework = True
            changes.append(f"{key} replaced: {a['name']} → {b['name']}")
            continue
        for field, sign in SPELL_FIELDS.items():
            old, new = a[field], b[field]
            if old == new or len(old) != len(new):
                continue
            spell_score += sign * sum(_rel(o, n) for o, n in zip(old, new, strict=True)) / len(old)
            changes.append(f"{key} {field} {_fmt(old)}→{_fmt(new)}")
    return stat_score, spell_score, rework, changes


def patch_deltas(versions: list[tuple[str, dict[str, JsonObj]]]) -> list[Row]:
    """One row per champion per patch transition. `versions` = [(patch, championFull data)], oldest first."""
    rows: list[Row] = []
    for (prev_patch, prev), (patch, cur) in pairwise(versions):
        systemic = systemic_fields(prev, cur)
        for key, champ in cur.items():
            if not is_champion(key):
                continue
            row: Row = {"champion": key, "patch": patch, "prev_patch": prev_patch, "systemic": sorted(systemic)}
            if key not in prev:
                rows.append(row | {"new": True, "stat_score": 0.0, "spell_score": 0.0, "rework": False, "changes": []})
                continue
            stat, spell, rework, changes = champion_delta(prev[key], champ, systemic)
            rows.append(
                row | {"new": False, "stat_score": stat, "spell_score": spell, "rework": rework, "changes": changes}
            )
    for r in rows:
        score = r["stat_score"] + r["spell_score"]
        r |= {"score": score, "magnitude": abs(score), "buffed": score > 0, "nerfed": score < 0}
        r["n_changes"] = len(r["changes"])
    return rows
