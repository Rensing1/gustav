# Plan: Auth Cache-Control Hardening + API Version Bump

Why
- Prevent caching of sensitive auth redirects/responses (DSGVO/Security-first).
- Reflect breaking contract change (`LearningSectionCore.unit_id`) via version bump.

User Story
- As a security-conscious admin, I need auth endpoints to prevent caching so that tokens, redirects, and logout flows aren’t stored by browsers/proxies.

BDD Scenarios
- Given GET /auth/login, When 302, Then header `Cache-Control: private, no-store`.
- Given GET /auth/callback with missing params, When 400, Then header `Cache-Control: private, no-store`.
- Given GET /auth/logout, When 302, Then header `Cache-Control: private, no-store` and cookie cleared.
- Given GET /auth/logout/success, When 200, Then header `Cache-Control: private, no-store`.

Design/Contract (API Contract-First)
- openapi.yml: bump `info.version` to 0.2.0; add Cache-Control headers on auth endpoints (302/200/400).

TDD (Red → Green)
1) Red: Add tests in `backend/tests/test_auth_cache_headers.py` for all auth endpoints.
2) Green: Set headers in `backend/web/routes/auth.py` and `backend/web/main.py` callback path.
3) Refactor: Keep minimal; add docstrings; avoid DB coupling in unrelated tests by defaulting Teaching repo to in-memory unless `TEACHING_DATABASE_URL` is set.

Docs
- README: clarify KC_BASE_URL vs KC_BASE; document WEB_BASE/REDIRECT_URI.
- .env.example: use `DUMMY_DO_NOT_USE` for service role.
- Dockerfile: add HEALTHCHECK.
- CHANGELOG: record version bump and cache headers.

