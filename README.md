# fele

*fele* — short for **Fearless Ledger**.

**Plan the whole series, not just the next pick.** fele is a coach-facing draft-prep and
Fearless series planner for League of Legends, built for Cloud9's LoL staff in the
[Cloud9 x JetBrains "Sky's The Limit" Hackathon 2026](https://cloud9.devpost.com/) (Category 2: Macro Scouting & Draft Management).

> Status: early scaffold (Phase 0–1 of [AGENT_PLAN.md](AGENT_PLAN.md)). Features below are the target, not yet built.

## What it does (target)

| Module | Answers |
|---|---|
| Opponent scouting | What pick/ban tendencies repeat for this opponent? How does their draft shift in Fearless G3/G4/G5? |
| Meta & patch view | What's strong in pro play and in current-patch high-elo solo queue? |
| ML draft engine | Win probability for a draft, opponent pick/ban prediction, ranked recommendations with reasons |
| Fearless series planner | Monte Carlo over a Bo3/Bo5: pool depletion, what to save for late games |
| Mock draft board | Real pro draft order, live win probability with uncertainty, keyboard shortcuts |
| "How to win" cards | Short insights per opponent, each with its evidence count |
| Coach preferences | Player comfort tiers, "refuses" picks, prio players, save lists — human knowledge the data can't see |

Every number carries its sample size. Recommendations are ranked options with reasons, never orders.

## Repository layout

```
engine/      Python 3.14 (uv): ingestion, statistics, models, FastAPI   → `uv run fele --help`
web/         React 19 + TypeScript + Vite + Tailwind + TanStack Query    → `pnpm dev`
config/      preferences.example.yaml (coach input schema; your real file is gitignored)
docs/        COMPLIANCE.md, research/, METHODOLOGY.md, MODEL_CARD.md, experiments/
scripts/     check_no_data.sh (blocks licensed data from ever being committed)
.idea/       shared PyCharm config: run configurations, DuckDB data source, module setup
data_local/  gitignored: Parquet, DuckDB, Data Dragon cache, Riot API cache
scratch/     gitignored: your own experiments and throwaway scripts
```

## Quick start

Prerequisites: macOS/Linux with [Homebrew](https://brew.sh), Docker.

```bash
# 1. Data: clone the GRID hackathon data NEXT TO this repo (never inside it)
git clone https://github.com/cloud9esports/stl-hackathon-2026-grid-starter.git ../stl-hackathon-2026-grid-starter

# 2. Secrets
cp .env.example .env    # add your Riot Developer Portal key

# 3. Toolchain + dependencies + git hooks, then static/external data and the DuckDB catalog
make setup
make data

# 4a. Everything in Docker
make up                 # web: http://localhost:8080 · API docs: http://localhost:8000/docs

# 4b. …or natively, with hot reload (two terminals)
cd engine && uv run fele serve     # http://localhost:8000/docs
cd web && pnpm dev                 # http://localhost:5173
```

`make help` lists all shortcuts. Engine commands (`uv run fele <cmd>`, or `docker compose run --rm fele <cmd>`):

| Command | What it does |
|---|---|
| `grid-summary` | Sanity check of the GRID data (counts only) |
| `ingest` | Replays all GRID feeds into Parquet tables with inferred roles (`lol.*`, ~45 s); see `docs/DATA_DICTIONARY.md` |
| `fetch-ddragon` | Data Dragon static data for every patch since 15.1 + the live patch's champion icons |
| `static` | Champion map (GRID ↔ Data Dragon), attribute tags, patch deltas (`static.*`); see `docs/DATA_DICTIONARY.md` |
| `fetch-leaguepedia-hf` | CC BY-SA pro pick/ban history, all leagues 2011–2026 (local only) |
| `riot-check` | Verifies the Riot key and prints its rate limits |
| `sample-soloq` / `soloq-aggregate` | High-elo solo queue sample of the live patch (KR/EUW/NA, resumable, 25% with timelines) → champion, matchup and item-build tables |
| `player-soloq` | Solo-queue champion pools for Riot IDs the coach entered in `config/preferences.yaml` (off by default) |
| `prefs-init` | Pre-fills `config/preferences.yaml` with Cloud9's latest lineup, inferred roles and top champions |
| `stats` | Draft priority, ban targeting, player pools, Elo, macro context, meta score (`aggregates.stats_*`); see `docs/METHODOLOGY.md` |
| `evaluate` | Walk-forward evaluation of a model and all baselines → `docs/experiments/<date>-<model>.md` + MLflow (`--model baseline_elo`) |
| `live` / `backtest` | Build the cached live draft context (production models refit on all games); recommender back-test report |
| `explain` / `holdout` | Coefficients, SHAP and posterior summaries of the Phase 8 models; the one-time final holdout check |
| `db` | Builds `data_local/fele.duckdb`: views `grid.*`, `lol.*`, `static.*`, `leaguepedia.*`, `soloq.*`, `aggregates.*` |
| `serve` | API with Swagger UI at `/docs`, ReDoc at `/redoc`, OpenAPI spec at `/openapi.json` |

### The web app

Pick a team → **Draft** (presence, picks, bans, first rotation and average slot, by side and by game number in the
series, with league comparison and strong/weak/noise labels; which players opponents ban against), **Players**
(current lineup, comfort champions, pool size with interval), **Macro** (jungle start side, first objectives vs
league, objective timings, early-kill heatmap). Plus **Meta** (live patch: pro presence, shrunk pro and solo-queue win
rates, patch changes) and **Data** (coverage). Every number shows its sample (`7/12`, `n=113`). Light and dark mode.

The API serves only precomputed aggregates (`data_local/aggregates`, `data_local/static`), never raw GRID events.
Set `DEMO_PASSWORD` in `.env` to put a hosted demo behind a password (HttpOnly session cookie; off when empty).

The web app's TypeScript API client is generated from the OpenAPI spec: `cd web && pnpm gen:api`.

### Querying the data

`make db` builds `data_local/fele.duckdb`, which holds views over the local files. In PyCharm, the **fele.duckdb** data
source is already configured (`.idea/dataSources.xml`): open the Database tool window and download the DuckDB driver
when prompted. From a terminal: `duckdb -readonly data_local/fele.duckdb`.

## Code quality

Strict by default, enforced in CI (`.github/workflows/`) and with `make check` locally:

| Area | Tooling |
|---|---|
| Python lint | Ruff with **every** rule set enabled (`select = ["ALL"]`), a few documented exceptions |
| Python format / types | Ruff formatter · Pyright **strict** |
| TypeScript | Biome (recommended + all React/test rules + extra strict rules) · `tsc` strict, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` |
| Static analysis | **JetBrains Qodana** (Community for Python) on every push/PR, findings in GitHub code scanning · `make qodana` locally |
| Tests | pytest + coverage gate, Hypothesis available for property tests · Vitest + v8 coverage |
| Data safety | `scripts/check_no_data.sh` as pre-commit hook and CI step (scans full git history) |
| Notebooks | `nbstripout` git filter: outputs are never committed |

## ML & statistics stack

Installed with `uv sync --all-extras` (extra `ml`) or `make setup`:

| Need | Library |
|---|---|
| DataFrames / SQL | Polars, DuckDB, PyArrow |
| Classical stats (binomial tests, Benjamini–Hochberg, GLMs) | SciPy, statsmodels |
| Models | scikit-learn (logistic, calibration), LightGBM (incl. LambdaRank) |
| Bayesian / hierarchical models | PyMC + ArviZ |
| Uncertainty | MAPIE (conformal prediction), bootstrap via NumPy |
| Tuning / tracking / explanations | Optuna, MLflow (local store in `data_local/mlruns`), SHAP |
| Verification | Hypothesis (property tests), Pandera (DataFrame schemas), deptry, pip-audit |
| Exploration | JupyterLab + matplotlib (group `notebook`) |

## JetBrains tools

| Tool | Used for |
|---|---|
| PyCharm | Engine development; committed run configurations (API, web, tests, data-leak check) and DuckDB data source |
| WebStorm | Web app |
| DataGrip / PyCharm Database tools | Querying `data_local/fele.duckdb` |
| Qodana | Static analysis in CI and locally |
| JetBrains Air (with Claude) / Junie | AI-assisted development — see [AI_SHOWCASE.md](AI_SHOWCASE.md) |

## Data & licenses

See [docs/COMPLIANCE.md](docs/COMPLIANCE.md). In short: GRID match data is used locally under the hackathon license and is
**never committed or redistributed**; the hosted demo serves aggregates only. Static champion data comes from Riot's
Data Dragon. Current-patch signals come from the official Riot API. Additional pro pick/ban history comes from
[Leaguepedia](https://lol.fandom.com) contributors (CC BY-SA 3.0), via the `gptilt/lol-esports-matches` dataset.

fele is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

## License

Code: [MIT](LICENSE). Data is not included and is subject to its own terms.
