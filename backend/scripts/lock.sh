#!/usr/bin/env sh
# Regenerates the hash-pinned lock files from pyproject.toml for every platform.
# Resolution ignores releases newer than LOCK_CUTOFF, so the same inputs always give the same files.
# Raise LOCK_CUTOFF (and re-run) to take dependency updates. Usage: scripts/lock.sh [output-dir]
set -eu
LOCK_CUTOFF="2026-10-30T00:00:00Z"
OUT="${1:-.}"
cd "$(dirname "$0")/.."
for spec in "requirements.lock:--extra ml" "requirements-dev.lock:--extra ml --extra dev"; do
  file="${spec%%:*}"
  extras="${spec#*:}"
  # shellcheck disable=SC2086
  uv pip compile pyproject.toml $extras --universal --python-version 3.12 --generate-hashes \
    --exclude-newer "$LOCK_CUTOFF" --no-header -q -o "$OUT/$file"
done
