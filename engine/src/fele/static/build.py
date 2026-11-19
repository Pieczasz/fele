"""Static tables from the cached Data Dragon files (run `fele fetch-ddragon` first) → data_local/static/*.parquet.

- `champions`: latest Data Dragon champion list joined with our attribute tags (champion_tags.csv).
- `champion_map`: GRID character id/name ↔ Data Dragon key ↔ Riot numeric id.
- `patch_deltas`: per champion per patch transition (see fele.static.deltas).
"""

import json
from pathlib import Path

import polars as pl

from fele.config import settings
from fele.ingest.build import parquet_dir
from fele.ingest.grid import read_meta
from fele.jsontypes import JsonObj
from fele.static.champions import build_mapping, resolve
from fele.static.ddragon import patch_of, versions_since
from fele.static.deltas import is_champion, patch_deltas

FIRST_PATCH = "15.1"  # first patch in the GRID data
TAGS_CSV = Path(__file__).with_name("champion_tags.csv")
SCALE = ("engage", "disengage", "peel", "frontline", "poke", "dive", "splitpush", "waveclear")
ROLES = frozenset({"top", "jungle", "mid", "bot", "support"})
ENUMS = {"damage": {"AD", "AP", "mixed"}, "scaling": {"early", "mid", "late"}, "range": {"melee", "ranged", "mixed"}}
MIXED_AP = (0.35, 0.65)  # ap_share range that counts as mixed damage


def static_dir() -> Path:
    return settings().local("static")


def _full(version: str) -> dict[str, JsonObj]:
    path = settings().local("ddragon") / version / "championFull.json"
    if not path.exists():
        msg = f"{path} missing — run `fele fetch-ddragon`"
        raise FileNotFoundError(msg)
    data: dict[str, JsonObj] = json.loads(path.read_text())["data"]
    return {k: v for k, v in data.items() if is_champion(k)}


def read_tags() -> pl.DataFrame:
    return pl.read_csv(TAGS_CSV, schema_overrides={"review": pl.String})


def tag_problems(tags: pl.DataFrame, keys: set[str]) -> list[str]:
    """Human-readable problems with the tag CSV (empty list = valid)."""
    problems: list[str] = []
    listed = tags["champion"].to_list()
    problems += [f"duplicate: {k}" for k in sorted({k for k in listed if listed.count(k) > 1})]
    problems += [f"missing tags: {k}" for k in sorted(keys - set(listed))]
    problems += [f"unknown champion: {k}" for k in sorted(set(listed) - keys)]
    for r in tags.iter_rows(named=True):
        c = r["champion"]
        bad_roles = set(r["roles"].split("|")) - ROLES
        problems += [f"{c}: unknown role(s) {sorted(bad_roles)}"] if bad_roles else []
        problems += [f"{c}: {col} not in 0-3" for col in SCALE if r[col] not in range(4)]
        problems += [f"{c}: {col}={r[col]!r}" for col, ok in ENUMS.items() if r[col] not in ok]
        lo, hi = MIXED_AP
        expected = "AD" if r["ap_share"] < lo else "AP" if r["ap_share"] > hi else "mixed"
        problems += [f"{c}: damage {r['damage']} but ap_share {r['ap_share']}"] if r["damage"] != expected else []
    return problems


def role_gaps(min_games: int = 5, min_share: float = 0.2) -> pl.DataFrame:
    """Champion roles seen in pro play (GRID, inferred roles) that champion_tags.csv doesn't list. Needs ingest."""
    parts = pl.read_parquet(parquet_dir() / "participants.parquet", columns=["champion", "inferred_role"])
    cmap = pl.read_parquet(static_dir() / "champion_map.parquet").select(pl.col("grid_name").alias("grid"), "champion")
    seen = (
        parts.drop_nulls()
        .group_by(pl.col("champion").alias("grid"), "inferred_role")
        .len()
        .with_columns(share=pl.col("len") / pl.col("len").sum().over("grid"))
        .filter(pl.col("len") >= min_games, pl.col("share") >= min_share)
        .join(cmap, on="grid")
        .join(read_tags().select("champion", "roles"), on="champion")
    )
    return seen.filter(~pl.col("roles").str.split("|").list.contains(pl.col("inferred_role"))).sort("champion")


def champion_map(latest: dict[str, JsonObj]) -> pl.DataFrame:
    """GRID characters.csv plus champions seen only in drafts (characters.csv omits never-picked ones, e.g. Graves)."""
    mapping = build_mapping({"data": latest})
    pairs = {(ch["character_id"], ch["name"]) for ch in read_meta("characters")}
    draft = parquet_dir() / "draft_actions.parquet"
    if draft.exists():
        pairs |= set(pl.read_parquet(draft, columns=["champion_id", "champion"]).unique().rows())
    rows: list[dict[str, object]] = []
    for grid_id, grid_name in sorted(pairs, key=lambda p: p[1]):
        hit = resolve(grid_name, mapping)
        rows.append(
            {
                "grid_character_id": grid_id,
                "grid_name": grid_name,
                "champion": hit["key"] if hit else None,
                "riot_id": hit["id"] if hit else None,
                "name": hit["name"] if hit else None,
            }
        )
    return pl.DataFrame(rows)


def build() -> dict[str, int]:
    vs: list[str] = json.loads((settings().local("ddragon") / "versions.json").read_text())
    versions = [(patch_of(v), _full(v)) for v in versions_since(FIRST_PATCH, vs)]
    latest = versions[-1][1]

    tags = read_tags()
    if problems := tag_problems(tags, set(latest)):
        msg = f"{TAGS_CSV.name}:\n  " + "\n  ".join(problems)
        raise ValueError(msg)
    first_seen = {k: p for p, data in reversed(versions) for k in data}  # oldest patch wins
    champions = pl.DataFrame(
        [
            {
                "champion": k,
                "riot_id": int(c["key"]),
                "ddragon_tags": c["tags"],
                "resource": c["partype"],
                "attack_range": c["stats"]["attackrange"],
                "first_patch": first_seen[k] if first_seen[k] != FIRST_PATCH else None,  # None = before 15.1
            }
            for k, c in latest.items()
        ]
    ).join(tags, on="champion")

    tables = {
        "champions": champions,
        "champion_map": champion_map(latest),
        "patch_deltas": pl.DataFrame(patch_deltas(versions)),
    }
    unmapped = tables["champion_map"].filter(pl.col("champion").is_null())["grid_name"].to_list()
    if unmapped:
        msg = f"GRID champions without a Data Dragon match: {unmapped}"
        raise ValueError(msg)
    counts: dict[str, int] = {}
    for name, df in tables.items():
        df.write_parquet(static_dir() / f"{name}.parquet")
        counts[name] = df.height
    return counts
