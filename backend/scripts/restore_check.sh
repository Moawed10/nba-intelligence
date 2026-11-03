#!/usr/bin/env sh
set -eu
DUMP="${1:?usage: restore_check.sh <dump-file> [source-database]}"
SOURCE="${2:-}"
TARGET="nba_restore_check_$$"
TABLES="players games player_game_stats team_game_stats predictions prediction_values prediction_evaluations game_predictions model_releases model_versions model_evaluations ingestion_runs"
counts() {
  for table in $TABLES; do
    printf '%s ' "$table"
    psql -d "$1" -Atc "SELECT count(*) FROM $table"
  done
}
(cd "$(dirname "$DUMP")" && shasum -a 256 -c "$(basename "$DUMP").sha256")
createdb "$TARGET"
trap 'dropdb --if-exists "$TARGET"' EXIT
pg_restore --no-owner --exit-on-error --dbname="$TARGET" "$DUMP"
counts "$TARGET" > "$DUMP.restored-counts"
cat "$DUMP.restored-counts"
if [ -n "$SOURCE" ]; then
  counts "$SOURCE" | diff - "$DUMP.restored-counts"
  echo "row counts match $SOURCE"
fi
echo "restore verified"
