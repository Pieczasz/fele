import time
from pathlib import Path

import httpx
import pytest
import respx

from fele.external.riot import RateLimiter, RiotClient

URL = "https://euw1.api.riotgames.com/lol/status/v4/platform-data"


@respx.mock
async def test_get_caches_successful_responses(tmp_settings: Path) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json={"ok": 1}, headers={"X-App-Rate-Limit": "5:1"}))
    async with RiotClient() as rc:
        assert await rc.get("euw1", "/lol/status/v4/platform-data") == {"ok": 1}
        assert await rc.get("euw1", "/lol/status/v4/platform-data") == {"ok": 1}
    assert route.call_count == 1
    assert list((tmp_settings / "data_local" / "riot_cache").rglob("*.json.gz"))


@respx.mock
@pytest.mark.usefixtures("tmp_settings")
async def test_get_returns_none_on_404() -> None:
    respx.get(URL).mock(return_value=httpx.Response(404))
    async with RiotClient() as rc:
        assert await rc.get("euw1", "/lol/status/v4/platform-data") is None


@respx.mock
@pytest.mark.usefixtures("tmp_settings")
async def test_get_retries_after_429() -> None:
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "0"}), httpx.Response(200, json=[1])]
    )
    async with RiotClient() as rc:
        assert await rc.get("euw1", "/lol/status/v4/platform-data", cache=False) == [1]
    assert route.call_count == 2


@respx.mock
@pytest.mark.usefixtures("tmp_settings")
async def test_get_rejects_bad_key() -> None:
    respx.get(URL).mock(return_value=httpx.Response(403))
    async with RiotClient() as rc:
        with pytest.raises(RuntimeError, match="expired"):
            await rc.get("euw1", "/lol/status/v4/platform-data")


@respx.mock
@pytest.mark.usefixtures("tmp_settings")
async def test_endpoint_helpers_build_routes() -> None:
    respx.get(url__regex=r".*/ids\?.*").mock(return_value=httpx.Response(200, json=["KR_1"]))
    respx.get(url__regex=r".*/challengerleagues/.*").mock(return_value=httpx.Response(200, json={"entries": []}))
    async with RiotClient() as rc:
        assert await rc.match_ids("asia", "p", start_time=1) == ["KR_1"]
        assert await rc.apex_league("kr") == {"entries": []}


async def test_rate_limiter_waits_when_window_full() -> None:
    limiter = RateLimiter([(2, 0.2)], safety=1.0)
    start = time.monotonic()
    for _ in range(3):
        await limiter.acquire()
    assert time.monotonic() - start >= 0.15
