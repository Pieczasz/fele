from collections.abc import Iterator
from pathlib import Path

import pytest

from fele.config import settings


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point FELE_DATA_DIR / STL_DATA_DIR at a temp dir with a fake key; never touches real data."""
    monkeypatch.setenv("FELE_DATA_DIR", str(tmp_path / "data_local"))
    monkeypatch.setenv("STL_DATA_DIR", str(tmp_path / "grid"))
    monkeypatch.setenv("RIOT_DEVELOPER_PLATFORM_API_KEY", "test-key")
    settings.cache_clear()
    yield tmp_path
    settings.cache_clear()
