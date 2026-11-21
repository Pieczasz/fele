"""Poll the League client once a second and keep the latest snapshot. Party history is prefetched in the lobby, so
champ select advice is ready the moment champ select starts.

Started by `fele serve --lcu` (FELE_LCU=1) in the API's lifespan; nothing runs otherwise.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace

import httpx

from fele.lcu.client import LcuClient
from fele.lcu.connect import Lcu, find_client
from fele.lcu.history import GAMES, Pool, parse_history, pool_of
from fele.lcu.state import ChampSelect, parse_session, party_of

log = logging.getLogger(__name__)
INTERVAL_S = 1.0
PARTY_PHASES = frozenset({"Lobby", "Matchmaking", "ReadyCheck", "ChampSelect"})
POOL_TTL_S = 6 * 3600
RETRY_S = 60


@dataclass(frozen=True)
class Snapshot:
    connected: bool = False
    phase: str | None = None
    queue: int = -1
    custom: bool = False
    me: str | None = None  # local player's puuid
    me_name: str | None = None
    party: dict[str, str | None] = field(default_factory=dict[str, str | None])  # puuid -> Riot ID
    champ_select: ChampSelect | None = None

    def key(self) -> Snapshot:
        """The snapshot without the ticking timer: a change here means the advice may change."""
        return replace(self, champ_select=replace(self.champ_select, time_left_ms=0)) if self.champ_select else self


class Watcher:
    def __init__(
        self,
        find: Callable[[], Lcu | None] = find_client,
        transport: httpx.AsyncBaseTransport | None = None,
        interval: float = INTERVAL_S,
    ) -> None:
        self.find, self.transport, self.interval = find, transport, interval
        self.snapshot = Snapshot()
        self.version = 0
        self.pools: dict[str, tuple[float, Pool]] = {}  # puuid -> (fetched at, pool)
        self._lcu: Lcu | None = None
        self._client: LcuClient | None = None
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def pool(self, puuid: str | None) -> Pool | None:
        got = self.pools.get(puuid) if puuid else None
        return got[1] if got else None

    async def run(self) -> None:
        try:
            while True:
                # a poll must never kill the watcher; the error is logged
                # noinspection PyBroadException
                try:
                    await self.tick()
                except Exception:
                    log.exception("League client poll failed")
                await asyncio.sleep(self.interval)
        finally:
            await self.close()

    async def close(self) -> None:
        for t in self._tasks.values():
            t.cancel()
        if self._client:
            await self._client.http.aclose()
        self._client = self._lcu = None

    def _publish(self, snap: Snapshot) -> None:
        if snap.key() != self.snapshot.key():
            self.version += 1
        self.snapshot = snap

    async def _connect(self) -> LcuClient | None:
        lcu = self.find()
        if lcu != self._lcu:
            await self.close()
            self._lcu = lcu
            self._client = LcuClient(lcu, self.transport) if lcu else None
        return self._client

    async def tick(self) -> None:
        client = await self._connect()
        phase = await client.phase() if client else None
        if client is None or phase is None:
            self._publish(Snapshot())
            return
        old = self.snapshot
        me, me_name = old.me, old.me_name
        if not old.connected or me is None:
            summoner = await client.me()
            me, me_name = (summoner.puuid or None, summoner.riot_id) if summoner else (None, None)
        party = old.party
        if phase in PARTY_PHASES:
            lobby = await client.lobby()
            party = party_of(lobby) or party  # the lobby can be briefly empty when champ select starts
        elif phase == "None":
            party = {}
        flow = await client.gameflow()
        queue, custom = (flow.game_data.queue.id, flow.game_data.is_custom_game) if flow else (-1, False)
        cs = None
        if phase == "ChampSelect":
            session = await client.champ_select()
            if session:
                known = {*party, *([me] if me else [])}
                cs = parse_session(session, known, queue, custom=custom)
        self._publish(
            Snapshot(
                connected=True,
                phase=phase,
                queue=queue,
                custom=custom,
                me=me,
                me_name=me_name,
                party=party,
                champ_select=cs,
            )
        )
        for puuid in {*party, *([me] if me else [])}:
            self._prefetch(client, puuid)

    def _prefetch(self, client: LcuClient, puuid: str) -> None:
        cached = self.pools.get(puuid)
        fresh = cached and time.monotonic() - cached[0] < POOL_TTL_S
        if fresh or (puuid in self._tasks and not self._tasks[puuid].done()):
            return

        async def fetch() -> None:
            # any client hiccup: retry later, advice works without the pool
            # noinspection PyBroadException
            try:
                games = parse_history(await client.match_history(puuid, GAMES), puuid)
            except Exception:  # noqa: BLE001
                log.debug("match history unavailable, retrying in %s s", RETRY_S)
                self.pools[puuid] = (time.monotonic() - POOL_TTL_S + RETRY_S, pool_of([]))
                return
            self.pools[puuid] = (time.monotonic(), pool_of(games))
            self.version += 1  # advice now has this player's pool

        self._tasks[puuid] = asyncio.create_task(fetch())

    async def settle(self) -> None:
        """Wait for the history fetches in flight (tests; the API never blocks on them)."""
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
