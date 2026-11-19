"""Response models. Every rate comes with its evidence: k of n and a 95% interval (lo, hi)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Period = Literal["recent", "all"]
Tendency = Literal["strong", "weak", "noise"]


class Rate(BaseModel):
    """k successes out of n, rate = k / n, Wilson 95% interval."""

    k: int
    n: int
    rate: float | None
    lo: float | None
    hi: float | None


class Info(BaseModel):
    ddragon_version: str | None
    live_patch: str | None
    demo_protected: bool


class Team(BaseModel):
    team_id: str
    name: str
    league: str
    games: int
    wins: int
    series: int
    first_game: datetime
    last_game: datetime


class DraftRow(Rate):
    champion: str
    key: str | None  # Data Dragon key for the icon
    split_type: Literal["all", "side", "game_bucket"]
    split: str
    picks: int
    bans: int
    base_rate: float  # league rate for the same champion and split
    first_rotation: Rate
    avg_slot: float | None
    tendency: Tendency


class ChampionCount(BaseModel):
    champion: str
    key: str | None
    count: int


class TargetedPlayer(Rate):
    """Opponents' bans that hit this player's earlier pro pool: k of the n bans the team faced."""

    player: str
    role: str | None
    champions: list[ChampionCount]


class Scouting(BaseModel):
    team: Team
    period: Period
    games: int  # team games in the period (the n behind every presence rate)
    draft: list[DraftRow]
    targeted_players: list[TargetedPlayer]


class MacroRate(Rate):
    metric: str
    split: str
    base_rate: float
    tendency: Tendency


class MacroTiming(BaseModel):
    metric: str
    n: int
    median_s: float
    q25_s: float
    q75_s: float


class KillCell(BaseModel):
    side: Literal["blue", "red"]
    kind: Literal["kill", "death"]
    cx: int
    cy: int
    count: int


class Macro(BaseModel):
    team: Team
    period: Period
    games: int
    rates: list[MacroRate]
    timings: list[MacroTiming]
    early_kills: list[KillCell]
    games_by_side: dict[str, int]


class PlayerChampion(Rate):
    champion: str
    key: str | None
    shrunk: float
    shrunk_lo: float
    shrunk_hi: float
    recent_games: float
    comfort: float
    last_played: datetime


class Player(BaseModel):
    player_id: str
    name: str
    role: str
    current: bool  # played in the team's latest games (within a week of its last game)
    last_game: datetime
    n: int
    unique_champions: int
    effective_pool: float
    effective_pool_lo: float
    effective_pool_hi: float
    depth: int
    meta_overlap: Rate
    champions: list[PlayerChampion]


class Players(BaseModel):
    team: Team
    players: list[Player]


class MetaRow(BaseModel):
    champion: str  # Data Dragon key
    name: str | None
    roles: list[str]
    presence: Rate  # games picked or banned, of games in the window
    picks: int
    bans: int
    pro_n: int | None
    pro_wr: float | None
    pro_wr_lo: float | None
    pro_wr_hi: float | None
    soloq_n: int | None
    soloq_wr: float | None
    soloq_wr_lo: float | None
    soloq_wr_hi: float | None
    delta: float | None
    meta_score: float


class Meta(BaseModel):
    window: str
    windows: list[str]
    patches: list[str]
    live_patch: str | None
    rows: list[MetaRow]


class LeagueCoverage(BaseModel):
    league: str
    teams: int
    games: int
    first_game: datetime
    last_game: datetime


class SoloqCoverage(BaseModel):
    patch: str
    matches: int


class Coverage(BaseModel):
    leagues: list[LeagueCoverage]
    soloq: list[SoloqCoverage]
    teams: list[Team]
