"""Everything a live draft needs, built once and cached: production models refit on *all* games (evaluation is
over and the holdout is spent), the feature-store state after the last game, Elo ratings, lineups, solo-queue lane
matchups and each team's style profile.

The cache (data_local/models/live.pkl) is our own file, rebuilt whenever an input Parquet file changes.
"""

import pickle
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import numpy.typing as npt
import polars as pl

from fele.config import settings
from fele.eval.run import inputs
from fele.features import state
from fele.models.action import LambdaRank
from fele.models.outcome import L3, LogisticFeatures
from fele.static.ddragon import patch_key
from fele.stats import elo
from fele.stats.data import game_context

type Floats = npt.NDArray[np.float32]

CACHE_VERSION = 3  # bump when the pickled classes change (the file name carries it)
POSITION = {"top": "TOP", "jungle": "JUNGLE", "mid": "MIDDLE", "bot": "BOTTOM", "support": "UTILITY"}
MATCHUP_PRIOR = 20.0  # pseudo-games shrinking solo-queue lane matchups toward 50%
STYLE_HALF_LIFE_DAYS = 120.0


@dataclass
class Player:
    player_id: str
    name: str
    role: str


@dataclass
class Live:
    builder: state.Builder
    ranker: LambdaRank
    outcome: LogisticFeatures
    ratings: dict[str, float]
    team_names: dict[str, str]
    lineups: dict[str, list[Player]]  # team -> players of its latest game
    patch: str | None
    now: datetime  # a day after the latest game in the data
    last_game: dict[str, datetime]  # team -> its latest game
    tags: dict[str, dict[str, float]]  # GRID champion -> tag values
    style: dict[str, Floats]  # team -> recency-weighted mean tags of its picks
    matchups: dict[tuple[str, str, str], tuple[int, int]]  # (role, champion, opponent) -> (games, wins)

    def now_for(self, team: str) -> datetime:
        """ "Now" for a team's recency weights: a day after its own latest game. Leagues' data end on different dates;
        anchoring every team to the dataset's last game would decay a whole league's pools toward zero."""
        last = self.last_game.get(team)
        return self.now if last is None else last + timedelta(days=1)

    @property
    def vocab(self) -> list[str]:
        return self.builder.vocab

    @property
    def roles(self) -> npt.NDArray[np.int8]:
        """role_rank (V x 5): 0 = primary role, state.UNTAGGED = not tagged."""
        return self.builder.role_rank

    def team_id(self, name_or_id: str) -> str:
        if name_or_id in self.team_names:
            return name_or_id
        for tid, name in self.team_names.items():
            if name.lower() == name_or_id.lower():
                return tid
        msg = f"Unknown team {name_or_id!r}"
        raise KeyError(msg)

    def matchup(self, role: str, champion: str, opponent: str) -> tuple[float, int]:
        """(shrunk win rate, games) of `champion` vs `opponent` in the same lane, high-elo solo queue."""
        games, wins = self.matchups.get((role, champion, opponent), (0, 0))
        return (wins + 0.5 * MATCHUP_PRIOR) / (games + MATCHUP_PRIOR), games


def _lineups(inp: state.Inputs) -> dict[str, list[Player]]:
    parts = inp.parts.join(inp.games.select("game_id", "started_at"), on="game_id")
    last = parts.group_by("team_id").agg(pl.col("game_id").sort_by("started_at").last())
    latest = parts.join(last, on=["team_id", "game_id"])
    out: dict[str, list[Player]] = {}
    for (team,), g in latest.group_by("team_id"):
        out[str(team)] = [
            Player(r["player_id"], r["player_name"].strip(), r["inferred_role"] or "") for r in g.iter_rows(named=True)
        ]
    return out


def champion_tags(inp: state.Inputs) -> dict[str, dict[str, float]]:
    key = dict(zip(inp.cmap["grid_name"].to_list(), inp.cmap["champion"].to_list(), strict=True))
    by_key = {r["champion"]: r for r in inp.champions.iter_rows(named=True)}
    out: dict[str, dict[str, float]] = {}
    for grid, k in key.items():
        r = by_key.get(k)
        if r is not None:
            out[grid] = {c: float(r[c]) for c in state.TAG_COLS} | {"scaling": state.SCALING.get(r["scaling"], 1.0)}
    return out


def _style(inp: state.Inputs, tags: dict[str, dict[str, float]], now: datetime) -> dict[str, Floats]:
    """A team's identity: recency-weighted mean champion tags of its picks."""
    cols = (*state.TAG_COLS, "scaling")
    picks = inp.draft.filter(pl.col("action") == "pick").join(inp.games.select("game_id", "started_at"), on="game_id")
    out: dict[str, Floats] = {}
    for (team,), g in picks.group_by("team_id"):
        total, weight = np.zeros(len(cols), np.float32), 0.0
        for champ, t in g.select("champion", "started_at").iter_rows():
            if champ in tags:
                w = 0.5 ** ((now - t).total_seconds() / 86400 / STYLE_HALF_LIFE_DAYS)
                total += w * np.array([tags[champ][c] for c in cols], np.float32)
                weight += w
        if weight:
            out[str(team)] = total / weight
    return out


def soloq_matchups(cmap: pl.DataFrame, champions: pl.DataFrame) -> dict[tuple[str, str, str], tuple[int, int]]:
    path = settings().local("aggregates") / "soloq_matchups.parquet"
    if not path.exists():
        return {}
    riot_to_grid = dict(
        champions.select("riot_id", "champion")
        .join(cmap.select("champion", "grid_name"), on="champion")
        .select("riot_id", "grid_name")
        .iter_rows()
    )
    role_of = {v: k for k, v in POSITION.items()}
    m = (
        pl.read_parquet(path)
        .group_by("position", "champion_id", "opponent_id")
        .agg(pl.col("games").sum(), pl.col("wins").sum())
    )
    out: dict[tuple[str, str, str], tuple[int, int]] = {}
    for pos, c, o, games, wins in m.iter_rows():
        if pos in role_of and c in riot_to_grid and o in riot_to_grid:
            out[role_of[pos], riot_to_grid[c], riot_to_grid[o]] = (int(games), int(wins))
    return out


def build_live() -> Live:
    inp = inputs()
    outcome_rows, act, builder = state.build_with_state(inp)
    actions = act.rows.with_row_index("idx")
    ranker = LambdaRank()
    ranker.fit(actions, act)
    model = LogisticFeatures(L3)
    model.fit(outcome_rows)
    ctx = game_context(inp.games, inp.series)
    last = ctx["started_at"].max()
    if not isinstance(last, datetime):
        raise TypeError("games.started_at must be a datetime column")
    now = last + timedelta(days=1)
    patches = sorted(inp.games["patch"].drop_nulls().unique().to_list(), key=patch_key)
    tags = champion_tags(inp)
    names = {}
    teams_path = settings().local("aggregates") / "stats_teams.parquet"
    if teams_path.exists():
        names = dict(pl.read_parquet(teams_path).select("team_id", "name").iter_rows())
    return Live(
        builder=builder,
        ranker=ranker,
        outcome=model,
        ratings=elo.current_ratings(ctx),
        team_names=names,
        lineups=_lineups(inp),
        patch=patches[-1] if patches else None,
        now=now,
        last_game=dict(
            game_context(inp.games, inp.series)
            .unpivot(["blue_team_id", "red_team_id"], index="started_at", value_name="team_id")
            .group_by("team_id")
            .agg(pl.col("started_at").max())
            .iter_rows()
        ),
        tags=tags,
        style=_style(inp, tags, now),
        matchups=soloq_matchups(inp.cmap, inp.champions),
    )


def _stamps() -> list[tuple[str, int]]:
    """(file name, modification time in ns) of every input of the live context."""
    root = settings().local()
    patterns = ("parquet/*.parquet", "static/*.parquet", "aggregates/soloq_*.parquet", "aggregates/stats_teams.parquet")
    return [(f.name, f.stat().st_mtime_ns) for pattern in patterns for f in sorted(root.glob(pattern))]


def _inputs_key() -> tuple[object, ...]:
    return CACHE_VERSION, *_stamps()


def _cache_path() -> Path:
    return settings().local("models") / f"live-v{CACHE_VERSION}.pkl"


_lock = threading.Lock()
_current: list[tuple[tuple[object, ...], Live]] = []  # at most one (key, live): older contexts are released


def _from_disk(path: Path, key: tuple[object, ...]) -> Live | None:
    try:
        stored_key, live = pickle.loads(path.read_bytes())  # noqa: S301 - our own cache file
    except OSError, pickle.UnpicklingError, EOFError, AttributeError, ImportError, ValueError:
        return None  # missing, truncated or from older code: rebuild
    return live if stored_key == key else None


def _load(key: tuple[object, ...]) -> Live:
    with _lock:  # one build at a time; concurrent requests wait for it instead of each building their own
        if _current and _current[0][0] == key:
            return _current[0][1]
        path = _cache_path()
        live = _from_disk(path, key)
        if live is None:
            live = build_live()
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(pickle.dumps((key, live)))
            tmp.replace(path)  # atomic: a crash mid-write never leaves a broken cache behind
        _current[:] = [(key, live)]
        return live


def live_ready() -> bool:
    """True when the cached live context matches the current data (no ~30 s rebuild needed)."""
    path = _cache_path()
    return path.exists() and path.stat().st_mtime_ns > max((t for _, t in _stamps()), default=0)


def get_live() -> Live:
    """The live context, from memory, the on-disk cache, or rebuilt (~30 s) when the data changed."""
    return _load(_inputs_key())
