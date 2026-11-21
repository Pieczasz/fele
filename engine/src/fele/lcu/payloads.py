"""The few League client payload fields fele reads. Unknown fields are ignored; missing ones get safe defaults, so
a client update that drops a field degrades the advice instead of crashing the watcher."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class Payload(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore", frozen=True)


class Player(Payload):
    cell_id: int = -1
    assigned_position: str = ""
    champion_id: int = 0
    champion_pick_intent: int = 0
    puuid: str = ""
    game_name: str = ""
    tag_line: str = ""

    @property
    def riot_id(self) -> str | None:
        return f"{self.game_name}#{self.tag_line}" if self.game_name and self.tag_line else None


class Action(Payload):
    id: int = 0
    actor_cell_id: int = -1
    type: str = ""
    is_ally_action: bool = False
    champion_id: int = 0
    completed: bool = False
    is_in_progress: bool = False


class Bans(Payload):
    my_team_bans: list[int] = []
    their_team_bans: list[int] = []


class Timer(Payload):
    phase: str = ""
    adjusted_time_left_in_phase: int = 0


class Session(Payload):
    """GET /lol-champ-select/v1/session"""

    local_player_cell_id: int = -1
    is_custom_game: bool = False
    my_team: list[Player] = []
    their_team: list[Player] = []
    actions: list[list[Action]] = []
    bans: Bans = Bans()
    timer: Timer = Timer()


class Lobby(Payload):
    """GET /lol-lobby/v2/lobby"""

    members: list[Player] = []


class Queue(Payload):
    id: int = -1


class GameData(Payload):
    queue: Queue = Queue()
    is_custom_game: bool = False


class Gameflow(Payload):
    """GET /lol-gameflow/v1/session"""

    game_data: GameData = GameData()


class Timeline(Payload):
    lane: str = ""
    role: str = ""


class Stats(Payload):
    win: bool = False


class Participant(Payload):
    participant_id: int = 0
    champion_id: int = 0
    stats: Stats = Stats()
    timeline: Timeline = Timeline()


class Identity(Payload):
    participant_id: int = 0
    player: Player = Player()


class HistoryGame(Payload):
    """One game of GET /lol-match-history/v1/products/lol/{puuid}/matches (games.games[])"""

    game_creation: int = 0
    game_duration: int = 0
    queue_id: int = -1
    participant_identities: list[Identity] = []
    participants: list[Participant] = []


class HistoryGames(Payload):
    games: list[HistoryGame] = []


class History(Payload):
    games: HistoryGames = HistoryGames()
