#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_FILE="${1:-}"
TARGET_DATABASE="${2:-}"

if [[ -z "$BACKUP_FILE" || -z "$TARGET_DATABASE" ]]; then
  printf 'Usage: %s <backup.dump> <target_database>\n' "$0" >&2
  exit 1
fi
if [[ ! -f "$BACKUP_FILE" ]]; then
  printf 'Backup file not found: %s\n' "$BACKUP_FILE" >&2
  exit 1
fi
if [[ ! "$TARGET_DATABASE" =~ ^[A-Za-z0-9_]+$ ]]; then
  printf 'Target database contains unsupported characters.\n' >&2
  exit 1
fi
if [[ "${RESTORE_CONFIRM:-}" != "RESTORE:$TARGET_DATABASE" ]]; then
  printf 'Set RESTORE_CONFIRM=RESTORE:%s to confirm destructive restore.\n' "$TARGET_DATABASE" >&2
  exit 1
fi

docker compose -f "$COMPOSE_FILE" exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$1" --clean --if-exists --no-owner --no-privileges' \
  restore "$TARGET_DATABASE" < "$BACKUP_FILE"

printf 'Restore completed for database: %s\n' "$TARGET_DATABASE"
