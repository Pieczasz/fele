import json
from pathlib import Path

import polars as pl
import pytest

from fele import prefs
from fele.external.soloq import champion_patch_table
from fele.ingest.grid import read_meta, series_index, series_path
from fele.static.ddragon import versions_since


def test_versions_since() -> None:
    versions = ["16.23.1", "16.1.1", "15.10.1", "15.2.1", "15.1.1", "14.24.1", "lolpatch_7.20"]
    assert versions_since("15.1", versions) == ["15.1.1", "15.2.1", "15.10.1", "16.1.1", "16.23.1"]


def test_meta_readers_filter_by_title(tmp_settings: Path) -> None:
    grid = tmp_settings / "grid"
    (grid / "meta").mkdir(parents=True)
    (grid / "lol").mkdir()
    (grid / "meta" / "teams.csv").write_text("title,team_id,name\nlol,1,A\nval,1,B\n")
    (grid / "lol" / "series.csv").write_text("series_id,event\n7,LCS\n")
    assert [r["name"] for r in read_meta("teams")] == ["A"]
    assert series_index() == [{"series_id": "7", "event": "LCS"}]
    assert series_path("7").name == "events_7_grid.jsonl.zst"


def test_champion_patch_table(tmp_settings: Path) -> None:
    out = tmp_settings / "data_local" / "soloq" / "kr"
    out.mkdir(parents=True)
    rows = [
        {"match_id": "m1", "platform": "kr", "patch": "16.23", "team_id": 100, "win": True, "champion_id": 1,
         "champion": "Annie", "position": "MIDDLE", "team_bans": [2], "duration_s": 1800},
        {"match_id": "m1", "platform": "kr", "patch": "16.23", "team_id": 200, "win": False, "champion_id": 2,
         "champion": "Olaf", "position": "JUNGLE", "team_bans": [1], "duration_s": 1800},
        {"match_id": "m2", "platform": "kr", "patch": "16.23", "team_id": 100, "win": False, "champion_id": 1,
         "champion": "Annie", "position": "MIDDLE", "team_bans": [], "duration_s": 1200},
    ]  # fmt: skip
    pl.DataFrame(rows).write_parquet(out / "batch_1.parquet")
    table = champion_patch_table()
    annie = table.filter(pl.col("champion") == "Annie").row(0, named=True)
    assert (annie["games"], annie["wins"], annie["matches"], annie["bans"]) == (2, 1, 2, 1)
    assert (annie["win_rate"], annie["avg_duration_s"]) == (0.5, 1500)


@pytest.mark.usefixtures("tmp_settings")
def test_champion_patch_table_empty() -> None:
    assert champion_patch_table().is_empty()


def test_prefs_fallback_to_example(tmp_path: Path) -> None:
    loaded = prefs.load(tmp_path / "missing.yaml")
    assert loaded.team
    assert json.loads(loaded.model_dump_json())["players"]
