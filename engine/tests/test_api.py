"""API on small synthetic aggregates: shapes, evidence fields, 404/503 paths and the demo password gate."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import polars as pl
import pytest

from fele.api import data
from fele.api.app import app

T0 = datetime(2026, 9, 1, tzinfo=UTC)
TEAM = "t1"


def _write(root: Path, folder: str, name: str, rows: list[dict[str, object]]) -> None:
    out = root / "data_local" / folder
    out.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).write_parquet(out / f"{name}.parquet")


def _rate(k: int, n: int, prefix: str = "") -> dict[str, object]:
    r = k / n
    return {f"{prefix}rate": r, f"{prefix}lo": max(0.0, r - 0.2), f"{prefix}hi": min(1.0, r + 0.2)}


@pytest.fixture
def aggregates(tmp_settings: Path) -> Path:
    team = {"team_id": TEAM, "name": "Team One", "league": "LCS", "games": 10, "wins": 6, "series": 4}
    _write(tmp_settings, "aggregates", "stats_teams", [team | {"first_game": T0, "last_game": T0}])
    draft = {
        "team_id": TEAM,
        "league": "LCS",
        "champion": "Wukong",
        "picks": 2,
        "bans": 1,
        "k": 3,
        "n": 10,
        "first_rotation": 2,
        "avg_slot": 5.0,
        "base_rate": 0.1,
        "split_type": "all",
        "split": "all",
        "p": 0.04,
        "q": 0.2,
        "tendency": "weak",
        "period": "recent",
    }
    _write(
        tmp_settings,
        "aggregates",
        "stats_team_draft",
        [draft | _rate(3, 10) | _rate(2, 10, "first_rotation_")],
    )
    target = {"team_id": TEAM, "target_player_id": "p1", "target_player": "Mid", "target_role": "mid", "k": 2, "n": 5}
    champions = [{"champion": "Wukong", "count": 2}]
    _write(
        tmp_settings,
        "aggregates",
        "stats_ban_targets",
        [target | _rate(2, 5) | {"champions": champions, "period": "recent"}],
    )
    mr = {"team_id": TEAM, "league": "LCS", "metric": "got_first_blood", "k": 6, "n": 10, "base_rate": 0.5}
    _write(
        tmp_settings,
        "aggregates",
        "stats_macro_rates",
        [mr | _rate(6, 10) | {"split": "all", "p": 0.7, "q": 0.9, "tendency": "noise", "period": "recent"}],
    )
    timing = {"team_id": TEAM, "metric": "drake_s", "n": 9, "median_s": 400.0, "q25_s": 360.0, "q75_s": 450.0}
    _write(tmp_settings, "aggregates", "stats_macro_timings", [timing | {"period": "recent"}])
    cell = {"team_id": TEAM, "side": "blue", "kind": "kill", "cx": 5, "cy": 6, "count": 3, "n": 5, "period": "recent"}
    _write(tmp_settings, "aggregates", "stats_early_kills", [cell])
    player = {
        "player_id": "p1",
        "role": "mid",
        "n": 40,
        "unique_champions": 9,
        "effective_pool": 6.5,
        "effective_pool_lo": 5.0,
        "effective_pool_hi": 8.0,
        "depth": 5,
        "meta_k": 3,
        "meta_n": 10,
        "player_name": "Mid",
        "team_id": TEAM,
    }
    _write(tmp_settings, "aggregates", "stats_players", [player | _rate(3, 10, "meta_overlap_")])
    pc = {
        "player_id": "p1",
        "champion": "Wukong",
        "n": 12,
        "k": 8,
        "last_played": T0,
        "recent_games": 4.2,
        "role": "mid",
        "shrunk": 0.6,
        "shrunk_lo": 0.4,
        "shrunk_hi": 0.75,
        "prior_a": 10.0,
        "prior_b": 10.0,
        "comfort": 5.0,
    }
    _write(tmp_settings, "aggregates", "stats_player_champions", [pc | _rate(8, 12)])
    meta_row = {
        "window": "live",
        "grid": "Wukong",
        "champion": "MonkeyKing",
        "name": "Wukong",
        "k": 4,
        "picks": 3,
        "bans": 1,
        "games": 10,
        "presence": 0.4,
        "presence_lo": 0.2,
        "presence_hi": 0.6,
        "pro_n": 3,
        "pro_wins": 2,
        "pro_wr": 0.52,
        "pro_wr_lo": 0.4,
        "pro_wr_hi": 0.6,
        "soloq_n": 100,
        "soloq_wr": 0.51,
        "soloq_wr_lo": 0.45,
        "soloq_wr_hi": 0.57,
        "delta": 0.02,
        "meta_score": 1.2,
    }
    _write(tmp_settings, "aggregates", "stats_meta", [meta_row])
    _write(tmp_settings, "aggregates", "stats_windows", [{"window": "live", "patch": "16.17"}])
    tgm = {"game_id": "g1", "team_id": TEAM, "league": "LCS", "started_at": T0}
    _write(tmp_settings, "aggregates", "stats_team_game_macro", [tgm])
    _write(tmp_settings, "static", "champion_map", [{"grid_name": "Wukong", "champion": "MonkeyKing"}])
    _write(tmp_settings, "static", "champions", [{"champion": "MonkeyKing", "roles": "jungle|top"}])
    return tmp_settings


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    data.clear_cache()  # each test has its own temp data dir
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.usefixtures("aggregates")
async def test_scouting_report_carries_evidence(client: httpx.AsyncClient):
    teams = (await client.get("/teams")).json()
    assert [t["name"] for t in teams] == ["Team One"]
    s = (await client.get(f"/teams/{TEAM}/scouting")).json()
    row = s["draft"][0]
    assert (row["champion"], row["key"], row["k"], row["n"], row["tendency"]) == ("Wukong", "MonkeyKing", 3, 10, "weak")
    assert row["first_rotation"] == {"k": 2, "n": 10, "rate": 0.2, "lo": 0.0, "hi": pytest.approx(0.4)}
    assert s["games"] == 10
    target = s["targeted_players"][0]
    assert (target["player"], target["k"], target["n"], target["champions"][0]["key"]) == ("Mid", 2, 5, "MonkeyKing")


@pytest.mark.usefixtures("aggregates")
async def test_macro_players_meta_coverage(client: httpx.AsyncClient):
    m = (await client.get(f"/teams/{TEAM}/macro")).json()
    assert (m["games"], m["games_by_side"], m["timings"][0]["median_s"]) == (10, {"blue": 5}, 400.0)
    p = (await client.get(f"/teams/{TEAM}/players")).json()["players"][0]
    assert (p["name"], p["meta_overlap"]["k"], p["champions"][0]["key"], p["current"]) == ("Mid", 3, "MonkeyKing", True)
    meta = (await client.get("/meta")).json()
    assert (meta["patches"], meta["rows"][0]["roles"], meta["rows"][0]["presence"]["n"]) == (
        ["16.17"],
        ["jungle", "top"],
        10,
    )
    cov = (await client.get("/coverage")).json()
    assert cov["leagues"][0] | {"first_game": None, "last_game": None} == {
        "league": "LCS",
        "teams": 1,
        "games": 1,
        "first_game": None,
        "last_game": None,
    }
    assert cov["soloq"] == []  # no solo-queue aggregate built: empty, not an error


@pytest.mark.usefixtures("aggregates")
async def test_unknown_team_and_window_are_404(client: httpx.AsyncClient):
    assert (await client.get("/teams/nope/scouting")).status_code == 404
    assert (await client.get("/meta", params={"window": "1.1"})).status_code == 404


@pytest.mark.usefixtures("tmp_settings")
async def test_missing_aggregates_are_503_with_a_hint(client: httpx.AsyncClient):
    r = await client.get("/teams")
    assert r.status_code == 503
    assert "make data" in r.json()["detail"]


@pytest.mark.usefixtures("aggregates")
async def test_demo_password_gate(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from fele.config import settings  # noqa: PLC0415 - settings must be rebuilt after the env change

    monkeypatch.setenv("DEMO_PASSWORD", "s3cret")
    settings.cache_clear()
    monkeypatch.setattr("fele.api.auth.FAILED_LOGIN_DELAY_S", 0)
    assert (await client.get("/info")).json()["demo_protected"] is True
    assert (await client.get("/teams")).status_code == 401
    assert (await client.get("/health")).status_code == 200
    assert (await client.post("/login", json={"password": "wrong"})).status_code == 401
    ok = await client.post("/login", json={"password": "s3cret"})
    assert ok.status_code == 204
    assert "s3cret" not in ok.headers["set-cookie"]  # the cookie holds an HMAC, never the password
    assert "httponly" in ok.headers["set-cookie"].lower()
    assert (await client.get("/teams")).status_code == 200
    await client.post("/logout")
    client.cookies.clear()
    assert (await client.get("/teams")).status_code == 401


@pytest.mark.usefixtures("aggregates")
async def test_bad_cookie_is_401_not_500(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from fele.config import settings  # noqa: PLC0415

    monkeypatch.setenv("DEMO_PASSWORD", "s3cret")
    settings.cache_clear()
    # a non-ASCII cookie (latin-1 on the wire): hmac.compare_digest on str would raise TypeError -> 500
    assert (await client.get("/teams", headers={"cookie": b"fele_session=caf\xe9"})).status_code == 401


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/series/simulate", {"us": "a", "them": "b", "sims": 100_000}),  # unbounded Monte Carlo = easy DoS
        ("/series/simulate", {"us": "a", "them": "b", "best_of": 3, "wins": 2}),  # series already over
        ("/series/simulate", {"us": "a", "them": "b", "start_game": 9}),
        ("/draft/recommend", {"us": "a", "them": "b", "actions": ["x"] * 21}),
        ("/draft/recommend", {"us": "a", "them": "b", "game_number": 0}),
    ],
)
@pytest.mark.usefixtures("aggregates")
async def test_engine_requests_are_bounded(client: httpx.AsyncClient, path: str, body: dict[str, object]):
    r = await client.post(path, json=body)
    assert r.status_code == 422  # rejected by validation, before any model work
