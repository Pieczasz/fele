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
