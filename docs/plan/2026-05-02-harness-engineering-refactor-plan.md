# Harness Engineering and Code Quality Refactor Plan

## Status
- Date: 2026-05-02
- Last updated: 2026-05-15
- Status: Draft v0.6, expanded with agentic harness research and PR-1 product decisions
- Time horizon: 3 months
- Strategy: harness first, then refactor in small PRs
- Gate strategy: security, public-repo hygiene, and initial CI gates are hard immediately; structural and workflow gates start as warnings and become hard later
- Scope decision: broad quality refactor with staged, test-protected removal of legacy FastAPI HTML/HTMX product paths
- Agentic harness decision: agent-first execution with human review; PR 1 delivers orientation and minimum gates; safety gates block immediately, structure gates start as warnings

## Summary
GUSTAV should not merely be "cleaned up"; it should become reliably refactorable. The first step is therefore a repository-local harness made of rules, tests, quality gates, architecture boundaries, planning artifacts, and agent workflows so that Codex and human developers work from the same expectations.

This follows the OpenAI harness-engineering framing: the harness is not one tool or one CI job, but the environment that lets agents work productively. For GUSTAV, that means:
- a short entry map for agents instead of long tribal-knowledge documents,
- versioned project memory that is easy to search and update,
- executable checks that encode architecture, security, and product constraints,
- readable feedback loops from tests, logs, route maps, and CI,
- periodic garbage collection for stale rules, plans, dead paths, and accepted debt.

The most important current findings are:
- The backend web adapter is partly monolithic (`backend/web/main.py`, `backend/web/routes/teaching.py`, `backend/web/routes/learning.py`, `backend/web/routes/app.py`, large `repo_db.py` files).
- Docker and import behavior are fragile: flat copies, `PYTHONPATH` as a crutch, mixed import styles, and Compose bind mounts that can hide image problems.
- Frontend verification is not part of `make verify`; `npm run check` was green during the 2026-05-15 survey and should now be wired into the main harness instead of being treated as unknown.
- API contract-first exists as a principle, but it is not yet strong enough as an automated refactor safeguard.
- FastAPI still contains legacy product HTML/HTMX paths, retired route handlers, and unreachable code behind retirement responses. These paths should be removed in stages after SvelteKit parity is covered by tests.
- Runtime route surfaces are not yet clearly separated: public API, BFF-internal, H5P service routes, retired HTML routes, health checks, and auth bridge routes need an explicit map before strict contract gates can be enforced.
- DB access is too scattered: route modules and repository modules open direct `psycopg` connections in many places, which hurts readability and makes pooling, transactions, RLS context, and N+1 checks harder.
- Frontend and H5P also have hotspots (`h5p-service/server.mjs`, large Svelte pages/components, large CSS files) and should be included in the same quality refactor instead of being deferred indefinitely.
- Security and GDPR/privacy are taken seriously, but they need to become harder executable gates.

Priority order:
1. lock down known security findings and baseline gates,
2. establish Docker/image parity and import discipline,
3. bring frontend and API contracts into the verify harness,
4. classify route surfaces and remove already-retired legacy HTML/HTMX product paths in a staged way,
5. only then strangle the monoliths through test-driven refactors.

## Key Decisions
- No big-bang rewrites. Every change must be small, testable, reviewable, and reversible.
- No product features in this refactor stream unless they are required to close security, packaging, or harness gaps.
- Security findings with concrete risk are not only documented; they get regression tests and hard gates.
- Refactors of existing behavior start with characterization tests or contract tests.
- Docker image parity is mandatory: local development must not simulate a different architecture than production.
- CI must use the same entry points as local development; a harness that only works on one machine does not count.
- New business logic must not continue to grow hotspot files.
- API changes start in `api/openapi.yml` and are then covered by contract tests.
- GDPR/privacy, FOSS, and supply-chain requirements are treated as verifiable gates, not as statements of intent.
- `backend/web/main.py` is an explicit refactor target. The desired end state is a small app-composition module with `create_app()`, not a mixed router, middleware, HTML, security, and helper monolith.
- SvelteKit is the canonical product UI. FastAPI should keep API, BFF/internal, health, H5P integration, and required auth bridge behavior, but should not keep retired product HTML/HTMX surfaces as long-term compatibility code.
- Legacy HTML removal is staged: first inventory and tests, then removal of already-retired/dead paths, then further removals only after parity or redirect behavior is covered.
- The target runtime entry point is package-oriented (`backend.web.main:app`) rather than relying on flat `main:app` imports from copied directories.
- DB performance work is part of the refactor scope: introduce a small shared connection/transaction boundary before replacing scattered direct DB calls.
- CSP and CSRF hardening should become stricter as legacy HTMX and inline-style dependencies are removed.
- `AGENTS.md` should become a concise map, not the full handbook. Detailed, versioned agent rules live under `docs/harness/`.
- Agent-first does not mean agent-autonomous product governance. Felix keeps authority over product direction, role model, pedagogy, privacy/retention, and breaking API decisions.
- PR 1 optimizes agent orientation and feedback quality, not full autonomy.
- The first harness must answer three questions for a new agent within five minutes:
  - Where are the current rules and plans?
  - Which checks prove this change is safe enough to review?
  - Which decisions must be escalated to Felix?

## Target Harness
The harness consists of documents and executable checks. Documentation is valuable only when it drives concrete agent rules, PR rules, or verification commands.

Planned harness artifacts:
- `docs/harness/INDEX.md`: entry point, check order, links to rules.
- `docs/harness/AGENT_PLAYBOOK.md`: Codex workflow, TDD, contract-first development, security checks, common pitfalls.
- `docs/harness/ARCHITECTURE_RULES.md`: allowed dependency directions, import rules, boundaries between routes, use cases, repositories, adapters, and serialization.
- `docs/harness/QUALITY_GATES.md`: warning and hard gates with deadlines.
- `docs/harness/SECURITY_BASELINE.md`: CSRF, authz/RLS, uploads, secrets, logging, admin/teacher flows.
- `docs/harness/API_CONTRACTS.md`: OpenAPI as source of truth, contract diff, public/internal endpoints.
- `docs/harness/DATA_INVENTORY.yml`: personal data by entity, purpose, access, retention, deletion, export, and LLM usage.
- `docs/harness/AUTONOMY_MATRIX.md`: allowed agent actions by risk and file category.
- `docs/harness/ROUTE_MAP.md`: web/API routes with surface classification, role, data access, response model, tests, risk, and retirement/removal decision.
- `docs/harness/HOTSPOTS.md`: baseline file sizes, owner area, growth budget, split target, and exception policy for backend, frontend, and H5P hotspots.
- `docs/harness/TECH_DEBT.md`: consciously accepted deviations with risk, review date, and exit criterion.
- `docs/plan/INDEX.md`: searchable index of planning documents.
- `docs/plan/MILESTONES.md`: 3-month roadmap with PR order.
- `docs/plan/DECISIONS.md`: key architecture decisions until a dedicated ADR system exists.

Minimum document contract for PR 1:
- Every harness document starts with purpose, owner, status, local checks, CI status, related plans, and review cadence.
- `INDEX.md` is the five-minute start page for agents.
- `AGENT_PLAYBOOK.md` defines repo bootstrap, planning rules, escalation rules, verification ladder, and final-response expectations.
- `AUTONOMY_MATRIX.md` maps autonomy by file category and risk level, not by agent identity.
- `QUALITY_GATES.md` lists each gate with status (`hard`, `warning`, `advisory`), local command, CI command, false-positive policy, and hardening date.
- `SECURITY_BASELINE.md` links concrete tests for secrets/PII, authn/authz, CSRF, RLS, uploads, privacy logging, and unsafe production defaults.
- `API_CONTRACTS.md` defines route-surface categories before enforcing strict OpenAPI parity:
  - public API,
  - BFF/internal,
  - H5P service,
  - auth bridge,
  - health/ops,
  - active legacy UI,
  - retired legacy UI.
- `HOTSPOTS.md` records the initial hotspot baseline and explains which files may not grow without a debt entry.
- `TECH_DEBT.md` records accepted deviations with risk, owner, review date, and exit criterion.
- `docs/plan/INDEX.md`, `MILESTONES.md`, and `DECISIONS.md` become the searchable planning memory for agents.

## Agent Workflow
Harness engineering includes more than tests and documentation. It also includes a controlled agent workflow. Agents should read code, find risks, create repair plans, make targeted changes, and verify their own work. For GUSTAV, agents may accelerate the work, but they must not merge unchecked changes.

### Base Model
- The product owner defines goal, scope, risk, and acceptance criteria.
- Codex creates or updates a plan under `docs/plan/` before implementation.
- An implementation agent works only on its own branch or worktree.
- A verification agent checks the same change against the harness, tests, security gates, and architecture rules.
- Optionally, a review agent checks a focused area:
  - security,
  - API contract,
  - GDPR/privacy and FOSS,
  - architecture boundaries,
  - frontend/UI behavior.
- Human approval remains required for PRs until GUSTAV has stable CI, security, and review gates.

Product-owner decisions from 2026-05-15:
- Target model: agent-first execution with human review.
- PR-1 capability: orientation plus minimum executable gates.
- Initial strictness: security, PII, secrets, and API/security-contract failures are hard; architecture, hotspot, import, route-surface, and frontend/H5P signals begin as warnings.
- Agentic runtime readability (start app, inspect logs, screenshots, metrics per worktree) is important, but follows after the first orientation and gate layer.

### Agent Roles
- Planner:
  - splits work into small PRs,
  - writes BDD, contract, and security scenarios,
  - updates `docs/plan/`.
- Implementer:
  - works test-first,
  - executes only the planned task,
  - does not modify unrelated work.
- Verifier:
  - runs targeted tests, quality gates, and `make verify`,
  - checks Docker/image parity when packaging is affected,
  - documents checks that were not run as residual risk.
- Reviewer:
  - looks for bugs, security gaps, architecture violations, and missing tests,
  - prioritizes findings by risk,
  - avoids style comments without practical value.
- Doc Gardener:
  - finds stale harness, architecture, and plan documents,
  - creates small correction PRs,
  - does not delete or archive obsolete knowledge without review.

### Repair Workflow
Automated repairs are appropriate for clearly bounded, testable issues:
- broken imports,
- stale documentation links,
- missing contract tests,
- failing frontend type checks,
- reproducible security regressions.

Automated repairs are not appropriate for open product decisions:
- changing the role model,
- making GDPR/privacy tradeoffs,
- introducing API breaking changes,
- changing pedagogical assessment logic,
- redefining data deletion or retention policy.

Every repair requires:
- a failing test or reproducible gate,
- a minimal change,
- renewed verification,
- short risk documentation.

### Autonomy Levels
- Level 0: agent writes a plan, human decides.
- Level 1: agent implements small tasks, human reviews every PR.
- Level 2: agent repairs gate failures within a PR, human reviews the final result.
- Level 3: agent creates review, documentation, and tech-debt PRs automatically, human merges after review.
- Level 4: agents may auto-merge only low-risk documentation or harness updates after green CI. This is not an initial target for GUSTAV.

### Autonomy Matrix
Autonomy levels are assigned by risk and file category, not globally.

- Documentation/harness:
  - agent may plan, edit, verify, and create small repair PRs,
  - human reviews content and merge.
- Tests:
  - agent may add missing regression tests and repair faulty tests,
  - human checks that tests lock down real behavior rather than implementation details.
- Docker/packaging:
  - agent may repair after a failing image-smoke gate,
  - verifier must run image-only smoke.
- Security:
  - agent may change code only with negative and positive tests,
  - security reviewer is mandatory.
- DB/migrations/RLS:
  - agent may change only after contract and migration tests,
  - human review is mandatory.
- API:
  - agent may not introduce breaking changes without `docs/plan/DECISIONS.md` and an OpenAPI diff,
  - API reviewer is mandatory.
- Pedagogical assessment logic:
  - agent may improve tests and readability,
  - domain changes require explicit product-owner decision.
- Retention/deletion/export:
  - agent may prepare and test,
  - GDPR/privacy decisions remain human decisions.

## Quality Gates
These gates are mandatory planning targets. The concrete implementation may use `make` targets, Python scripts, shell checks, CI jobs, or a combination, but every gate needs a clear local command and a clear pass/fail rule.

### Hard Gates From Week 1
- Security Regression Gate:
  - unauthenticated access to protected endpoints,
  - student access to another student's, course's, or submission's data,
  - teacher access to unrelated courses,
  - admin/teacher functions without the required role,
  - CSRF-protected mutation without valid protection,
  - upload with invalid MIME type, extension, or size,
  - prompt-injection scenario with data-leak risk,
  - secret or personal test data in the repository.
- Public Repo Hygiene Gate:
  - no secrets,
  - no real personal data,
  - no sensitive logs,
  - no unlicensed assets,
  - no `.env` leaks.
- Minimal CI Gate:
  - CI runs the same local entry point as developers,
  - at least security baseline, public-repo hygiene, and image smoke are visible in CI from PR 1,
  - CI must not use separate dev-only paths.

### Warning From Month 1, Hard By Month 2
- Docker Image-Only Gate:
  - image builds without local bind mounts,
  - app starts from the image,
  - critical imports work,
  - healthcheck is reachable.
- Import Discipline Gate:
  - no new flat imports,
  - no new scattered `sys.path` manipulation,
  - package-oriented imports become the target state.
- Frontend Health Gate:
  - `npm run check` is green,
  - no new Svelte errors,
  - frontend check is part of `make verify`.
- Hotspot Growth Gate:
  - `backend/web/main.py`,
  - `backend/web/routes/teaching.py`,
  - `backend/web/routes/learning.py`,
  - `backend/web/routes/app.py`,
  - large `repo_db.py` files,
  - `h5p-service/server.mjs`,
  - large Svelte route/component files,
  - large CSS files
  must not grow after the deadline.
  Each hotspot file gets an absolute LOC baseline; net growth blocks unless a security fix documents risk, exception, and removal deadline in `TECH_DEBT.md`.
- Route Surface Gate:
  - every route is classified as public API, BFF/internal, H5P service, auth bridge, health/ops, active UI, or retired legacy UI,
  - no new product HTML route may be added to FastAPI,
  - retired legacy UI routes need a removal issue, test owner, and removal target.
- Package-Oriented Runtime Gate:
  - app import works via `backend.web.main:app`,
  - no duplicate module instances from mixed flat/package imports,
  - Docker image startup uses the same package layout as tests.

### Hard From Month 2
- API Contract Gate:
  - OpenAPI snapshot or diff,
  - no undocumented breaking changes,
  - contract tests for core flows,
  - H5P service and non-API HTML/BFF routes are classified explicitly instead of being accidental OpenAPI drift.
- Full Verify Gate:
  - backend tests,
  - frontend check,
  - packaging smoke,
  - security minimum,
  - any introduced lint/format/repo-hygiene checks.
- Architecture Boundary Gate:
  - routes contain no new business logic,
  - use cases know no FastAPI details,
  - DB access is not expanded from arbitrary routes,
  - security guards are centralized,
  - serializers/read models do not import private route helpers.
- DB Access Boundary Gate:
  - new direct `psycopg.connect` calls are blocked outside approved repository or DB infrastructure modules,
  - shared connection/transaction helpers are used for new data access,
  - teacher dashboard and learning analytics queries are checked for N+1 behavior before extraction PRs merge.
- Legacy HTML Exit Gate:
  - already-retired product HTML/HTMX routes are removed after characterization tests prove the intended replacement behavior,
  - remaining compatibility routes must be listed in `TECH_DEBT.md` with owner, risk, and exit criterion.
- Tech Debt Visibility Gate:
  - accepted deviations are listed in `TECH_DEBT.md`,
  - every entry has risk, review date, and exit criterion.

## 3-Month Roadmap

### Month 1: Establish Trust
Goal: security baseline, minimal executable harness, visible Docker/import risks.

#### PR 1: Harness Minimum
- Create the first concrete agentic harness layer, focused on orientation and safety feedback, not full autonomy.
- Create minimal but usable harness documents:
  - `docs/harness/INDEX.md`: five-minute agent entry point with read order, current milestone, critical gates, and stop/escalate rules.
  - `docs/harness/AGENT_PLAYBOOK.md`: planning workflow, Red-Green-Refactor rule, API contract-first rule, verification ladder, git/worktree safety, final report format.
  - `docs/harness/AUTONOMY_MATRIX.md`: risk levels by file category; which changes agents may plan, implement, repair, or must escalate.
  - `docs/harness/QUALITY_GATES.md`: gate table with status, local command, CI command, owner, false-positive handling, and date when warning becomes hard.
  - `docs/harness/SECURITY_BASELINE.md`: selected hard tests and policy notes for secrets, PII, authn/authz, CSRF, RLS, uploads, logging, and prod-safe config.
  - `docs/harness/API_CONTRACTS.md`: OpenAPI source-of-truth rule, route-surface taxonomy, and staged plan for live-vs-static contract diff.
  - `docs/harness/HOTSPOTS.md`: initial baseline for backend, frontend, H5P, CSS, OpenAPI, and DB-access hotspots.
  - `docs/harness/TECH_DEBT.md`: exception template with owner, risk, review date, and exit criterion.
- Create planning memory:
  - `docs/plan/INDEX.md`: curated index of active/refactor/security plans instead of a raw file dump.
  - `docs/plan/MILESTONES.md`: current 3-month PR sequence with status and next action.
  - `docs/plan/DECISIONS.md`: lightweight ADR-style decision log until a full ADR process exists.
- Define the planned local entry points:
  - `make harness-minimum`: hard PR-1 safety gate.
  - `make harness-signals`: warning-only signals for structure, frontend, H5P, imports, and image parity.
  - `make verify`: remains the full local/prod-like verification gate.
- Planned `harness-minimum` hard checks:
  - public repo safety and PII/secret hygiene,
  - unsafe production defaults and config security,
  - unauthenticated API access behavior,
  - OpenAPI write-security/cache-control policy,
  - privacy logging contract,
  - test-environment guards,
  - DB-required gate behavior,
  - build hygiene checks,
  - `docker compose config` validation.
- Planned `harness-signals` warning checks:
  - `frontend` Svelte check,
  - H5P Node tests,
  - hotspot baseline and growth report,
  - import-discipline inventory,
  - route-surface inventory,
  - direct DB-access inventory,
  - Docker image-only smoke as a visible but initially non-blocking signal.
- Introduce a first GitHub Actions workflow in the implementation PR:
  - run the same `make harness-minimum` entry point as local development,
  - use Python 3.11 and `backend/web/requirements.txt`,
  - install Node dependencies only for jobs that actually need frontend or H5P signals,
  - keep full Supabase/OpenAI/E2E flows out of PR-1 CI unless explicitly provided as opt-in jobs.
- Acceptance:
  - A new agent can find working rules, critical gates, and known debt within 5 minutes.
  - Every harness document links to concrete checks or PR rules.
  - `AGENTS.md` can later be shortened because `docs/harness/INDEX.md` points to the durable rules.
  - Security/PII/secrets/API-security-contract failures are specified as hard blockers.
  - Structure, hotspot, import, route-surface, frontend, H5P, and image-only findings are visible as warning signals with an escalation path.
  - CI is planned to run the same `make harness-minimum` entry point as local development.

#### PR 2: Security Baseline for CSRF and Session
- Define behavior for missing `Origin`/`Referer` headers.
- Add negative and positive tests for CSRF-relevant write operations.
- Check SameSite/session-cookie rules for critical mutations.
- Acceptance:
  - The known CSRF finding is either fixed or documented with justified residual risk.
  - CSRF/session regressions run as a hard gate.

#### PR 3: Security Baseline for Authz and RLS
- Define mandatory negative access tests:
  - student A cannot see student B's data,
  - teacher A cannot see unrelated courses,
  - admin/teacher functions are role-separated,
  - API filters do not replace RLS/database isolation.
- Mark authz/RLS-critical tests as a required set for refactors.
- Acceptance:
  - Authz/RLS regressions are visible as a hard gate.

#### PR 4: Security Baseline for Uploads and LLM Data Boundaries
- Define minimal upload tests for MIME type, extension, size, and path manipulation.
- Document which upload content may enter AI/LLM flows.
- Add an initial prompt-injection/data-leak scenario as a regression test, or document it as an explicit open gate failure.
- Acceptance:
  - Upload and LLM data risks are testable or visible as gate gaps, not only prose.

#### PR 5: Docker Image-Only Smoke
- Build a smoke test that starts the image without Compose bind mounts.
- Check critical imports from `backend.web`, `backend.learning`, `backend.scratch`, `backend.makecode`, or document explicit optional boundaries.
- Make visible which files are currently available only through local mounts.
- Acceptance:
  - Image-only startup failures are reproducible.
  - Compose can no longer hide packaging failures.
  - The `local_vision`/`backend.scratch`/`backend.makecode` import issue is either fixed or documented as a hard production blocker.

#### PR 6: Import Inventory and Blocking Rules
- Inventory flat imports (`routes.*`, `components`, mixed `backend.*` imports).
- Inventory scattered `sys.path` manipulation in tests.
- Add a warning gate that makes new violations visible.
- Document the target import scheme.
- Acceptance:
  - Existing debt is counted and findable.
  - New violations are visible in verify.

#### PR 7: Make Frontend Check Visible
- Record the current green `npm run check` result as the baseline.
- Add the frontend check as a required signal in the verify path.
- Define: after the API baseline, no backend PR can be considered green without frontend contract compatibility.
- Acceptance:
  - Frontend quality is no longer outside the main harness.

### Month 2: Enforce Parity and Contracts
Goal: establish local=prod parity, freeze API baseline, and make frontend verification a hard gate.

#### PR 8: Package-Oriented App Start
- Update the packaging contract from flat `main:app`/`routes.*` imports to package-oriented `backend.web.main:app` startup.
- Clean up the Dockerfile toward package-oriented copies of the backend package.
- Reduce `PYTHONPATH` dependency as an architecture crutch and prevent duplicate module instances from mixed import styles.
- Make the Docker image-only smoke hard no later than this PR.
- Acceptance:
  - App startup no longer depends accidentally on working directory or bind mounts.

#### PR 9: Centralize Test Imports
- Introduce central test import configuration.
- Gradually remove scattered `sys.path` manipulation.
- Tighten the Import Discipline Gate.
- Acceptance:
  - Tests better mirror production imports.
  - New tests may not introduce local import crutches.

#### PR 10: API Contract Baseline
- Create an OpenAPI baseline with diff/snapshot check.
- Mark public API, BFF/internal, H5P service, auth bridge, health/ops, active UI, and retired legacy UI surfaces.
- Define:
  - `api/openapi.yml` is the source of truth,
  - generated or live app spec is compared against it,
  - undocumented `/api/*` endpoints are gate failures,
  - intentionally non-OpenAPI surfaces are listed in the route map instead of ignored,
  - breaking changes require an entry in `docs/plan/DECISIONS.md`.
- Define contract tests for critical flows:
  - login/auth,
  - courses,
  - learning units/sections,
  - student submissions,
  - feedback/assessment,
  - H5P results,
  - teacher dashboard,
  - uploads,
  - admin/role functions.
- Acceptance:
  - Refactors can make API breaks visible.

#### PR 11: Make Frontend Verification Hard
- Keep the current green Svelte check as the baseline.
- Make `npm run check` a hard gate.
- Add frontend verification to `make verify`.
- Acceptance:
  - Platform quality is no longer backend-only.

#### PR 12: Architecture Boundary Rules
- Make architecture rules mechanically checkable where possible.
- Prevent new business logic in routes.
- Inventory DB access paths from web adapters.
- Document the target structure for central security guards and serialization.
- Acceptance:
  - Clean Architecture is backed by checks and review rules, not only documentation.

### Month 3: Strangle the Monoliths Safely
Goal: shrink large files, remove retired legacy UI surfaces, and improve DB/runtime boundaries without changing intended product behavior.

#### PR 13: Route Surface Map and Refactor Order
- Create `docs/harness/ROUTE_MAP.md` with:
  - route/endpoint,
  - surface classification,
  - role,
  - data access,
  - response model,
  - existing tests,
  - risk,
  - legacy status,
  - removal or retention decision,
  - planned target layer.
- Sort monolith strangulation and legacy removal by risk and usage, not by file shape.
- Acceptance:
  - Before the first functional split, it is clear which routes are security-critical, frequently used, retired, or owned by SvelteKit.

#### PR 14: Extract Security Guards
- Add characterization tests for existing guard/authz flows.
- Extract reusable security guards from hotspot files.
- Preserve semantics unless already decided security fixes require deliberate behavior changes.
- Acceptance:
  - Security logic becomes more readable, centralized, and testable.

#### PR 15: Shrink `backend/web/main.py` to App Composition
- Add characterization tests for app startup, middleware order, security headers, router registration, error handling, static handling, and selected retired route behavior.
- Introduce a `create_app()` factory and move app construction responsibilities into focused modules:
  - middleware setup,
  - router registration,
  - lifespan/startup wiring,
  - security headers,
  - static/error handling,
  - legacy retirement decisions.
- Keep `backend/web/main.py` as a small Uvicorn export and composition entry point.
- Acceptance:
  - `backend/web/main.py` shrinks measurably and no longer contains route implementation or large HTML/helper blocks.
  - `backend.web.main:app` still imports and starts in tests and Docker image smoke.

#### PR 16: Legacy HTML/HTMX Exit Wave 1
- Remove already-retired and unreachable FastAPI product HTML/HTMX code first.
- Confirm SvelteKit ownership or intended 404/410 behavior with tests before deleting handlers.
- Remove unused static assets, templates, and helper functions only after no route references them.
- Acceptance:
  - Direct backend access to removed retired product UI paths has an intentional tested result.
  - No active `/api/*`, H5P, health, BFF/internal, or required auth bridge behavior is removed accidentally.

#### PR 17: First Risk-Based Teaching Route Split
- Split `backend/web/routes/teaching.py` according to the Route Map where risk and benefit justify the first cut.
- Keep routes thin and move orchestration into use-case wiring.
- Use contract diff to verify API neutrality.
- Acceptance:
  - The largest route hotspot shrinks measurably.
  - No API regression occurs without an intentional contract change.

#### PR 18: Separate Serialization and Response Models
- Separate request/response shaping from business logic.
- Stabilize API models for core flows.
- Improve readability for new contributors and students.
- Acceptance:
  - Routes contain less shaping logic.
  - Response behavior remains protected by contract tests.

#### PR 19: Sharpen Repository/DB Boundaries and Connection Handling
- Inventory the large `repo_db.py` files.
- Introduce a small shared DB connection/transaction boundary before moving query code.
- Extract low-risk, well-tested data-access pieces first.
- Prevent new query logic in routes.
- Replace direct route-level DB calls with repository/read-model calls in the first selected flows.
- Check teacher dashboard and learning analytics reads for avoidable N+1 patterns.
- Pay special test attention to RLS-relevant access paths.
- Acceptance:
  - Data access becomes more controlled and easier to verify.
  - New data access has a clear place for connection reuse, transaction scope, and RLS context.

#### PR 20: Frontend and H5P Hotspot Split
- Add hotspot baselines for large Svelte pages/components, large CSS files, and `h5p-service/server.mjs`.
- Split only after behavior or component tests cover the selected area.
- For H5P, separate security/auth/session concerns, route handlers, storage integration, and response helpers without changing public H5P behavior.
- For frontend pages, extract state/data-loading/view components according to existing SvelteKit patterns.
- Acceptance:
  - H5P and frontend hotspots stop growing and at least one high-value hotspot shrinks with tests.
  - `npm run check` and relevant H5P/frontend tests remain green.

#### PR 21: Quality Scorecard v1
- Create a monthly scorecard:
  - hotspot LOC trend,
  - security test status,
  - contract diff status,
  - frontend/backend verification status,
  - open `TECH_DEBT` entries,
  - Docker/image parity status.
- Acceptance:
  - Progress is public, measurable, and auditable.

## Security, GDPR/Privacy, and FOSS Risks

### Security
- CSRF with missing `Origin`/`Referer`:
  - affected methods,
  - affected endpoints,
  - SameSite/session-cookie rules,
  - explicit decision for allowed exceptions,
  - target behavior: browser-cookie writes require `Origin` or `Referer` unless a tested bearer/service exception applies.
- CSP and inline execution/style risks:
  - current FastAPI HTML/HTMX compatibility may require temporary inline-style allowances,
  - after legacy HTML removal, reduce `unsafe-inline` allowances where product behavior permits,
  - H5P keeps its own separately documented CSP because it has different runtime constraints.
- Authorization:
  - student A must never see student B's data,
  - teacher A must not see unrelated courses,
  - admin functions are isolated,
  - API filters do not replace database isolation.
- Uploads:
  - file types,
  - size limits,
  - path manipulation,
  - metadata leaks,
  - unchecked delivery,
  - deletion deadlines.
- AI/LLM functions:
  - prompt injection through student submissions,
  - no unrelated student data in context,
  - no authorization decision by LLM,
  - logging minimization,
  - human accountability for pedagogically sensitive assessments.
- Secrets and deployment:
  - no `.env` leaks,
  - no tokens in logs,
  - no unsafe production defaults,
  - no debug mode in production.

### GDPR/Privacy
- `docs/harness/DATA_INVENTORY.yml` is mandatory before new AI, feedback, or analytics flows. It contains, for every personal data group:
  - entity,
  - purpose,
  - school/legal context,
  - role access,
  - retention period,
  - deletion path,
  - export path,
  - LLM/third-party usage.
- Data inventory at least for:
  - student accounts,
  - course memberships,
  - task work,
  - uploads,
  - H5P results,
  - AI feedback,
  - assessment data,
  - logs,
  - audit data.
- For every data group:
  - purpose,
  - access,
  - retention,
  - deletion,
  - export,
  - LLM/third-party boundary.
- Tenant separation:
  - not only UI-side,
  - cross-tenant tests,
  - database queries are always scoped.

### FOSS and Supply Chain
- Dependency license check.
- SBOM or equivalent dependency overview.
- Secret scan.
- Vulnerability scan.
- Reproducible builds with lockfiles.
- No real personal data in fixtures, screenshots, or demos.
- No proprietary or unclear-license teaching material in the repository.
- Clear contributor rules for privacy, tests, and security disclosure.

## Verification
Before implementation of this plan, no product files are changed. After plan approval, implementation proceeds PR by PR.

Minimum verification per PR:
- targeted tests first,
- then the affected gate,
- then `make verify` once the PR changes the verify path.

Additional verification by risk:
- Docker/packaging PRs: image-only smoke.
- Runtime packaging PRs: import through `backend.web.main:app`, no duplicate module instances, Docker image smoke.
- API PRs: OpenAPI diff, route-surface classification, and contract tests.
- Security PRs: negative and positive security tests.
- Legacy HTML PRs: route-map entry, SvelteKit parity or intentional direct-backend result, and static-asset reference check.
- Frontend PRs: `npm run check` and relevant frontend tests.
- H5P PRs: H5P service tests and unchanged public H5P API behavior.
- DB/RLS PRs: migrations against the local Supabase structure, no special local-only paths.

## Open Decisions
- Exact technical implementation of gates:
  - pure `make` targets,
  - Python check scripts,
  - GitHub Actions,
  - or a combination.
- Deadline and thresholds for hotspot LOC.
- Whether `TECH_DEBT.md` stays under `docs/harness/` or later moves into ADR/governance documents.

Recommended defaults:
- Gate implementation starts locally via `make`; CI runs the same entry point from PR 1 onward.
- Frontend check is a required signal from PR 7 and hard no later than PR 11; the 2026-05-15 green result is the baseline.
- Hotspot Growth Gate becomes hard directly after PR 6.
- Legacy HTML removal is staged: retired/dead paths first, then additional removals only after route-map and parity tests.
- `backend/web/main.py` gets its own PR before deeper route splits.
- Frontend and H5P hotspots are included in the same quality scorecard as backend hotspots.
- `TECH_DEBT.md` initially stays under `docs/harness/` because that is easiest for agents to find.
- GitHub Actions are introduced with PR 1, at least for security baseline, public-repo hygiene, and Docker/image smoke.

## Next Step After Plan Approval
1. Create a dedicated branch: `feature/harness-engineering-refactor`.
2. Implement PR 1: harness minimum and plan index.
3. Then implement PRs 2 through 4 directly so CSRF, authz/RLS, uploads, and LLM data boundaries do not wait behind documentation work.
4. After every PR: update plan status and reduce open decisions.
