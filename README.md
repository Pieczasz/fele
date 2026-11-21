# fele

*fele* — short for **Fearless Ledger**.

**Plan the whole series, not just the next pick.** fele is a coach-facing draft-prep and
Fearless series planner for League of Legends, built for Cloud9's LoL staff in the
[Cloud9 x JetBrains "Sky's The Limit" Hackathon 2026](https://cloud9.devpost.com/) (Category 2: Macro Scouting & Draft Management).

## The problem

Under **Fearless draft** (2025+), every champion a team picks is gone for the rest of the series, for both teams.
A Bo5 is no longer five separate drafts but one plan: what to play now, what to save for game 4, what the opponent
will run out of. Coaches prepare this in spreadsheets today, by hand, from VOD notes and memory.

fele turns that prep into one tool for Cloud9's coaching staff: scout the opponent from official match data,
plan the whole series with Fearless locks, and rehearse the draft against a model of how that opponent drafts.
Every number shows its sample size, and every recommendation is a ranked option with its reasons, never an order.

## What a coach does with it

1. **Pick the opponent → scouting report.** Their draft priorities (by side and by game number in the series), the
   players opponents ban against, each player's pool size, macro habits vs their league, and **"how to win" cards**:
   short insights that carry their evidence, e.g. *"⟨champion⟩ is a game-1 priority: they take it in their first
   rotation in k of their n game 1s"*.
2. **Plan the series.** The Fearless planner tracks every game, the locks, both teams' remaining pools and a save
   list ("keep Azir for game 3+"). A Monte Carlo simulation of the rest of the series gives the series win
   probability, the scenario "what if we lose the next game?", and whether the save plan changes anything beyond
   noise. Export to CSV or JSON.
3. **Rehearse the draft.** The mock draft board follows the real 2026 pro draft order. On our turn: five ranked
   options, each with reasons. On theirs: what this opponent most likely does next. A live win probability with its
   range sits on top. Keyboard-driven, and a finished draft is saved into the series plan.
4. **Add what the data can't see.** Coach inputs: each player's comfort tiers and refusals, team style, never-pick
   and must-ban lists. They're stored in the browser and used by the recommendations immediately.
5. **fele Live in your own games.** With `fele serve --lcu`, fele follows the League client on the same computer:
   lobby, then champ select (Ranked Solo/Duo, Flex, Clash). Your party's recent games load from the client while you
   queue. On your turn you get five ranked bans or picks, each with its reasons: live-patch high-elo strength at your
   position, your own recent games on it, the lane matchup against the enemy pick, and what the comp lacks. Names and
   stats only for you and your party; other teammates show as "Ally", and the enemy team is never looked up.

| Page | Answers |
|---|---|
| Scouting (Draft / Players / Macro) | What repeats for this opponent, with n, league comparison and strong/weak/noise labels |
| Series planner | What's locked, what's left, what to save; series win probability ± Monte Carlo error |
| Mock draft | Options for our pick/ban with reasons; their likely next action; live win probability |
| Meta | Live patch: pro presence, shrunk pro and high-elo solo-queue win rates, patch changes |
| Coach | Comfort tiers, refusals, style, save / never-pick / must-ban lists |
| Live | Champ select in your own games: your party's recent pools and ranked options for the current ban or pick |
| Data | Coverage: games per league and team, solo-queue sample size |

## How it works

```
GRID official match data ──► ingest: replay every event feed ──► Parquet tables, inferred roles (99.9% agreement)
Data Dragon (Riot)        ──► champion map, reviewed role/attribute tags, patch changes
Riot API (high-elo solo)  ──► live-patch champion strength and lane matchups (aggregates only)
                                  │
                                  ▼
             statistics (Polars): rates with Wilson intervals, empirical-Bayes shrinkage,
             Benjamini–Hochberg tests, Elo, player pools, macro habits, meta score
                                  │
             time-respecting feature store (state as of each game, leakage-tested)
                                  │
             models: outcome (Elo; 16 challengers tried) · draft actions (LightGBM LambdaRank)
                                  │
             engine: ranked options with reasons, rollout win probability, Fearless series simulator
                                  │
             FastAPI (aggregates + cached models only) ──► React web app
```

**What the models can and can't do** (details: [docs/MODEL_CARD.md](docs/MODEL_CARD.md),
[docs/METHODOLOGY.md](docs/METHODOLOGY.md)):

- **Predicting the opponent's draft works.** The draft-action model puts the team's actual pick or ban in its top
  10 options 71% of the time (walk-forward over 8 months), against 51% for champion popularity.
- **Predicting the winner from the draft barely works, and we say so.** Sixteen models (logistic, Bayesian
  hierarchical, trees, boosting, kernels, ensembles) failed to beat a plain Elo rating by a significant margin on a
  locked holdout. So win probabilities are Elo-dominated, and the draft board labels its "draft edge" as weak
  evidence rather than pretending otherwise.
- **Validation:** walk-forward folds grouped by series, a holdout used exactly once (decision committed before the
  run), paired bootstrap intervals, and leakage tests that change future results and require earlier features to
  stay identical.

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
| `serve` | API with Swagger UI at `/docs`, ReDoc at `/redoc`, OpenAPI spec at `/openapi.json`; `--lcu` also follows the local League client (fele Live) |
| `lcu-fake` | A scripted fake League client (lobby → Ranked Flex champ select, looping) to try fele Live without the game |
| `lcu-capture` | Records anonymised League client payloads to `data_local/lcu_captures/` (parser checks) |
| `eval-solo` | Champ-select scorer check on the cached high-elo matches → `docs/experiments/<date>-solo.md` |

### The web app

Pick a team → **Draft** (presence, picks, bans, first rotation and average slot, by side and by game number in the
series, with league comparison and strong/weak/noise labels; which players opponents ban against), **Players**
(current lineup, comfort champions, pool size with interval), **Macro** (jungle start side, first objectives vs
league, objective timings, early-kill heatmap). Plus **Meta** (live patch: pro presence, shrunk pro and solo-queue win
rates, patch changes), **Series plan**, **Mock draft** and **Coach** (described above) and **Data** (coverage). Every
number shows its sample (`7/12`, `n=113`). Light and dark mode. Mock draft keys: `/` search, `1`–`5` take an option,
`Backspace` undo, `S` skip a ban.

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
| Tests | pytest (coverage gate 70%), Hypothesis property tests, a synthetic world for the draft engine · Vitest + v8 coverage |
| Dead code / dependencies | vulture, deptry, pip-audit (Python) · knip, pnpm audit (web) |
| Data safety | `scripts/check_no_data.sh` as pre-commit hook and CI step (scans full git history) |
| Notebooks | `nbstripout` git filter: outputs are never committed |

## ML & statistics stack

Installed with `uv sync --all-extras` (extra `ml`) or `make setup`:

| Need | Library |
|---|---|
| DataFrames / SQL | Polars, DuckDB, PyArrow |
| Classical stats (Wilson intervals, binomial tests, Benjamini–Hochberg, beta priors) | SciPy |
| Models | scikit-learn (logistic, calibration), LightGBM (incl. LambdaRank) |
| Bayesian / hierarchical models | PyMC + ArviZ |
| Uncertainty | bootstrap and paired bootstrap over series (NumPy), Monte Carlo error |
| Tuning / tracking / explanations | Optuna, MLflow (local store in `data_local/mlruns`), SHAP |
| Verification | Hypothesis (property tests), deptry, vulture, pip-audit |
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
Data Dragon. Current-patch signals come from the official Riot API. `fele fetch-leaguepedia-hf` can add pro pick/ban
history from [Leaguepedia](https://lol.fandom.com) contributors (CC BY-SA 3.0, via the `gptilt/lol-esports-matches`
dataset) to the local DuckDB catalog for exploration; it is kept separate and not used by the app or the models.

fele is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

## License

Code: [MIT](LICENSE). Data is not included and is subject to its own terms.
