"""Solo-queue sampler, aggregates and player pools on synthetic Riot payloads (fake ids, no real personal data)."""

import json
import re
from pathlib import Path

import httpx
import polars as pl
import pytest
import respx
import yaml

from fele.external import soloq
from fele.external.player_soloq import parse_riot_id, player_rows, pool_table
from fele.external.riot import RiotClient
from fele.prefs import Preferences

POSITIONS = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")
BLUE = ("Aatrox", "Vi", "Ahri", "Jinx", "Leona")
RED = ("Gnar", "Sejuani", "Azir", "Kaisa", "Nautilus")
DORANS, SWORD, BOOTS = 1055, 3031, 3006
ITEMS = {
    "data": {
        str(DORANS): {"gold": {"purchasable": True, "total": 450}, "maps": {"11": True}, "tags": []},
        str(SWORD): {"gold": {"purchasable": True, "total": 3400}, "maps": {"11": True}, "tags": []},
        "1038": {"gold": {"purchasable": True, "total": 1300}, "maps": {"11": True}, "into": ["3031"]},
        "2003": {"gold": {"purchasable": True, "total": 1000}, "maps": {"11": True}, "tags": ["Consumable"]},
        str(BOOTS): {"gold": {"purchasable": True, "total": 1100}, "maps": {"11": True}, "tags": ["Boots"]},
    }
}


def _match(match_id: str, version: str = "16.23.700.1", *, blue_wins: bool = True) -> dict[str, object]:
    players = [
        {
            "participantId": i + 1,
            "puuid": f"puuid-{i}",
            "teamId": 100 if i < 5 else 200,
            "win": (i < 5) == blue_wins,
            "championId": i,
            "championName": (BLUE + RED)[i],
            "teamPosition": POSITIONS[i % 5],
        }
        for i in range(10)
    ]
    teams = [{"teamId": 100, "bans": [{"championId": 99}]}, {"teamId": 200, "bans": []}]
    info = {
        "gameVersion": version,
        "gameStartTimestamp": 1_790_000_000_000,
        "gameDuration": 1800,
        "queueId": 420,
        "participants": players,
        "teams": teams,
    }
    return {"metadata": {"matchId": match_id}, "info": info}


def _event(kind: str, pid: int, **kw: int) -> dict[str, object]:
    return {"type": kind, "participantId": pid, **kw}


TIMELINE = {
    "info": {
        "frames": [
            {"events": [_event("ITEM_PURCHASED", 1, itemId=DORANS), _event("ITEM_PURCHASED", 1, itemId=BOOTS)]},
            {
                "events": [
                    _event("ITEM_PURCHASED", 1, itemId=SWORD),
                    _event("ITEM_PURCHASED", 2, itemId=SWORD),
                    _event("ITEM_UNDO", 2, beforeId=SWORD, afterId=0),
                ]
            },
        ]
    }
}


def test_completed_items_and_item_order():
    done = frozenset(soloq.completed_items(ITEMS))
    assert done == {SWORD, BOOTS}  # not starters, components or consumables
    assert soloq.item_order(TIMELINE, done) == {1: [BOOTS, SWORD], 2: []}


def test_participant_rows_and_tables():
    rows = soloq.participant_rows(_match("M1"), "kr", {1: [BOOTS, SWORD]})
    rows += soloq.participant_rows(_match("M2", blue_wins=False), "euw1")
    assert rows[0]["core_items"] == [BOOTS, SWORD]
    assert rows[1]["core_items"] == []
    assert rows[10]["core_items"] is None  # no timeline sampled
    df = pl.DataFrame(rows)
    champ = soloq.champion_patch_table(df).filter(pl.col("champion") == "Aatrox").row(0, named=True)
    assert (champ["games"], champ["wins"], champ["bans"], champ["platforms"]) == (2, 1, None, 2)
    mu = soloq.matchup_table(df).filter(pl.col("champion") == "Ahri")
    assert mu.select("opponent", "position", "games", "wins").row(0) == ("Azir", "MIDDLE", 2, 1)
    items = soloq.items_table(df)
    assert items.select("champion", "core_items", "share").row(0) == ("Aatrox", [BOOTS, SWORD], 1.0)


def test_wants_timeline_is_deterministic():
    assert not soloq.wants_timeline("KR_1", 0.0)
    assert soloq.wants_timeline("KR_1", 1.0)
    picks = [soloq.wants_timeline(f"KR_{i}", 0.25) for i in range(400)]
    assert picks == [soloq.wants_timeline(f"KR_{i}", 0.25) for i in range(400)]
    assert 60 < sum(picks) < 140


def _mock_riot(matches: dict[str, dict[str, object]]) -> dict[str, respx.Route]:
    league = "https://kr.api.riotgames.com/lol/league/v4/{}leagues/by-queue/RANKED_SOLO_5x5"
    respx.get(league.format("challenger")).mock(return_value=httpx.Response(200, json={"entries": [{"puuid": "P"}]}))
    respx.get(league.format("grandmaster")).mock(return_value=httpx.Response(200, json={"entries": []}))
    base = re.escape("https://asia.api.riotgames.com/lol/match/v5/matches/")
    ids = respx.get(url__regex=base + r"by-puuid/P/ids").mock(return_value=httpx.Response(200, json=list(matches)))

    def one(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=matches[request.url.path.rsplit("/", 1)[1]])

    detail = respx.get(url__regex=base + r"KR_\d+$").mock(side_effect=one)
    timeline = respx.get(url__regex=base + r"KR_\d+/timeline$").mock(return_value=httpx.Response(200, json=TIMELINE))
    return {"ids": ids, "match": detail, "timeline": timeline}


@respx.mock
async def test_sample_counts_patch_and_resumes_without_repeat_requests(tmp_settings: Path):
    dd = tmp_settings / "data_local" / "ddragon" / "16.23.1"
    dd.mkdir(parents=True)
    (dd / "item.json").write_text(json.dumps(ITEMS))
    soloq.completed_for_patch.cache_clear()
    routes = _mock_riot({"KR_1": _match("KR_1"), "KR_2": _match("KR_2", "16.22.1.1")})

    stats = await soloq.sample("kr", 5, patch="16.23", timeline_share=1.0)
    assert stats == {"matches": 2, "on_patch": 1, "timelines": 2, "throttled": 0}
    again = await soloq.sample("kr", 5, patch="16.23", timeline_share=1.0)
    assert again["matches"] == 0
    assert routes["match"].call_count == 2  # second run: everything already sampled
    assert routes["timeline"].call_count == 2

    rows = pl.read_parquet(next((tmp_settings / "data_local" / "soloq" / "kr").glob("*.parquet")))
    assert rows.height == 20
    assert "puuid" not in rows.columns
    assert rows.filter(pl.col("champion") == "Aatrox")["core_items"].to_list() == [[BOOTS, SWORD]] * 2


def test_parse_riot_id():
    assert parse_riot_id("Some Name#NA1@na1") == ("Some Name", "NA1", "na1")
    with pytest.raises(ValueError, match="GameName#TAG@platform"):
        parse_riot_id("NoTag@na1")
    with pytest.raises(ValueError, match="GameName#TAG@platform"):
        parse_riot_id("Name#TAG@mars")


@respx.mock
@pytest.mark.usefixtures("tmp_settings")
async def test_player_rows_keep_only_the_players_own_games():
    respx.get(url__regex=r"https://americas\.api\.riotgames\.com/riot/account/v1/accounts/by-riot-id/.*").mock(
        return_value=httpx.Response(200, json={"puuid": "puuid-2"})
    )
    respx.get(url__regex=r".*/by-puuid/puuid-2/ids.*").mock(return_value=httpx.Response(200, json=["NA1_1"]))
    respx.get(url__regex=r".*/matches/NA1_1$").mock(return_value=httpx.Response(200, json=_match("NA1_1")))
    async with RiotClient() as rc:
        rows = await player_rows(rc, "Mid", "Someone#C9@na1", days=30, max_matches=10)
    assert rows == [
        {
            "player": "Mid",
            "champion": "Ahri",
            "position": "MIDDLE",
            "patch": "16.23",
            "game_start_ms": 1_790_000_000_000,
            "win": True,
        }
    ]
    pool = pool_table(rows * 2)
    assert pool.select("player", "champion", "games", "wins").row(0) == ("Mid", "Ahri", 2, 2)
    assert pool_table([]).is_empty()


def test_player_soloq_is_off_by_default():
    example = Path(__file__).parents[2] / "config" / "preferences.example.yaml"
    prefs = Preferences.model_validate(yaml.safe_load(example.read_text()))
    assert not any(p.riot_ids for p in prefs.players)
