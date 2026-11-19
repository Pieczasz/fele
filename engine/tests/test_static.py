"""Champion tags CSV, patch deltas and champion mapping (synthetic Data Dragon data; real data behind a marker)."""

import polars as pl
import pytest

from fele.ingest.build import parquet_dir
from fele.static.build import read_tags, role_gaps, static_dir, tag_problems
from fele.static.deltas import champion_delta, level_stats, patch_deltas

STATS = {"hp": 600, "hpperlevel": 100, "attackdamage": 60, "attackspeed": 0.65, "attackspeedperlevel": 2}


def _champ(stats=None, cooldown=(10, 9, 8, 7, 6), spell_id="XQ"):
    spell = {"id": spell_id, "name": spell_id, "maxrank": 5, "cooldown": list(cooldown), "cost": [50] * 5}
    return {"stats": stats or dict(STATS), "spells": [spell | {"range": [600] * 5}]}


def test_level_stats_includes_growth():
    lv = level_stats(STATS)
    assert lv["hp"] == 600 + 100 * 8
    assert lv["attackspeed"] == pytest.approx(0.65 * 1.16)


def test_champion_delta_directions():
    stat, spell, rework, changes = champion_delta(_champ(), _champ(cooldown=(9, 8, 7, 6, 5)), set())
    assert (stat, rework) == (0, False)
    assert spell > 0  # shorter cooldown = buff
    assert changes == ["Q cooldown 10/9/8/7/6→9/8/7/6/5"]
    stat, *_ = champion_delta(_champ(), _champ(stats=STATS | {"hp": 550}), set())
    assert stat == pytest.approx(-50 / 1400)
    *_, rework, changes = champion_delta(_champ(), _champ(spell_id="NewQ"), set())
    assert rework
    assert changes == ["Q replaced: XQ → NewQ"]


def test_patch_deltas_systemic_new_and_mode_variants():
    old = {k: _champ() for k in ("A", "B", "C")}
    new = {k: _champ(stats=STATS | {"attackdamage": 0}) for k in ("A", "B", "C")}
    new["B"]["stats"]["hp"] = 700
    new |= {"D": _champ(), "Jade_A": _champ()}
    rows = {r["champion"]: r for r in patch_deltas([("1.1", old), ("1.2", new)])}
    assert set(rows) == {"A", "B", "C", "D"}  # Jade_ mode variant skipped
    assert rows["A"]["systemic"] == ["attackdamage"]  # changed for everyone → not a champion change
    assert (rows["A"]["n_changes"], rows["A"]["buffed"], rows["A"]["nerfed"]) == (0, False, False)
    assert rows["B"]["buffed"]
    assert rows["B"]["changes"] == ["hp 600→700"]
    assert rows["D"]["new"]


def test_tags_csv_is_valid():
    tags = read_tags()
    assert tag_problems(tags, set(tags["champion"])) == []


def test_tag_problems_catches_bad_rows():
    row = read_tags().head(1)
    bad = row.with_columns(roles=pl.lit("top|adc"), engage=pl.lit(5, row["engage"].dtype), damage=pl.lit("AP"))
    problems = tag_problems(pl.concat([bad, row]), {"Aatrox", "Zed"})
    assert "duplicate: Aatrox" in problems
    assert "missing tags: Zed" in problems
    assert "Aatrox: unknown role(s) ['adc']" in problems
    assert "Aatrox: engage not in 0-3" in problems
    assert "Aatrox: damage AP but ap_share 0.0" in problems


@pytest.mark.real_data
def test_static_acceptance_on_real_data():
    """Phase 3 acceptance: run `uv run fele fetch-ddragon && uv run fele static` (after ingest), then `-m real_data`."""
    cmap = pl.read_parquet(static_dir() / "champion_map.parquet")
    assert cmap["champion"].null_count() == 0
    drafted = pl.read_parquet(parquet_dir() / "draft_actions.parquet")["champion_id"].unique()
    assert drafted.is_in(cmap["grid_character_id"].implode()).all()
    champions = pl.read_parquet(static_dir() / "champions.parquet")
    assert champions["champion"].is_in(read_tags()["champion"].implode()).all()
    assert role_gaps().is_empty()
    deltas = pl.read_parquet(static_dir() / "patch_deltas.parquet")
    games = pl.read_parquet(parquet_dir() / "games.parquet")["patch"].drop_nulls().unique()
    assert games.filter(games != "15.1").is_in(deltas["patch"].implode()).all()
