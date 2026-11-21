"""Record what the League client sends during a lobby and champ select, anonymised, to check the parsers against
real payloads (`fele lcu-capture`). Identity fields are replaced by stable placeholders before anything is written;
files go to data_local/ (gitignored) and only reach tests after a human has looked at them."""

import asyncio
import json
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx

from fele.lcu.connect import Lcu
from fele.lcu.history import GAMES

IDENTITY_KEYS = frozenset(
    {"puuid", "gameName", "tagLine", "summonerId", "accountId", "summonerName", "displayName", "internalName",
     "obfuscatedPuuid", "obfuscatedSummonerId", "playerAlias", "profileIconId"}
)  # fmt: skip
PATHS = (
    "/lol-gameflow/v1/gameflow-phase",
    "/lol-gameflow/v1/session",
    "/lol-lobby/v2/lobby",
    "/lol-champ-select/v1/session",
)


class Anonymiser:
    """Parses JSON and replaces identity fields with stable placeholders (same input -> same placeholder)."""

    def __init__(self) -> None:
        self.ids: dict[str, str] = {}

    def __call__(self, text: str) -> Any:  # noqa: ANN401 - JSON
        return json.loads(text, object_hook=self._object)

    def _object(self, obj: dict[str, Any]) -> dict[str, Any]:
        return {k: self._value(k, v) for k, v in obj.items()}

    def _value(self, key: str, value: Any) -> Any:  # noqa: ANN401
        if key in IDENTITY_KEYS and value not in ("", None, 0):
            return self.ids.setdefault(f"{key}:{value}", f"{key}-{len(self.ids) + 1}")
        return value


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1), encoding="utf-8")


async def capture(lcu: Lcu, out: Path, seconds: int, interval: float = 1.0) -> int:
    """Write one anonymised JSON frame per second while the client is reachable. Returns the number of frames."""
    _write(out / "started.json", {})
    anon = Anonymiser()
    frames = 0
    async with httpx.AsyncClient(base_url=lcu.base_url, auth=("riot", lcu.password), verify=False, timeout=2) as http:  # noqa: S501 - loopback
        me = (await http.get("/lol-summoner/v1/current-summoner")).json()
        puuid = me.get("puuid", "")
        history = await http.get(
            f"/lol-match-history/v1/products/lol/{puuid}/matches", params={"begIndex": 0, "endIndex": GAMES}
        )
        _write(out / "history.json", anon(history.text))
        for _ in range(seconds):
            frame: dict[str, Any] = {}
            for path in PATHS:
                r = await http.get(path)
                frame[path] = anon(r.text) if r.status_code == HTTPStatus.OK else None
            _write(out / f"frame-{frames:04d}.json", frame)
            frames += 1
            await asyncio.sleep(interval)
    return frames
