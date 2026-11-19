"""Map GRID champion display names (e.g. "Wukong", "K'Sante") to Data Dragon keys/ids."""

import re
from typing import TypedDict

from fele.jsontypes import JsonObj

# GRID/display names whose Data Dragon key isn't derivable by stripping punctuation.
OVERRIDES = {
    "wukong": "MonkeyKing",
    "nunu & willump": "Nunu",
    "renata glasc": "Renata",
}


class Champion(TypedDict):
    key: str
    id: int
    name: str
    tags: list[str]


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_mapping(ddragon_champions: JsonObj) -> dict[str, Champion]:
    """normalized name -> Champion, built from champion.json."""
    out: dict[str, Champion] = {}
    data: dict[str, JsonObj] = ddragon_champions["data"]
    for key, c in data.items():
        entry = Champion(key=key, id=int(c["key"]), name=c["name"], tags=list(c["tags"]))
        out[normalize(c["name"])] = entry
        out[normalize(key)] = entry
    return out


def resolve(grid_name: str, mapping: dict[str, Champion]) -> Champion | None:
    key = OVERRIDES.get(grid_name.strip().lower())
    return mapping.get(normalize(key or grid_name))
