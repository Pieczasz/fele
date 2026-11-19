"""FastAPI app. Serves aggregates and model outputs only — never raw GRID events.

Interactive docs are generated from the code: Swagger UI at /docs, ReDoc at /redoc, spec at /openapi.json.
"""

from datetime import timedelta
from typing import Annotated, Any, Literal

import polars as pl
from fastapi import Body, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from fele import prefs
from fele.api import auth, models
from fele.api.data import MissingDataError, champion_keys, ddragon_version, table
from fele.static.ddragon import live_patch

DESCRIPTION = """
**fele** (short for *Fearless Ledger*) — draft prep and Fearless series planning for League of Legends coaches.

Every statistic carries its sample size; recommendations are ranked options with reasons, never orders.
Only aggregates are served — raw GRID match data never leaves the local machine.
"""
DRAFT_TOP = 30  # champions per split in a scouting report
PLAYER_TOP = 8  # champions per player
CURRENT_WINDOW = timedelta(days=7)  # a player is "current" if they played within a week of the team's last game
META_MIN_PRESENCE = 1  # meta rows need at least one pick/ban in the window or a solo-queue sample

app = FastAPI(
    title="fele API",
    version="0.2.0",
    description=DESCRIPTION,
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=[
        {"name": "system", "description": "Health, login and service metadata."},
        {"name": "scouting", "description": "Opponent reports built from GRID pro games (aggregates only)."},
        {"name": "meta", "description": "Champion strength per patch window, pro play + high-elo solo queue."},
        {"name": "coach", "description": "Coach and player preferences (comfort picks, prio players, save lists)."},
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


# --- coach ------------------------------------------------------------------------------------------------------
@app.get("/preferences", tags=["coach"], summary="Current coach preferences")
def preferences() -> prefs.Preferences:
    """Coach input from `config/preferences.yaml`, falling back to the example file."""
    return prefs.load()
