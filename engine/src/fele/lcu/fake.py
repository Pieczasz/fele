"""A scripted stand-in for the League client: lobby, then a Ranked Flex champ select that advances by itself.

`fele lcu-fake` writes a lockfile and serves plain http on 127.0.0.1, so `FELE_LCU_LOCKFILE=<it> fele serve --lcu`
shows fele Live end to end without the game installed (demo, E2E tests). Players and games are made up; champion ids
are real so the advice uses the real solo-queue sample.
"""

import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ME, FRIEND = "fake-me", "fake-friend"
LOBBY_S = 4.0  # seconds in the lobby before champ select starts
STEP_S = 3.0  # seconds per draft turn
# champion ids: Ahri 103, Orianna 61, Lee Sin 64, Viego 234, Jinx 222, Thresh 412, Garen 86, Zed 238, ...
ALLY_BANS, ENEMY_BANS = (157, 777, 238, 245, 91), (64, 103, 81, 360, 555)
ENEMY_PICKS, ALLY_PICKS = (266, 121, 4, 498, 89), (86, 234, 61, 222, 412)
POSITIONS = ("top", "jungle", "middle", "bottom", "utility")
PICK_ORDER = ((0,), (5, 6), (1, 2), (7, 8), (3, 4), (9,))  # cells per pick turn: blue 0-4, red 5-9


def _games(puuid: str, champs: list[tuple[int, str, bool]]) -> list[dict[str, Any]]:
    now = int(time.time() * 1000)
    return [
        {
            "gameCreation": now - i * 20 * 3_600_000,
            "gameDuration": 1700,
            "queueId": 440 if i % 2 else 420,
            "participantIdentities": [{"participantId": 1, "player": {"puuid": puuid}}],
            "participants": [
                {"participantId": 1, "championId": c, "stats": {"win": w}, "timeline": {"lane": lane, "role": "SOLO"}}
            ],
        }
        for i, (c, lane, w) in enumerate(champs)
    ]


HISTORY = {
    ME: _games(ME, [(61, "MIDDLE", True), (103, "MIDDLE", True), (61, "MIDDLE", False), (4, "MIDDLE", True)] * 5),
    FRIEND: _games(FRIEND, [(234, "JUNGLE", True), (64, "JUNGLE", False), (234, "JUNGLE", True)] * 6),
}


def session_at(t: float) -> dict[str, Any]:
    """The champ-select session `t` seconds after it started: 10 bans at once, then picks 1-2-2-2-2-1."""
    step = int(t // STEP_S)  # 0 = ban phase, 1..6 = pick turns, 7 = finalization
    bans_done = step >= 1
    actions: list[list[dict[str, Any]]] = [
        [
            {
                "id": cell,
                "actorCellId": cell,
                "type": "ban",
                "isAllyAction": cell < 5,  # noqa: PLR2004
                "championId": (ALLY_BANS[cell] if cell < 5 else ENEMY_BANS[cell - 5]) if bans_done else 0,  # noqa: PLR2004
                "completed": bans_done,
                "isInProgress": step == 0,
            }
            for cell in range(10)
        ]
    ]
    for turn, cells in enumerate(PICK_ORDER, start=1):
        actions.append(
            [
                {
                    "id": 100 + cell,
                    "actorCellId": cell,
                    "type": "pick",
                    "isAllyAction": cell < 5,  # noqa: PLR2004
                    "championId": (ALLY_PICKS[cell] if cell < 5 else ENEMY_PICKS[cell - 5]) if step > turn else 0,  # noqa: PLR2004
                    "completed": step > turn,
                    "isInProgress": step == turn,
                }
                for cell in cells
            ]
        )
    picked = {a["actorCellId"]: a["championId"] for turn in actions[1:] for a in turn if a["completed"]}
    names = {0: ("Teammate", "EUW", "fake-0"), 1: ("Friend", "EUW", FRIEND), 2: ("Me", "EUW", ME)}
    my_team = [
        {
            "cellId": cell,
            "assignedPosition": POSITIONS[cell],
            "championId": picked.get(cell, 0),
            "championPickIntent": 61 if cell == 2 and step == 0 else 0,  # noqa: PLR2004
            "puuid": names.get(cell, ("", "", f"fake-{cell}"))[2],
            "gameName": names.get(cell, ("",))[0],
            "tagLine": names.get(cell, ("", ""))[1],
        }
        for cell in range(5)
    ]
    their_team = [{"cellId": c, "championId": picked.get(c, 0), "puuid": "", "gameName": ""} for c in range(5, 10)]
    final = step > len(PICK_ORDER)
    return {
        "localPlayerCellId": 2,
        "isCustomGame": False,
        "myTeam": my_team,
        "theirTeam": their_team,
        "actions": actions,
        "bans": {"myTeamBans": [], "theirTeamBans": []},
        "timer": {
            "phase": "FINALIZATION" if final else "BAN_PICK",
            "adjustedTimeLeftInPhase": int((STEP_S - t % STEP_S) * 1000),
        },
    }


class FakeClient:
    def __init__(self, loop: bool = True) -> None:  # noqa: FBT001, FBT002
        self.started = time.monotonic()
        self.loop = loop

    def elapsed(self) -> float:
        cycle = LOBBY_S + STEP_S * (len(PICK_ORDER) + 3)
        t = time.monotonic() - self.started
        return t % cycle if self.loop else t

    def route(self, path: str) -> Any:  # noqa: ANN401 - JSON
        t = self.elapsed()
        in_cs = t >= LOBBY_S
        routes: dict[str, Any] = {
            "/lol-gameflow/v1/gameflow-phase": "ChampSelect" if in_cs else "Lobby",
            "/lol-gameflow/v1/session": {"gameData": {"queue": {"id": 440}, "isCustomGame": False}},
            "/lol-summoner/v1/current-summoner": {"puuid": ME, "gameName": "Me", "tagLine": "EUW"},
            "/lol-lobby/v2/lobby": {
                "members": [
                    {"puuid": ME, "gameName": "Me", "tagLine": "EUW"},
                    {"puuid": FRIEND, "gameName": "Friend", "tagLine": "EUW"},
                ]
            },
        }
        if in_cs:
            routes["/lol-champ-select/v1/session"] = session_at(t - LOBBY_S)
        for puuid, games in HISTORY.items():
            routes[f"/lol-match-history/v1/products/lol/{puuid}/matches"] = {"games": {"games": games}}
        return routes.get(path)


def serve(lockfile: Path, port: int = 0, *, loop: bool = True) -> ThreadingHTTPServer:
    """Start the fake client in a background thread and write its lockfile. Returns the server (call shutdown())."""
    fake = FakeClient(loop)
    password = secrets.token_urlsafe(12)

    class Handler(BaseHTTPRequestHandler):
        # http.server's method name
        # noinspection PyPep8Naming
        def do_GET(self) -> None:
            body = fake.route(self.path.split("?")[0])
            ok = body is not None
            data = json.dumps(body if ok else {"message": "not found"}).encode()
            self.send_response(200 if ok else 404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        # the base class's parameter name
        # noinspection PyShadowingBuiltins
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    lockfile.write_text(f"LeagueClient:0:{server.server_port}:{password}:http", encoding="utf-8")
    return server
