"""Local DuckDB catalog (data_local/fele.duckdb) for querying everything from PyCharm/DataGrip.

Only views are created: they point at the GRID clone and the Parquet files in data_local/, so the
.duckdb file stays tiny and holds no data of its own. It is gitignored anyway.
"""

from pathlib import Path

import duckdb

from fele.config import settings

GRID_META = ("games", "rosters", "players", "teams", "tournaments", "characters")


def db_path() -> Path:
    return settings().local() / "fele.duckdb"


def _sql_path(p: Path) -> str:
    return str(p).replace("'", "''")


def _csv(p: Path) -> str:
    return f"SELECT * FROM read_csv_auto('{_sql_path(p)}', all_varchar=true)"


def build_catalog() -> dict[str, list[str]]:
    """(Re)create schemas grid / leaguepedia / soloq with views over local files. Returns created views."""
    s = settings()
    views: dict[str, str] = {}
    if s.meta_dir.exists():
        for t in GRID_META:  # meta tables hold both titles; keep LoL only
            views[f"grid.{t}"] = f"{_csv(s.meta_dir / f'{t}.csv')} WHERE title = 'lol'"
        views["grid.series"] = _csv(s.lol_dir / "series.csv")
    lp = s.local("external", "leaguepedia_hf")
    for f in sorted(lp.glob("*.parquet")):
        views[f"leaguepedia.{f.stem}"] = f"SELECT * FROM read_parquet('{_sql_path(f)}')"
    soloq = s.local("soloq")
    if any(soloq.glob("*/*.parquet")):
        views["soloq.participants"] = (
            f"SELECT * FROM read_parquet('{_sql_path(soloq)}/*/*.parquet', union_by_name=true)"
        )
    agg = s.local("aggregates")
    for f in sorted(agg.glob("*.parquet")):
        views[f"aggregates.{f.stem}"] = f"SELECT * FROM read_parquet('{_sql_path(f)}')"

    created: dict[str, list[str]] = {}
    with duckdb.connect(db_path()) as con:
        for name, sql in views.items():
            schema, view = name.split(".")
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            con.execute(f"CREATE OR REPLACE VIEW {schema}.{view} AS {sql}")
            created.setdefault(schema, []).append(view)
    return created
