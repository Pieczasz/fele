"""Local DuckDB catalog (data_local/fele.duckdb) for querying everything from PyCharm/DataGrip.

Only views are created: they point at the GRID clone and the Parquet files in data_local/, so the
.duckdb file stays tiny and holds no data of its own. It is gitignored anyway.
"""

from pathlib import Path

import duckdb
import polars as pl

from fele.config import settings

GRID_META = ("games", "rosters", "players", "teams", "tournaments", "characters")
PARQUET_SCHEMAS = (  # schema -> data_local/ folder of Parquet files, one view per file
    ("lol", ("parquet",)),  # `fele ingest`
    ("static", ("static",)),  # `fele static`
    ("leaguepedia", ("external", "leaguepedia_hf")),  # `fele fetch-leaguepedia-hf`
    ("aggregates", ("aggregates",)),  # `fele soloq-aggregate`, `fele stats`
)


def db_path() -> Path:
    return settings().local() / "fele.duckdb"


def write_tables(out: Path, tables: dict[str, pl.DataFrame]) -> dict[str, int]:
    """Write each frame to out/<name>.parquet and return the row counts."""
    for name, df in tables.items():
        df.write_parquet(out / f"{name}.parquet")
    return {name: df.height for name, df in tables.items()}


def _sql_path(p: Path) -> str:
    return str(p).replace("'", "''")


def _csv(p: Path) -> str:
    return f"SELECT * FROM read_csv_auto('{_sql_path(p)}', all_varchar=true)"


def build_catalog() -> dict[str, list[str]]:
    """(Re)create schemas grid / lol / static / leaguepedia / soloq / aggregates as views over local files."""
    s = settings()
    views: dict[str, str] = {}
    if s.meta_dir.exists():
        for t in GRID_META:  # meta tables hold both titles; keep LoL only
            views[f"grid.{t}"] = f"{_csv(s.meta_dir / f'{t}.csv')} WHERE title = 'lol'"
        views["grid.series"] = _csv(s.lol_dir / "series.csv")
    for schema, parts in PARQUET_SCHEMAS:
        for f in sorted(s.local(*parts).glob("*.parquet")):
            views[f"{schema}.{f.stem}"] = f"SELECT * FROM read_parquet('{_sql_path(f)}')"
    soloq = s.local("soloq")
    if any(soloq.glob("*/*.parquet")):
        views["soloq.participants"] = (
            f"SELECT * FROM read_parquet('{_sql_path(soloq)}/*/*.parquet', union_by_name=true)"
        )

    created: dict[str, list[str]] = {}
    with duckdb.connect(db_path()) as con:
        for name, sql in views.items():
            schema, view = name.split(".")
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            con.execute(f"CREATE OR REPLACE VIEW {schema}.{view} AS {sql}")
            created.setdefault(schema, []).append(view)
    return created
