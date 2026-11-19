#!/usr/bin/env bash
# Fails if any tracked or staged file looks like licensed data or is larger than 5 MB.
# Usage: scripts/check_no_data.sh            (checks tracked + staged files)
#        scripts/check_no_data.sh --history  (also scans the whole git history)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

PATTERN='\.(zst|jsonl|parquet|sqlite3?|duckdb|arrow|feather)$|stl-hackathon-2026-grid-starter/|(^|/)data_local/|(^|/)riot_cache/|(^|/)mlruns/|(^|/)\.env$|(^|/)meta/(games|rosters|players|teams|tournaments|characters)\.csv$|(^|/)series\.csv$'
MAX_BYTES=$((5 * 1024 * 1024))
fail=0

files=$( { git ls-files; git diff --cached --name-only --diff-filter=ACMR; } | sort -u )

bad=$(printf '%s\n' "$files" | grep -Ei "$PATTERN" || true)
if [[ -n "$bad" ]]; then
  echo "❌ Data-like files are tracked or staged (licensed data must never be committed):"
  printf '   %s\n' $bad
  fail=1
fi

while IFS= read -r f; do
  [[ -f "$f" ]] || continue
  size=$(wc -c < "$f")
  if (( size > MAX_BYTES )); then
    echo "❌ File larger than 5 MB: $f ($size bytes)"
    fail=1
  fi
done <<< "$files"

if [[ "${1:-}" == "--history" ]]; then
  hist=$(git log --all --name-only --pretty=format: | sort -u | grep -Ei "$PATTERN" || true)
  if [[ -n "$hist" ]]; then
    echo "❌ Data-like files found in git history:"
    printf '   %s\n' $hist
    fail=1
  fi
fi

if (( fail )); then exit 1; fi
echo "✅ No data files tracked or staged."
