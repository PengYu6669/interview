#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-./backups/postgres}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  printf 'Compose file not found: %s\n' "$COMPOSE_FILE" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd -P)"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="$BACKUP_DIR/interview_copilot_$TIMESTAMP.dump"
TEMP_FILE="$BACKUP_FILE.partial"

cleanup() {
  rm -f -- "$TEMP_FILE"
}
trap cleanup EXIT

docker compose -f "$COMPOSE_FILE" exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-privileges' \
  > "$TEMP_FILE"

if [[ ! -s "$TEMP_FILE" ]]; then
  printf 'Backup command produced an empty archive.\n' >&2
  exit 1
fi

mv -- "$TEMP_FILE" "$BACKUP_FILE"
trap - EXIT
printf 'Backup created: %s\n' "$BACKUP_FILE"
