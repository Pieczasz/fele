"""fele Live: League client connection, champ-select parsing (with the privacy rule), history pools, the champ-select
scorer, the watcher and /lcu/state. The client is faked with httpx.MockTransport; payloads follow the client's shape
(camelCase JSON) with made-up ids."""

import time
from pathlib import Path
from typing import Any

import httpx
import polars as pl
import pytest

from fele.engine import solo
from fele.lcu import connect, history, payloads, state, view
from fele.lcu.watch import Watcher

ME, FRIEND, STRANGER = "puuid-me", "puuid-friend", "puuid-stranger"
# champion ids: 1-5 tops, 11-15 junglers, 21-25 mids, 31-35 bots, 41-45 supports
ROLE_BASE = {"top": 1, "jungle": 11, "mid": 21, "bot": 31, "support": 41}
POS = {"top": "TOP", "jungle": "JUNGLE", "mid": "MIDDLE", "bot": "BOTTOM", "support": "UTILITY"}


def _champions() -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for role, base in ROLE_BASE.items():
        for i in range(5):
            cid = base + i
            rows.append(
                {
                    "riot_id": cid,
                    "champion": f"Key{cid}",
                    "name": f"Champ {cid}",
                    "roles": role,
                    "scaling": "mid",
                    "ap_share": 1.0 if role == "mid" else 0.0,
                    **dict.fromkeys(("engage", "disengage", "peel", "frontline", "poke", "dive"), 1.0),
                    **dict.fromkeys(("splitpush", "waveclear", "hard_cc"), 1.0),
                    "frontline": 3.0 if role == "top" and i == 0 else 1.0,
                }
            )
    return pl.DataFrame(rows)


def _data() -> solo.SoloData:
    """Champion `base` is the strongest of each role (60% over 200 games); others 48%."""
    patch: list[dict[str, Any]] = []
    mu: list[dict[str, Any]] = []
    for role, base in ROLE_BASE.items():
        for i in range(5):
            games = 200 if i == 0 else 100
            wins = 120 if i == 0 else 48
            patch.append(
                {
                    "patch": "16.23",
                    "champion_id": base + i,
                    "position": POS[role],
                    "games": games,
                    "wins": wins,
                    "bans": 300 if i == 0 else 10,
                    "matches": 1000,
                }
            )
    # mid: Champ 22 beats Champ 21 in lane (Champ 21 wins only 30% of 50 games against it)
    mu.append({"position": "MIDDLE", "champion_id": 21, "opponent_id": 22, "games": 50, "wins": 15})
    mu.append({"position": "MIDDLE", "champion_id": 22, "opponent_id": 21, "games": 50, "wins": 35})
    return solo.build_solo(_champions(), pl.DataFrame(patch), pl.DataFrame(mu))


def _player(cell: int, position: str, puuid: str, champ: int = 0, name: str = "") -> dict[str, Any]:
    return {
        "cellId": cell,
        "assignedPosition": position,
        "championId": champ,
        "championPickIntent": 0,
        "puuid": puuid,
        "gameName": name,
        "tagLine": "EUW" if name else "",
    }


def _session(**over: Any) -> dict[str, Any]:
    s: dict[str, Any] = {
        "localPlayerCellId": 2,
        "isCustomGame": False,
        "myTeam": [
            _player(0, "top", STRANGER, name="Stranger"),
            _player(1, "jungle", FRIEND, name="Friend"),
            _player(2, "middle", ME, name="Me"),
            _player(3, "bottom", ""),
            _player(4, "utility", ""),
        ],
        "theirTeam": [{"cellId": 5 + i, "championId": 0, "puuid": "", "gameName": ""} for i in range(5)],
        "actions": [
            [
                {
                    "id": i,
                    "actorCellId": i,
                    "type": "ban",
                    "isAllyAction": i < 5,
                    "championId": 0,
                    "completed": False,
                    "isInProgress": i == 2,
                }
                for i in range(10)
            ],
            [{"id": 99, "type": "ten_bans_reveal", "completed": False}],
        ],
        "bans": {"myTeamBans": [], "theirTeamBans": []},
        "timer": {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 25_000},
    }
    return s | over


def _cs(session: dict[str, Any] | None = None, party: set[str] | None = None) -> state.ChampSelect:
    return state.parse_session(payloads.Session.model_validate(session or _session()), party or {ME, FRIEND}, 420)


def _games(puuid: str, champs: list[tuple[int, str, bool]], queue: int = 420) -> list[dict[str, Any]]:
    now = int(time.time() * 1000)
    return [
        {
            "gameCreation": now - i * 3_600_000,
            "gameDuration": 1800,
            "queueId": queue,
            "participantIdentities": [{"participantId": 1, "player": {"puuid": puuid}}],
            "participants": [
                {"participantId": 1, "championId": c, "stats": {"win": w}, "timeline": {"lane": lane, "role": "SOLO"}}
            ],
        }
        for i, (c, lane, w) in enumerate(champs)
    ]


# --- connection -----------------------------------------------------------------------------------------------------
def test_lockfile_and_process_args_are_parsed():
    lcu = connect.parse_lockfile("LeagueClient:123:54321:s3cret:https\n")
    assert lcu is not None
    assert lcu == connect.Lcu(54321, "s3cret", "https")
    assert lcu.base_url == "https://127.0.0.1:54321"
    assert "s3cret" not in repr(lcu)  # the token never shows up in logs
    assert connect.parse_lockfile("garbage") is None
    args = '"/Applications/League of Legends.app/.../LeagueClientUx" --remoting-auth-token=abc --app-port=6000'
    assert connect.parse_process_args(args) == connect.Lcu(6000, "abc")
    assert connect.parse_process_args("other process --app-port=1") is None


def test_find_client_honours_the_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    lock = tmp_path / "lockfile"
    monkeypatch.setenv("FELE_LCU_LOCKFILE", str(lock))
    assert connect.find_client() is None  # client closed: no lockfile, and no process scan under the override
    lock.write_text("LeagueClient:1:7000:pw:http", encoding="utf-8")
    assert connect.find_client() == connect.Lcu(7000, "pw", "http")


# --- champ select -------------------------------------------------------------------------------------------------
def test_session_keeps_identities_only_for_me_and_party():
    cs = _cs()
    by_cell = {a.cell: a for a in cs.allies}
    assert by_cell[2].me
    assert by_cell[2].name == "Me#EUW"
    assert by_cell[2].puuid == ME
    assert by_cell[1].name == "Friend#EUW"
    assert by_cell[1].puuid == FRIEND
    assert by_cell[0].name is None
    assert by_cell[0].puuid is None
    assert [a.position for a in cs.allies] == ["top", "jungle", "mid", "bot", "support"]
    assert cs.queue_name == "Ranked Solo/Duo"
    assert len(cs.actions) == 10  # the reveal marker is not an action
    assert cs.current is not None
    assert cs.current.cell == 2
    assert cs.current.kind == "ban"
    assert cs.time_left_ms == 25_000


def test_session_collects_bans_and_picks():
    s = _session()
    s["actions"] = [
        [
            {"id": 1, "actorCellId": 2, "type": "ban", "isAllyAction": True, "championId": 1, "completed": True},
            {"id": 2, "actorCellId": 7, "type": "ban", "isAllyAction": False, "championId": 11, "completed": True},
        ],
        [
            {"id": 3, "actorCellId": 5, "type": "pick", "isAllyAction": False, "championId": 22, "completed": True},
            {"id": 4, "actorCellId": 2, "type": "pick", "isAllyAction": True, "championId": 0, "isInProgress": True},
        ],
    ]
    s["theirTeam"][1]["championId"] = 33  # shown before its action completed
    cs = _cs(s)
    assert cs.ally_bans == (1,)
    assert cs.enemy_bans == (11,)
    assert cs.enemy_picks == (22, 33)
    assert cs.unavailable == {1, 11, 22, 33}
    assert cs.current is not None
    assert cs.current.kind == "pick"
    assert cs.current.ally


def test_party_comes_from_the_lobby():
    lobby = payloads.Lobby.model_validate(
        {"members": [{"puuid": ME, "gameName": "Me", "tagLine": "EUW"}, {"puuid": FRIEND}, {"gameName": "x"}]}
    )
    assert state.party_of(lobby) == {ME: "Me#EUW", FRIEND: None}
    assert state.party_of(None) == {}


# --- history ------------------------------------------------------------------------------------------------------
def test_history_keeps_own_summoners_rift_rows_and_builds_a_pool():
    raw = _games(ME, [(21, "MIDDLE", True), (21, "MIDDLE", True), (22, "MIDDLE", False), (31, "BOTTOM", True)])
    raw += _games(ME, [(23, "MIDDLE", True)], queue=450)  # ARAM: dropped
    raw.append(raw[0] | {"gameDuration": 200})  # remake: dropped
    games = history.parse_history([payloads.HistoryGame.model_validate(g) for g in raw], ME)
    assert [g.champion for g in games] == [21, 21, 22, 31]
    assert games[3].position == "bot"
    pool = history.pool_of(games)
    assert pool.games == 4
    assert pool.wins == 3
    assert pool.top(1, "mid")[0][0] == 21
    wr, n = pool.shrunk(21)
    assert n == 2
    assert pool.win_rate < wr < 1.0


# --- scorer -------------------------------------------------------------------------------------------------------
def test_picks_are_legal_on_role_and_explained():
    data = _data()
    cs = _cs()
    opts = solo.pick_options(data, cs, 2, None)
    assert opts
    assert all(o.role == "mid" for o in opts)
    assert {data.names[c] for c in range(21, 26)} >= {o.champion for o in opts}
    assert opts[0].champion == "Champ 21"  # the strongest mid
    assert any("high-elo games" in r for r in opts[0].reasons)


def test_comfort_and_lane_change_the_pick():
    data = _data()
    pool = history.pool_of(
        history.parse_history(
            [payloads.HistoryGame.model_validate(g) for g in _games(ME, [(24, "MIDDLE", True)] * 8)], ME
        )
    )
    s = _session()
    s["actions"] = [
        [{"id": 1, "actorCellId": 5, "type": "pick", "isAllyAction": False, "championId": 21, "completed": True}]
    ]
    opts = solo.pick_options(data, _cs(s), 2, pool, "Me#EUW")
    names = [o.champion for o in opts]
    assert "Champ 21" not in names  # taken by the enemy
    assert names[0] == "Champ 24"  # 8 recent games, all won
    assert any(r.startswith("Me: 8 of the last 8 games") for r in opts[0].reasons)
    lane = next(o for o in opts if o.champion == "Champ 22")
    assert lane.parts["lane"] > 0
    assert any("vs Champ 21 in lane" in r for r in lane.reasons)


def test_bans_skip_teammates_hovers_and_find_counters():
    data = _data()
    s = _session()
    s["myTeam"][0]["championPickIntent"] = 1  # a teammate hovers the strongest top: don't ban it
    pool = history.pool_of(
        history.parse_history(
            [payloads.HistoryGame.model_validate(g) for g in _games(ME, [(21, "MIDDLE", True)] * 5)], ME
        )
    )
    opts = solo.ban_options(data, _cs(s), {2: (pool, "Me#EUW")}, top_n=25)
    names = [o.champion for o in opts]
    assert "Champ 1" not in names
    counter = next(o for o in opts if o.champion == "Champ 22")
    assert counter.parts["counter"] > 0
    assert any("counters Me's Champ 21" in r for r in counter.reasons)
    assert all(o.reasons for o in opts)


def test_stranger_turn_gets_no_personal_stats():
    data = _data()
    w = Watcher(find=lambda: None)
    w.pools[STRANGER] = (time.monotonic(), history.pool_of([]))  # even if we had it, the snapshot hides the puuid
    s = _session()
    s["actions"] = [
        [{"id": 1, "actorCellId": 0, "type": "pick", "isAllyAction": True, "championId": 0, "isInProgress": True}]
    ]
    advice = view.advice(data, _cs(s), w)
    assert advice is not None
    assert advice.kind == "pick"
    assert advice.for_cell == 0
    assert advice.for_name is None
    assert all("games on it" not in r for o in advice.options for r in o.reasons)


# --- watcher + API ------------------------------------------------------------------------------------------------
def _fake_client(session: dict[str, Any] | None, phase: str = "ChampSelect") -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "127.0.0.1"
        assert request.headers["authorization"].startswith("Basic ")
        path = request.url.path
        routes: dict[str, Any] = {
            "/lol-gameflow/v1/gameflow-phase": phase,
            "/lol-gameflow/v1/session": {"gameData": {"queue": {"id": 440}, "isCustomGame": False}},
            "/lol-summoner/v1/current-summoner": {"puuid": ME, "gameName": "Me", "tagLine": "EUW"},
            "/lol-lobby/v2/lobby": {
                "members": [
                    {"puuid": ME, "gameName": "Me", "tagLine": "EUW"},
                    {"puuid": FRIEND, "gameName": "Friend", "tagLine": "EUW"},
                ]
            },
            f"/lol-match-history/v1/products/lol/{ME}/matches": {
                "games": {"games": _games(ME, [(23, "MIDDLE", True)] * 6)}
            },
            f"/lol-match-history/v1/products/lol/{FRIEND}/matches": {
                "games": {"games": _games(FRIEND, [(12, "JUNGLE", True)] * 4)}
            },
        }
        if session is not None:
            routes["/lol-champ-select/v1/session"] = session
        if path not in routes:
            return httpx.Response(404, json={"message": "not found"})
        return httpx.Response(200, json=routes[path])

    return httpx.MockTransport(handler)


async def test_watcher_follows_the_client_and_prefetches_party_history():
    lcu = connect.Lcu(1234, "pw", "http")
    w = Watcher(find=lambda: lcu, transport=_fake_client(None, phase="Lobby"))
    await w.tick()
    assert w.snapshot.connected
    assert w.snapshot.phase == "Lobby"
    assert w.snapshot.champ_select is None
    assert w.snapshot.party == {ME: "Me#EUW", FRIEND: "Friend#EUW"}
    assert w.snapshot.queue == 440
    await w.settle()  # the prefetch the lobby started
    assert w.pool(ME) is not None
    assert w.pool(FRIEND) is not None
    v = w.version
    w.transport = _fake_client(_session())
    await w.close()  # force a reconnect with the new transport
    await w.tick()
    assert w.version > v
    assert w.snapshot.champ_select is not None
    v = w.version
    await w.tick()
    assert w.version == v  # nothing changed (the timer alone doesn't count)
    w.find = lambda: None
    await w.tick()
    assert not w.snapshot.connected
    await w.close()


async def test_lcu_state_endpoint(monkeypatch: pytest.MonkeyPatch):
    from fele.api.app import app  # noqa: PLC0415

    data = _data()
    monkeypatch.setattr(solo, "load_solo", lambda: data)
    w = Watcher(find=lambda: connect.Lcu(1, "pw", "http"), transport=_fake_client(_session()))
    await w.tick()
    await w.settle()
    app.state.watcher = w
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            body = (await c.get("/lcu/state")).json()
    finally:
        app.state.watcher = None
        await w.close()
    assert body["enabled"]
    assert body["connected"]
    assert body["phase"] == "ChampSelect"
    assert body["party"] == ["Me#EUW", "Friend#EUW"]
    cs = body["champ_select"]
    names = {a["cell"]: a["name"] for a in cs["allies"]}
    assert names == {0: None, 1: "Friend#EUW", 2: "Me#EUW", 3: None, 4: None}
    assert next(a for a in cs["allies"] if a["cell"] == 1)["pool"][0]["champion"]["name"] == "Champ 12"
    advice = body["advice"]
    assert advice["kind"] == "ban"
    assert advice["for_name"] == "you"
    assert len(advice["options"]) == solo.TOP_N
    assert "pw" not in str(body)


# --- evaluation ---------------------------------------------------------------------------------------------------
def test_eval_solo_reads_cached_matches_and_reports(tmp_path: Path):
    import gzip  # noqa: PLC0415
    import json  # noqa: PLC0415

    from fele.eval import solo as ev  # noqa: PLC0415

    cache = tmp_path / "riot_cache" / "ab"
    cache.mkdir(parents=True)
    for i in range(8):  # one player always on Champ 24 in mid, the rest fixed
        parts = [
            {"puuid": "main", "teamId": 100, "teamPosition": "MIDDLE", "championId": 24, "win": i % 2 == 0},
            {"puuid": "opp", "teamId": 200, "teamPosition": "MIDDLE", "championId": 21, "win": i % 2 == 1},
        ]
        match = {
            "metadata": {"matchId": f"M{i}"},
            "info": {
                "queueId": 420,
                "gameStartTimestamp": i * 1000,
                "participants": parts,
                "teams": [{"bans": [{"championId": 1}]}, {"bans": [{"championId": -1}]}],
            },
        }
        (cache / f"m{i}.json.gz").write_bytes(gzip.compress(json.dumps(match).encode()))
    (cache / "timeline.json.gz").write_bytes(gzip.compress(json.dumps({"info": {"frames": []}}).encode()))
    players = ev.player_games(ev.cached_matches(tmp_path / "riot_cache"))
    assert sorted(len(p) for p in players) == [8, 8]
    main = next(p for p in players if p[0].champion == 24)
    assert main[0].enemy_laner == 21
    assert main[0].bans == (1,)
    r = ev.ranks(_data(), [main], {})
    assert r == [1, 1, 1]  # games 6-8: the pool from earlier games puts Champ 24 first
    text = ev.report(_data(), players)
    assert "| scorer | 6 |" in text


# --- fake client ----------------------------------------------------------------------------------------------------
def test_fake_session_walks_through_a_flex_draft():
    from fele.lcu import fake  # noqa: PLC0415

    def cs(t: float) -> state.ChampSelect:
        return state.parse_session(payloads.Session.model_validate(fake.session_at(t)), {fake.ME, fake.FRIEND}, 440)

    start = cs(0.5)
    assert start.current is not None
    assert start.current.kind == "ban"
    assert start.allies[2].intent == 61  # Orianna hovered while banning
    first_pick = cs(fake.STEP_S + 0.5)
    assert len(first_pick.ally_bans) == 5
    assert len(first_pick.enemy_bans) == 5
    assert first_pick.current is not None
    assert first_pick.current.cell == 0
    done = cs(fake.STEP_S * 10)
    assert done.current is None
    assert sorted(done.ally_picks) == sorted(fake.ALLY_PICKS)
    assert set(done.enemy_picks) == set(fake.ENEMY_PICKS)


async def test_watcher_finds_the_fake_client_through_its_lockfile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from fele.lcu import fake  # noqa: PLC0415

    lock = tmp_path / "lockfile"
    server = fake.serve(lock, loop=False)
    monkeypatch.setenv("FELE_LCU_LOCKFILE", str(lock))
    w = Watcher()
    try:
        await w.tick()
        await w.settle()
        assert w.snapshot.connected
        assert w.snapshot.phase == "Lobby"
        assert w.snapshot.party == {fake.ME: "Me#EUW", fake.FRIEND: "Friend#EUW"}
        pool = w.pool(fake.ME)
        assert pool is not None
        assert pool.top(1, "mid")[0][0] == 61  # Orianna, the most played
    finally:
        await w.close()
        server.shutdown()
        server.server_close()


def test_no_pick_advice_once_locked_during_their_turn():
    from fele.lcu import fake  # noqa: PLC0415

    w = Watcher(find=lambda: None)
    t = fake.STEP_S * 4 + 0.5  # turn 4: the enemy picks; we (cell 2) locked on turn 3
    cs = state.parse_session(payloads.Session.model_validate(fake.session_at(t)), {fake.ME}, 440)
    assert cs.ally(2) is not None
    assert cs.current is not None
    assert not cs.current.ally
    assert view.advice(_data(), cs, w) is None


def test_simultaneous_bans_advise_me_and_spare_party_comfort_picks():
    s = _session()
    for a in s["actions"][0]:
        a["isInProgress"] = True  # solo-queue bans: everyone at once
    cs = _cs(s)
    assert cs.current is not None
    assert cs.current.cell == cs.me
    friend = history.pool_of(
        history.parse_history(
            [payloads.HistoryGame.model_validate(g) for g in _games(FRIEND, [(11, "JUNGLE", True)] * 5)], FRIEND
        )
    )
    opts = solo.ban_options(_data(), cs, {1: (friend, "Friend#EUW")}, top_n=25)
    assert "Champ 11" not in [o.champion for o in opts]  # the friend's main is never a ban suggestion


def test_captures_are_anonymised_consistently():
    from fele.lcu.capture import Anonymiser  # noqa: PLC0415

    anon = Anonymiser()
    out = anon('{"myTeam": [{"puuid": "abc", "gameName": "Real", "championId": 103}], "me": {"puuid": "abc"}, "x": ""}')
    assert out["myTeam"][0]["puuid"] == out["me"]["puuid"] == "puuid-1"
    assert out["myTeam"][0]["gameName"] == "gameName-2"
    assert out["myTeam"][0]["championId"] == 103
    assert "abc" not in str(out)
    assert "Real" not in str(out)


# --- scrims: tournament draft in pro order --------------------------------------------------------------------------
def test_tournament_draft_maps_to_the_pro_board():
    from fele.lcu import fake  # noqa: PLC0415

    def cs(t: float) -> state.ChampSelect:
        return state.parse_session(payloads.Session.model_validate(fake.scrim_session_at(t)), set(), 0)

    early = state.pro_order(cs(fake.STEP_S * 3 + 0.5))
    assert early is not None
    assert early.we_pick_first
    assert early.we_are_blue
    assert early.actions == (157, 64, 777)
    done = state.pro_order(cs(fake.STEP_S * 25))
    assert done is not None
    assert len(done.actions) == 20
    assert state.pro_order(_cs()) is None  # solo queue's simultaneous bans are not the pro order
    data = _data()
    full = view.champ_select(data, cs(fake.STEP_S * 25), Watcher(find=lambda: None))
    assert full.pro_draft is not None
    assert len(full.pro_draft.actions) == 20
