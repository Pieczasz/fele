"""Minimal Riot API client: per-routing-host rate limiting, Retry-After handling, on-disk cache.

Rate limits are enforced per routing value (e.g. euw1, europe), so each host gets its own limiter.
Raw responses are cached gzip-compressed under data_local/riot_cache/ (gitignored, never committed).
The API key is read from settings and never logged.
"""

import asyncio
import gzip
import hashlib
import json
import logging
import time
from collections import deque
from collections.abc import Sequence
from http import HTTPStatus
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import httpx

from fele.config import settings
from fele.jsontypes import JsonObj

log = logging.getLogger(__name__)

PLATFORM_TO_REGION = {
    "kr": "asia",
    "jp1": "asia",
    "euw1": "europe",
    "eun1": "europe",
    "tr1": "europe",
    "ru": "europe",
    "me1": "europe",
    "na1": "americas",
    "br1": "americas",
    "la1": "americas",
    "la2": "americas",
    "oc1": "sea",
    "sg2": "sea",
    "tw2": "sea",
    "vn2": "sea",
}

RANKED_SOLO_QUEUE = 420
MAX_RETRIES = 5

type Limits = Sequence[tuple[int, float]]

# Development-key defaults; replaced by X-App-Rate-Limit from the first response.
DEFAULT_LIMITS: Limits = ((20, 1.0), (100, 120.0))


class RateLimiter:
    """Sliding-window limiter over several (count, seconds) windows, sharing one log of sent requests."""

    def __init__(self, limits: Limits = DEFAULT_LIMITS, safety: float = 0.9) -> None:
        self.safety = safety
        self.windows: list[tuple[int, float]] = []
        self.set_limits(limits)
        self.sent: deque[float] = deque()  # send times, oldest first; outlives limit changes
        self.synced = False  # limits taken from a real X-App-Rate-Limit header
        self.lock = asyncio.Lock()
        self.blocked_until = 0.0

    def set_limits(self, limits: Limits) -> None:
        self.windows = [(max(1, int(n * self.safety)), span) for n, span in limits]

    async def acquire(self) -> None:
        async with self.lock:
            while True:
                now = time.monotonic()
                longest = max(span for _, span in self.windows)
                while self.sent and now - self.sent[0] >= longest:
                    self.sent.popleft()
                wait = max(0.0, self.blocked_until - now)
                for n, span in self.windows:
                    recent = [t for t in self.sent if now - t < span]
                    if len(recent) >= n:  # wait until enough of them age out of this window
                        wait = max(wait, span - (now - recent[len(recent) - n]))
                if wait <= 0:
                    self.sent.append(now)
                    return
                await asyncio.sleep(wait + 0.01)


def parse_limits(header: str | None) -> Limits | None:
    if not header:
        return None
    return [(int(n), float(s)) for n, s in (part.split(":") for part in header.split(","))]


class RiotClient:
    def __init__(self) -> None:
        secret = settings().riot_api_key
        key = secret.get_secret_value() if secret else ""
        if not key:
            raise RuntimeError("Set RIOT_DEVELOPER_PLATFORM_API_KEY in .env")
        self._http = httpx.AsyncClient(headers={"X-Riot-Token": key}, timeout=30)
        self.cache_dir = settings().local("riot_cache")
        self.limiters: dict[str, RateLimiter] = {}  # one per routing host (euw1, europe, …)
        self.throttled = 0  # 429 responses seen (should stay ~0: the limiter runs at 90 % of the app limit)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        await self._http.aclose()

    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode()).hexdigest()
        return self.cache_dir / h[:2] / f"{h}.json.gz"

    async def get(self, host: str, path: str, params: dict[str, Any] | None = None, *, cache: bool = True) -> Any:  # noqa: ANN401
        """GET https://{host}.api.riotgames.com{path}. Returns parsed JSON, or None on 404."""
        url = str(httpx.URL(f"https://{host}.api.riotgames.com{path}", params=params or {}))
        cp = self._cache_path(url)
        if cache and cp.exists():
            return json.loads(gzip.decompress(cp.read_bytes()))

        limiter = self.limiters.setdefault(host, RateLimiter())
        for attempt in range(MAX_RETRIES):
            await limiter.acquire()
            r = await self._http.get(url)
            if not limiter.synced and (lim := parse_limits(r.headers.get("X-App-Rate-Limit"))):
                limiter.set_limits(lim)
                limiter.synced = True
            status = r.status_code
            if status == HTTPStatus.OK:
                if cache:  # the raw body: no re-serialising, and level 6 is ~3x faster than gzip's default 9
                    cp.parent.mkdir(parents=True, exist_ok=True)
                    cp.write_bytes(gzip.compress(r.content, compresslevel=6))
                return r.json()
            if status == HTTPStatus.NOT_FOUND:
                return None
            if status == HTTPStatus.TOO_MANY_REQUESTS or status >= HTTPStatus.INTERNAL_SERVER_ERROR:
                self.throttled += status == HTTPStatus.TOO_MANY_REQUESTS
                delay = float(r.headers.get("Retry-After", 2**attempt))
                log.warning("%s %s on %s, sleeping %.1fs", status, host, path.split("/")[3], delay)
                limiter.blocked_until = time.monotonic() + delay
                continue
            if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise RuntimeError(f"Riot API {status}: key missing, invalid or expired (dev keys last 24h)")
            r.raise_for_status()
        raise RuntimeError(f"Giving up on {host}{path} after {MAX_RETRIES} attempts")

    # --- endpoint helpers -------------------------------------------------
    async def account_by_riot_id(self, region: str, game_name: str, tag: str) -> JsonObj | None:
        return await self.get(region, f"/riot/account/v1/accounts/by-riot-id/{game_name}/{tag}")

    async def apex_league(
        self, platform: str, tier: str = "challenger", queue: str = "RANKED_SOLO_5x5"
    ) -> JsonObj | None:
        return await self.get(platform, f"/lol/league/v4/{tier}leagues/by-queue/{queue}", cache=False)

    async def match_ids(
        self, region: str, puuid: str, start_time: int | None = None, count: int = 100, queue: int = RANKED_SOLO_QUEUE
    ) -> list[str] | None:
        params: dict[str, Any] = {"queue": queue, "count": count, "type": "ranked"}
        if start_time:
            params["startTime"] = start_time
        return await self.get(region, f"/lol/match/v5/matches/by-puuid/{puuid}/ids", params, cache=False)

    async def match(self, region: str, match_id: str) -> JsonObj | None:
        return await self.get(region, f"/lol/match/v5/matches/{match_id}")

    async def timeline(self, region: str, match_id: str) -> JsonObj | None:
        return await self.get(region, f"/lol/match/v5/matches/{match_id}/timeline")
