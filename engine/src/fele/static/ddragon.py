"""Data Dragon: Riot's free static data (champions, items, icons) per patch, cached locally."""

import json
from pathlib import Path
from typing import Any

import httpx

from fele.config import settings
from fele.jsontypes import JsonObj

BASE = "https://ddragon.leagueoflegends.com"


def _cache_dir() -> Path:
    return settings().local("ddragon")


def _get_json(client: httpx.Client, url: str, dest: Path, *, refresh: bool = False) -> Any:  # noqa: ANN401 - raw JSON
    if dest.exists() and not refresh:
        return json.loads(dest.read_text())
    r = client.get(url)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(r.text)
    return r.json()


def versions(client: httpx.Client, *, refresh: bool = True) -> list[str]:
    return _get_json(client, f"{BASE}/api/versions.json", _cache_dir() / "versions.json", refresh=refresh)


def version_for_patch(patch: str, all_versions: list[str]) -> str | None:
    """'15.1' -> '15.1.1' (first DDragon version of that patch)."""
    matches = [v for v in all_versions if v.startswith(f"{patch}.")]
    return matches[-1] if matches else None


def _data(client: httpx.Client, version: str, name: str) -> JsonObj:
    url = f"{BASE}/cdn/{version}/data/en_US/{name}.json"
    return _get_json(client, url, _cache_dir() / version / f"{name}.json")


def champions(client: httpx.Client, version: str, *, full: bool = False) -> JsonObj:
    return _data(client, version, "championFull" if full else "champion")


def items(client: httpx.Client, version: str) -> JsonObj:
    return _data(client, version, "item")


def summoners(client: httpx.Client, version: str) -> JsonObj:
    return _data(client, version, "summoner")


def champion_icon(client: httpx.Client, version: str, key: str) -> Path:
    dest = _cache_dir() / version / "img" / "champion" / f"{key}.png"
    if not dest.exists():
        r = client.get(f"{BASE}/cdn/{version}/img/champion/{key}.png")
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
    return dest
