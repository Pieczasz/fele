"""Streaming access to the GRID LoL feeds. Never loads a whole file into memory."""

import csv
import json
from collections.abc import Iterator
from compression import zstd
from pathlib import Path

from fele.config import settings
from fele.jsontypes import JsonObj


def read_envelopes(path: Path) -> Iterator[JsonObj]:
    with zstd.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def iter_events(path: Path) -> Iterator[tuple[JsonObj, JsonObj]]:
    """Yield (envelope, event) pairs in feed order."""
    for env in read_envelopes(path):
        for ev in env["events"]:
            yield env, ev


def final_state(path: Path) -> JsonObj | None:
    """The seriesState of the last event that has one (= final box score)."""
    last: JsonObj | None = None
    for _, ev in iter_events(path):
        last = ev.get("seriesState") or last
    return last


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_meta(table: str, title: str = "lol") -> list[dict[str, str]]:
    """Rows of meta/<table>.csv for one title (lol/val)."""
    return [r for r in _read_csv(settings().meta_dir / f"{table}.csv") if r.get("title", title) == title]


def series_index() -> list[dict[str, str]]:
    return _read_csv(settings().lol_dir / "series.csv")


def series_path(series_id: str) -> Path:
    return settings().lol_dir / f"events_{series_id}_grid.jsonl.zst"
