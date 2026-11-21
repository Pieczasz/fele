"""FastAPI app. Serves aggregates and model outputs only — never raw GRID events.

Interactive docs are generated from the code: Swagger UI at /docs, ReDoc at /redoc, spec at /openapi.json.
"""

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from datetime import timedelta
from typing import TYPE_CHECKING, Annotated, Any, Literal

import polars as pl
from fastapi import Body, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from fele import prefs
from fele.api import auth, models
from fele.api.data import MissingDataError, champion_keys, ddragon_version, table
from fele.config import settings
from fele.static.ddragon import live_patch

if TYPE_CHECKING:
    from fele.engine.live import Live
    from fele.lcu.watch import Watcher

DESCRIPTION = """
**fele** (short for *Fearless Ledger*) — draft prep and Fearless series planning for League of Legends coaches.

Every statistic carries its sample size; recommendations are ranked options with reasons, never orders.
Only aggregates are served — raw GRID match data never leaves the local machine.
"""
DRAFT_TOP = 30  # champions per split in a scouting report
PLAYER_TOP = 8  # champions per player
CURRENT_WINDOW = timedelta(days=7)  # a player is "current" if they played within a week of the team's last game
META_MIN_PRESENCE = 1  # meta rows need at least one pick/ban in the window or a solo-queue sample


@contextlib.asynccontextmanager
async def lifespan(api: FastAPI) -> AsyncGenerator[None]:
    """With FELE_LCU=1 (`fele serve --lcu`), watch the local League client in the background."""
    task = None
    api.state.watcher = None
    if settings().fele_lcu:
        from fele.lcu.watch import Watcher  # noqa: PLC0415 - only when enabled

        api.state.watcher = Watcher()
        task = asyncio.create_task(api.state.watcher.run())
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    lifespan=lifespan,
    title="fele API",
    version="0.2.0",
    description=DESCRIPTION,
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=[
        {"name": "system", "description": "Health, login and service metadata."},
        {"name": "scouting", "description": "Opponent reports built from GRID pro games (aggregates only)."},
        {"name": "meta", "description": "Champion strength per patch window, pro play + high-elo solo queue."},
        {
            "name": "draft",
            "description": "Draft recommendations, live win probability and the Fearless series simulator.",
        },
        {"name": "coach", "description": "Coach and player preferences (comfort picks, prio players, save lists)."},
        {"name": "live", "description": "fele Live: champ select from the local League client (fele serve --lcu)."},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
app.middleware("http")(auth.gate)


@app.exception_handler(MissingDataError)
def missing_data(_: Request, exc: MissingDataError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=503)


class Health(BaseModel):
    status: Literal["ok"]
    service: str


# --- helpers ----------------------------------------------------------------------------------------------------
def _rate(row: dict[str, Any], prefix: str = "", k: str = "k", n: str = "n") -> models.Rate:
    return models.Rate(k=row[k], n=row[n], rate=row[f"{prefix}rate"], lo=row[f"{prefix}lo"], hi=row[f"{prefix}hi"])


def _team(team_id: str) -> models.Team:
    rows = table("stats_teams").filter(pl.col("team_id") == team_id)
    if rows.is_empty():
        raise HTTPException(404, f"No team {team_id!r}")
    return models.Team.model_validate(rows.row(0, named=True))


# --- system -----------------------------------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/health", tags=["system"], summary="Liveness check")
def health() -> Health:
    return Health(status="ok", service="fele")


@app.get("/info", tags=["system"], summary="Data Dragon version, live patch, whether a login is needed")
def info() -> models.Info:
    return models.Info(ddragon_version=ddragon_version(), live_patch=live_patch(), demo_protected=auth.protected())


@app.post("/login", tags=["system"], summary="Unlock the hosted demo", status_code=204)
async def login(password: Annotated[str, Body(embed=True)], request: Request, response: Response) -> None:
    if not await auth.login(password, request, response):
        raise HTTPException(401, "Wrong password")


@app.post("/logout", tags=["system"], summary="End the demo session", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(auth.COOKIE)


# --- scouting ---------------------------------------------------------------------------------------------------
@app.get("/teams", tags=["scouting"], summary="Teams with games in the data")
def teams() -> list[models.Team]:
    return [models.Team.model_validate(r) for r in table("stats_teams").iter_rows(named=True)]


@app.get("/teams/{team_id}/scouting", tags=["scouting"], summary="Draft priorities and who opponents ban against")
def scouting(team_id: str, period: models.Period = "recent") -> models.Scouting:
    """Presence (picked or banned by the team) per champion, overall and by side and game number in the series."""
    team = _team(team_id)
    keys = champion_keys()
    draft = (
        table("stats_team_draft")
        .filter(pl.col("team_id") == team_id, pl.col("period") == period)
        .sort("k", "picks", descending=True)
        .group_by("split_type", "split", maintain_order=True)
        .head(DRAFT_TOP)
    )
    rows = [
        models.DraftRow(
            **_rate(r).model_dump(),
            champion=r["champion"],
            key=keys.get(r["champion"]),
            split_type=r["split_type"],
            split=r["split"],
            picks=r["picks"],
            bans=r["bans"],
            base_rate=r["base_rate"],
            first_rotation=_rate(r, "first_rotation_", k="first_rotation"),
            avg_slot=r["avg_slot"],
            tendency=r["tendency"],
        )
        for r in draft.iter_rows(named=True)
    ]
    targets = table("stats_ban_targets").filter(pl.col("team_id") == team_id, pl.col("period") == period)
    targeted = [
        models.TargetedPlayer(
            **_rate(r).model_dump(),
            player=r["target_player"],
            role=r["target_role"],
            champions=[
                models.ChampionCount(champion=c["champion"], key=keys.get(c["champion"]), count=c["count"])
                for c in r["champions"]
            ],
        )
        for r in targets.iter_rows(named=True)
    ]
    games = next((r.n for r in rows if r.split_type == "all"), 0)
    return models.Scouting(team=team, period=period, games=games, draft=rows, targeted_players=targeted)


@app.get("/teams/{team_id}/macro", tags=["scouting"], summary="Jungle starts, first objectives, timings, early kills")
def macro(team_id: str, period: models.Period = "recent") -> models.Macro:
    """Positions are event-time snapshots and the feed has no normal camp events (see docs/METHODOLOGY.md)."""
    team = _team(team_id)

    def mine(name: str) -> pl.DataFrame:
        return table(name).filter(pl.col("team_id") == team_id, pl.col("period") == period)

    rates = [
        models.MacroRate(
            **_rate(r).model_dump(),
            metric=r["metric"],
            split=r["split"],
            base_rate=r["base_rate"],
            tendency=r["tendency"],
        )
        for r in mine("stats_macro_rates").iter_rows(named=True)
    ]
    timings = [models.MacroTiming.model_validate(r) for r in mine("stats_macro_timings").iter_rows(named=True)]
    cells = mine("stats_early_kills")
    games = dict(cells.select("side", "n").unique().iter_rows())
    early = [models.KillCell.model_validate(r) for r in cells.iter_rows(named=True)]
    return models.Macro(
        team=team,
        period=period,
        games=next((r.n for r in rates if r.metric == "got_first_blood" and r.split == "all"), 0),
        rates=rates,
        timings=timings,
        early_kills=early,
        games_by_side=games,
    )


@app.get("/teams/{team_id}/players", tags=["scouting"], summary="Player champion pools and comfort")
def players(team_id: str) -> models.Players:
    """Players whose latest game was for this team, with their most comfortable champions (pro games)."""
    team = _team(team_id)
    keys = champion_keys()
    summary = table("stats_players").filter(pl.col("team_id") == team_id)
    champs = table("stats_player_champions").filter(pl.col("player_id").is_in(summary["player_id"].implode()))
    last = dict(champs.group_by("player_id").agg(pl.col("last_played").max()).iter_rows())
    order = {r: i for i, r in enumerate(prefs.Role)}
    out: list[models.Player] = []
    for p in sorted(summary.iter_rows(named=True), key=lambda r: (order.get(r["role"], 9), -r["n"])):
        top = champs.filter(pl.col("player_id") == p["player_id"]).sort("comfort", descending=True).head(PLAYER_TOP)
        last_game = last[p["player_id"]]
        out.append(
            models.Player(
                player_id=p["player_id"],
                name=p["player_name"],
                role=p["role"],
                current=last_game >= team.last_game - CURRENT_WINDOW,
                last_game=last_game,
                n=p["n"],
                unique_champions=p["unique_champions"],
                effective_pool=p["effective_pool"],
                effective_pool_lo=p["effective_pool_lo"],
                effective_pool_hi=p["effective_pool_hi"],
                depth=p["depth"],
                meta_overlap=_rate(p, "meta_overlap_", k="meta_k", n="meta_n"),
                champions=[
                    models.PlayerChampion(
                        **_rate(c).model_dump(),
                        champion=c["champion"],
                        key=keys.get(c["champion"]),
                        shrunk=c["shrunk"],
                        shrunk_lo=c["shrunk_lo"],
                        shrunk_hi=c["shrunk_hi"],
                        recent_games=c["recent_games"],
                        comfort=c["comfort"],
                        last_played=c["last_played"],
                    )
                    for c in top.iter_rows(named=True)
                ],
            )
        )
    out.sort(key=lambda player: not player.current)  # current lineup first, role order kept within each group
    return models.Players(team=team, players=out)


MACRO_TEXT = {
    "jungle_top_start": (
        "Jungler starts on the top half",
        "expect early top-side pressure; plan the invade or counter",
    ),
    "got_first_scuttle": ("Wins the first scuttle", "contest the river at ~3:30 or trade elsewhere"),
    "got_first_blood": ("Gets first blood", "respect their early skirmishing"),
    "got_first_tower": ("Takes the first tower", "expect early lane swaps/plates focus"),
    "got_first_drake": ("Takes the first drake", "decide early whether to contest or trade for grubs"),
    "got_first_grubs": ("Takes the first grubs", "decide early whether to contest or trade for drake"),
    "got_first_herald": ("Takes the first herald", "track their jungler around 14:00"),
    "grubs_before_drake": ("Prioritises grubs before drake", "the bot side is where they give ground early"),
}
CARD_MIN_GAMES = 5


def _draft_cards(team_id: str) -> list[models.Card]:
    draft = table("stats_team_draft").filter(pl.col("team_id") == team_id, pl.col("period") == "all")
    g1 = draft.filter(pl.col("split") == "G1", pl.col("n") >= CARD_MIN_GAMES, pl.col("first_rotation") >= 3)  # noqa: PLR2004
    cards = [
        models.Card(
            kind="draft",
            title=f"{r['champion']} is a game-1 priority",
            detail=f"They take it (pick or ban) in their first rotation in {r['first_rotation_rate']:.0%} of game "
            "1s. Ban it, or have a plan for facing it, when you draft game 1.",
            evidence=f"{r['first_rotation']}/{r['n']} game 1s",
            strength="descriptive",
            champions=[r["champion"]],
        )
        for r in g1.sort("first_rotation_rate", descending=True).head(2).iter_rows(named=True)
    ]
    strong = draft.filter(
        pl.col("split") == "all", pl.col("tendency") == "strong", pl.col("rate") > pl.col("base_rate")
    )
    top = strong.with_columns(gap=pl.col("rate") - pl.col("base_rate")).sort("gap", descending=True).head(2)
    cards.extend(
        models.Card(
            kind="draft",
            title=f"They prioritise {r['champion']} far more than their league",
            detail=f"Picked or banned in {r['rate']:.0%} of their games vs {r['base_rate']:.0%} league-wide "
            f"({r['picks']} picks, {r['bans']} bans). Not chance (survives the multiple-testing correction).",
            evidence=f"{r['k']}/{r['n']} games",
            strength="strong",
            champions=[r["champion"]],
        )
        for r in top.iter_rows(named=True)
    )
    return cards


def _player_cards(team_id: str) -> list[models.Card]:
    cards: list[models.Card] = []
    try:
        pool = players(team_id).players
    except HTTPException:
        pool = []
    current = [p for p in pool if p.current]
    targets = table("stats_ban_targets").filter(
        pl.col("team_id") == team_id,
        pl.col("period") == "all",
        pl.col("target_player").is_in([p.name for p in current]),  # players who left don't get a card
    )
    for r in targets.sort("k", descending=True).head(1).iter_rows(named=True):
        champs = [c["champion"] for c in r["champions"][:3]]
        cards.append(
            models.Card(
                kind="players",
                title=f"{r['target_player']} is the player opponents fear",
                detail=f"{r['rate']:.0%} of the bans they face hit {r['target_player']}'s pool ({', '.join(champs)}). "
                "Their draft is built around keeping that player on comfort.",
                evidence=f"{r['k']}/{r['n']} bans faced",
                strength="descriptive",
                champions=champs,
            )
        )
    regulars = [p for p in current if p.n >= 20]  # noqa: PLR2004
    if regulars:
        thin = min(regulars, key=lambda p: p.effective_pool)
        top = [c.champion for c in thin.champions[:3]]
        cards.append(
            models.Card(
                kind="players",
                title=f"{thin.name} has the shallowest pool",
                detail=f"About {thin.effective_pool:.1f} equally-played champions over {thin.n} pro games; most "
                f"comfortable: {', '.join(top)}. Targeted bans and Fearless depletion hit hardest here.",
                evidence=f"n={thin.n} games, 95% {thin.effective_pool_lo:.1f}–{thin.effective_pool_hi:.1f}",
                strength="descriptive",
                champions=top,
            )
        )
    return cards


def _macro_cards(team_id: str) -> list[models.Card]:
    rates = table("stats_macro_rates").filter(
        pl.col("team_id") == team_id,
        pl.col("period") == "all",
        pl.col("split") == "all",
        pl.col("tendency") != "noise",
        pl.col("rate") > pl.col("base_rate"),  # the card texts describe doing it MORE than the league
    )
    cards: list[models.Card] = []
    for r in rates.sort("p").head(3).iter_rows(named=True):
        what, todo = MACRO_TEXT.get(r["metric"], (r["metric"], ""))
        cards.append(
            models.Card(
                kind="macro",
                title=f"{what}: {r['rate']:.0%} vs {r['base_rate']:.0%} league",
                detail=f"{todo.capitalize()}."
                + (" Positions are event snapshots, not tracking." if r["metric"] == "jungle_top_start" else ""),
                evidence=f"{r['k']}/{r['n']} games",
                strength=r["tendency"],
            )
        )
    return cards


def _model_cards(team_id: str) -> list[models.Card]:
    """Their likeliest first bans / first pick, from the draft model (only if the live context is already built)."""
    from fele.engine import recommend  # noqa: PLC0415 - heavy
    from fele.engine.draft import DraftState  # noqa: PLC0415
    from fele.engine.live import get_live, live_ready  # noqa: PLC0415

    if not live_ready():
        return []
    live = get_live()
    us = prefs.load().team
    try:
        m = recommend.matchup(live, us, team_id, we_are_blue=True)
    except KeyError:
        return []
    first_ban = recommend.action_probs(m, [DraftState(we_pick_first=True).play("")])[0]
    first_pick = recommend.action_probs(m, [DraftState(we_pick_first=False, actions=("",) * 6)])[0]
    cards: list[models.Card] = []
    for probs, what in ((first_ban, "first ban"), (first_pick, "first pick (when they pick first)")):
        top = [int(i) for i in probs.argsort()[::-1][:3]]
        names = [live.vocab[i] for i in top]
        cards.append(
            models.Card(
                kind="model",
                title=f"Their likeliest {what} vs {us}",
                detail=", ".join(f"{live.vocab[i]} {probs[i]:.0%}" for i in top) + ". Draft-model estimate; the actual "
                "pick or ban was in its top 10 71% of the time (walk-forward).",
                evidence="model (LambdaRank)",
                strength="model",
                champions=names,
            )
        )
    return cards


@app.get("/teams/{team_id}/cards", tags=["scouting"], summary='"How to win" cards with their evidence')
def team_cards(team_id: str) -> list[models.Card]:
    """Short, evidence-backed insights from the statistics (all games) and the draft model."""
    _team(team_id)
    return [*_draft_cards(team_id), *_player_cards(team_id), *_macro_cards(team_id), *_model_cards(team_id)]


# --- meta -------------------------------------------------------------------------------------------------------
@app.get("/meta", tags=["meta"], summary="Champion meta score per patch window")
def meta(window: Annotated[str, Query(description="`live` or a GRID patch such as 16.17")] = "live") -> models.Meta:
    """Pro presence, shrunk pro and solo-queue win rates and the patch delta, combined into one documented score."""
    all_meta = table("stats_meta")
    windows = table("stats_windows")
    names = windows["window"].unique(maintain_order=True).to_list()
    if window not in names:
        raise HTTPException(404, f"Unknown window {window!r}")
    roles = dict(table("champions", "static").select("champion", pl.col("roles").str.split("|")).iter_rows())
    rows = all_meta.filter(
        pl.col("window") == window, (pl.col("k") >= META_MIN_PRESENCE) | pl.col("soloq_n").is_not_null()
    ).drop_nulls("champion")
    return models.Meta(
        window=window,
        windows=names,
        patches=windows.filter(pl.col("window") == window)["patch"].to_list(),
        live_patch=live_patch(),
        rows=[
            models.MetaRow(
                champion=r["champion"],
                name=r["name"],
                roles=roles.get(r["champion"], []),
                presence=models.Rate(
                    k=r["k"], n=r["games"], rate=r["presence"], lo=r["presence_lo"], hi=r["presence_hi"]
                ),
                picks=r["picks"],
                bans=r["bans"],
                pro_n=r["pro_n"],
                pro_wr=r["pro_wr"],
                pro_wr_lo=r["pro_wr_lo"],
                pro_wr_hi=r["pro_wr_hi"],
                soloq_n=r["soloq_n"],
                soloq_wr=r["soloq_wr"],
                soloq_wr_lo=r["soloq_wr_lo"],
                soloq_wr_hi=r["soloq_wr_hi"],
                delta=r["delta"],
                meta_score=r["meta_score"],
            )
            for r in rows.iter_rows(named=True)
        ],
    )


@app.get("/coverage", tags=["meta"], summary="How much data is behind the numbers")
def coverage() -> models.Coverage:
    tgm = table("stats_team_game_macro")
    leagues = (
        tgm.group_by("league")
        .agg(
            teams=pl.col("team_id").n_unique(),
            games=pl.col("game_id").n_unique(),
            first_game=pl.col("started_at").min(),
            last_game=pl.col("started_at").max(),
        )
        .sort("games", descending=True)
    )
    try:
        soloq = table("soloq_champion_patch").group_by("patch").agg(pl.col("matches").first()).sort("patch")
    except MissingDataError:
        soloq = pl.DataFrame(schema={"patch": pl.String, "matches": pl.Int64})
    return models.Coverage(
        leagues=[models.LeagueCoverage.model_validate(r) for r in leagues.iter_rows(named=True)],
        soloq=[models.SoloqCoverage.model_validate(r) for r in soloq.iter_rows(named=True)],
        teams=teams(),
    )


# --- draft engine (Phase 9) -------------------------------------------------------------------------------------


def _key_map() -> dict[str, str]:
    return champion_keys()


@app.get("/champions", tags=["draft"], summary="Champions for the draft board")
def champions() -> list[models.ChampionInfo]:
    keys = _key_map()
    roles = dict(table("champions", "static").select("champion", pl.col("roles").str.split("|")).iter_rows())
    return [models.ChampionInfo(name=n, key=k, roles=roles.get(k, [])) for n, k in sorted(keys.items())]


def _check_champions(live: Live, names: list[str]) -> None:
    """A typo must not be silently ignored (the engine would draft as if that slot were empty)."""
    unknown = sorted({c for c in names if c and c not in live.builder.index})
    if unknown:
        raise HTTPException(422, f"Unknown champion(s): {', '.join(unknown)}")


@app.post("/draft/recommend", tags=["draft"], summary="Ranked options for our next pick/ban, with reasons")
def draft_recommend(req: models.DraftRequest) -> models.DraftAdvice:
    """Options, never orders: each comes with its evidence. The live win probability completes the draft many times
    with the draft-action model and averages the outcome model (Elo-dominated; see docs/MODEL_CARD.md)."""
    from fele.engine import comp, recommend  # noqa: PLC0415 - heavy; only for draft requests
    from fele.engine.draft import THEM, US, DraftState  # noqa: PLC0415
    from fele.engine.live import get_live  # noqa: PLC0415

    live = get_live()
    try:
        m = recommend.matchup(
            live,
            req.us,
            req.them,
            we_are_blue=req.we_are_blue,
            game_number=req.game_number,
            series_score=req.series_score,
        )
        _check_champions(live, [*req.actions, *req.locked, *req.save])
        s = DraftState(req.we_pick_first, locked=frozenset(req.locked))
        for c in req.actions:
            s = s.play(c)
    except (KeyError, ValueError) as e:
        raise HTTPException(422, str(e)) from e
    prefs_ = req.preferences or prefs.load()
    team_name = live.team_names.get(m.them, req.them)
    options = recommend.recommend(m, s, prefs_, req.mode, enemy_name=team_name, save=req.save)
    likely: list[models.Likely] = []
    if not s.complete and s.who(s.slot) == THEM:
        probs = recommend.action_probs(m, [s])[0]
        top = [int(i) for i in probs.argsort()[::-1][: recommend.TOP_N]]
        likely = [
            models.Likely(champion=live.vocab[i], key=_key_map().get(live.vocab[i]), probability=float(probs[i]))
            for i in top
        ]
    mean, p10, p90 = recommend.rollout_win_prob(m, s)
    keys = _key_map()
    nxt = (
        None
        if s.complete
        else models.NextAction.model_validate(
            {"slot": s.slot, "who": s.who(s.slot), "kind": s.kind(s.slot), "phase": s.phase(s.slot)}
        )
    )

    def comp_out(result: comp.Comp) -> models.CompOut:
        return models.CompOut.model_validate(result, from_attributes=True)

    return models.DraftAdvice(
        next=nxt,
        options=[
            models.OptionOut(
                champion=o.champion,
                key=keys.get(o.champion),
                role=o.role,
                score=o.score,
                parts=o.parts,
                reasons=o.reasons,
                win_prob=o.win_prob,
            )
            for o in options
        ],
        likely=likely,
        win_prob=models.WinProb(mean=mean, p10=p10, p90=p90),
        our_comp=comp_out(comp.analyze(live.tags, s.picks(US))),
        their_comp=comp_out(comp.analyze(live.tags, s.picks(THEM))),
    )


@app.post("/series/simulate", tags=["draft"], summary="Monte Carlo of a Fearless Bo3/Bo5, optionally with a save plan")
def series_simulate(req: models.SeriesRequest) -> models.SeriesPlan:
    from fele.engine import series  # noqa: PLC0415 - heavy
    from fele.engine.live import get_live  # noqa: PLC0415

    live = get_live()
    _check_champions(live, [*req.locked, *req.save])
    sims = req.sims
    prefs_ = req.preferences or prefs.load()
    start = series.SeriesStart(
        game=req.start_game,
        wins=req.wins,
        losses=req.losses,
        locked=frozenset(req.locked),
        we_first=req.we_start_blue if req.we_first_next is None else req.we_first_next,
        we_blue=req.we_blue_next,
    )

    def run(save: dict[str, int]) -> series.SeriesResult:
        return series.simulate(
            live,
            req.us,
            req.them,
            best_of=req.best_of,
            prefs=prefs_,
            save=save,
            sims=sims,
            start=start,
            key_champions=req.key_champions or None,
        )

    try:
        plan = run(req.save)
        base = run({}) if req.save else None
    except KeyError as e:
        raise HTTPException(422, str(e)) from e
    diff = se = None
    if base is not None:
        diff = plan.series_win - base.series_win
        se = float((plan.series_win_se**2 + base.series_win_se**2) ** 0.5)
    return models.SeriesPlan(
        plan=models.SeriesOut.model_validate(plan, from_attributes=True),
        no_plan=models.SeriesOut.model_validate(base, from_attributes=True) if base else None,
        difference=diff,
        difference_se=se,
        within_noise=None if diff is None or se is None else abs(diff) < 2 * se,
    )


# --- coach ------------------------------------------------------------------------------------------------------
@app.get("/preferences", tags=["coach"], summary="Current coach preferences")
def preferences() -> prefs.Preferences:
    """Coach input from `config/preferences.yaml`, falling back to the example file."""
    return prefs.load()


# --- fele Live (local League client) --------------------------------------------------------------------------------
class _AdviceCache:
    version = -1
    advice: models.LiveAdvice | None = None


@app.get("/lcu/state", tags=["live"], summary="League client status, champ select and advice")
async def lcu_state(request: Request) -> models.LiveState:
    """What the local client shows now (party members by name, other allies as "Ally", enemies hidden), with ranked
    options for the action in progress. Advice is recomputed only when the draft or a party pool changes."""
    from fele.engine.solo import load_solo  # noqa: PLC0415 - heavy modules only when used
    from fele.lcu import view  # noqa: PLC0415

    watcher: Watcher | None = getattr(request.app.state, "watcher", None)
    data = load_solo()
    cs = watcher.snapshot.champ_select if watcher else None
    if watcher and cs and _AdviceCache.version != watcher.version:
        _AdviceCache.advice, _AdviceCache.version = view.advice(data, cs, watcher), watcher.version
    return view.live_state(data, watcher, _AdviceCache.advice)
