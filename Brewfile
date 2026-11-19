# Local toolchain for fele: `brew bundle`
tap "jetbrains/utils"

brew "uv"        # Python 3.14 + engine dependencies
brew "node"      # web app
brew "pnpm"
brew "duckdb"    # query data_local/fele.duckdb from the terminal
brew "zstd"      # peek into GRID .zst feeds (zstdcat file | head)
brew "jq"        # inspect JSON (Riot responses, OpenAPI spec)
brew "gh"        # GitHub CLI
# Qodana CLI (optional; `docker compose --profile qodana run --rm qodana` works without it).
# Third-party tap: run `brew trust jetbrains/utils` first if you want it.
brew "jetbrains/utils/qodana"
