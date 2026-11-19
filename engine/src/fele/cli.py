"""`fele` command-line entry points (run with `uv run fele --help`)."""

import asyncio
from collections import Counter, defaultdict
from typing import Annotated, NoReturn

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

    s = settings()
    if not s.lol_dir.exists():
        die(f"GRID data not found at {s.stl_data_dir} — clone it or set STL_DATA_DIR")
    series, games, rosters = series_index(), read_meta("games"), read_meta("rosters")
    patches = Counter(g["patch"] or "<empty>" for g in games)
    c9 = [g for g in games if "Cloud9" in g["team1_name"] + g["team2_name"]]
    numbers = Counter(int(g["game_number"]) for g in games)
    typer.echo(f"series={len(series)} games={len(games)} roster_rows={len(rosters)}")
    typer.echo(
        f"patches: {len(patches)} distinct, {min(p for p in patches if p[0].isdigit())} .. "
        f"{max(patches, key=lambda p: tuple(map(int, p.split('.'))) if p[0].isdigit() else (0,))}"
    )
    typer.echo(f"games by number in series: {dict(sorted(numbers.items()))}")
    typer.echo(f"Cloud9 games: {len(c9)}  events: {sorted(Counter(r['event'] for r in series))[:3]}...")


@app.command()
def fetch_ddragon(
    all_patches: Annotated[bool, typer.Option(help="Also fetch champion.json for every GRID patch")] = True,
) -> None:
    """Download Data Dragon static data (champions, items, summoners, icons) into data_local/ddragon."""
    from fele.ingest.grid import read_meta
    from fele.static import champions as ch
    from fele.static import ddragon as dd

    with httpx.Client(timeout=30, follow_redirects=True) as c:
        vs = dd.versions(c)
        latest = vs[0]
        typer.echo(f"latest Data Dragon version: {latest}")
        champs = dd.champions(c, latest, full=True)
        dd.items(c, latest)
        dd.summoners(c, latest)
        for key in champs["data"]:
            dd.champion_icon(c, latest, key)
        typer.echo(f"latest: {len(champs['data'])} champions + icons, items, summoners cached")

        if all_patches and settings().meta_dir.exists():
            patches = sorted(
                {g["patch"] for g in read_meta("games") if g["patch"]},
                key=lambda patch: tuple(map(int, patch.split("."))),
            )
            missing: list[str] = []
            for p in patches:
                v = dd.version_for_patch(p, vs)
                if v:
                    dd.champions(c, v)
                else:
                    missing.append(p)
            typer.echo(f"GRID patches: {len(patches)} fetched, no DDragon version for: {missing or 'none'}")

            mapping = ch.build_mapping(champs)
            names = {r["name"] for r in read_meta("characters")}
            unmapped = sorted(n for n in names if not ch.resolve(n, mapping))
            typer.echo(f"GRID champions: {len(names)}, unmapped: {unmapped or 'none'}")


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
def sample_soloq(platforms: str = "kr,euw1,na1", matches: int = 300, days: int = 14) -> None:
    """Sample high-elo ranked solo matches per platform (resumable; cached)."""
    from fele.external.soloq import sample

    async def run() -> list[int]:
        return await asyncio.gather(*(sample(name.strip(), matches, days) for name in platforms.split(",")))

    for p, n in zip(platforms.split(","), asyncio.run(run()), strict=True):
        typer.echo(f"{p}: {n} new matches")


@app.command()
def soloq_aggregate() -> None:
    """Build data_local/aggregates/soloq_champion_patch.parquet from sampled matches."""
    from fele.external.soloq import champion_patch_table

    df = champion_patch_table()
    if df.is_empty():
        die("No sampled matches yet — run `fele sample-soloq` first")
    out = settings().local("aggregates") / "soloq_champion_patch.parquet"
    df.write_parquet(out)
    typer.echo(f"{df.height} rows -> {out}")
    typer.echo(df.filter(df["games"] >= MIN_GAMES_TO_SHOW).sort("win_rate", descending=True).head(10))


@app.command()
def prefs_init(team: str = "Cloud9 Kia", top_n: int = 6) -> None:
    """Pre-fill config/preferences.yaml (gitignored) with the team's latest roster and most-played champions."""
    from fele.ingest.grid import read_meta

    dest = settings().fele_config_dir / "preferences.yaml"
    if dest.exists():
        die(f"{dest} exists — edit it directly or delete it first")
    rows = [r for r in read_meta("rosters") if r["team_name"] == team]
    if not rows:
        die(f"No roster rows for {team!r}")
    games = {g["game_id"]: g["started_at"] for g in read_meta("games")}
    latest_game = max(rows, key=lambda r: games.get(r["game_id"], ""))["game_id"]
    current = [r for r in rows if r["game_id"] == latest_game]
    pools: dict[str, Counter[str]] = defaultdict(Counter)
    for r in rows:
        pools[r["player_id"]][r["character_name"]] += 1
    roles = ["top", "jungle", "mid", "bot", "support"]  # roster order is NOT reliable — verify by hand
    extra_role = roles[0]
    doc: dict[str, object] = {
        "team": team,
        "weight": 0.5,
        "players": [
            {
                "name": r["player_name"].strip(),
                "role": roles[i] if i < len(roles) else extra_role,
                "riot_ids": [],
                "wants_prio": False,
                "pool": [
                    {"champion": c, "comfort": "comfortable", "note": f"{n} pro games in GRID data"}
                    for c, n in pools[r["player_id"]].most_common(top_n)
                ],
                "hates_playing_against": [],
            }
            for i, r in enumerate(current)
        ],
        "strategy": {"save_for_late_games": [], "must_ban_vs_opponent": {}, "never_pick": [], "style_tags": []},
    }
    dest.write_text(
        "# Generated by `fele prefs-init` — VERIFY ROLES (roster order != role) and edit comfort.\n"
        + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    )
    typer.echo(
        f"wrote {dest} ({len(current)} players from the latest game) — roles are GUESSED from roster order; fix them"
    )


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
