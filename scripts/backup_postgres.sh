#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backup_dir="${BACKUP_DIR:-$project_dir/backups}"
retention_days="${BACKUP_RETENTION_DAYS:-7}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$backup_dir/newsradar-$timestamp.dump"
temporary="$target.tmp"
trap 'rm -f "$temporary"' EXIT

cd "$project_dir"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

compose=(
  docker-compose
  --env-file .env.prod
  -f docker-compose.prod.yml
)

"${compose[@]}" exec -T db sh -lc \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$temporary"

test -s "$temporary"
mv "$temporary" "$target"

# Verify that pg_restore can read the archive before considering it a backup.
"${compose[@]}" exec -T db pg_restore --list < "$target" > /dev/null

find "$backup_dir" -maxdepth 1 -type f -name 'newsradar-*.dump' \
  -mtime "+$retention_days" -delete

echo "Backup created: $target"
