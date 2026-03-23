# GUSTAV — AI‑assisted learning platform for schools (alpha‑2)

GUSTAV (recursive acronym in German: “GUSTAV unterstützt Schüler tadellos als Vertretungslehrer”) is a self‑hosted, AI‑assisted learning platform built for classroom use. It focuses on fast formative feedback for students and a clear overview for teachers.

Status: **alpha‑2** (breaking changes expected).

## What it does

- Primary web app via SvelteKit (Browser-BFF); FastAPI is being reduced to an API-focused backend adapter
- Keycloak login (OIDC Authorization Code Flow + PKCE) with server‑side sessions
- Teaching workflows: courses, reusable units, sections, materials, tasks, and per‑course section releases
- Learning workflows: student submissions (text + uploads) and asynchronous analysis/feedback via `learning-worker`
- Supabase (Postgres + Storage) with SQL migrations under `supabase/migrations/`
- Contract‑first API: `api/openapi.yml`

## Tech stack (high level)

- Web: SvelteKit + FastAPI
- Identity: Keycloak (theme included)
- DB/Storage: Supabase (Postgres + Storage)
- Reverse proxy / TLS: Caddy (`app.localhost`, `id.localhost`)

## Local demo (quickstart)

### Prerequisites

- Linux
- Docker + Docker Compose
- Supabase CLI
- Free ports `80` and `443` (for `https://app.localhost`)

### Start

```bash
git clone https://github.com/Rensing1/gustav.git gustav
cd gustav

cp .env.example .env

# Start local Supabase services.
supabase start

# Apply SQL migrations (first-time setup).
supabase db reset --yes

# Update SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in .env (see `.env.example` for guidance).
supabase status

# Start the app stack (web + keycloak + caddy + worker + h5p).
docker compose up -d --build
```

Open:
- App: `https://app.localhost`

Notes:
- Caddy uses an internal local CA (`tls internal`). Your browser may show a TLS warning unless you trust the CA.
- If `app.localhost` / `id.localhost` do not resolve to `127.0.0.1`, add them to `/etc/hosts` (see `docs/references/network_topology.md`).
- This public repo does not ship production ops runbooks. Production requires environment‑specific TLS/SMTP/secrets (see `.env.example` and `docs/ARCHITECTURE.md`).

## Tests

Most common:

```bash
make test
make verify
```

See `docs/references/make_targets.md` for all targets and prerequisites.

## Documentation

Start here:
- Architecture: `docs/ARCHITECTURE.md`
- Domain boundaries: `docs/bounded_contexts.md`
- API contract: `api/openapi.yml`

Platform direction:
- `frontend/` hosts the new SvelteKit application shell.
- `backend/web/` is being migrated away from product SSR/HTMX pages toward API-only responsibilities.

References:
- Teaching: `docs/references/teaching.md`
- Learning: `docs/references/learning.md`
- Identity & sessions: `docs/references/user_management.md`
- Storage wiring: `docs/references/storage_and_gateway.md`
- Research notes: `docs/research/`
- Changelog: `docs/CHANGELOG.md`
- Roadmap (placeholder): `docs/ROADMAP.md`

## Issue reporting

Please open a GitHub Issue and include:

- Steps to reproduce
- Expected vs actual behavior
- Relevant logs (e.g. `docker compose logs --tail=200 web`), with secrets and PII removed
- `supabase status` output (redact keys)
- Your OS + Docker/Supabase CLI versions

## License

AGPL‑3.0. See `LICENCE.md` (and `docs/LICENCE.md`). Third‑party notices: `THIRD_PARTY_NOTICES.md`.
