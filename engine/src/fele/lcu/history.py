"""Recent games of the local player and party members, from the client's own match history (no Riot API key, no rate
limit), turned into a champion pool per player."""

import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from fele.lcu import payloads

SR_QUEUES = frozenset({400, 420, 440, 490, 700})  # Summoner's Rift draft, ranked, quickplay, Clash
REMAKE_S = 300
HALF_LIFE_DAYS = 30.0
WR_PRIOR = 10.0  # pseudo-games shrinking a champion's win rate toward the player's overall rate
GAMES = 40
_LANES = {"TOP": "top", "JUNGLE": "jungle", "MIDDLE": "mid", "MID": "mid"}


@dataclass(frozen=True)
class Game:
    champion: int
    position: str | None
    win: bool
    start_ms: int
    queue: int


@dataclass
class ChampStat:
    games: int = 0
    wins: int = 0
    weight: float = 0.0  # recency-weighted games
    last_ms: int = 0
    positions: Counter[str] = field(default_factory=Counter[str])


@dataclass
class Pool:
    games: int
    wins: int
    champions: dict[int, ChampStat]
    positions: Counter[str]  # games per position

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.5

    def shrunk(self, champion: int) -> tuple[float, int]:
        """(win rate shrunk toward the player's overall rate, games) on a champion."""
        s = self.champions.get(champion)
        if s is None:
            return self.win_rate, 0
        return (s.wins + WR_PRIOR * self.win_rate) / (s.games + WR_PRIOR), s.games

    def top(self, n: int, position: str | None = None) -> list[tuple[int, ChampStat]]:
        rows = [(c, s) for c, s in self.champions.items() if position is None or s.positions[position]]
        return sorted(rows, key=lambda r: (-r[1].weight, -r[1].games))[:n]


def _position(p: payloads.Participant) -> str | None:
    lane, role = p.timeline.lane.upper(), p.timeline.role.upper()
    if lane == "BOTTOM":
        return "support" if "SUPPORT" in role else "bot"
    return _LANES.get(lane)


def parse_history(games: list[payloads.HistoryGame], puuid: str) -> list[Game]:
    """The player's own row of each Summoner's Rift game; remakes and other modes dropped."""
    out: list[Game] = []
    for g in games:
        if g.queue_id not in SR_QUEUES or g.game_duration < REMAKE_S:
            continue
        pid = next((i.participant_id for i in g.participant_identities if i.player.puuid == puuid), None)
        parts = g.participants
        me = next((p for p in parts if p.participant_id == pid), parts[0] if len(parts) == 1 else None)
        if me and me.champion_id:
            out.append(Game(me.champion_id, _position(me), me.stats.win, g.game_creation, g.queue_id))
    return out


def pool_of(games: list[Game], now_ms: int | None = None) -> Pool:
    now_ms = now_ms or int(time.time() * 1000)
    champs: defaultdict[int, ChampStat] = defaultdict(ChampStat)
    positions: Counter[str] = Counter()
    for g in games:
        s = champs[g.champion]
        s.games += 1
        s.wins += g.win
        s.weight += 0.5 ** (max(now_ms - g.start_ms, 0) / 86_400_000 / HALF_LIFE_DAYS)
        s.last_ms = max(s.last_ms, g.start_ms)
        if g.position:
            s.positions[g.position] += 1
            positions[g.position] += 1
    return Pool(len(games), sum(g.win for g in games), dict(champs), positions)
