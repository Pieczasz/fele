"""Data Dragon: Riot's free static data (champions, items, icons) per patch, cached locally."""

import json
from pathlib import Path

import httpx

from fele.config import settings
from fele.jsontypes import JsonObj

BASE = "https://ddragon.leagueoflegends.com"


def _cache_dir() -> Path:
    return settings().local("ddragon")


def _download(client: httpx.Client, url: str, dest: Path) -> None:
    r = client.get(url)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)


def refresh_versions(client: httpx.Client) -> list[str]:
    """Download versions.json (always: it changes every patch) and return the numeric versions, newest first."""
    _download(client, f"{BASE}/api/versions.json", _cache_dir() / "versions.json")
    return cached_versions()


def cached_versions() -> list[str]:
    """Numeric versions from the cached versions.json, newest first ([] if never fetched)."""
    path = _cache_dir() / "versions.json"
    return [v for v in json.loads(path.read_text()) if v[0].isdigit()] if path.exists() else []


def fetch(client: httpx.Client, version: str, name: str) -> None:
    """Download data/en_US/<name>.json of a version unless it is cached (cache hits aren't parsed)."""
    dest = _cache_dir() / version / f"{name}.json"
    if not dest.exists():
        _download(client, f"{BASE}/cdn/{version}/data/en_US/{name}.json", dest)


def cached(version: str, name: str) -> JsonObj:
    """A cached Data Dragon file, e.g. cached("16.23.1", "championFull")."""
    path = _cache_dir() / version / f"{name}.json"
    if not path.exists():
        msg = f"{path} missing — run `fele fetch-ddragon`"
        raise FileNotFoundError(msg)
    return json.loads(path.read_text())


def patch_of(version: str) -> str:
    """'16.3.1' -> '16.3'."""
    return ".".join(version.split(".")[:2])


def live_patch() -> str | None:
    """Newest patch in the cached versions.json (refreshed by `fele fetch-ddragon`), e.g. '16.23'."""
    vs = cached_versions()
    return patch_of(vs[0]) if vs else None


def patch_key(patch: str) -> tuple[int, ...]:
    return tuple(int(x) for x in patch.split("."))


def versions_since(first_patch: str, all_versions: list[str]) -> list[str]:
    """One Data Dragon version per patch from `first_patch` on, oldest first (e.g. 15.1.1 .. 16.23.1)."""
    by_patch = {patch_of(v): v for v in all_versions}  # newest first, so the oldest version of a patch wins
    return [by_patch[p] for p in sorted(by_patch, key=patch_key) if patch_key(p) >= patch_key(first_patch)]


def fetch_champion_icon(client: httpx.Client, version: str, key: str) -> None:
    dest = _cache_dir() / version / "img" / "champion" / f"{key}.png"
    if not dest.exists():
        _download(client, f"{BASE}/cdn/{version}/img/champion/{key}.png", dest)
