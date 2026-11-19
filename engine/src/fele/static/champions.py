"""Map GRID champion display names (e.g. "Wukong", "K'Sante") to Data Dragon keys/ids."""

import re
from typing import TypedDict

from fele.jsontypes import JsonObj


class Champion(TypedDict):
    key: str
    id: int
    name: str


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_mapping(ddragon_champions: JsonObj) -> dict[str, Champion]:
    """normalized name and normalized key -> Champion (so "Wukong" and "MonkeyKing" both resolve)."""
    out: dict[str, Champion] = {}
    data: dict[str, JsonObj] = ddragon_champions["data"]
    for key, c in data.items():
        entry = Champion(key=key, id=int(c["key"]), name=c["name"])
        out[normalize(c["name"])] = entry
        out[normalize(key)] = entry
    return out


def resolve(grid_name: str, mapping: dict[str, Champion]) -> Champion | None:
    return mapping.get(normalize(grid_name))
