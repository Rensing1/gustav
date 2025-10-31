#!/usr/bin/env bash
set -euo pipefail

echo "== GUSTAV Preflight =="

WEB_BASE=${WEB_BASE:-http://app.localhost:8100}
KC_BASE=${KC_BASE:-http://id.localhost:8100}
KC_REALM=${KC_REALM:-gustav}
DB_HOST=${DB_HOST:-127.0.0.1}
DB_PORT=${DB_PORT:-54322}
APP_DB_USER=${APP_DB_USER:-gustav_app}
APP_DB_PASSWORD=${APP_DB_PASSWORD:-CHANGE_ME_DEV}

fail=0

echo "[1/6] docker compose ps"
docker compose ps || { echo "compose ps failed"; fail=1; }

echo "[2/6] supabase status"
supabase status || { echo "supabase status failed"; fail=1; }

echo "[3/6] Health check: $WEB_BASE/health"
code=$(curl -s -o /dev/null -w "%{http_code}" "$WEB_BASE/health" || true)
if [[ "$code" != "200" ]]; then echo "Health != 200 ($code)"; fail=1; fi

echo "[4/6] Keycloak OIDC well-known"
code=$(curl -s -o /dev/null -w "%{http_code}" "$KC_BASE/realms/$KC_REALM/.well-known/openid-configuration" || true)
if [[ "$code" != "200" ]]; then echo "OIDC well-known != 200 ($code)"; fail=1; fi

echo "[5/6] DB role membership (pg_has_role)"
export PGPASSWORD="$APP_DB_PASSWORD"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$APP_DB_USER" -d postgres -v ON_ERROR_STOP=1 -tAc "select pg_has_role(current_user, 'gustav_limited', 'member');" | grep -q t \
  || { echo "pg_has_role check failed"; fail=1; }

echo "[6/6] Pytest (quick)"
if [[ -x .venv/bin/pytest ]]; then
  . .venv/bin/activate
  pytest -q || fail=1
else
  echo "pytest not found, skipping"
fi

if [[ "$fail" != 0 ]]; then
  echo "Preflight: FAIL"
  exit 1
fi
echo "Preflight: OK"

