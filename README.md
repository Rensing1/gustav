# GUSTAV — AI-assisted learning platform for schools (alpha3 / 0.0.3)

GUSTAV (recursive acronym in German: "GUSTAV unterstützt Schüler tadellos als Vertretungslehrer") is a self-hosted learning platform for classroom use. It helps teachers prepare linear and modular learning units, release content step by step in a course, collect student submissions, and support a feedback cycle in which work, feedback, revision, and further teaching decisions inform each other.

This is a personal public project by a teacher, not a startup product and not a polished SaaS offering. Status: **alpha3 / 0.0.3** (breaking changes expected).

In practice, the flow is meant to be cyclical rather than one-directional: a teacher prepares and releases content, students work on it, GUSTAV helps generate feedback and make progress visible, students revise their work, and that in turn becomes the basis for further pedagogical and didactic decisions. AI is part of that cycle, but it is a tool inside the process, not the point of the project.

## Why this project exists

GUSTAV exists because I want to develop teaching practice and software in parallel, in public, and against the same reality: the classroom.

The project is not meant to "digitize school" in a vague or sales-driven sense. It is meant to test what useful digital support for teaching can look like when the software is shaped by real classroom use, and when classroom practice can react back to the software instead of being forced into a closed product.

I also consider Free and Open Source Software the better foundation for education than proprietary systems. In education, software should be inspectable, understandable, adaptable, and shareable. That is not only a personal conviction; I think it follows from the educational setting itself. For GUSTAV, openness is tied to transparency, self-determination, and the possibility that others can examine, critique, host, improve, and build on the platform.

## What GUSTAV can do today

- Create and manage courses, reusable learning units, sections, materials, and tasks
- Support both `linear` and `modular` learning units; modular units can use phases, modules, and dependency-based progression
- Release sections per course or unlock modular content per student, instead of exposing everything at once
- Accept student submissions as text and uploads
- Process submissions asynchronously for analysis and formative feedback
- Make progress and recent submission status visible to teachers during ongoing classroom work
- Support interactive H5P-based tasks alongside native and upload-based task types
- Authenticate users via Keycloak with server-side sessions
- Keep data and files in Supabase Postgres/Storage with SQL migrations and a contract-first API in `api/openapi.yml`

If you are a teacher, the useful question is probably: "Would this support parts of my own teaching?"

If you are a developer, the useful question is probably: "What does a classroom-driven learning platform actually look like in code, architecture, and tradeoffs?"

## AI transparency

GUSTAV uses AI in two different ways, and it is important to keep them separate.

In the product, AI is used for analysis and formative feedback on student submissions. The current learning pipeline is built around DSPy-based prompts/programs and operator-configured OpenAI-compatible endpoints, with local infrastructure options such as Ollama in the overall setup.

In development, AI tools are used as conversation, drafting, review, and debugging aids. They help explore implementation options and documentation wording, but they do not replace pedagogical judgment, architectural decisions, code review, or responsibility for what ends up in the project.

## Trying it locally

### Prerequisites

- Linux
- Docker + Docker Compose
- Supabase CLI
- Free ports `80` and `443` (for `https://app.localhost`)

### Start

Recommended path (`make` wrappers):

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

# Provision local DB login users used by app and worker.
make db-login-user
make learning-worker-db-login-user

# Start the local app stack and copy the local Caddy root CA helper file.
make up
```

Manual path (explicit CLI steps):

```bash
git clone https://github.com/Rensing1/gustav.git gustav
cd gustav

cp .env.example .env

supabase start
supabase db reset --yes
supabase status

# Update SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in .env.
make db-login-user
make learning-worker-db-login-user

mkdir -p .tmp/dev_uploads .tmp
touch .tmp/caddy-root.crt

# Start the app stack (frontend + web + keycloak + caddy + learning-worker + h5p).
docker compose up -d --build
```

Open:
- App: `https://app.localhost`

Notes:
- Caddy uses an internal local CA (`tls internal`). Your browser may show a TLS warning unless you trust the CA.
- If `app.localhost` / `id.localhost` do not resolve to `127.0.0.1`, add them to `/etc/hosts` (see `docs/references/network_topology.md`).
- The local setup is the best starting point if you want to understand or evaluate the platform.

### Trust local HTTPS in Firefox and Chromium/Codex

`make up` exports only Caddy's public root CA to `.tmp/caddy-root.crt`; it never changes host or browser trust stores automatically. Inspect the current state first:

```bash
make local-ca-status
```

On Debian/Ubuntu, install the NSS command-line tool once if the status output requests it:

```bash
sudo apt install libnss3-tools
```

Then close Firefox and Codex completely and run the explicit, idempotent trust step:

```bash
make trust-local-ca
```

The command validates the current CA before installing it in the Linux system store, Chromium's shared NSS database, and active classic, Snap, or Flatpak Firefox profiles. Restart Firefox and Codex afterwards. If the Caddy data volume is deleted and recreated, the local CA changes; `make local-ca-status` will report the stale fingerprint and `make trust-local-ca` will replace only GUSTAV's managed certificate entry.

### Reusable teacher and student browser personas

For repeatable local development and browser testing, provision the dedicated teacher and student personas together with the modular test landscape:

```bash
make dev-accounts
```

The command is idempotent. Credentials remain only in the ignored local `.env`; never print or commit them. Use `make reset-dev-accounts` only when all data owned by the dedicated development teacher may be replaced with the defined mixed learning state. `make test-dev-accounts` runs the opt-in browser smoke for both personas, including modular graph states, H5P, the resumable AI dialog, and diagnostics.

The application, identity, and storage services must remain local. A remote AI provider such as Mistral is supported only through HTTPS. See [the E2E guide](docs/tests/e2e_howto.md#lokale-browser-personas) for setup, safety boundaries, expected fixture state, and troubleshooting.

## Self-hosting notes

GUSTAV is self-hostable, but at this stage it should be approached as an experimental system that is best explored locally first.

Running it outside a local evaluation setup means taking responsibility for infrastructure and operations yourself, including at least:

- TLS and domain setup
- secrets management
- SMTP / identity configuration
- backups and restore strategy
- deployment and update workflow
- school-specific privacy and compliance review

If you want to use H5P, you should plan for additional operational and security complexity. In GUSTAV, H5P runs as a dedicated sidecar service behind `/h5p/*`, and H5P packages/libraries are treated as trusted content rather than as harmless static files.

This public repository does not ship production runbooks. Production use therefore requires your own operational decisions and your own validation process. See `.env.example` and [docs/ARCHITECTURE.md](/home/felix/gustav-alpha2/docs/ARCHITECTURE.md) for the current technical baseline.

## Current limitations and open problems

This README should not pretend that GUSTAV is further along than it is.

- The project is still in `alpha3 / 0.0.3`. Breaking changes are expected.
- The architecture is in transition: `frontend/` hosts the new SvelteKit application shell, while `backend/web/` still contains transition and legacy-style responsibilities.
- The intended Clean Architecture split is not fully extracted yet; some UI- and adapter-near logic still lives in the web layer.
- IServ SSO is planned, but not finished.
- AI-generated analysis and feedback are useful, but they are not authoritative and must be used critically in educational practice.
- H5P support exists, but it adds operational and security overhead compared to plain text, file, or native task flows.
- The public roadmap is not mature yet; `docs/ROADMAP.md` is currently a placeholder.
- This repository is open about direction and intent, but not yet complete in documentation for production operations.

That is intentional. The point of publishing GUSTAV is not to claim completeness, but to show work in progress, document decisions in the open, and invite scrutiny and collaboration.

## Tests

Most common:

```bash
make test
make verify-preflight-db
```

Full verification:

```bash
make verify
```

`make verify` is intentionally heavyweight. It chains preflight checks, Python tests,
H5P sidecar tests, Supabase integration tests, OpenAI-compatible endpoint smoke
tests, and E2E tests.

If `make verify-preflight-db` reports owner drift on `public.learning_submissions`,
use the official local repair path:

```bash
make reset-local
```

See `docs/references/make_targets.md` for all targets and prerequisites.

## Documentation

Start here:

- Architecture: [docs/ARCHITECTURE.md](/home/felix/gustav-alpha2/docs/ARCHITECTURE.md)
- Domain boundaries: [docs/bounded_contexts.md](/home/felix/gustav-alpha2/docs/bounded_contexts.md)
- API contract: [api/openapi.yml](/home/felix/gustav-alpha2/api/openapi.yml)

Useful references:

- Teaching: `docs/references/teaching.md`
- Teaching Authoring CLI: `docs/references/gustav_cli.md`
- Learning: `docs/references/learning.md`
- Identity & sessions: `docs/references/user_management.md`
- Storage wiring: `docs/references/storage_and_gateway.md`
- Research notes: `docs/research/`
- Changelog: `docs/CHANGELOG.md`
- Roadmap: `docs/ROADMAP.md`

## Contributing and feedback

You are welcome to use this repository in different ways:

- as a teacher who wants to see what this kind of platform could look like
- as a developer who wants to inspect or improve the implementation
- as a self-hoster who wants to try the system and report back

If you open an issue, please include:

- steps to reproduce
- expected vs actual behavior
- relevant logs (for example `docker compose logs --tail=200 web`), with secrets and PII removed
- `supabase status` output (with keys redacted)
- your OS + Docker/Supabase CLI versions

Concrete criticism is welcome. Bug reports, architectural objections, operational notes, and pedagogical questions are all useful.

## License

AGPL-3.0. See `LICENCE.md` (and `docs/LICENCE.md`). Third-party notices: `THIRD_PARTY_NOTICES.md`.
