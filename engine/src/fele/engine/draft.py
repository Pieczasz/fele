"""Draft state in the real pro order (validated in Phase 2): bans ABABAB, picks ABBAAB, bans BABA, picks BAAB, where
A is the first-pick team (red side may pick first since 2026 "First Selection"). Hard Fearless: champions picked in
earlier games of the series are unavailable to both teams."""

from dataclasses import dataclass, field

from fele.ingest.replay import DRAFT_TEMPLATE, draft_phase

US, THEM = "us", "them"


@dataclass(frozen=True)
class DraftState:
    we_pick_first: bool
    actions: tuple[str, ...] = ()  # champions in template order (a skipped ban is "")
    locked: frozenset[str] = field(default_factory=frozenset[str])  # Fearless: picked in earlier games of the series

    @property
    def slot(self) -> int:
        """Next template slot, 1-20 (21 = draft complete)."""
        return len(self.actions) + 1

    @property
    def complete(self) -> bool:
        return len(self.actions) >= len(DRAFT_TEMPLATE)

    def who(self, slot: int) -> str:
        team = DRAFT_TEMPLATE[slot - 1][1]
        return US if (team == "A") == self.we_pick_first else THEM

    @staticmethod
    def kind(slot: int) -> str:
        return DRAFT_TEMPLATE[slot - 1][0]

    @staticmethod
    def phase(slot: int) -> str:
        return draft_phase(slot)

    def picks(self, side: str) -> list[str]:
        return [c for i, c in enumerate(self.actions, 1) if c and self.kind(i) == "pick" and self.who(i) == side]

    def bans(self) -> list[str]:
        return [c for i, c in enumerate(self.actions, 1) if c and self.kind(i) == "ban"]

    def taken(self) -> set[str]:
        return {c for c in self.actions if c} | set(self.locked)

    def play(self, champion: str) -> DraftState:
        if self.complete:
            raise ValueError("draft is complete")
        if champion and champion in self.taken():
            msg = f"{champion} is not available (picked, banned or Fearless-locked)"
            raise ValueError(msg)
        return DraftState(self.we_pick_first, (*self.actions, champion), self.locked)
