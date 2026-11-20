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


# --- Phase 9: draft engine --------------------------------------------------------------------------------------
class ChampionInfo(BaseModel):
    name: str  # GRID name (used in drafts)
    key: str | None  # Data Dragon key (icons)
    roles: list[str]


class DraftRequest(BaseModel):
    us: str  # team name or GRID id
    them: str
    we_are_blue: bool = True
    we_pick_first: bool = True
    actions: list[str] = []  # champions in pro draft order so far ("" = skipped ban)
    locked: list[str] = []  # Fearless: champions picked in earlier games of this series
    game_number: int = 1
    series_score: int = 0  # our wins - their wins so far
    mode: Literal["best", "comfort_only", "save"] = "best"


class NextAction(BaseModel):
    slot: int
    who: Literal["us", "them"]
    kind: Literal["pick", "ban"]
    phase: str


class OptionOut(BaseModel):
    champion: str
    key: str | None
    role: str | None
    score: float
    parts: dict[str, float]
    reasons: list[str]
    win_prob: float | None


class WinProb(BaseModel):
    mean: float
    p10: float
    p90: float
    note: str = "Outcome model is Elo-dominated: drafts move it a few points at most (docs/MODEL_CARD.md)."


class CompOut(BaseModel):
    champions: list[str]
    ap_share: float
    damage: str
    totals: dict[str, float]
    scaling: str
    warnings: list[str]
    contribution: dict[str, float]


class DraftAdvice(BaseModel):
    next: NextAction | None
    options: list[OptionOut]
    win_prob: WinProb
    our_comp: CompOut
    their_comp: CompOut


class SeriesRequest(BaseModel):
    us: str
    them: str
    best_of: Literal[1, 3, 5] = 3
    we_start_blue: bool = True
    save: dict[str, int] = {}  # champion -> first game we may pick it (Fearless plan)
    sims: int = 200


class SeriesOut(BaseModel):
    best_of: int
    sims: int
    series_win: float
    series_win_se: float
    expected_games: float
    availability: dict[str, list[float]]
    depletion: dict[str, list[float]]
    notes: list[str]


class SeriesPlan(BaseModel):
    plan: SeriesOut
    no_plan: SeriesOut | None  # same seed, no save list (only when a plan was given)
    difference: float | None  # plan - no plan, series win probability
    difference_se: float | None
    within_noise: bool | None  # |difference| < 2 standard errors: don't read anything into it
