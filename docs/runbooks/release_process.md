# Release-Prozess

Status: Stable

## Reihenfolge
1) `supabase migration up` (Schema/Policies aktuell).
2) Build/Deploy Container: `docker compose up -d --build`.
3) Smoke‑Tests: `/health`, Login‑Flow, einfache API‑Calls.
4) Tests: `.venv/bin/pytest -q` (Unit/Integration), `RUN_E2E=1 pytest -q -m e2e`.
5) Freigabe.

## Rollback
- Container Revert (letztes Image), DB‑Migrations Revert/Hotfix.
- Abbruchkriterien wie im Hardware Playbook.

