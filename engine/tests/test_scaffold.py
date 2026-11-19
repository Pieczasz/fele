import json
from compression import zstd

import httpx

from fele import prefs
from fele.api.app import app
from fele.config import REPO_ROOT
from fele.external.riot import parse_limits
from fele.external.soloq import participant_rows
from fele.ingest.grid import read_envelopes
from fele.static.champions import build_mapping, resolve

DDRAGON = {
    "data": {
        "MonkeyKing": {"key": "62", "name": "Wukong", "tags": ["Fighter"]},
        "KSante": {"key": "897", "name": "K'Sante", "tags": ["Tank"]},
        "Nunu": {"key": "20", "name": "Nunu & Willump", "tags": ["Tank"]},
    }
}


async def test_health_and_preferences():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/health")).json()["status"] == "ok"
        assert (await client.get("/preferences")).json()["team"]


def test_example_preferences_validate():
    p = prefs.load(REPO_ROOT / "config" / "preferences.example.yaml")
    assert {pl.role for pl in p.players} == set(prefs.Role)


def test_champion_mapping():
    m = build_mapping(DDRAGON)
    assert resolve("Wukong", m)["key"] == "MonkeyKing"
    assert resolve("K'Sante", m)["id"] == 897
    assert resolve("Nunu & Willump", m)["key"] == "Nunu"
    assert resolve("Not A Champ", m) is None


def test_parse_limits():
    assert parse_limits("100:120,20:1") == [(100, 120.0), (20, 1.0)]
    assert parse_limits(None) is None


def test_stream_synthetic_feed(tmp_path):
    # synthetic feed written at test time; real GRID files never live in the repo
    path = tmp_path / "events_1_grid.jsonl.zst"
    envs = [
        {"sequenceNumber": i, "events": [{"type": "x-y-z", "seriesState": {"n": i} if i else None}]} for i in range(3)
    ]
    with zstd.open(path, "wt", encoding="utf-8") as f:
        f.writelines(json.dumps(e) + "\n" for e in envs)
    assert [e["sequenceNumber"] for e in read_envelopes(path)] == [0, 1, 2]


def test_participant_rows():
    m = {
        "metadata": {"matchId": "KR_1"},
        "info": {
            "gameVersion": "16.23.712.1234",
            "gameStartTimestamp": 1,
            "gameDuration": 1800,
            "queueId": 420,
            "teams": [{"teamId": 100, "bans": [{"championId": 62}]}, {"teamId": 200, "bans": []}],
            "participants": [
                {"teamId": 100, "win": True, "championId": 897, "championName": "KSante", "teamPosition": "TOP"}
            ],
        },
    }
    (row,) = participant_rows(m, "kr")
    assert row["patch"] == "16.23"
    assert row["team_bans"] == [62]
    assert row["position"] == "TOP"
