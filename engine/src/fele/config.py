"""Paths and secrets. Everything comes from env vars or the repo-root .env (gitignored)."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    stl_data_dir: Path = Field(default=REPO_ROOT.parent / "stl-hackathon-2026-grid-starter")
    fele_data_dir: Path = Field(default=REPO_ROOT / "data_local")
    fele_config_dir: Path = Field(default=REPO_ROOT / "config")
    riot_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("RIOT_DEVELOPER_PLATFORM_API_KEY", "RIOT_API_KEY")
    )
    demo_password: SecretStr | None = None

    @property
    def lol_dir(self) -> Path:
        return self.stl_data_dir / "lol"

    @property
    def meta_dir(self) -> Path:
        return self.stl_data_dir / "meta"

    def local(self, *parts: str) -> Path:
        """A path under data_local/, created on demand."""
        p = self.fele_data_dir.joinpath(*parts)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def settings() -> Settings:
    return Settings()
