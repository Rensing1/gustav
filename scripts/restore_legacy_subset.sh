#!/usr/bin/env bash
set -euo pipefail

# Restore only the minimal subset of objects from a Supabase backup needed
# for Keycloak user import: auth.users and public.profiles into a temporary DB.

if [[ $# -lt 7 ]]; then
  echo "Usage: $0 <dump_tar_gz> <db_host> <db_port> <db_user> <db_pass> <target_db> <workdir>" >&2
  exit 2
fi

DUMP_TGZ="$1"; shift
DB_HOST="$1"; shift
DB_PORT="$1"; shift
DB_USER="$1"; shift
DB_PASS="$1"; shift
TARGET_DB="$1"; shift
WORKDIR="$1"; shift

mkdir -p "$WORKDIR/legacy_full"
tar -xzf "$DUMP_TGZ" -C "$WORKDIR/legacy_full"

DUMP_FILE="$(find "$WORKDIR/legacy_full" -type f -name db_all.dump | head -n1)"
if [[ -z "$DUMP_FILE" ]]; then
  echo "db_all.dump not found in $DUMP_TGZ" >&2
  exit 1
fi

export PGPASSWORD="$DB_PASS"

dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" --if-exists "$TARGET_DB" || true
createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$TARGET_DB"

# Prepare required extensions/schemas to satisfy table definitions
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TARGET_DB" -v ON_ERROR_STOP=1 \
  -c 'create extension if not exists pgcrypto;' \
  -c 'create extension if not exists "uuid-ossp";' \
  -c 'create schema if not exists auth;' >/dev/null

# Restore only table definitions and data for auth.users and public.profiles
pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TARGET_DB" \
  --no-owner --no-privileges --section=pre-data -n auth   -t users   "$DUMP_FILE"
pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TARGET_DB" \
  --no-owner --no-privileges --section=data     -n auth   -t users   "$DUMP_FILE"

# Ensure required enum type exists before restoring profiles
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TARGET_DB" -v ON_ERROR_STOP=1 \
  -c $'do $$ begin\n  if not exists (select 1 from pg_type t join pg_namespace n on n.oid=t.typnamespace where t.typname=\'user_role\' and n.nspname=\'public\') then\n    create type public.user_role as enum (\'student\',\'teacher\',\'admin\');\n  end if;\nend $$;' >/dev/null
pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TARGET_DB" \
  --no-owner --no-privileges --section=pre-data -n public -t profiles "$DUMP_FILE"
pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TARGET_DB" \
  --no-owner --no-privileges --section=data     -n public -t profiles "$DUMP_FILE"

echo "Restored minimal subset into database '$TARGET_DB' from $DUMP_FILE"
