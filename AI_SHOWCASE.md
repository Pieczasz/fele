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
