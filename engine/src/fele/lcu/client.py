"""Thin async client for the local League client API. Every getter returns None when the client is gone or the
endpoint has nothing (404 outside champ select), so callers just poll."""

import logging
from http import HTTPStatus
from typing import Self

import httpx
from pydantic import ValidationError

from fele.lcu import payloads
from fele.lcu.connect import Lcu
from fele.lcu.payloads import Payload

log = logging.getLogger(__name__)
TIMEOUT_S = 2.0
HISTORY_PAGE = 20  # the client serves match history in pages of 20


class LcuClient:
    def __init__(self, lcu: Lcu, transport: httpx.AsyncBaseTransport | None = None) -> None:
        # the client's certificate is self-signed by Riot and the host is always 127.0.0.1
        self.http = httpx.AsyncClient(
            base_url=lcu.base_url,
            auth=("riot", lcu.password),
            verify=False,  # noqa: S501 - loopback only, Riot's self-signed certificate
            timeout=TIMEOUT_S,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.http.aclose()

    async def get[T: Payload](self, path: str, model: type[T], **params: int) -> T | None:
        try:
            r = await self.http.get(path, params=params or None)
        except httpx.HTTPError:
            return None
        if r.status_code != HTTPStatus.OK:
            return None
        try:
            return model.model_validate_json(r.content)
        except ValidationError:
            log.debug("unexpected reply from %s", path)
            return None

    async def phase(self) -> str | None:
        try:
            r = await self.http.get("/lol-gameflow/v1/gameflow-phase")
        except httpx.HTTPError:
            return None
        return r.json() if r.status_code == HTTPStatus.OK and r.text.startswith('"') else None

    async def gameflow(self) -> payloads.Gameflow | None:
        return await self.get("/lol-gameflow/v1/session", payloads.Gameflow)

    async def champ_select(self) -> payloads.Session | None:
        return await self.get("/lol-champ-select/v1/session", payloads.Session)

    async def me(self) -> payloads.Player | None:
        return await self.get("/lol-summoner/v1/current-summoner", payloads.Player)

    async def lobby(self) -> payloads.Lobby | None:
        return await self.get("/lol-lobby/v2/lobby", payloads.Lobby)

    async def match_history(self, puuid: str, games: int) -> list[payloads.HistoryGame]:
        """A player's recent games as the client shows them (newest first), in pages of 20."""
        out: list[payloads.HistoryGame] = []
        for start in range(0, games, HISTORY_PAGE):
            page = await self.get(
                f"/lol-match-history/v1/products/lol/{puuid}/matches",
                payloads.History,
                begIndex=start,
                endIndex=min(start + HISTORY_PAGE, games),
            )
            got = page.games.games if page else []
            out.extend(got)
            if len(got) < HISTORY_PAGE:
                break
        return out
