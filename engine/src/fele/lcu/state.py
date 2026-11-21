"""Champion select as the client reports it -> a small frozen snapshot. Pure functions, unit-tested on recorded JSON.

The draft order is read from the session's `actions` (solo queue, flex, Clash and tournament draft differ), never
hard-coded. Privacy rule (docs/COMPLIANCE.md): an ally's identity is kept only for the local player and lobby party
members; everyone else is "Ally". Enemies are never identified.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from fele.ingest.replay import DRAFT_TEMPLATE
from fele.lcu import payloads

QUEUES = {
    0: "Custom game",
    400: "Normal draft",
    420: "Ranked Solo/Duo",
    440: "Ranked Flex",
    490: "Quickplay",
    700: "Clash",
    720: "ARAM Clash",
}
BLUE_CELLS = 5  # cells 0-4 are blue side, 5-9 red
POSITIONS = {"top": "top", "jungle": "jungle", "middle": "mid", "bottom": "bot", "utility": "support"}

type Kind = Literal["ban", "pick"]


@dataclass(frozen=True)
class Ally:
    cell: int
    position: str | None  # top/jungle/mid/bot/support; None in blind/custom games without positions
    champion: int  # locked or currently shown champion id, 0 = none
    intent: int  # pre-pick hover (planning phase), 0 = none
    puuid: str | None  # only for the local player and party members
    name: str | None  # Riot ID "game#tag", same rule
    me: bool


@dataclass(frozen=True)
class Action:
    id: int
    cell: int
    kind: Kind
    ally: bool
    champion: int
    completed: bool
    in_progress: bool


@dataclass(frozen=True)
class ChampSelect:
    queue: int
    custom: bool
    me: int  # local player's cell
    allies: tuple[Ally, ...]
    enemy_picks: tuple[int, ...]  # champion ids the enemy has locked (or shown), in order
    ally_bans: tuple[int, ...]
    enemy_bans: tuple[int, ...]
    actions: tuple[Action, ...]  # the full order, flattened
    phase: str  # PLANNING / BAN_PICK / FINALIZATION
    time_left_ms: int

    @property
    def queue_name(self) -> str:
        return QUEUES.get(self.queue, f"Queue {self.queue}")

    @property
    def current(self) -> Action | None:
        """The action in progress; ours when several run at once (solo-queue bans are simultaneous)."""
        live = [a for a in self.actions if a.in_progress and not a.completed]
        return next((a for a in live if a.cell == self.me), live[0] if live else None)

    @property
    def unavailable(self) -> set[int]:
        """Champions nobody may pick now: bans and locked picks on both sides."""
        locked = {a.champion for a in self.actions if a.completed and a.kind == "pick"}
        return {*self.ally_bans, *self.enemy_bans, *locked, *self.enemy_picks} - {0}

    @property
    def ally_picks(self) -> list[int]:
        return [a.champion for a in self.allies if a.champion]

    def ally(self, cell: int) -> Ally | None:
        return next((a for a in self.allies if a.cell == cell), None)


def _actions(session: payloads.Session) -> tuple[Action, ...]:
    return tuple(
        Action(
            id=a.id,
            cell=a.actor_cell_id,
            kind="ban" if a.type == "ban" else "pick",
            ally=a.is_ally_action,
            champion=a.champion_id,
            completed=a.completed,
            in_progress=a.is_in_progress,
        )
        for turn in session.actions
        for a in turn
        if a.type in {"ban", "pick"}  # skips "ten_bans_reveal" and other markers
    )


def parse_session(
    session: payloads.Session, party: Iterable[str], queue: int = -1, *, custom: bool = False
) -> ChampSelect:
    """`party`: puuids of the local player's lobby members (the local player is always kept)."""
    party = set(party)
    allies: list[Ally] = []
    for p in session.my_team:
        me = p.cell_id == session.local_player_cell_id
        visible = me or (bool(p.puuid) and p.puuid in party)
        allies.append(
            Ally(
                cell=p.cell_id,
                position=POSITIONS.get(p.assigned_position.lower()),
                champion=p.champion_id,
                intent=p.champion_pick_intent,
                puuid=(p.puuid or None) if visible else None,
                name=p.riot_id if visible else None,
                me=me,
            )
        )
    actions = _actions(session)
    done = [a for a in actions if a.completed]
    enemy_locked = [a.champion for a in done if a.kind == "pick" and not a.ally]
    enemy_picks = tuple(dict.fromkeys([*enemy_locked, *(p.champion_id for p in session.their_team if p.champion_id)]))
    ally_bans = [*session.bans.my_team_bans, *(a.champion for a in done if a.kind == "ban" and a.ally)]
    enemy_bans = [*session.bans.their_team_bans, *(a.champion for a in done if a.kind == "ban" and not a.ally)]
    return ChampSelect(
        queue=queue,
        custom=custom or session.is_custom_game,
        me=session.local_player_cell_id,
        allies=tuple(allies),
        enemy_picks=enemy_picks,
        ally_bans=tuple(dict.fromkeys(c for c in ally_bans if c)),
        enemy_bans=tuple(dict.fromkeys(c for c in enemy_bans if c)),
        actions=actions,
        phase=session.timer.phase,
        time_left_ms=session.timer.adjusted_time_left_in_phase,
    )


def party_of(lobby: payloads.Lobby | None) -> dict[str, str | None]:
    """Lobby members: puuid -> Riot ID (None when the client doesn't give one)."""
    return {m.puuid: m.riot_id for m in (lobby.members if lobby else []) if m.puuid}


@dataclass(frozen=True)
class ProOrder:
    """A champ select that follows the pro (tournament draft) order, as the mock board wants it."""

    actions: tuple[int, ...]  # completed actions in order; 0 = skipped ban
    we_pick_first: bool
    we_are_blue: bool


def pro_order(cs: ChampSelect) -> ProOrder | None:
    """The draft in pro order, when the client's action order is exactly the pro template (custom tournament draft,
    scrims); None for solo queue's simultaneous bans and other orders."""
    if len(cs.actions) != len(DRAFT_TEMPLATE) or not cs.allies:
        return None
    first_ally = cs.actions[0].ally
    if any(
        (a.kind, "A" if a.ally == first_ally else "B") != t for a, t in zip(cs.actions, DRAFT_TEMPLATE, strict=True)
    ):
        return None
    done: list[int] = []
    for a in cs.actions:
        if not a.completed:
            break
        done.append(a.champion)
    return ProOrder(tuple(done), we_pick_first=first_ally, we_are_blue=min(a.cell for a in cs.allies) < BLUE_CELLS)
