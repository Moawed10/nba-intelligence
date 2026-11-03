#!/usr/bin/env sh
set -eu
DATABASE="${1:?usage: backup.sh <database-or-url> <directory> [keep-days]}"
DIRECTORY="${2:?usage: backup.sh <database-or-url> <directory> [keep-days]}"
KEEP_DAYS="${3:-14}"
mkdir -p "$DIRECTORY"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="$DIRECTORY/nba-intelligence-$STAMP.dump"
pg_dump --format=custom --no-owner --file="$FILE.partial" --dbname="$DATABASE"
pg_restore --list "$FILE.partial" > /dev/null
mv "$FILE.partial" "$FILE"
(cd "$DIRECTORY" && sha256sum "$(basename "$FILE")" > "$(basename "$FILE").sha256" 2>/dev/null \
  || shasum -a 256 "$(basename "$FILE")" > "$(basename "$FILE").sha256")
find "$DIRECTORY" -name 'nba-intelligence-*' -mtime "+$KEEP_DAYS" -delete
echo "$FILE"
