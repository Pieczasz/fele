"""Coach / player preferences: the human knowledge the data can't see.

Stored in config/preferences.yaml (gitignored, per user). See config/preferences.example.yaml.
These are inputs to the recommendation engine, never overwritten by models.
"""

from enum import StrEnum
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, Field

from fele.config import settings

if TYPE_CHECKING:
    from pathlib import Path


class Role(StrEnum):
    top = "top"
    jungle = "jungle"
    mid = "mid"
    bot = "bot"
    support = "support"


class Comfort(StrEnum):
    signature = "signature"  # best champions, trusted on stage in any game
    comfortable = "comfortable"
    playable = "playable"  # practiced, situational
    learning = "learning"  # scrim-only so far
    refuses = "refuses"  # player won't / shouldn't play it


class ChampionNote(BaseModel):
    champion: str
    comfort: Comfort = Comfort.comfortable
    note: str = ""


class PlayerPrefs(BaseModel):
    name: str
    role: Role
    riot_ids: list[str] = Field(default_factory=list, description="'GameName#TAG@platform', entered by the coach")
    pool: list[ChampionNote] = Field(default_factory=list[ChampionNote])
    hates_playing_against: list[str] = Field(default_factory=list, description="lane opponents to ban/avoid")
    wants_prio: bool = False  # draft priority: secure this player's picks early


class SeriesStrategy(BaseModel):
    save_for_late_games: list[str] = Field(default_factory=list, description="hold for G3+ under Fearless")
    must_ban_vs_opponent: dict[str, list[str]] = Field(default_factory=dict, description="opponent -> champions")
    never_pick: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list, description="e.g. early, teamfight, pick, scaling")


class Preferences(BaseModel):
    team: str
    players: list[PlayerPrefs]
    strategy: SeriesStrategy = SeriesStrategy()
    weight: float = Field(0.5, ge=0, le=1, description="how much coach input shifts model scores (0 = ignore)")


def load(path: Path | None = None) -> Preferences:
    path = path or settings().fele_config_dir / "preferences.yaml"
    if not path.exists():
        path = settings().fele_config_dir / "preferences.example.yaml"
    return Preferences.model_validate(yaml.safe_load(path.read_text()))
