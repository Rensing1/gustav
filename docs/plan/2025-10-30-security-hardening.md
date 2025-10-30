# Plan: Minimal Security Hardening (Startup Guard, EXECUTE Grants, Health Contract)

Goal: Enforce production safety and align docs/tests with current behavior.

Steps:
- Add tests (TDD):
  - config guard fails in prod with dummy service role key; allows in dev.
  - RLS helper EXECUTE grants — PUBLIC denied, `gustav_limited` allowed.
- Update API contract: document `GET /health` (no auth, `Cache-Control: no-store`).
- Implement minimal code: `backend/web/config.ensure_secure_config_on_startup()` and call from `main`.
- Ops hardening: purge `gcc` after `pip install` in Dockerfile to reduce attack surface.
- Docs: CHANGELOG entries for guard and health.

Notes:
- Guard scope: triggers only for prod-like envs (`prod|production|stage|staging`).
- DSN TLS: basic guard rejects `sslmode=disable` in production.
