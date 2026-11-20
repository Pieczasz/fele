# AI-Powered Workflow Story

How fele was built with AI agents (JetBrains Air / Junie / Claude) under human review.
One entry per phase of [AGENT_PLAN.md](AGENT_PLAN.md): what was asked, what the agent produced, what the human corrected.

## Workflow

- The human writes a phased plan with acceptance criteria and checkpoints (`AGENT_PLAN.md`).
- The agent runs one phase at a time, with ground rules: never commit data, never print secrets, cite sources, mark unverified claims.
- Research is delegated to parallel sub-agents (rules, Riot platform, external data sources), each writing a cited report to `docs/research/`.
- Guardrails are code, not promises: `scripts/check_no_data.sh` runs as a pre-commit hook and in CI.

## Log

### Phase 0 + 1 — Research, compliance, scaffold (2026-11-18)

- **Asked:** research rules/licenses/data sources, scaffold the monorepo, gather all legal data, support coach/player preferences.
- **Agent produced:** three parallel research reports with citations; `docs/COMPLIANCE.md`; uv/Python 3.14 engine with GRID
  streaming reader, Data Dragon client, rate-limited cached Riot API client, solo-queue sampler; coach preferences schema;
  React/Vite web shell with typed API client; CI with data-leak check; PyCharm run configurations.
- **Caught along the way:**
  - Pyright flagged `typer.Exit("message")` — Exit takes an exit code, so error messages would have been lost.
  - `openapi-typescript` crashes on TypeScript 7 (native port has no JS API) → generator runs via `pnpm dlx` with TS 5.9.
  - Roster order in GRID is not role order (Cloud9's latest roster listed a support as "top") → role inference stays a Phase 2 task.
- **Human corrections:** _(fill in at checkpoint)_

### Tooling round — strict quality gates, Docker, rename to fele (2026-11-19)

- **Asked:** JetBrains Qodana in CI, strict lint/format for Python and TypeScript, Docker for every service, DuckDB in PyCharm,
  rename the project to `fele`, audit the ML/statistics toolchain, publish to a public GitHub repo with `.idea` committed.
- **Agent produced:** Ruff `select = ["ALL"]` + Pyright strict (fixed ~200 findings by typing JSON payloads properly);
  Biome + strict `tsc`; Qodana workflow + local `docker compose --profile qodana` run; Compose stack (api, web/nginx,
  CLI, Qodana); `fele db` DuckDB catalog + shared PyCharm data source; ML extra (PyMC, statsmodels, MAPIE, Optuna, SHAP,
  MLflow) verified on Python 3.14 with a tiny PyMC sampling check; Makefile + Brewfile; coverage gates.
- **Caught along the way:**
  - Biome's `all` preset enables Solid/Qwik/React Native rules; its autofix rewrote React `className` to `class`.
    Switched to recommended + all React rules + a hand-picked strict set, and reverted the damage.
  - Qodana found 5 real issues ruff/pyright missed (functional `StrEnum` PyCharm can't type, mutable default argument,
    shadowed names, a confusing `max()` over a set) → fixed, now 0 problems.
  - The Qodana image ships Python 3.12, fele needs 3.14 → `bootstrap` builds a uv venv in Qodana's cache dir so the
    host `.venv` is never touched.
  - In Docker the computed repo root is `/`, so config lookup only worked by accident → explicit `FELE_CONFIG_DIR`.
  - A deprecation warning suggested installing an unfamiliar package (`httpx2`); the install was blocked as a
    supply-chain risk, and the API tests switched to `httpx.ASGITransport` instead.
- **Human corrections:** project name (`fele`), Docker + DuckDB-in-PyCharm request, "commit `.idea`/`.air` as evidence".

### Phase 2 — GRID ingestion & role inference (2026-11-19)

- **Asked:** "continue working" → the plan's Phase 2: clean, tested tables from the GRID feeds, role inference,
  draft-order validation, the Fearless re-pick investigation, a data dictionary.
- **Agent produced:** a feed replayer that applies rollbacks, a 45-second parallel ingest into 10 Parquet tables
  (`lol.*` in DuckDB), role inference that scores all 120 role assignments per team-game, `fele ingest`, a
  `prefs-init` that uses the inferred roles, synthetic-feed unit tests + a `real_data` acceptance test,
  `docs/DATA_DICTIONARY.md`.
- **Caught along the way:**
  - The plan's "Smite purchase" check can't work: the feed names no jungle items or summoner spells. Neutral-monster
    kills are used instead.
  - The first role model (lane = role) agreed with players' usual roles only 88% of the time. Early-2025 lane swaps
    send the top laner bot and the duo top, and supports roam too much to anchor the duo's lane. Scoring both lane
    hypotheses with champion priors learned from confident games (EM) brought it to 99.9%. The remaining "errors"
    are real role changes (a jungler who moved to support).
  - The "5 Fearless re-picks" were draft corrections GRID rolled back; 0 remain.
  - GRID renumbers draft actions when a ban is skipped → slots are aligned to the template instead of trusting `seq`.
  - The data confirms the 2026 First Selection rule: red side picked first in ~45% of 2026 games, almost never in 2025.
  - `slayDragon` duplicates the typed drake event since 15.10 → dropped to avoid double counting.
  - Benched substitutes appear as "active" with no champion → dropped.
  - GRID ships Riot PUUIDs for pro players; deliberately not ingested (licence §3(e), no profiling via other data).
  - A formatter rewrapped a block mid-edit, leaving a reference to a not-yet-defined variable that Pyright didn't flag;
    caught by reading the function back before running it.
- **Human corrections:** _(fill in at checkpoint: spot-check Cloud9 games in PyCharm)_

### Phase 3 — Static data & champion knowledge (2026-11-19)

- **Asked:** "continue development" → the plan's Phase 3: Data Dragon for every patch, GRID ↔ Data Dragon champion
  mapping, a champion attribute tag CSV for human review, numeric patch deltas.
- **Agent produced:** `fele fetch-ddragon` (47 versions, 15.1.1 → 16.23.1) and `fele static` (DuckDB schema `static`);
  `champion_tags.csv` with 15 attributes for all 173 champions and a written rubric; a validator that fails the build on
  missing/duplicate/out-of-range tags; a check of tagged roles against roles inferred from pro games; patch deltas with
  readable change lists; synthetic unit tests + a `real_data` acceptance test.
- **Caught along the way:**
  - Data Dragon spell `effect` arrays are zeros, so damage changes can't be measured; deltas use base stats,
    cooldowns, costs and ranges, and the docs say so.
  - Patch 16.5 shows every champion "nerfed": Data Dragon set AD growth to 0 for all champions. Fields that change for
    most champions at once are now treated as game-wide and kept out of champion scores.
  - 16.15 added `Jade_*` mode variants of 60 champions → skipped.
  - Graves was only ever banned, so GRID's `characters.csv` leaves him out; the map also reads champions from drafts.
  - Shyvana was reworked in 16.6 and Locke/Zaahen came out after the agent's knowledge cutoff: their tags were drafted
    from Data Dragon ability text and flagged for review instead of guessed from memory.
- **Human corrections:** _(fill in at checkpoint: review the tag CSV, starting with rows that have a `review` note)_

### Phase 4 — Riot API: solo-queue meta sample (2026-11-19)

- **Asked:** "continue" → the plan's Phase 4: current-patch high-elo meta signal, matchups, item builds, and (only if
  approved) pro players' solo-queue pools.
- **Agent produced:** the Phase 1 sampler extended to target the live patch (counting only its games and starting
  near its release), deterministic 25% timeline sampling for item builds, a 429 counter, and partial results that
  survive interruption. Added `soloq_matchups` and `soloq_items` aggregates, plus a `player-soloq` command limited to
  coach-entered Riot IDs and off by default. Tests use synthetic Riot payloads with fake ids, including a resume test
  that proves a re-run makes no match or timeline requests.
- **Result:** 907 new patch-16.23 matches (KR 300, EUW 305, NA 302), 205 timelines, 0 rate-limit errors on a
  development key.
- **Caught along the way:** the first sample (Phase 1) was mostly the previous patch (16.22): only 10–26% of games
  were on 16.23, so the "current patch" signal was thin. The sampler now counts only target-patch games.
- **Human corrections:** _(fill in at checkpoint: key handling and data volume)_

### Phase 5 — Statistics layer (2026-11-19)

- **Asked:** "continue" → the plan's Phase 5: shrunk win rates with intervals, team draft priority (side and
  game-number splits), ban targeting, player pools, time-respecting Elo, macro context, tendency significance, meta
  score, and a Cloud9 scouting notebook.
- **Agent produced:** `fele.stats` (core / draft / pools / elo / macro / meta) and `fele stats`, which writes 12
  tables in 7 s. Every rate carries k, n and a 95% interval. 11 unit tests on hand-worked synthetic data, a
  real-data acceptance test that every interval contains its estimate, `docs/METHODOLOGY.md`, and
  `engine/notebooks/cloud9_scouting.ipynb` (committed without outputs).
- **Caught along the way:**
  - The first shrinkage fit used L-BFGS-B, which silently stopped at the parameter bounds. Every win rate was being
    pulled almost all the way to 50%. A simulation test (recover a Beta(30, 30) prior) exposed it; Nelder–Mead fixes it.
  - Priors fitted per patch window swung between no shrinkage and complete pooling (~20 games per champion per
    window), so one prior per role is now fitted over all windows.
  - Honest finding: across ~7,000 jungle games, champion win rates vary no more than chance. Shrunk pro win rates
    stay near 50%, and the meta score leans on presence instead.
  - The bootstrap interval for effective pool size sat entirely below the estimate (resampling loses rare
    champions); switched to a basic bootstrap widened to contain the estimate.
  - GRID ends at 16.17 while the solo-queue sample is 16.23, so they never shared a window → a `live` window joins
    the latest pro window with the live solo-queue sample and the Data Dragon changes since.
- **Human corrections:** _(fill in at checkpoint: sanity-check the numbers against LoL knowledge)_

### Phase 6 — First dashboard (2026-11-19)

- **Asked:** "continue with phase 6": API over the aggregates, a coach-facing web app (team picker, scouting, player
  pools, macro with heatmap, meta, coverage), evidence badges everywhere, demo password, dark and light mode.
- **Agent produced:** FastAPI endpoints with typed response models (every rate carries k, n and its interval), an
  mtime-keyed Parquet cache, a constant-time password gate with an HttpOnly HMAC cookie, and React pages built on
  shared `RateBar` / `NBadge` / `TendencyBadge` components. Data Dragon icons and map, the light/dark toggle and the
  Riot boilerplate are included. API tests use synthetic aggregates and the web tests use a fake API.
- **Checked in a real browser (Chrome DevTools):** FlyQuest (Cloud9's most frequent opponent) shows its full report
  in ~330 ms on the dev server; Lighthouse accessibility 100, best practices 96.
- **Caught along the way:**
  - React flagged a duplicate key: a player appeared once per inferred role in the "players opponents ban against"
    list. Fixed in the stats table (one row per player, most common role), not hidden in the UI.
  - The players page listed everyone whose latest game was for the team, so FlyQuest showed two top laners. The
    API now marks the current lineup (played within a week of the team's last game) and the page shows earlier
    players separately.
  - In the last 120 days some teams have only a couple of games, so the report shows the games behind each
    period.
- **Human corrections:** _(fill in at checkpoint: 30-second screen capture, Cloud9 office-hours feedback)_

### Phase 7 — Evaluation harness & baselines (2026-11-19)

- **Asked:** "lets continue do the phase 7": the validation protocol, metrics, paired bootstrap, baselines and
  leakage tests, behind one command.
- **Agent produced:** `fele.eval` (series-grouped walk-forward splits, a holdout that is locked and single-use,
  outcome and draft-action metrics, series bootstrap), `fele.features` (pre-game outcome rows; draft-action rows that
  know only earlier actions and Fearless locks), five baselines, and `fele evaluate` with a markdown report and an
  MLflow run. Leakage tests run on synthetic data and the real 745 series.
- **Findings:** the latest 15% of series is all 2026 LCS/LEC (no LCK or LTA in 2026), so the holdout tests a
  different league mix than most training data. Side alone predicts nothing out of sample, and Elo is a strong
  bar (log loss 0.628, AUC 0.71).
- **Caught along the way:**
  - The first team-specific draft baseline lost to the global one: it counted a team's whole history, so champions
    from long-gone patches dominated. Fixed once, by design (same recent-patch window as the global baseline), and
    then left alone. More tweaking would have been tuning on the test folds. It now ranks better but is
    overconfident, and the report shows both.
  - The paired comparison initially sorted one model's rows by its own predictions, which would silently misalign
    the pairs. Rows are now kept in fold order and their alignment is asserted.
  - scikit-learn ships no type stubs: one small adapter module is checked in Pyright basic mode, so the rest stays
    strict.
- **Human corrections:** _(fill in at checkpoint: review the baseline report)_

### Phase 8 — Model ladder (2026-11-19 → 2026-11-20)

- **Asked:** "make sure we are not overfitting, you can try many python libs, many forms of machine learning:
  supervised, unsupervised, regressions, parametrized and non parametrized methods, everything possible".
- **Agent produced:** a time-respecting feature store; 16 outcome models across regularised regression,
  hierarchical Bayes (PyMC), unsupervised archetypes (SVD + k-means), kNN, random forest, extra trees, RBF SVM,
  Gaussian process, naive Bayes, LightGBM (grid + Optuna), Platt/isotonic calibration and ensembles; a conditional
  logit and LambdaRank for draft actions; explanations (coefficients, SHAP, posterior summaries); a model card; and a
  one-time holdout run.
- **How overfitting was kept out:**
  - Features see only the past. A real-data test flips every later result and scrambles every later draft, and
    requires earlier features to be identical.
  - All tuning happens on inner folds.
  - A pre-registered promotion rule decides, with paired series bootstraps.
  - The decision was committed (`ef5a890`) before the holdout was opened, and the holdout was used exactly once.
- **Findings:** who wins is barely predictable beyond Elo. Every outcome model landed within 0.005 log loss of Elo
  or was significantly worse, so Elo stays, and the holdout agrees. The next pick/ban is very predictable:
  LambdaRank reaches 69% top-10 on the walk-forward folds and 64% on the holdout, against 51% and 41% for the
  baseline.
- **Caught along the way:**
  - The first regularised model *lost* to Elo: uniform L2 shrank the strong Elo signal along with the noise. It now
    uses a custom penalised logistic regression with Elo unpenalised.
  - The champion vocabulary was built from the games, so it depended on future drafts. The leakage test caught it;
    the vocabulary now comes from the static champion map.
  - kNN crashed when an early inner fold was smaller than k, and the GP constructor ignored its own parameter grid.
    Both are fixed and covered by smoke tests.
  - The holdout calibration error (0.069) looked like a failure, but a simulation showed that a perfectly
    calibrated model scores 0.056 (90% range 0.033–0.084) on 316 games, so it is reported as noise rather than
    hidden or "fixed".
- **Human corrections:** _(fill in at checkpoint: approve the model choice in docs/MODEL_CARD.md)_

### Phase 9 — Recommendation engine & Fearless simulator (2026-11-20)

- **Asked:** recommendations that "help pick the best champion based on already picked ones, preferences, team comp,
  team playing style, enemy team, and last matches/games", as long as they have a real basis.
- **Agent produced:** `fele.engine` with:
  - a live context: production models refit on all games, cached;
  - a draft state with the pro order and Fearless locks;
  - ranked options in under 0.4 s, each part a reason with its evidence count: pro behaviour (LambdaRank), coach
    comfort, the player's recent games, composition gaps, style fit, shrunk solo-queue lane matchups, and the win
    probability after the enemy's likeliest answers;
  - ban threat from the enemy's side, rollout win probability, and a composition analyzer;
  - a Monte Carlo Fearless Bo3/Bo5 simulator;
  - API endpoints, a back-test, and property tests.
- **Caught along the way:**
  - The Hypothesis property test found a real simulator bug: a game result moved a series into the other side group
    within the same round, so a "best of 3" could play 4 games and series odds were skewed.
  - Plan comparisons were easy to over-read (59% vs 69% with 100 sims each). The API now returns the difference
    with its standard error and a "within noise" flag.
  - A ban reason could say "if they get it: +0.8% for us", which argues against the ban. Fixed.
  - The back-test shows the extra parts (comp, style, lane) make the engine match pro picks slightly *less*. That is
    reported as-is, and the weights stay fixed: tuning them on holdout drafts would be the overfitting the user
    asked to avoid.
- **Human corrections:** _(fill in at checkpoint: mock Bo5 vs a real opponent)_

### Phase 10 — Product integration (2026-11-20)

- **Asked:** "continue": the mock draft board, the Fearless series planner, "how to win" cards and coach inputs.
- **Agent produced:**
  - `/draft`: pro draft order, champion grid with search, role filter and Fearless locks (labelled with the game),
    win-probability bar with its range, ranked options with reasons, keyboard shortcuts, and "save to series";
  - `/planner`: game tabs, locks, remaining pools for both teams, a save list, simulation with a "lose the next game"
    branch and a "within noise" flag, plus JSON/CSV import and export;
  - "how to win" cards on each scouting page, each with evidence n and a strength label;
  - `/coach`: pools, comfort, style and must-bans, stored in the browser.
- **Caught along the way:**
  - Driving the flow in Chrome showed the planner's availability table labelled a simulation from game 2 as "G1". The
    API now returns `first_game`.
  - Ban slots truncated champion names to "N..". They now show the icon only, with the name for screen readers and
    as a tooltip.
- **Human corrections:** _(fill in at checkpoint: approve the video flow)_
