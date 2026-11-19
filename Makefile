# fele developer shortcuts. `make help` lists them.
.PHONY: help setup data check fix test qodana up down db

help:  ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

setup:  ## install toolchain + dependencies, enable the data-leak hook
	brew bundle --file=Brewfile || true
	cd engine && uv sync --all-extras --all-groups
	cd web && pnpm install
	git config core.hooksPath .githooks
	cd engine && uv run nbstripout --install --attributes ../.gitattributes

data:  ## ingest GRID, fetch static/external data, build the DuckDB catalog (needs the GRID clone + .env)
	cd engine && uv run fele ingest && uv run fele fetch-ddragon && uv run fele fetch-leaguepedia-hf && uv run fele db

check:  ## everything CI runs (lint, format, types, tests, data-leak guard)
	scripts/check_no_data.sh
	cd engine && uv run ruff check src tests && uv run ruff format --check src tests && uv run pyright && uv run pytest
	cd web && pnpm lint && pnpm typecheck && pnpm coverage

fix:  ## auto-fix lint + formatting
	cd engine && uv run ruff check --fix src tests && uv run ruff format src tests
	cd web && pnpm format

test:  ## tests only
	cd engine && uv run pytest
	cd web && pnpm test

qodana:  ## JetBrains Qodana scan in Docker (report: scratch/qodana)
	docker compose --profile qodana run --rm qodana

up:  ## run web (http://localhost:8080) + API (http://localhost:8000/docs) in Docker
	docker compose up --build -d

down:  ## stop the Docker stack
	docker compose down

db:  ## rebuild data_local/fele.duckdb views
	cd engine && uv run fele db
