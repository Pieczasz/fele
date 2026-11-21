# fele — Build Plan for AI Coding Agents

> Cloud9 x JetBrains "Sky's The Limit" Hackathon 2026 — Category 2 (LoL): Macro Scouting & Draft Management System
> Plan written: 2026-11-18 · Submission deadline: **2027-01-12 11:00 PT** · Internal target: **2027-01-09**

## Quick links:
https://cloud9.devpost.com/?ref_feature=challenge&ref_medium=your-open-hackathons&ref_content=Submissions+open
https://cloud9.devpost.com/rules
https://cloud9.devpost.com/updates
https://github.com/cloud9esports/stl-hackathon-2026-grid-starter
https://developer.riotgames.com/docs/portal#_getting-started

## How to use this file

Give this file to your coding agent (Claude via JetBrains Air, Junie, etc.) and run it **one phase at a time**:

> "Read AGENT_PLAN.md. Execute Phase N only. Follow the Ground Rules. Stop at the phase checkpoint and report: what you did, what failed, open questions, and the acceptance-criteria results."

Do not ask the agent to run several phases in one go. Every phase ends with a **🛑 Checkpoint** where a human reviews the result before the next phase starts. Commit after each phase, after checking that no data files are staged.

---

## 0. Ground rules for the agent (non-negotiable)

1. **Never commit data.** No GRID `.zst`/`.jsonl` files, no Parquet/DuckDB/SQLite built from them, no copies of `meta/` or `series.csv`, no Riot API raw responses. All local data lives in `data_local/` (gitignored) or the sibling GRID repo. Before every commit run `git diff --cached --name-only` and the data-leak check script (Phase 1).
2. **Never put secrets in code or git.** The Riot API key goes in `.env` (gitignored). Never print it in logs.
3. **Only use data sources marked ✅ in `docs/COMPLIANCE.md`** (created in Phase 0). No scraping of u.gg, OP.GG, lolalytics, Mobalytics or similar sites. If a source's license is unclear, stop and ask.
4. **AI tools and the GRID data:** the GRID license requires opting out of training/retention in any AI tool that offers it. The human must confirm this is done before the agent reads data excerpts.
5. **Research claims need sources.** When researching rules or licenses, write the URL and date checked next to each conclusion. If something can't be verified, mark it `UNVERIFIED` — never guess.
6. **No leakage, no peeking.** Follow the validation protocol in Section 5. The final holdout set is touched exactly once, at the end of Phase 8.
7. **Prefer simple and explainable.** A more complex model is only adopted if it beats the simpler one on walk-forward validation (Section 5.5).
8. **Recommendations are options, not orders.** Always show several ranked options with reasons and uncertainty (Riot policy: tools may highlight decisions and give multiple choices, but should not dictate them).
9. **Show the evidence.** Every statistic shown in the UI carries its sample size (e.g. "7/10 games").
10. **Stop and ask** when: a license is unclear, a design choice changes scope, data contradicts this plan, or an acceptance criterion can't be met.

---

## 1. Project brief

**Product:** *fele* — a coach-facing web app that replaces draft-prep spreadsheets for Cloud9's LoL staff.

**Core idea:** plan the **whole Bo3/Bo5 series** under hard Fearless rules, powered by statistics and ML, not just the next pick. (Last year's category winner already did single-draft "top 5 next pick" recommendations, so the series level is our differentiator.)

**Users:** Cloud9 head coach / analysts (judge panel includes Cloud9's LoL head coach, an ML engineer from JetBrains, and Cloud9's AI engineer).

**Modules (priority order):**

1. **Opponent scouting report** — pick/ban priorities by side, phase and game number in series; ban targeting of C9 players; player champion pools and comfort; macro context (jungle start side, first scuttle, grubs vs drake priority, objective timings). All with sample sizes.
2. **Meta & patch view** — what is strong *now*: champion priority in pro play per patch + current-patch strength from high-elo solo queue (Riot API), with patch-change signals.
3. **ML draft engine** — win-probability model, opponent pick/ban prediction model, and a recommendation engine for picks, bans and comps.
4. **Fearless series planner** — Monte Carlo simulation of the series: locked champions, pool depletion per player, "save list" for late games, scenario branches.
5. **Mock draft board** — real pro draft order, live win probability with uncertainty band, recommendation options with reason codes.
6. **"How to win" cards** — short, evidence-backed counter-strategy insights.

**Stack:** Python (engine: Polars, DuckDB, scikit-learn, LightGBM, PyMC/NumPyro, FastAPI) + TypeScript/React (web UI). JetBrains: PyCharm, WebStorm, DataGrip, JetBrains Air (+ Junie).

---

## 2. Verified facts (checked 2026-11-18 — re-verify only if a phase depends on them)

### 2.1 Hackathon rules (official rules + submission specifics)

- Submission period: 2026-11-17 11:00 PT → **2027-01-12 11:00 PT**. Judging 2027-01-27 → 2027-02-03. Winners ~2027-02-08.
- Must use ≥1 JetBrains tool (IDE, JetBrains Air or Junie). Other editors/AI allowed alongside.
- Repo on GitHub/GitLab/Bitbucket, **public**, with an **open-source license detectable in the repo About section**, containing all source, assets and run instructions. Committing `.idea`, `.junie`, `.air` folders is encouraged as evidence.
- Working demo link if website (private site allowed if login credentials are in testing instructions). Must stay available free until judging ends (2027-02-03).
- Demo video < 3 min, public on YouTube, **no third-party trademarks or copyrighted music without permission**, shows the project running.
- Text description (features + which JetBrains tools did what) and a methodology write-up.
- Bonus prize (Best AI-Powered Workflow Story): a URL to a write-up, e.g. `AI_SHOWCASE.md` in the repo.
- Third-party APIs/data: entrant must hold all rights/licenses; must comply with Riot developer policies.
- Judging: Stage 1 pass/fail (fits theme + reasonably uses JetBrains tools). Stage 2: five equally weighted criteria — Technological Implementation (JetBrains use, non-trivial), Design, Potential Impact, Quality of the Idea, Presentation. Tie-break order follows that list. Judging may include automated AI analysis → clear README and write-ups matter.
- Category 2 judges want: draft-tendency analysis / draft organization / Fearless support answering e.g. "What pick/ban tendencies repeat most often for this opponent?" and "How does the opponent's draft strategy shift in Fearless Game 3, 4, 5?" Bonus ideas: data-backed "how to win" insights, live draft win-rate impact.

### 2.2 GRID data (repo `cloud9esports/stl-hackathon-2026-grid-starter`, inspected directly)

- LoL: **745 series, 1,739 games**; LCK, LEC, LTA North/South/Cross-Conference (2025), LCS (2026). Dates 2025-01-15 → 2026-10-13. Patches **15.1 → 16.17** (2 games have an empty patch field).
- Cloud9 appears as **"Cloud9 Kia"** (team_id 47351): 142 games / 53 series.
- Format: one zstd-compressed JSONL file per series; each line is an envelope with `events[]`; each event has `type` = `{actor}-{action}-{target}`, plus `seriesState` (full snapshot) and `seriesStateDelta`. A `!` before the action means rollback of an earlier event (e.g. `player-!purchased-item`, `team-!picked-character`) — must be undone during replay.
- `meta/*.csv` (games, rosters, players, teams, tournaments, characters) answer many questions without opening feeds. IDs are strings and unique per `title` (`lol`/`val`).
- **Draft:** `team-picked-character` / `team-banned-character` events and `games[].draftActions` (sequence number, ban/pick, drafter team, champion). 20 actions per game.
- **Present:** item purchases/sells/undos, level-ups (with player position snapshot), kills, multikills, tower/plate/inhibitor/nexus events, scuttles (top/bot), void grubs, each drake type, herald, baron, Atakhan, NPC respawn clocks, team/player gold, damage, vision score, KDA.
- **Absent:** no ward placement events; no events for normal jungle camps (raptors, wolves, etc.); **no role column**. Positions exist only as snapshots at event times (not continuous tracking).
- **Roster order ≠ role.** Checked: "jungle" champions appear at roster index 1 only ~57% of the time; ADCs at index 3 only ~50%. → Role inference is required (Phase 2).
- **Hard Fearless confirmed** in all leagues: after applying rollbacks there are **no** re-picks (Phase 2). Raw `team-picked-character` events show 183 apparent re-picks, all draft corrections later undone with `team-!picked-character`. Bans don't carry over.
- **Small samples late in series:** series reaching game 4: 79 (49 end there, 30 go to game 5) (all leagues; corrected 2026-11-18 from `meta/games.csv`). Cloud9: 4 and 6.
- **2026 draft rules (Phase 0):** draft order A B A B A B / A B B A A B / B A B A / B A A B where A = first-pick team, which **may be red side** (First Selection: holder picks side *or* pick order; loser of previous game holds it from G2). No Fearless reset in G5 (LCS). Details: `docs/COMPLIANCE.md` §3.
- Champion names are display names (e.g. "Wukong", "K'Sante") — Data Dragon uses keys like `MonkeyKing`, `KSante` → mapping table required.
- License: data only for this hackathon, during the hackathon; no redistribution or commercial use; **never commit data** (incl. derived extracts); aggregates, charts, screenshots are OK. AI tools must have training/retention opt-out enabled where offered.

### 2.3 Riot developer platform

- Riot API (developer.riotgames.com): development key (rate-limited, expires every 24 h); personal key for small projects; production key for public products. Relevant endpoints: `account-v1` (Riot ID ↔ PUUID), `match-v5` (match IDs by PUUID, match details, timelines), `league-v4` (Challenger/Grandmaster/Master ladders).
- Policies relevant to us: no data-broker apps; API key never in code; must post Riot's legal boilerplate ("not endorsed by Riot Games…" — copy exact text from developer.riotgames.com/docs/lol); products should increase decision diversity and **not remove decisions** (highlight + multiple choices); **no MMR/Elo calculators that replace official ranking**; **cannot identify or analyze players deliberately hidden by the game**; register a product that serves players.
- Data Dragon: free static data + images per patch (champions, items, runes, summoner spells). Latest version at time of writing: 16.23.1 → **pro data in GRID ends at 16.17, ~6 patches behind the live client.** This is why we need current-patch signals from solo queue.
- League Client API (LCU) exists but is officially unsupported. Revised 2026-11-21: used locally only for fele Live
  (champ select in the user's own games and scrims), under the conditions in docs/COMPLIANCE.md.
- Since 2026-10-06 Riot blocks game-memory access for unknown third-party apps → no memory reading of any kind.

### 2.4 Other sources (status must be confirmed in Phase 0)

| Source | Possible use | Status |
|---|---|---|
| Leaguepedia (lol.fandom.com) Cargo API | LPL/international pro games, rosters, possibly players' known accounts | ⚠️ resolved in Phase 0 — see `docs/COMPLIANCE.md`; bulk copy via HF `gptilt/lol-esports-matches` (CC BY-SA 3.0) |
| Oracle's Elixir CSV downloads | Pro match datasets incl. leagues GRID lacks | UNVERIFIED — check terms of use |
| CommunityDragon | Extra static assets/data | UNVERIFIED — community project, check terms |
| u.gg / OP.GG / lolalytics / Mobalytics | — | ❌ No public API; do not scrape |

---

## 3. Architecture & repository layout

```
hackathon/
├── stl-hackathon-2026-grid-starter/   ← GRID data repo (cloned, NEVER inside the project)
└── fele/                   ← our public repo
    ├── LICENSE                        (MIT)
    ├── README.md                      (judge-facing: what, why, how to run, JetBrains usage)
    ├── AGENT_PLAN.md                  (this file)
    ├── AI_SHOWCASE.md                 (bonus prize write-up, kept up to date every phase)
    ├── .env.example                   (RIOT_API_KEY=, STL_DATA_DIR=, DEMO_PASSWORD=)
    ├── docs/
    │   ├── COMPLIANCE.md              (Phase 0: data source matrix, rule checklist)
    │   ├── DATA_DICTIONARY.md         (Phase 2: tables & columns)
    │   ├── METHODOLOGY.md             (statistics + ML approach, for the submission)
    │   ├── MODEL_CARD.md              (Phase 8: models, metrics, limits)
    │   └── experiments/               (experiment reports, markdown only)
    ├── engine/                        (Python, managed with uv)
    │   ├── pyproject.toml
    │   ├── src/fele/
    │   │   ├── config.py              (paths, env vars)
    │   │   ├── ingest/                (GRID streaming, replay, rollback handling)
    │   │   ├── static/                (Data Dragon, champion mapping, attribute tags)
    │   │   ├── external/              (Riot API client, rate limiter, cache)
    │   │   ├── features/              (feature builders, time-respecting)
    │   │   ├── stats/                 (shrinkage, intervals, tendencies, Elo)
    │   │   ├── models/                (outcome, action, bayesian, gbm)
    │   │   ├── engine/                (recommendation, draft rollout, series simulator)
    │   │   ├── eval/                  (splits, metrics, calibration, bootstrap)
    │   │   └── api/                   (FastAPI app)
    │   ├── scripts/                   (CLI entry points: ingest, build-features, train, evaluate, export)
    │   ├── notebooks/                 (exploration only; no outputs committed)
    │   └── tests/
    ├── web/                           (React + TypeScript + Vite)
    ├── data_local/                    (gitignored: parquet, duckdb, caches, mlruns)
    └── .github/workflows/ci.yml       (lint, tests, data-leak check)
```

Data flow:

```
GRID .zst ──► ingest (stream, replay, rollbacks) ──► Parquet tables ──► DuckDB views
Data Dragon ──► static tables (champions, items, tags, patch deltas)      │
Riot API ──► cached raw JSON (local) ──► soloq aggregates ────────────────┤
                                                                           ▼
                                  features ──► models ──► engine (recommend, simulate)
                                                                           │
                                         FastAPI (aggregates + model outputs only)
                                                                           │
                                                   React web app (behind login)
```

---

## 4. Phases

Each phase lists: **Goal → Tasks → Deliverables → Acceptance criteria → 🛑 Checkpoint.**
After every phase the agent also appends a short entry to `AI_SHOWCASE.md` (what was asked, what the agent produced, what the human corrected).

### Phase 0 — Research & compliance (no code)

**Goal:** know exactly what data we may use and what rules constrain the product.

**Tasks**
1. Read and summarize, with URLs and dates: hackathon Official Rules (`cloud9.devpost.com/rules`), Submission Specifics, the GRID data `LICENSE.md`, `README.md` and `AGENTS.md`, Riot General Policies, Riot LoL game policy (developer.riotgames.com/docs/lol), Riot API Terms of Use.
2. For each candidate source in Section 2.4 and any new one you find, record: what data, license/terms, attribution needs, whether use in a public open-source repo + hosted demo is allowed, rate limits. Classify ✅ allowed / ⚠️ allowed with conditions / ❌ not allowed / ❓ ask organizers.
3. Riot API specifics: current development-key rate limits and expiry; whether a personal key is worth applying for (and how long approval takes); match-v5 regional routing for EUW/NA/KR; which endpoints expose `puuid` for Challenger/GM ladders.
4. **Pro players' solo-queue accounts:** find a legitimate way to map pro players to Riot IDs (e.g. publicly listed by the players/teams, Leaguepedia if its terms allow, or manual entry by the coach in app config). Check against the "deliberately hidden players" policy. Default design: a config file where the coach enters Riot IDs manually.
5. Hosted demo vs GRID license: confirm that serving **aggregates only** (no raw events) from a login-protected demo is acceptable. Draft a short question for the Cloud9 Discord / support@devpost.com in case it's ambiguous.
6. Verify the 2026 pro draft rules: standard pick/ban order, hard Fearless details for LCS, and the 2026 side/first-pick selection rule ("First Selection") — record how it changes draft simulation.
7. Video rules: list which visuals are safe (Data Dragon champion icons under Riot policy; our own UI) and which are not (broadcast footage, copyrighted music).

**Deliverables:** `docs/COMPLIANCE.md` with the source matrix, a rules checklist, the Riot boilerplate placement plan, open questions for organizers.

**Acceptance:** every source has a status and a citation; no ❓ left unflagged.

**🛑 Checkpoint:** human approves the source list and sends any organizer questions.

---

### Phase 1 — Repository scaffolding

**Goal:** a clean monorepo that runs end-to-end with a "hello" API and page.

**Tasks**
1. `engine/`: uv project, Python 3.14 (if a key dependency lacks 3.14 wheels, use 3.13 + the `zstandard` package and document it). Add ruff, pyright (or mypy), pytest, polars, duckdb, pyarrow, fastapi, uvicorn, pydantic, httpx, scikit-learn, lightgbm, mlflow (local file store in `data_local/mlruns`), pymc or numpyro (add later in Phase 8 if needed).
2. `web/`: Vite + React + TypeScript, Tailwind, TanStack Query, Recharts, React Router, ESLint, Vitest. A typed API client generated from FastAPI's OpenAPI schema.
3. `.gitignore`: the GRID README entries (`stl-hackathon-2026-grid-starter/`, `*.zst`, `*.jsonl`, `*.parquet`, `*.sqlite`, `*.duckdb`) plus `data_local/`, `.env`, `mlruns/`, notebook outputs.
4. `scripts/check_no_data.sh` + pre-commit hook + CI step: fail if any tracked file matches data patterns or is larger than 5 MB.
5. CI (GitHub Actions): lint + tests for engine and web, data-leak check. CI must not need GRID data (use tiny synthetic fixtures).
6. `config.py`: `STL_DATA_DIR` (default `../stl-hackathon-2026-grid-starter`), `FELE_DATA_DIR` (default `./data_local`), `RIOT_API_KEY` from env.
7. MIT `LICENSE`, initial `README.md` skeleton, `.env.example`, `AI_SHOWCASE.md` skeleton. JetBrains run configurations for API, web dev server and tests (commit `.idea` run configs, excluding workspace-specific files).

**Acceptance:** `uv run pytest` and `pnpm test` pass; `GET /health` works and the web app displays its response; data-leak check blocks a test `.parquet` file.

**🛑 Checkpoint:** human pushes the repo and confirms the license shows on GitHub.

---

### Phase 2 — GRID ingestion with Polars & DuckDB

**Goal:** turn the GRID feeds into clean, tested analytical tables.

**Tasks**
1. Streaming reader: iterate envelopes line by line (never load whole files). Parallelize across series files with a process pool.
2. Replay logic: apply rollback events (`!` actions) by removing the matching earlier event; drop games whose start was rolled back; derive results from per-game final state, not from `team-won-series` (some feeds lack it).
3. Write Parquet tables to `data_local/parquet/` and register DuckDB views in `data_local/fele.duckdb`:

| Table | Grain | Key columns |
|---|---|---|
| `series` | series | series_id, event, stage, league, season, format (bo1/3/5), scheduled_start, team ids, winner |
| `games` | game | game_id, series_id, game_number, patch, started_at, duration_s, blue_team_id, red_team_id, winner_team_id |
| `draft_actions` | draft action | game_id, seq (1–20), phase (ban1/pick1/ban2/pick2), action (ban/pick), team_id, side, champion |
| `participants` | player-game | game_id, team_id, player_id, player_name, champion, inferred_role, role_confidence, kills, deaths, assists, gold, damage, vision_score, win |
| `objectives` | event | game_id, t_s, team_id, player_id, type (scuttle_top, grub, drake_<type>, herald, baron, atakhan, tower, plate…) |
| `kills` | event | game_id, t_s, killer, victim, assists, x, y |
| `levelups` | event | game_id, t_s, player_id, level, x, y |
| `item_events` | event | game_id, t_s, player_id, item, action (buy/sell/undo) |
| `fearless_state` | game | game_id, champions locked before this game (list), count |

4. **Role inference:** combine (a) Smite purchase/summoner spell signals for jungle, (b) early position snapshots (level 1–3 positions per lane), (c) champion role priors from Data Dragon tags / solo-queue role frequencies, (d) roster order as a weak prior. Solve as an assignment problem per team-game (Hungarian algorithm over role probabilities). Store confidence; flag low-confidence games.
5. Validate the standard draft order from `draftActions` sequences and record it in the data dictionary.
6. ~~Investigate the 5 Fearless re-picks~~ Done: they are rolled-back draft entries; 0 remain (see `docs/DATA_DICTIONARY.md`).
7. `docs/DATA_DICTIONARY.md` for every table.

**Acceptance (tests on real data, run locally):**
- game count equals `meta/games.csv` (minus documented exclusions); every finished game has 20 draft actions (document exceptions) and 10 participants with exactly one player per role per team;
- jungle assignments agree with Smite purchases in ≥ 98% of games; manual spot check of 20 random games;
- full ingest runs in < 15 min on a laptop; idempotent re-runs.

**🛑 Checkpoint:** human explores the tables in DataGrip and spot-checks Cloud9 games.

---

### Phase 3 — Static data & champion knowledge

**Goal:** a patch-aware champion knowledge base.

**Tasks**
1. Data Dragon client: `versions.json`, champion/item/summoner data for every patch present in GRID (15.1–16.17) and the current live patch. Cache locally (gitignored). Champion square icons may be cached for the UI.
2. Name mapping table GRID display name ↔ Data Dragon key ↔ numeric id (handle `Wukong`/`MonkeyKing`, apostrophes, spaces). Test: every GRID champion maps.
3. **Champion attribute tags** (versioned CSV in the repo — this is our own work, not licensed data): primary roles, damage type (AD/AP/mixed, with share), engage, disengage, peel, frontline, poke, dive, split-push, waveclear, scaling (early/mid/late), hard CC count, range class. Agent drafts from Data Dragon tags/stats + its own knowledge; **human reviews** a sample and anything uncertain.
4. **Patch delta features:** diff champion base stats and spell numbers between consecutive Data Dragon versions → per champion per patch: `buffed`, `nerfed`, magnitude score. (Patch notes text is copyrighted — derive from numbers only.)

**Acceptance:** all champions mapped; tags cover 100% of champions seen in data + current roster; patch delta table exists for every patch transition.

**Status (2026-11-19):** done — `fele static`; tags in `engine/src/fele/static/champion_tags.csv` (173 champions, rows with a `review` note need a look); deltas from base stats + cooldowns/costs/ranges only (Data Dragon has no spell damage numbers). See `docs/DATA_DICTIONARY.md`.

**🛑 Checkpoint:** human reviews the tag CSV (this directly affects comp analysis quality).

---

### Phase 4 — External data via the Riot API (only ✅ uses from Phase 0)

**Goal:** current-patch meta signal and (if approved) pro players' recent solo-queue activity.

**Tasks**
1. Riot API client: async httpx, regional routing, token-bucket rate limiter that respects both limit windows and `Retry-After`, retries with backoff, on-disk cache keyed by URL (raw JSON compressed in `data_local/riot_cache/`, gitignored).
2. **High-elo meta sampler:** for KR, EUW, NA: Challenger + Grandmaster ladders → PUUIDs → ranked solo match IDs (queue 420) since the current patch release → match details (+ timelines for item builds, sampled). Budget-aware: a resumable job that collects N matches per region per day.
3. Aggregate to `soloq_champion_patch` (champion × role × patch: games, wins, picks, bans if available, avg game length) and `soloq_matchups` (lane opponent pairs) and `soloq_items` (common completed-item orders). Store aggregates only.
4. **Pro players' solo queue** (only if Phase 0 approved a source): `config/players.yaml` with Riot IDs entered by the coach → recent ranked games → `player_soloq_pool` (champion, games, wins, last played, patch). Respect the hidden-player policy: skip anything not publicly retrievable via the API.
5. Never store or display anything derived from data Riot marks as private/hidden.

**Acceptance:** sampler resumes after interruption without duplicate requests; no 429 storms; aggregates for the current patch exist for ≥ 3 regions; unit tests with recorded fixtures (fixtures contain no real personal data).

**Status (2026-11-19):** done. `fele sample-soloq` collected 300+ patch-16.23 matches per region (KR/EUW/NA, 1,069 in total with earlier runs, 205 new timelines, 0 × 429). `fele soloq-aggregate` builds `soloq_champion_patch`, `soloq_matchups` and `soloq_items`. `fele player-soloq` exists but stays off until the coach enters Riot IDs. See `docs/DATA_DICTIONARY.md`.

**🛑 Checkpoint:** human confirms the key handling and data volume.

---

### Phase 5 — Statistics layer

**Goal:** trustworthy descriptive statistics that power scouting and feed the models.

**Tasks**
1. Win rates with **empirical-Bayes beta-binomial shrinkage** (prior fitted per role/patch window) + Wilson/Bayesian credible intervals.
2. Draft priority metrics per team and per patch window: presence (pick+ban rate), first-rotation priority, ban targeting (which opponent player's pool a ban hits, using player pools), side and phase splits, **game-number-in-series splits** (G1 vs G2 vs G3+ under Fearless).
3. Player pool metrics: unique champions, effective pool size (exp of entropy), comfort score (recency-weighted games, win rate shrunk), pool depth per role, overlap with current meta.
4. Team strength: time-respecting Elo/Glicko-2 per league computed only from earlier matches (note: almost no cross-league games in this data → ratings are comparable within a league only; use league offsets carefully or keep per-league). Internal use only — never displayed as a player ranking.
5. Macro context: jungler starting side (level 1–3 positions), first scuttle side/time, grub vs first drake priority, first objective timings, early kill locations (heatmap data). Pathing claims must state the limits (no camp events).
6. Tendency significance: compare a team's rate vs league base rate with a binomial test + Benjamini–Hochberg correction; mark tendencies as "strong / weak / noise".
7. Meta score per champion per patch: combine pro presence, shrunk pro win rate, solo-queue current-patch strength, and patch delta → documented formula.

**Acceptance:** unit tests on synthetic data with known answers; every metric function returns value + n + interval; a notebook (no outputs committed) reproducing a Cloud9 scouting summary.

**Status (2026-11-19):** done. `fele stats` (7 s) writes 12 `stats_*` tables; methods in `docs/METHODOLOGY.md`; Cloud9 summary in `engine/notebooks/cloud9_scouting.ipynb`. Finding: pro champion win rates are mostly noise (EB prior strength 180–670 games, jungle fully pooled).

**🛑 Checkpoint:** human sanity-checks numbers against own LoL knowledge.

---

### Phase 6 — First dashboard (vertical slice)

**Goal:** a coach can open the app, pick an opponent, and read a useful report.

**Tasks**
1. Precompute aggregates to `data_local/aggregates/` (JSON/Parquet). The API serves only these — never raw events.
2. FastAPI endpoints: `/teams`, `/teams/{id}/scouting`, `/teams/{id}/players`, `/meta?patch=`, `/coverage` (sample sizes per team/league).
3. Web pages: team picker → Scouting overview (priority table by side/phase/game number), Player pools (icons, comfort, form), Macro context (heatmap + timings), Meta view (current patch), Data coverage. Evidence badges ("n=12") everywhere.
4. Simple password gate for the hosted demo (env `DEMO_PASSWORD`), Riot legal boilerplate in the footer.
5. Design: clear visual hierarchy, coach-friendly language, dark and light mode, fast.

**Acceptance:** report for Cloud9's most frequent opponent loads in < 1 s locally; every number has n; Lighthouse accessibility ≥ 90.

**Status (2026-11-19):** done. API (`/teams`, `/teams/{id}/scouting|players|macro`, `/meta`, `/coverage`, `/info`, `/login`) serves aggregates only; web pages Teams → Draft / Players / Macro, Meta, Data. Cloud9's most frequent opponent (FlyQuest) renders in ~330 ms on the dev server (API 3–20 ms); Lighthouse accessibility 100. `DEMO_PASSWORD` gate with HttpOnly HMAC cookie.

**🛑 Checkpoint:** human records a 30-second screen capture and, if possible, asks for feedback in Cloud9 Discord office hours.

---

### Phase 7 — Evaluation harness & baselines (before any fancy model)

**Goal:** a rigorous, reusable way to judge every model.

**Tasks**
1. Implement the validation protocol from Section 5.4 (walk-forward splits by date, series-grouped, final holdout locked).
2. Metrics: log loss, Brier score, ROC AUC, accuracy, calibration (reliability curve, ECE); for the action model: top-1/5/10 accuracy, log loss, mean reciprocal rank.
3. Paired bootstrap over series for model comparisons; learning curves; result reports written to `docs/experiments/` and MLflow.
4. Baselines: outcome — constant 0.5, blue-side rate, team-Elo-only logistic; action — global frequency per patch window, team frequency per slot.
5. Leakage tests: automated checks that every feature row only uses data with timestamps before the game start (Section 5.3).

**Acceptance:** one command (`fele evaluate --model baseline_elo`) produces a full report; leakage tests pass.

**Status (2026-11-19):** done. `fele evaluate --model baseline_elo` → `docs/experiments/2026-11-19-baseline_elo.md` (+ MLflow) in ~4 s. Holdout = latest 112 series (2026-02-27 → 2026-10-12), locked and single-use. Bar to beat: outcome log loss 0.628 (Elo), draft top-10 50.7% (global frequency). Leakage tests pass on synthetic and real data. Method: `docs/METHODOLOGY.md`.

**🛑 Checkpoint:** human reviews the baseline report — these numbers are the bar to beat.

---

### Phase 8 — Model ladder (the main ML effort)

**Goal:** the best model that is *justified by validation*, not the most complex one.

Climb the ladder in Section 5.5 step by step. For each rung: build features, train, evaluate with the Phase 7 harness, write an experiment report, decide promote/reject using the promotion rule. Train both model families:

- **A. Draft outcome model** — P(blue wins | final draft, teams, players, patch, side, series context).
- **B. Draft action model** — P(next pick/ban = champion c | draft state, team, series Fearless state, patch).

Also:
1. Hyperparameters via nested walk-forward (inner folds only), Optuna with small budgets.
2. Interpretability: coefficients for linear models, SHAP for GBM, posterior summaries for Bayesian models.
3. Calibration post-processing (isotonic/Platt) fitted only on inner validation folds.
4. At the very end: evaluate the chosen models **once** on the final holdout; write `docs/MODEL_CARD.md` (data, features, metrics with CIs vs baselines, calibration, known failure modes, what the model must not be used for).

**Acceptance:** the chosen model beats the Elo baseline on walk-forward log loss with a paired-bootstrap 95% CI excluding zero, and is calibrated (ECE ≤ 0.05). If nothing beats the baseline meaningfully, report that honestly and keep the simpler model — an honest result is better for the judges than an overfit one.

**Status (2026-11-20):** done. 16 outcome rungs (linear, Bayesian, unsupervised features, trees, kernels, kNN, boosting with Optuna, calibration, ensembles) + 2 draft-action models, all nested-tuned. Outcome: nothing beats Elo significantly → **Elo kept**. Draft actions: **LambdaRank** (top-10 69% → 64% on holdout vs 51% / 41% baseline). Holdout used once (decision committed first). See `docs/MODEL_CARD.md`.

**🛑 Checkpoint:** human reads the model card and approves the model choice.

---

### Phase 9 — Recommendation engine & Fearless series simulator

**Goal:** turn models into coach decisions.

**Tasks**
1. **Draft rollout:** given a partial draft, sample completions with model B (respecting draft order, roles still open, Fearless locks, bans) → estimate live win probability with model A as the mean over rollouts + interval.
2. **Recommendations:** for our next action, score candidates (top ~25 by prior) with expectimax over the opponent's response (depth 1–2, beam search), objective = expected win probability; also offer constrained modes ("comfort only", "save for later games"). Output top 5 with reason codes (e.g. *denies opponent comfort pick (8/10 games)*, *counters picked jungler*, *fills AP damage gap*, *strong on current patch*, *low Fearless cost*).
3. **Series simulator:** Monte Carlo over a Bo3/Bo5 (side selection rules from Phase 0), hard Fearless locks, opponent behaviour from model B. Outputs: probability each key champion is still available in game k, expected pool depletion per player, value of saving a champion (win-prob difference across the series), series win probability per plan.
4. **Comp analyzer:** from attribute tags → damage split, engage/peel balance, scaling curve, warnings; contribution of each pick to model A's output.
5. Performance: a recommendation request returns in < 2 s (precompute, vectorize, cache).

**Acceptance:** back-test — on held-out real drafts, how often were the team's actual picks within our top 5, and did recommended alternatives have higher predicted win probability (report, don't overclaim); simulator respects Fearless in 100% of simulated series (property-based tests).

**Status (2026-11-20):** engine done (`fele.engine`): live context, ranked options with reasons (< 0.4 s), depth-1 expectimax, rollout win probability, comp analyzer, Fearless series simulator, API (`/draft/recommend`, `/series/simulate`, `/champions`). Back-test and Fearless property tests in place. The mock-draft UI is Phase 10.

**🛑 Checkpoint:** human plays through a mock Bo5 vs a real opponent and notes anything a coach would find wrong.

---

### Phase 10 — Product integration

**Goal:** a complete, coherent product (the "Design" criterion).

**Tasks**
1. **Mock draft board:** real pro draft order, champion grid with search/role filters, Fearless-locked champions greyed out with the game they were used in, live win-probability bar with uncertainty band, recommendation panel with reasons.
2. **Fearless series planner:** game tabs G1–G5, locked list, per-player remaining pools for both teams, save list, scenario branches ("if we lose G1"), import/export plan as JSON/CSV (replaces the spreadsheet).
3. **"How to win" cards:** generated from statistics + model outputs, each with evidence and n, e.g. "They first-pick X in 60% of G1s (6/10). Banning X lowers their predicted G1 win probability by Y pp (interval)."
4. Coach inputs: editable Cloud9 champion pools and priorities stored locally per user.
5. Empty states, loading states, error handling; keyboard shortcuts in the draft board.

**Acceptance:** a full flow (choose opponent → read report → plan series → run mock draft) works without dead ends; usability pass by someone who plays LoL but didn't build it.

**Status (2026-11-20):** done in `web/`: mock draft board (`/draft`, keyboard: `/` search, `1`–`5` take option,
Backspace undo, `S` skip ban), Fearless series planner (`/planner`: games, locks, remaining pools, save list,
simulate with a "lose the next game" branch, JSON/CSV import/export), "how to win" cards on each scouting page,
coach inputs (`/coach`, stored in the browser). Full flow checked in Chrome; usability pass by an outside player
still open.

**🛑 Checkpoint:** human approves the flow that will be shown in the video.

---

### Phase 11 — Hardening, deployment, submission

**Tasks**
1. Deploy: web (Vercel/Cloudflare Pages) + API (Fly.io/Render) or one container; only aggregates and model artifacts uploaded (verify the bundle contains no raw GRID data); password gate; uptime monitoring until 2027-02-03.
2. Judge-facing `README.md`: problem, users, features, screenshots, architecture, how to run locally (incl. cloning the GRID repo next to the project and running ingest), JetBrains tools used and what each did, data sources and licenses, Riot boilerplate, limitations.
3. `docs/METHODOLOGY.md` (submission write-up): data, statistics, models, validation, results vs baselines, limitations.
4. `AI_SHOWCASE.md` final edit: workflow with JetBrains Air/Junie/Claude, concrete examples, what AI got wrong and how it was caught.
5. Video script (< 3 min): 0:00 problem (coach spreadsheet) → 0:20 scouting report → 1:00 Fearless series planner → 1:50 mock draft with live win probability and reasons → 2:30 how it's built (JetBrains + ML validation) → 2:50 close. No broadcast footage, no copyrighted music.
6. Final checklist (Section 7).

**Status (2026-11-20):** in progress. Done without the human: judge-facing `README.md` (problem, flow, architecture,
honest results), `docs/VIDEO_SCRIPT.md`, the live context slimmed to the state the server needs (161 MB → 5 MB, no
per-game draft rows), CI gates for dead code and vulnerable dependencies, a synthetic draft world so CI tests the
engine end to end. Waiting on the human: hosting choice and the organizer question on hosted aggregates
(COMPLIANCE §4), screenshots (they show GRID-derived numbers), recording the video.

**2026-11-21: scope extended by the human** (plan: fele Live via the League client, UX pass, E2E tests, AI features;
details in docs/COMPLIANCE.md and AI_SHOWCASE.md). Milestone 1 (fele Live for the user's own champ select) done.

**🛑 Checkpoint:** human submits on Devpost by 2027-01-09.

---

## 5. Modeling specification

### 5.1 Problems

| ID | Question | Target | Unit |
|---|---|---|---|
| A | Who wins given the draft? | blue win (0/1) | game |
| B | What will this team pick/ban next? | champion among available ones | draft action |
| C | What should we pick/ban? | ranked options (A + B combined) | decision |
| D | How does the series play out? | series outcome, pool depletion | Bo3/Bo5 |

### 5.2 Features (all computed time-respecting, as of the game's start)

- **Context:** side, patch window, league, game number in series, series score, Fearless locked count, days since patch release.
- **Team strength:** pre-match Elo/Glicko (per league), recent form, side-specific performance.
- **Champion strength:** shrunk pro win rate (patch-window weighted), pro presence/priority, current solo-queue strength for the champion-role, patch delta (buff/nerf magnitude).
- **Player–champion comfort:** pro games on champion (recency-weighted), shrunk pro win rate on it, solo-queue games on current patch (if approved), first-time-on-stage flag.
- **Composition:** aggregated attribute tags per team (AD/AP share, frontline, engage, peel, poke, scaling), difference blue − red, balance flags.
- **Interactions:** lane matchup and duo synergy terms as shrunk estimates (hierarchical / factorization), never raw tiny-sample win rates.
- **Action model only:** slot index, roles still open, team's historical priority for the champion in this slot/phase, ban-target signal (champion in opponent player pools), counter/synergy with picks so far, Fearless availability.

### 5.3 Leakage checklist (automated tests in Phase 7)

- ❌ In-game stats (gold, kills, objectives) as draft-model features — they happen after the draft.
- ❌ Any aggregate (win rates, Elo, comfort, priority) computed with the current game or later games.
- ❌ Games from the same series split across train and test folds.
- ❌ Solo-queue data dated after the match.
- ❌ Patch information from later patches (e.g. using the 16.17 tag file to describe a 15.3 game is fine only for static attributes, never for strength).
- ❌ Hyperparameter tuning or calibration on the outer test folds or holdout.

### 5.4 Validation protocol

1. Sort series by date. **Final holdout:** the most recent ~15% of series (expected: late LCS Split 3 2026 + LCS Promotion 2026 + end of LEC Spring 2026 — confirm in Phase 7). Locked until the end of Phase 8.
2. **Walk-forward outer folds** on the rest: e.g. train on everything before month m, test on month m, for the last ~8 months; aggregate metrics over folds.
3. **Grouping:** split by series, never by game.
4. **Inner folds** (inside each training window) for hyperparameters and calibration.
5. Report every metric with a paired bootstrap 95% CI (resampling series) and the difference to the Elo baseline.
6. Sub-reports: by league, by game number (G1 vs G3+), by patch age, and for Cloud9 games only (small n — descriptive).

### 5.5 Complexity ladder & promotion rule

| Rung | Outcome model (A) | Action model (B) |
|---|---|---|
| L0 | constant, blue-side rate | global frequency per patch window |
| L1 | logistic: side + Elo | team-specific frequency per slot (smoothed) |
| L2 | + champion strength, player comfort (L2-regularized logistic) | conditional logit over available champions with priority + comfort features |
| L3 | + composition tags, shrunk matchup/synergy terms | + roles-open, counter/synergy, ban-target features |
| L4 | LightGBM, strong regularization, monotone constraints where sensible (e.g. Elo ↑ → win ↑) | LightGBM LambdaRank over candidate champions |
| L5 | hierarchical Bayesian (PyMC/NumPyro): team, player×champion, champion×patch random effects | hierarchical multinomial for team tendencies with league-level pooling |
| L6 (optional) | set-based neural model (DeepSets/attention over 10 champions) | sequence model over draft actions |

**Promotion rule:** a rung replaces the current model only if
(1) walk-forward log loss improves with a paired-bootstrap 95% CI below zero,
(2) calibration ECE ≤ 0.05 (after inner-fold calibration),
(3) it is not worse on the G3+ (Fearless late-game) slice,
(4) its explanations still make sense to a LoL expert.
Otherwise keep the simpler model and record why. **Expect small gains**: the draft is only one of many factors in a pro game, and ~1.7k games is a small dataset. An ensemble of the best two rungs is allowed if it passes the same rule.

### 5.6 Uncertainty everywhere

- Win probabilities shown with intervals (bootstrap, posterior, or rollout spread).
- Recommendations show expected gain **and** its uncertainty; if gains overlap, say so ("these 3 options are statistically similar").
- Tendencies labeled strong/weak/noise (Phase 5, task 6).

---

## 6. Timeline (8 weeks)

| Week | Dates | Phases |
|---|---|---|
| 1 | Nov 18 – Nov 24 | Register, redeem JetBrains codes, Phase 0, Phase 1 |
| 2 | Nov 25 – Dec 1 | Phase 2, Phase 3 |
| 3 | Dec 2 – Dec 8 | Phase 4 (start sampler early — it needs days), Phase 5, Phase 6 |
| 4 | Dec 9 – Dec 15 | Phase 7, Phase 8 rungs L1–L2 |
| 5 | Dec 16 – Dec 22 | Phase 8 rungs L3–L5, holdout evaluation, model card |
| 6 | Dec 23 – Dec 29 | Phase 9 (lighter week — holidays) |
| 7 | Dec 30 – Jan 5 | Phase 10, start Phase 11 deployment |
| 8 | Jan 6 – Jan 9 | Phase 11: docs, video, final checklist, **submit Jan 9** |

**Cut order if behind:** L6 → pro players' solo-queue → "how to win" cards → L5 → scenario branches in the series planner. Never cut: scouting report, Fearless planner, validated model with honest metrics.

---

## 7. Final submission checklist

- [ ] Public repo; LICENSE visible in GitHub About section
- [ ] `git log --all --name-only | grep -Ei '\.(zst|jsonl|parquet|sqlite|duckdb)$'` prints nothing (whole history)
- [ ] No API keys anywhere in history
- [ ] README: run instructions incl. GRID repo clone + ingest; JetBrains tools and their roles; data sources + licenses; Riot boilerplate
- [ ] `.idea` / `.air` / `.junie` folders committed (no secrets inside)
- [ ] Demo URL works in a private browser window; login credentials in the Devpost testing instructions; stays up until 2027-02-03
- [ ] Video < 3:00, public on YouTube, no broadcast footage or copyrighted music
- [ ] Devpost text description, methodology write-up, category = Category 2
- [ ] Bonus: link to `AI_SHOWCASE.md`
- [ ] All materials in English
- [ ] Submitted before 2027-01-12 11:00 PT (target 2027-01-09)

---

## 8. Open questions for the human (answer before the related phase)

1. Solo or team entry? (Affects who submits as Representative.)
2. Which Riot regions matter most for the meta sampler (KR, EUW, NA)?
3. Will the coach enter pro players' Riot IDs manually, or did Phase 0 approve a source?
4. Hosting provider and budget (free tiers are enough).
5. Any answer from organizers about serving aggregates in a hosted demo?
