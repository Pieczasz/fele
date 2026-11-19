"""`fele` command-line entry points (run with `uv run fele --help`)."""

import asyncio
from collections import Counter
from typing import NoReturn

import httpx
import typer
import yaml

from fele.config import settings

MIN_GAMES_TO_SHOW = 20

app = typer.Typer(no_args_is_help=True, help="fele engine CLI")


def die(msg: str) -> NoReturn:
    typer.echo(msg, err=True)
    raise typer.Exit(1)


@app.command()
def grid_summary() -> None:
    """Aggregate overview of the local GRID LoL data (counts only, no raw rows)."""
    from fele.ingest.grid import read_meta, series_index
    from fele.static.ddragon import patch_key

    s = settings()
    if not s.lol_dir.exists():
        die(f"GRID data not found at {s.stl_data_dir} — clone it or set STL_DATA_DIR")
    series, games, rosters = series_index(), read_meta("games"), read_meta("rosters")
    patches = Counter(g["patch"] or "<empty>" for g in games)
    c9 = [g for g in games if "Cloud9" in g["team1_name"] + g["team2_name"]]
    numbers = Counter(int(g["game_number"]) for g in games)
    typer.echo(f"series={len(series)} games={len(games)} roster_rows={len(rosters)}")
    numeric = sorted((p for p in patches if p[0].isdigit()), key=patch_key)
    typer.echo(f"patches: {len(patches)} distinct, {numeric[0]} .. {numeric[-1]}")
    typer.echo(f"games by number in series: {dict(sorted(numbers.items()))}")
    typer.echo(f"Cloud9 games: {len(c9)}  events: {sorted(Counter(r['event'] for r in series))[:3]}...")


@app.command()
def fetch_ddragon() -> None:
    """Cache Data Dragon (championFull, items, summoners) for every patch since 15.1, plus the latest icons."""
    from fele.static import ddragon as dd
    from fele.static.build import FIRST_PATCH

    with httpx.Client(timeout=60, follow_redirects=True) as c:
        wanted = dd.versions_since(FIRST_PATCH, dd.refresh_versions(c))
        for v in wanted:
            for name in ("championFull", "item", "summoner"):
                dd.fetch(c, v, name)
        latest = wanted[-1]
        for key in dd.cached(latest, "championFull")["data"]:
            dd.fetch_champion_icon(c, latest, key)
    typer.echo(f"Data Dragon {wanted[0]} .. {latest}: {len(wanted)} versions cached (+ latest champion icons)")


@app.command()
def static() -> None:
    """Build static tables (champion mapping, tags, patch deltas) into data_local/static and refresh the DB."""
    from fele.db import build_catalog
    from fele.ingest.build import parquet_dir
    from fele.static.build import build, role_gaps, static_dir

    for name, n in build().items():
        typer.echo(f"{name}: {n}")
    build_catalog()
    typer.echo(f"-> {static_dir()} (DuckDB schema `static`)")
    if (parquet_dir() / "participants.parquet").exists():
        gaps = role_gaps()
        typer.echo(f"pro roles missing from champion_tags.csv: {gaps.rows() if gaps.height else 'none'}")


@app.command()
def riot_check(platform: str = "euw1") -> None:
    """Smoke-test the Riot API key and print the rate limits (never prints the key)."""
    key = settings().riot_api_key
    if not key:
        die("RIOT_DEVELOPER_PLATFORM_API_KEY is not set in .env")
    r = httpx.get(
        f"https://{platform}.api.riotgames.com/lol/status/v4/platform-data",
        headers={"X-Riot-Token": key.get_secret_value()},
        timeout=15,
    )
    typer.echo(
        f"status={r.status_code} app-limit={r.headers.get('X-App-Rate-Limit')} "
        f"method-limit={r.headers.get('X-Method-Rate-Limit')}"
    )
    if r.status_code in (401, 403):
        typer.echo("Key rejected — development keys expire every 24h; regenerate at developer.riotgames.com")


@app.command()
def sample_soloq(
    platforms: str = "kr,euw1,na1",
    matches: int = 300,
    days: int = 14,
    patch: str | None = None,
    timeline_share: float = 0.25,
) -> None:
    """Sample high-elo ranked solo matches per platform (resumable; cached). Counts only `patch` (default: live)."""
    from fele.external.riot import RiotClient
    from fele.external.soloq import sample
    from fele.static.ddragon import live_patch

    target = patch or live_patch()
    names = [p.strip() for p in platforms.split(",")]

    async def run() -> tuple[list[dict[str, int]], int]:
        async with RiotClient() as rc:  # one client: platforms share regional rate limits (euw1/eun1 → europe)
            jobs = (sample(rc, p, matches, days, patch=target, timeline_share=timeline_share) for p in names)
            return await asyncio.gather(*jobs), rc.throttled

    results, throttled = asyncio.run(run())
    for p, counts in zip(names, results, strict=True):
        typer.echo(f"{p}: {counts} (patch {target})")
    typer.echo(f"429 responses: {throttled}")


@app.command()
def soloq_aggregate() -> None:
    """Build data_local/aggregates/soloq_{champion_patch,matchups,items}.parquet from sampled matches."""
    from fele.db import build_catalog, write_tables
    from fele.external.soloq import champion_patch_table, items_table, matchup_table, sample_rows

    rows = sample_rows()
    tables = {
        "soloq_champion_patch": champion_patch_table(rows),
        "soloq_matchups": matchup_table(rows),
        "soloq_items": items_table(rows),
    }
    if tables["soloq_champion_patch"].is_empty():
        die("No sampled matches yet — run `fele sample-soloq` first")
    for name, n in write_tables(settings().local("aggregates"), tables).items():
        typer.echo(f"{name}: {n} rows")
    build_catalog()
    champ = tables["soloq_champion_patch"]
    typer.echo(champ.filter(champ["games"] >= MIN_GAMES_TO_SHOW).sort("win_rate", descending=True).head(10))


@app.command()
def player_soloq(days: int = 30, max_matches: int = 100) -> None:
    """Recent solo-queue champion pools for Riot IDs the coach entered in config/preferences.yaml (off if none)."""
    from fele import prefs
    from fele.external.player_soloq import pools

    p = prefs.load()
    if not any(pl.riot_ids for pl in p.players):
        die("No riot_ids in config/preferences.yaml — this feature stays off until the coach enters them")
    df = asyncio.run(pools(p, days, max_matches))
    out = settings().local("aggregates") / "player_soloq_pool.parquet"
    df.write_parquet(out)
    typer.echo(f"{df.height} player-champion rows -> {out}")


def _team_roles(team: str) -> list[tuple[str, str, list[tuple[str, int]]]]:
    """Latest lineup of `team` with each player's usual inferred role and top champions (needs `fele ingest`)."""
    import polars as pl

    from fele.ingest.build import parquet_dir
    from fele.ingest.grid import read_meta

    src = parquet_dir() / "participants.parquet"
    if not src.exists():
        die("Run `fele ingest` first (roles come from data_local/parquet/participants.parquet)")
    games = pl.read_parquet(parquet_dir() / "games.parquet").select("game_id", "started_at")
    rows = pl.read_parquet(src).join(games, on="game_id")
    team_ids = [t["team_id"] for t in read_meta("teams") if t["name"] == team]
    rows = rows.filter(pl.col("team_id").is_in(team_ids))
    if rows.is_empty():
        die(f"No games for {team!r}")
    latest = rows.sort("started_at").tail(1)["game_id"].item()
    out: list[tuple[str, str, list[tuple[str, int]]]] = []
    for p in rows.filter(pl.col("game_id") == latest).iter_rows(named=True):
        mine = rows.filter(pl.col("player_id") == p["player_id"])
        roles = mine["inferred_role"].drop_nulls()
        if roles.is_empty():  # role inference skipped every game of this player: let the coach fill it in
            typer.echo(f"{p['player_name']}: no inferred role, left out", err=True)
            continue
        role = str(roles.mode().sort().first())
        pool = mine.group_by("champion").len().sort(["len", "champion"], descending=[True, False])
        out.append((p["player_name"].strip(), role, [(c, n) for c, n in pool.rows()]))
    return out


@app.command()
def prefs_init(team: str = "Cloud9 Kia", top_n: int = 6, force: bool = False) -> None:
    """Pre-fill config/preferences.yaml (gitignored) with the team's latest lineup, inferred roles and top champions."""
    from fele.prefs import SeriesStrategy

    dest = settings().fele_config_dir / "preferences.yaml"
    if dest.exists() and not force:
        die(f"{dest} exists — edit it directly, or pass --force to overwrite")
    lineup = _team_roles(team)
    doc: dict[str, object] = {
        "team": team,
        "weight": 0.5,
        "players": [
            {
                "name": name,
                "role": role,
                "riot_ids": [],
                "wants_prio": False,
                "pool": [
                    {"champion": c, "comfort": "comfortable", "note": f"{n} pro games in GRID data"}
                    for c, n in pool[:top_n]
                ],
                "hates_playing_against": [],
            }
            for name, role, pool in lineup
        ],
        "strategy": SeriesStrategy().model_dump(),
    }
    dest.write_text(
        "# Generated by `fele prefs-init` — roles inferred from games; edit comfort tiers and notes.\n"
        + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    )
    typer.echo(f"wrote {dest} ({len(lineup)} players from the latest game)")


HF_DATASET = "https://huggingface.co/datasets/gptilt/lol-esports-matches/resolve/main"


@app.command()
def fetch_leaguepedia_hf() -> None:
    """Download the CC BY-SA 3.0 Leaguepedia mirror (gptilt/lol-esports-matches) into data_local/external.

    Attribution: Leaguepedia (lol.fandom.com) contributors, CC BY-SA 3.0, via the gptilt Hugging Face dataset.
    Kept local; never mixed into GRID-derived files.
    """
    import polars as pl

    out = settings().local("external", "leaguepedia_hf")
    with httpx.Client(timeout=120, follow_redirects=True) as c:
        for name in ("games", "matches", "tournaments"):
            r = c.get(f"{HF_DATASET}/{name}/{name}.parquet")
            r.raise_for_status()
            (out / f"{name}.parquet").write_bytes(r.content)
            df = pl.read_parquet(out / f"{name}.parquet")
            typer.echo(f"{name}: {df.height} rows, {len(df.columns)} cols, {len(r.content) / 1e6:.1f} MB")


@app.command()
def ingest(workers: int | None = None) -> None:
    """Replay every GRID LoL feed into Parquet tables (data_local/parquet) with inferred roles, then refresh the DB."""
    from fele.db import build_catalog
    from fele.ingest.build import build, parquet_dir

    if not settings().lol_dir.exists():
        die(f"GRID data not found at {settings().stl_data_dir} — clone it or set STL_DATA_DIR")
    counts = build(workers)
    for name, n in counts.items():
        typer.echo(f"{name}: {n}")
    build_catalog()
    typer.echo(f"-> {parquet_dir()} (DuckDB schema `lol`)")


@app.command()
def stats() -> None:
    """Phase 5 statistics (draft priority, pools, Elo, macro, meta) -> data_local/aggregates/stats_*.parquet."""
    from fele.db import build_catalog
    from fele.stats.build import build

    for name, n in build().items():
        typer.echo(f"{name}: {n}")
    build_catalog()


@app.command()
def evaluate(model: str = "baseline_elo", mlflow: bool = True) -> None:
    """Walk-forward evaluation of a model and all baselines -> docs/experiments/<date>-<model>.md (+ MLflow run)."""
    from fele.eval import run
    from fele.models.baselines import ACTION_MODELS, OUTCOME_MODELS

    if model not in {*OUTCOME_MODELS, *ACTION_MODELS}:
        die(f"Unknown model {model!r}; choose from {sorted({*OUTCOME_MODELS, *ACTION_MODELS})}")
    data, res = run.evaluate(model)
    path = run.write_report(model, run.report(model, data, res))
    typer.echo(f"report -> {path}")
    if mlflow:
        typer.echo(f"MLflow run {run.log_mlflow(model, res, path)} (data_local/mlflow.db)")


@app.command()
def db() -> None:
    """Build data_local/fele.duckdb: views over GRID meta, Leaguepedia, solo-queue data (open it in PyCharm)."""
    from fele.db import build_catalog, db_path

    for schema, views in build_catalog().items():
        typer.echo(f"{schema}: {', '.join(views)}")
    typer.echo(f"-> {db_path()}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = True) -> None:
    """Run the API (http://localhost:8000/docs)."""
    import uvicorn

    uvicorn.run("fele.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
