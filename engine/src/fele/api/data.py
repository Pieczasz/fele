"""Read-only access to precomputed tables (data_local/aggregates and data_local/static). Never raw GRID events.

Each Parquet file is read once and cached until its modification time changes, so `fele stats` refreshes the
API without a restart and a request costs a dictionary lookup plus a filter.
"""

from functools import lru_cache
from pathlib import Path

import polars as pl

from fele.config import settings
from fele.static.ddragon import cached_versions


class MissingDataError(LookupError):
    """An aggregate the API needs hasn't been built yet."""


@lru_cache(maxsize=64)
def _read(file: tuple[Path, int]) -> pl.DataFrame:
    """(path, mtime) is the cache key, so a rebuilt file is read again."""
    return pl.read_parquet(file[0])


def clear_cache() -> None:
    _read.cache_clear()


def table(name: str, folder: str = "aggregates") -> pl.DataFrame:
    path = settings().local(folder) / f"{name}.parquet"
    if not path.exists():
        msg = f"{folder}/{name}.parquet missing — run `make data` (fele ingest, static, stats, soloq-aggregate)"
        raise MissingDataError(msg)
    return _read((path, path.stat().st_mtime_ns))


def ddragon_version() -> str | None:
    vs = cached_versions()
    return vs[0] if vs else None


def champion_keys() -> dict[str, str]:
    """GRID champion name -> Data Dragon key (for icons)."""
    cmap = table("champion_map", "static")
    return dict(zip(cmap["grid_name"].to_list(), cmap["champion"].to_list(), strict=True))
