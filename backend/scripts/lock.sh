#!/usr/bin/env sh
set -eu
LOCK_CUTOFF="2026-10-30T00:00:00Z"
OUT="${1:-.}"
cd "$(dirname "$0")/.."
for spec in "requirements.lock:--extra ml" "requirements-dev.lock:--extra ml --extra dev"; do
  file="${spec%%:*}"
  extras="${spec#*:}"
  uv pip compile pyproject.toml $extras --universal --python-version 3.12 --generate-hashes \
    --exclude-newer "$LOCK_CUTOFF" --no-header -q -o "$OUT/$file"
done
