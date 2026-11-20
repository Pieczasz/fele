"""Fearless series simulator (Monte Carlo over a Bo3/Bo5).

Each simulated game: both teams draft with the draft-action model (LambdaRank) — our picks skip champions the coach
rules out (never-pick, refuses) and any champion a plan saves for later games — then the winner is drawn from the
outcome model's win probability. Hard Fearless: every champion picked in a game is unavailable for the rest of that
series. Side rule (2026 First Selection, assumption for who chooses what): the loser of a game takes first pick next
game and the winner then chooses blue side. Game 1's side and pick order come from the caller.

Outputs come with their Monte Carlo error. Comparing plans uses common random numbers (same seed), so a difference
reflects the plan, not luck — but the outcome model is Elo-dominated, so plan differences are small by construction.
"""

from dataclasses import dataclass, field

import numpy as np

from fele.engine.draft import THEM, US, DraftState
from fele.engine.live import Live
from fele.engine.recommend import Matchup, action_probs, matchup, saved_for_later, win_prob
from fele.prefs import Comfort, Preferences

SIMS = 200
COMFORT_POOL = {Comfort.signature, Comfort.comfortable}


@dataclass
class SeriesResult:
    best_of: int
    first_game: int  # availability/depletion lists start at this game number
    sims: int
    series_win: float
    series_win_se: float
    expected_games: float
    availability: dict[str, list[float]]  # champion -> P(still available at the start of game k)
    depletion: dict[str, list[float]]  # our player -> share of their comfortable pool still available in game k
    notes: list[str] = field(default_factory=list[str])
    drafts: list[list[tuple[list[str], list[str]]]] = field(default_factory=list[list[tuple[list[str], list[str]]]])
    # per simulated series: (our picks, their picks) of each game — only with record=True (for tests)


@dataclass(frozen=True)
class SeriesStart:
    """Where the series stands (scenario branches such as "if we lose G1")."""

    game: int = 1  # next game number
    wins: int = 0
    losses: int = 0
    locked: frozenset[str] = frozenset()  # champions already picked in this series (hard Fearless)
    we_first: bool = True  # we have first pick in the next game
    we_blue: bool | None = None  # we are blue in the next game (None: same as we_first)


@dataclass
class _Sim:
    locked: set[str] = field(default_factory=set[str])
    games: list[tuple[list[str], list[str]]] = field(default_factory=list[tuple[list[str], list[str]]])
    wins: int = 0
    losses: int = 0
    we_first: bool = True
    we_blue: bool = True

    def done(self, need: int) -> bool:
        return self.wins >= need or self.losses >= need


def _blocked(prefs: Preferences | None, save: dict[str, int], game: int) -> set[str]:
    """Champions our side won't pick this game: saved for later, never-pick, and refusals no teammate covers (the
    simulated draft doesn't know which player takes a pick, so one player's refusal can't block it for everyone)."""
    out = saved_for_later(prefs, save, game)
    if prefs is not None:
        out |= set(prefs.strategy.never_pick)
        refused = {n.champion for p in prefs.players for n in p.pool if n.comfort == Comfort.refuses}
        played = {n.champion for p in prefs.players for n in p.pool if n.comfort != Comfort.refuses}
        out |= refused - played
    return out


def _draft(live: Live, m: Matchup, sims: list[_Sim], blocked: set[str], rng: np.random.Generator) -> list[DraftState]:
    states = [DraftState(we_pick_first=s.we_first, locked=frozenset(s.locked)) for s in sims]
    block_idx = [live.builder.index[c] for c in blocked if c in live.builder.index]
    while not states[0].complete:
        probs = action_probs(m, states)
        nxt: list[DraftState] = []
        for st, row in zip(states, probs, strict=True):
            p = row
            if st.who(st.slot) == US and st.kind(st.slot) == "pick" and block_idx:
                p = row.copy()
                p[block_idx] = 0.0
                p = p / p.sum() if p.sum() > 0 else row
            nxt.append(st.play(live.vocab[rng.choice(len(p), p=p)]))
        states = nxt
    return states


def simulate(  # noqa: PLR0913 - one series setup
    live: Live,
    us: str,
    them: str,
    *,
    best_of: int = 3,
    we_start_blue: bool = True,
    prefs: Preferences | None = None,
    save: dict[str, int] | None = None,
    key_champions: list[str] | None = None,
    sims: int = SIMS,
    seed: int = 0,
    record: bool = False,
    start: SeriesStart | None = None,
) -> SeriesResult:
    """save: champion -> first game number we may pick it in (e.g. {"Azir": 3} = keep Azir for game 3+)."""
    rng = np.random.default_rng(seed)
    need = best_of // 2 + 1
    start = start or SeriesStart(we_first=we_start_blue)
    runs = [
        _Sim(
            locked=set(start.locked),
            wins=start.wins,
            losses=start.losses,
            we_first=start.we_first,
            we_blue=start.we_first if start.we_blue is None else start.we_blue,
        )
        for _ in range(sims)
    ]
    pools = {
        p.name: [n.champion for n in p.pool if n.comfort in COMFORT_POOL] for p in (prefs.players if prefs else [])
    }
    keys = key_champions or sorted({c for cs in pools.values() for c in cs})
    avail: dict[str, list[float]] = {c: [] for c in keys}
    depletion: dict[str, list[float]] = {name: [] for name in pools}
    for game in range(start.game, best_of + 1):
        alive = [r for r in runs if not r.done(need)]
        if not alive:
            break
        for c in keys:
            avail[c].append(float(np.mean([c not in r.locked for r in alive])))
        for name, pool in pools.items():
            depletion[name].append(
                float(np.mean([np.mean([c not in r.locked for c in pool]) for r in alive])) if pool else 1.0
            )
        # split BEFORE playing: a game flips first pick to the loser, which must not move a series into the other
        # group and let it play twice in one round (found by the Fearless property test)
        groups = {
            (first, blue): [r for r in alive if (r.we_first, r.we_blue) == (first, blue)]
            for first in (True, False)
            for blue in (True, False)
        }
        for (_, blue), group in groups.items():
            if not group:
                continue
            m = matchup(live, us, them, we_are_blue=blue, game_number=game)
            states = _draft(live, m, group, _blocked(prefs, save or {}, game), rng)
            for r, st in zip(group, states, strict=True):
                m.series_score = r.wins - r.losses
                won = rng.random() < win_prob(m, st.picks(US), st.picks(THEM))
                r.wins, r.losses = r.wins + won, r.losses + (not won)
                r.locked |= set(st.picks(US)) | set(st.picks(THEM))
                r.games.append((st.picks(US), st.picks(THEM)))
                r.we_first, r.we_blue = not won, won  # the loser takes first pick, the winner then picks blue
    outcome = np.array([r.wins >= need for r in runs], float)
    return SeriesResult(
        best_of=best_of,
        first_game=start.game,
        sims=sims,
        series_win=float(outcome.mean()),
        series_win_se=float(outcome.std(ddof=1) / np.sqrt(sims)),
        expected_games=float(np.mean([r.wins + r.losses for r in runs])),
        availability=avail,
        depletion=depletion,
        drafts=[r.games for r in runs] if record else [],
        notes=[
            "Both teams draft as the draft model expects (our side skips champions the coach rules out).",
            "Side rule assumed: the loser takes first pick next game and the winner chooses blue side.",
            "Win probabilities are Elo-dominated: different plans change series odds by small amounts.",
        ],
    )
