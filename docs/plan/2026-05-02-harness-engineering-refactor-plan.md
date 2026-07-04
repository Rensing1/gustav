# Harness Engineering and Code Quality Refactor Plan

## Status
- Date: 2026-05-02
- Last updated: 2026-07-04
- Status: Draft v1.0; PR 1 "Harness Minimum", PR 2 "CSRF and Session Baseline", PR 3 "Authz and RLS Baseline", PR 4 "Uploads and LLM Data Boundaries", PR 5 "Docker Image-Only Smoke", PR 6 "Import Inventory and Blocking Rules", PR 7 "Make Frontend Check Visible", PR 8 "Package-Oriented App Start", the first PR 9 slices "Centralize Test Imports" and "Teaching Test Import Cleanup Batch 1", the first PR 10 slice "API Contract Baseline", PR 11 "Make Frontend Verification Hard", the first PR 12 slice "Architecture Boundary Rules", the first PR 13 slice "Route Surface Map", the first PR 14 slice "Security Guard Extraction", PR 15 "Shrink backend/web/main.py to App Composition", the first PR 16 slice "Legacy HTML/HTMX Exit Wave 1", the first PR 17 slices "Task-Centric H5P Teaching Route Split", "H5P Authoring Helper Extraction", "Teaching Shared Response/Identity Helpers", "Teaching Task-Service Provider Boundary", "Teaching Guard/CSRF Boundary", and "Teaching Module Authoring Boundary", and the first PR 18 slices "Task Serializer Extraction", "Modular Graph Serializer Extraction", "Core Teaching Response Serializer Extraction", and "Latest Submission Payload Extraction" implemented in the working tree; follow-up PRs for further test-import cleanup, H5P service runtime parity, broader guard extraction, additional Teaching route splits/use-case wiring, further serialization/response model extraction, repository/DB boundary cleanup, frontend/H5P hotspot splitting, and further legacy route cleanup remain open
- Time horizon: 3 months
- Strategy: harness first, then refactor in small PRs
- Gate strategy: security, public-repo hygiene, and initial CI gates are hard immediately; structural and workflow gates start as warnings and become hard later
- Scope decision: broad quality refactor with staged, test-protected removal of legacy FastAPI HTML/HTMX product paths
- Agentic harness decision: agent-first execution with human review; PR 1 delivers orientation and minimum gates; safety gates block immediately, structure gates start as warnings
- Current check: PR-1 harness artifacts, repo-governed skill sources, `docs/plan/INDEX.md`, `docs/plan/MILESTONES.md`, `docs/plan/DECISIONS.md`, `make harness-minimum`, `make harness-signals`, `make test-import-boundaries`, `make test-frontend-h5p`, `make test-docker-image-smoke`, `make test-route-map`, `make verify`, `make test-full-prod-like`, and the GitHub Actions harness workflow are present in the working tree.

## Summary
GUSTAV should not merely be "cleaned up"; it should become reliably refactorable. The first step is therefore a repository-local harness made of rules, tests, quality gates, architecture boundaries, planning artifacts, and agent workflows so that Codex and human developers work from the same expectations.

This follows the AI harness-engineering framing: the harness is not one tool, one prompt, or one CI job, but the environment that lets agents work productively. For GUSTAV, that means:
- a short entry map for agents instead of long tribal-knowledge documents,
- versioned project memory that is easy to search and update,
- project-specific skills for repeated agent workflows, loaded only when needed,
- a dedicated AI harness specification that connects agent roles, autonomy, evidence, skill lifecycle, and human review,
- executable checks that encode architecture, security, and product constraints,
- readable feedback loops from tests, logs, route maps, and CI,
- evidence packages for agent runs, including context used, commands, failures, verification, and residual risk,
- periodic garbage collection for stale rules, plans, dead paths, and accepted debt.

The most important current findings are:
- The backend web adapter is partly monolithic (`backend/web/main.py`, `backend/web/routes/teaching.py`, `backend/web/routes/learning.py`, `backend/web/routes/app.py`, large `repo_db.py` files).
- Docker and import behavior are fragile: flat copies, `PYTHONPATH` as a crutch, mixed import styles, and Compose bind mounts that can hide image problems.
- Frontend verification is part of `make verify`; `npm run check`, Frontend-Vitest, and H5P Node tests now run in the hard deterministic gate.
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
- Project-specific agent skills are part of the harness, but they are narrow workflow tools, not product-governance authority.
- Every project skill needs a purpose, trigger, allowed actions, prohibited actions, stop criteria, verification requirements, and a review/eval path.
- Repo-governed project skills live under `docs/harness/skills/<skill>/SKILL.md`; personal or local skills may help an agent, but they are not repo-authoritative until they are listed in `docs/harness/SKILLS.md` and reviewable in the repository.
- Skills with broad tool permissions, external-network access, secrets handling, data deletion, migrations, or production-impacting behavior require human review before use.
- All initial GUSTAV skills may be active from PR 1, but "active" only means "allowed to use inside the autonomy matrix"; it never grants extra authority over TDD, contract-first work, security review, migrations, or human merge decisions.
- Agent runs should produce enough evidence to reconstruct what context was used, which commands ran, which failures occurred, how failures were attributed, and what remains unverified.
- Agent-first does not mean agent-autonomous product governance. The product owner keeps authority over product direction, role model, pedagogy, privacy/retention, and breaking API decisions.
- Level 3 autonomy is an initial target only for documentation, review, and tech-debt PR preparation; product code, API, security, DB, migration, privacy, and pedagogy decisions remain lower-autonomy and human-reviewed.
- PR 1 optimizes agent orientation and feedback quality, not full autonomy.
- The first harness must answer three questions for a new agent within five minutes:
  - Where are the current rules and plans?
  - Which checks prove this change is safe enough to review?
  - Which decisions must be escalated to the product owner?

## Target Harness
The harness consists of documents and executable checks. Documentation is valuable only when it drives concrete agent rules, PR rules, or verification commands.

Planned harness artifacts:
- `docs/harness/INDEX.md`: entry point, check order, links to rules.
- `docs/harness/AI_HARNESS.md`: central AI harness specification for agent roles, autonomy, evidence, skill lifecycle, manual evals, escalation, and human review.
- `docs/harness/AGENT_PLAYBOOK.md`: Codex workflow, TDD, contract-first development, security checks, common pitfalls.
- `docs/harness/ARCHITECTURE_RULES.md`: allowed dependency directions, import rules, boundaries between routes, use cases, repositories, adapters, and serialization.
- `docs/harness/QUALITY_GATES.md`: warning and hard gates with deadlines.
- `docs/harness/TEST_STRATEGY.md`: test layers, marker rules, gate profiles, and cleanup rules for the large existing test portfolio.
- `docs/harness/SECURITY_BASELINE.md`: CSRF, authz/RLS, uploads, secrets, logging, admin/teacher flows.
- `docs/harness/TEST_PORTFOLIO.md`: grouped inventory of existing tests with purpose, dependencies, marker/gate assignment, risk, and keep/merge/rewrite/retire decisions.
- `docs/harness/API_CONTRACTS.md`: OpenAPI as source of truth, contract diff, public/internal endpoints.
- `docs/harness/DATA_INVENTORY.yml`: personal data by entity, purpose, access, retention, deletion, export, and LLM usage.
- `docs/harness/AUTONOMY_MATRIX.md`: allowed agent actions by risk and file category.
- `docs/harness/ROUTE_MAP.md`: web/API routes with surface classification, role, data access, response model, tests, risk, and retirement/removal decision.
- `docs/harness/HOTSPOTS.md`: baseline file sizes, owner area, growth budget, split target, and exception policy for backend, frontend, and H5P hotspots.
- `docs/harness/TECH_DEBT.md`: consciously accepted deviations with risk, review date, and exit criterion.
- `docs/harness/SKILLS.md`: project-skill inventory, trigger rules, allowed actions, verification duties, eval requirements, and supply-chain rules.
- `docs/harness/SKILL_EVALS.md`: manual forward-test ledger for project skills, with scenario, result, gaps, activation status, and next review date.
- `docs/harness/skills/<skill>/SKILL.md`: reviewable repo source for each approved GUSTAV project skill.
- `docs/plan/INDEX.md`: searchable index of planning documents.
- `docs/plan/MILESTONES.md`: 3-month roadmap with PR order.
- `docs/plan/DECISIONS.md`: key architecture decisions until a dedicated ADR system exists.

Minimum document contract for PR 1:
- Every harness document starts with purpose, owner, status, local checks, CI status, related plans, and review cadence.
- `INDEX.md` is the five-minute start page for agents.
- `AI_HARNESS.md` defines the AI-harness contract: agent roles, autonomy boundaries, skill lifecycle, evidence duties, failure attribution, stop/escalation rules, and the relationship between personal tools and repo-governed project skills.
- `AGENT_PLAYBOOK.md` defines repo bootstrap, planning rules, escalation rules, verification ladder, and final-response expectations.
- `AUTONOMY_MATRIX.md` maps autonomy by file category and risk level, not by agent identity.
- `QUALITY_GATES.md` lists each gate with status (`hard`, `warning`, `advisory`), local command, CI command, false-positive policy, and hardening date.
- `TEST_STRATEGY.md` defines the intended test pyramid for GUSTAV: domain/use-case, adapter, OpenAPI/API contract, API integration, DB/RLS/migration, frontend, H5P, and E2E smoke tests.
- `SECURITY_BASELINE.md` links concrete tests for secrets/PII, authn/authz, CSRF, RLS, uploads, privacy logging, and unsafe production defaults.
- `TEST_PORTFOLIO.md` records the first grouped test inventory and classifies test groups as `keep`, `merge`, `rewrite`, or `retire-later`.
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
- `SKILLS.md` lists approved GUSTAV skills, their source location under `docs/harness/skills/`, trigger phrases, allowed tools/actions, prohibited actions, stop/escalation rules, verification commands, eval status, activation status, and review cadence.
- `SKILL_EVALS.md` records manual forward-tests for each active skill: scenario prompt, pressure condition, expected artifact, observed result, gaps found, reviewer, activation decision, and next review date.
- `docs/plan/INDEX.md`, `MILESTONES.md`, and `DECISIONS.md` become the searchable planning memory for agents.

Initial project-skill candidates:
- `gustav-plan-status`: inspect `docs/plan/` documents, find stale or missing status blocks, and propose or apply documentation-only status updates.
- `gustav-pr-review`: review a GUSTAV branch against `master` and persist prioritized findings in `docs/plan/YYYY-MM-DD-PR-fix.md`.
- `gustav-pr-fix`: read an existing PR-fix plan, verify open findings, design tests first, implement minimal fixes, and update the plan.
- `gustav-api-contract`: enforce OpenAPI-first changes, route-surface classification, contract tests, and breaking-change decision entries.
- `gustav-security-review`: focus on authn/authz, RLS, CSRF, uploads, privacy logging, unsafe defaults, and PII/secrets.
- `gustav-route-map`: classify web/API routes, identify retired legacy UI paths, and update `docs/harness/ROUTE_MAP.md`.
- `gustav-harness-gardener`: find stale harness, roadmap, tech-debt, source, and skill documents, then prepare small correction PRs.

Project skills live first as reviewable repo sources under `docs/harness/skills/<skill>/SKILL.md`. A later installation or sync step may copy them into a tool-compatible local skill directory, but PR 1 should not depend on local personal skill paths. A skill is accepted only when its behavior is narrower than the general agent instructions, its risks are explicit, and its verification path is documented. Personal skills outside the repository may be used as optional helper context, but they are not official GUSTAV harness behavior.

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
- Warning hygiene: warning-only gates may exist as staged work, but green hard-gate commands should not emit incidental warnings. Any warning seen during a green gate is treated as cleanup work with evidence or a documented hardening follow-up.
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

Before a second repair attempt, the agent must classify the failure:
- wrong or missing context,
- tool/environment failure,
- flaky or incorrect test,
- real product regression,
- security or contract regression,
- incomplete verification,
- model reasoning error.

This classification belongs in the final report or the PR-fix document. It prevents random patching and gives the verifier a concrete failure hypothesis to challenge.

### Episode Evidence
Each non-trivial agent run should leave enough evidence for human review:
- goal and scope,
- plans, harness documents, and source files read,
- commands executed and their relevant results,
- failed tests or gates and failure attribution,
- files changed,
- verification completed,
- verification intentionally skipped with residual risk.

For small documentation-only updates, the final response can serve as the evidence package. For code, security, API, DB, or migration work, the evidence should also be persisted in the relevant plan or PR-fix document.

Evidence should stay close to the work instead of creating a separate run-log archive by default:
- documentation-only maintenance: final response or the edited plan status is enough,
- PR review/fix work: write the evidence into the matching `docs/plan/*PR-fix*.md`,
- planned feature/refactor work: write the evidence into the relevant `docs/plan/*.md`,
- skill/harness work: write skill-specific test evidence into `docs/harness/SKILL_EVALS.md`,
- high-risk work: duplicate the key residual risks in the PR description so reviewers do not need to hunt through long logs.

### Autonomy Levels
- Level 0: agent writes a plan, human decides.
- Level 1: agent implements small tasks, human reviews every PR.
- Level 2: agent repairs gate failures within a PR, human reviews the final result.
- Level 3: agent creates review, documentation, and tech-debt PRs automatically, human merges after review.
- Level 4: agents may auto-merge only low-risk documentation or harness updates after green CI. This is not an initial target for GUSTAV.

Initial autonomy target:
- Level 1-2 is allowed for code, tests, API, security, DB, migration, frontend, and H5P work, with the review rules below.
- Level 3 is allowed only for documentation, review, plan-status, harness-gardening, and tech-debt PR preparation.
- Level 4 is out of scope for the first three months.
- No autonomy level allows an agent to decide product direction, privacy/retention policy, role semantics, breaking API behavior, or pedagogical assessment meaning.

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

### Project Skills and Autonomy
Skills improve repeatability and reduce context load, but they do not increase autonomy by themselves. A skill may only automate decisions that are already allowed by the autonomy matrix for the affected file category and risk level.

Project-skill rules:
- Skills are loaded only when their trigger matches the task.
- Skills must be small enough to review and update.
- Skills may reference helper scripts, but the script purpose and verification command must be documented.
- Skills may not silently broaden tool access or network access.
- Skills may not encode product, privacy, role-model, or breaking API decisions without a linked decision entry.
- Third-party skills are treated as supply-chain inputs and need review before adoption.
- Repo-governed GUSTAV skills are sourced from `docs/harness/skills/<skill>/SKILL.md` and inventoried in `docs/harness/SKILLS.md`.
- A skill can be `active` in PR 1 only if it has a manual forward-test entry in `docs/harness/SKILL_EVALS.md`; the entry may document gaps, but the gaps must have an owner, risk, and review date.
- Active skills still obey the autonomy matrix. For example, `gustav-security-review` may guide review and planning, but security code changes still require negative and positive tests plus human review.
- Personal/local skills can inform an agent's work, but official GUSTAV behavior must be traceable to repo-governed skill files.

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
- Skill Governance Signal:
  - approved project skills are listed in `docs/harness/SKILLS.md`,
  - repo-governed skill sources exist under `docs/harness/skills/<skill>/SKILL.md`,
  - every skill has purpose, trigger, allowed actions, stop criteria, verification, eval status, and review date,
  - every active skill has a manual forward-test entry in `docs/harness/SKILL_EVALS.md`,
  - examples contain no secrets, PII, school identifiers, or proprietary teaching material,
  - broad tool or network access is visible as risk, not hidden in the skill body.

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
- Skill Safety Gate:
  - no new project skill without review metadata in `docs/harness/SKILLS.md`,
  - no skill with unsafe tool permissions, network access, production mutation, migration execution, or secrets handling unless explicitly reviewed,
  - every active skill has at least one realistic manual forward-test scenario with expected artifact, observed result, activation decision, and review date,
  - scripted skill evals are intentionally out of scope for PR 1 and may be introduced later only after the manual scenarios prove stable.

## 3-Month Roadmap

### Month 1: Establish Trust
Goal: security baseline, minimal executable harness, visible Docker/import risks.

#### PR 1: Harness Minimum
- Create the first concrete agentic harness layer, focused on orientation and safety feedback, not full autonomy.
- Create minimal but usable harness documents:
  - `docs/harness/INDEX.md`: five-minute agent entry point with read order, current milestone, critical gates, and stop/escalate rules.
  - `docs/harness/AI_HARNESS.md`: central AI harness contract for agent roles, autonomy levels, evidence packages, skill lifecycle, manual forward-tests, stop rules, and human review.
  - `docs/harness/AGENT_PLAYBOOK.md`: planning workflow, Red-Green-Refactor rule, API contract-first rule, verification ladder, git/worktree safety, final report format.
  - `docs/harness/AUTONOMY_MATRIX.md`: risk levels by file category; which changes agents may plan, implement, repair, or must escalate.
  - `docs/harness/QUALITY_GATES.md`: gate table with status, local command, CI command, owner, false-positive handling, and date when warning becomes hard.
  - `docs/harness/TEST_STRATEGY.md`: explicit test strategy for the large existing suite, including layers, marker policy, gate profiles, E2E limits, and cleanup rules.
  - `docs/harness/SECURITY_BASELINE.md`: selected hard tests and policy notes for secrets, PII, authn/authz, CSRF, RLS, uploads, logging, and prod-safe config.
  - `docs/harness/TEST_PORTFOLIO.md`: grouped baseline of existing backend, frontend, H5P, DB, security, contract, E2E, and legacy tests with first keep/merge/rewrite/retire decisions.
  - `docs/harness/API_CONTRACTS.md`: OpenAPI source-of-truth rule, route-surface taxonomy, and staged plan for live-vs-static contract diff.
  - `docs/harness/HOTSPOTS.md`: initial baseline for backend, frontend, H5P, CSS, OpenAPI, and DB-access hotspots.
  - `docs/harness/TECH_DEBT.md`: exception template with owner, risk, review date, and exit criterion.
  - `docs/harness/SKILLS.md`: project-skill inventory, governance rules, initial skill candidates, eval expectations, and supply-chain policy.
  - `docs/harness/SKILL_EVALS.md`: manual forward-test ledger for active skills, with scenario, expected artifact, observed result, known gaps, activation decision, and next review date.
- Create reviewable skill source drafts under `docs/harness/skills/<skill>/SKILL.md`:
  - documentation and harness maintenance: `gustav-plan-status`, `gustav-harness-gardener`,
  - PR work: `gustav-pr-review`, `gustav-pr-fix`,
  - contract and security work: `gustav-api-contract`, `gustav-security-review`,
  - route and legacy surface work: `gustav-route-map`.
- Organize the initial skill drafting with parallel subagents by risk group:
  - one pass for documentation/harness skills,
  - one pass for PR review/fix skills,
  - one pass for API/security skills,
  - one pass for route/legacy skills.
- Mark all initial skills as active only inside the autonomy matrix:
  - documentation/harness skills may support Level 3 PR preparation,
  - review/fix skills may support Level 1-2 code work with human review,
  - API/security/route skills may guide analysis, tests, and plans but cannot authorize breaking API, migration, privacy, or security decisions.
- Create planning memory:
  - `docs/plan/INDEX.md`: curated index of active/refactor/security plans instead of a raw file dump.
  - `docs/plan/MILESTONES.md`: current 3-month PR sequence with status and next action.
  - `docs/plan/DECISIONS.md`: lightweight ADR-style decision log until a full ADR process exists.
- Define the planned local entry points:
  - `make harness-minimum`: hard PR-1 safety gate.
  - `make harness-signals`: warning-only signals for structure, frontend, H5P, imports, and image parity.
  - `make test-fast`: planned fast profile for in-process, domain, adapter, and contract tests.
  - `make test-db-security`: planned profile for DB, RLS, migration, Authz, and CSRF tests.
  - `make test-frontend-h5p`: planned profile for Svelte check, Vitest, and H5P Node tests.
  - `make test-full-prod-like`: opt-in profile for Supabase, OpenAI-compatible endpoint, Docker/Compose, and E2E smoke tests.
  - `make verify`: deterministic hard gate for local refactor work; external OpenAI and browser E2E smokes stay in `test-full-prod-like`.
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
  - skill-governance inventory,
  - skill manual-forward-test inventory,
  - Docker image-only smoke as a visible but initially non-blocking signal.
- Introduce a first GitHub Actions workflow in the implementation PR:
  - run the same `make harness-minimum` entry point as local development,
  - use Python 3.11 and `backend/web/requirements.txt`,
  - install Node dependencies only for jobs that actually need frontend or H5P signals,
  - keep full Supabase/OpenAI/E2E flows out of PR-1 CI unless explicitly provided as opt-in jobs.
- Acceptance:
  - A new agent can find working rules, critical gates, and known debt within 5 minutes.
  - Every harness document links to concrete checks or PR rules.
  - `AI_HARNESS.md` explains how agent roles, autonomy, evidence, skills, evals, stop rules, and human review fit together.
  - Project skills are documented as a controlled harness layer, not as unreviewed automation.
  - All initial project skills have repo-visible `SKILL.md` sources, `SKILLS.md` inventory entries, and at least one manual forward-test entry in `SKILL_EVALS.md`.
  - "Active skill" means allowed workflow guidance inside the autonomy matrix, not extra authority to make product, API, DB, security, privacy, or merge decisions.
  - `AGENTS.md` can later be shortened because `docs/harness/INDEX.md` points to the durable rules.
  - Security/PII/secrets/API-security-contract failures are specified as hard blockers.
  - Structure, hotspot, import, route-surface, frontend, H5P, skill-governance, and image-only findings are visible as warning signals with an escalation path.
  - Green hard gates are warning-clean unless a transition note names the warning, owner, and hardening path.
  - CI is planned to run the same `make harness-minimum` entry point as local development.

#### PR 2: Security Baseline for CSRF and Session
- Define behavior for missing `Origin`/`Referer` headers.
- Add negative and positive tests for CSRF-relevant write operations.
- Check SameSite/session-cookie rules for critical mutations.
- Acceptance:
  - Done in working tree: `docs/plan/2026-07-02-csrf-session-baseline.md` documents behavior and evidence.
  - Done in working tree: `make test-db-security` runs CSRF/session regression tests.
  - Done in working tree: BFF session-sync cookie flags are asserted directly.

#### PR 3: Security Baseline for Authz and RLS
- Define mandatory negative access tests:
  - student A cannot see student B's data,
  - teacher A cannot see unrelated courses,
  - admin/teacher functions are role-separated,
  - API filters do not replace RLS/database isolation.
- Mark authz/RLS-critical tests as a required set for refactors.
- Acceptance:
  - Done in working tree: `docs/plan/2026-07-02-authz-rls-baseline.md` documents behavior and evidence.
  - Done in working tree: `make test-db-security` sets `REQUIRE_DB_TESTS=1` and runs Authz/RLS/RLS-migration regression tests.
  - Done in working tree: `make harness-minimum` runs `backend/tests/test_makefile_targets.py`, so CI catches accidental gate-composition regressions.

#### PR 4: Security Baseline for Uploads and LLM Data Boundaries
- Define minimal upload tests for MIME type, extension, size, and path manipulation.
- Document which upload content may enter AI/LLM flows.
- Add an initial prompt-injection/data-leak scenario as a regression test, or document it as an explicit open gate failure.
- Acceptance:
  - Done in working tree: `docs/plan/2026-07-02-upload-llm-boundaries.md` documents behavior, product decision, evidence, and residual risks.
  - Done in working tree: `make test-upload-llm-boundaries` runs focused upload, storage, signature, feedback/DSPy, and privacy contracts.
  - Done in working tree: `backend/tests/test_upload_llm_boundaries_contract.py` pins the rule that student submissions are not content-filtered, normalized, moderated, or rewritten before LLM use; technical packaging remains allowed.

#### PR 5: Docker Image-Only Smoke
- Build a smoke test that starts the image without Compose bind mounts.
- Check critical imports from `backend.web`, `backend.learning`, `backend.scratch`, `backend.makecode`, or document explicit optional boundaries.
- Make visible which files are currently available only through local mounts.
- Acceptance:
  - Done in working tree: `docs/plan/2026-07-02-docker-image-only-smoke.md` documents behavior, evidence, and residual import/startup risks.
  - Done in working tree: `make test-docker-image-smoke` builds the web image, runs critical imports without volumes, starts the image, and checks `/health`.
  - Done in working tree: `harness-signals` runs the image-only smoke as a warning signal while `harness-minimum` runs the fast source contract.

#### PR 6: Import Inventory and Blocking Rules
- Inventory flat imports (`routes.*`, `components`, mixed `backend.*` imports).
- Inventory scattered `sys.path` manipulation in tests.
- Add a warning gate that makes new violations visible.
- Document the target import scheme.
- Acceptance:
  - Done in working tree: `backend/tools/import_boundary_scan.py` counts flat `routes.*`, flat `components`, mixed `backend.web.routes.*`, and scattered `sys.path` mutation debt.
  - Done in working tree: `docs/harness/IMPORT_BOUNDARY_BASELINE.json` stores the current baseline and `docs/harness/IMPORT_INVENTORY.md` makes the debt findable.
  - Done in working tree: `make test-import-boundaries` and `make verify` fail if a category grows beyond the baseline; `make harness-signals` reports the same scan warning-only.
  - Done in working tree: `docs/harness/ARCHITECTURE_RULES.md` documents the target scheme and keeps the `backend.web.main:app` migration scoped to PR 8.

#### PR 7: Make Frontend Check Visible
- Record the current green `npm run check` result as the baseline.
- Add the frontend check as a required signal in the verify path.
- Define: after the API baseline, no backend PR can be considered green without frontend contract compatibility.
- Acceptance:
  - Done in working tree: `docs/plan/2026-07-02-frontend-check-visible.md` records the baseline and evidence.
  - Done in working tree: `make test-frontend-h5p` runs `npm run check`, frontend Vitest, and H5P Node tests.
  - Done in working tree: `make verify` runs `make test-frontend-h5p`, so Frontend/H5P quality is no longer outside the full harness.
  - Done in working tree: `frontend/vitest.config.ts` uses `127.0.0.1` so frontend unit tests do not depend on `localhost` DNS resolution.

### Month 2: Enforce Parity and Contracts
Goal: establish local=prod parity, freeze API baseline, and make frontend verification a hard gate.

#### PR 8: Package-Oriented App Start
- Update the packaging contract from flat `main:app`/`routes.*` imports to package-oriented `backend.web.main:app` startup.
- Clean up the Dockerfile toward package-oriented copies of the backend package.
- Reduce `PYTHONPATH` dependency as an architecture crutch and prevent duplicate module instances from mixed import styles.
- Make the Docker image-only smoke hard no later than this PR.
- Acceptance:
  - Done in working tree: `docs/plan/2026-07-02-package-oriented-app-start.md` documents the implementation and evidence.
  - Done in working tree: Dockerfile starts `uvicorn backend.web.main:app` and keeps only `/app` on `PYTHONPATH`.
  - Done in working tree: Dockerfile copies `backend` once as `/app/backend`; Compose mounts `./backend` once as `/app/backend`.
  - Done in working tree: productive Web-Adapter imports use `backend.web.*`, bounded-context imports use `backend.identity_access.*` and `backend.teaching.*`.
  - Done in working tree: `make verify` runs `make test-docker-image-smoke`; the image-only smoke imports `backend.web.main` without bind mounts and reaches `/health`.

#### PR 9: Centralize Test Imports
- Introduce central test import configuration.
- Gradually remove scattered `sys.path` manipulation.
- Tighten the Import Discipline Gate.
- Acceptance:
  - Done in working tree: `backend/tests/import_paths.py` is the central pytest import-path bootstrap.
  - Done in working tree: `backend/tests/conftest.py` delegates import-path setup to `configure_test_import_paths()` and no longer mutates `sys.path` directly.
  - Done in working tree: `backend/tests/packaging/test_test_import_paths_contract.py` blocks regressions in the central pytest bootstrap.
  - Done in working tree: `make test-import-boundaries` remains the hard baseline gate that prevents new local import crutches.
  - Done in working tree: Teaching test import cleanup batch 1 migrated five small tests away from `routes.teaching`/`from routes import teaching` and removed three local `sys.path` mutations by using the central test import configuration plus dynamic package-oriented imports.
  - Done in working tree: `docs/harness/IMPORT_BOUNDARY_BASELINE.json` now pins `flat_routes_imports` at 348 and `sys_path_mutations` at 105; `backend_web_routes_imports` remains unchanged at 22.
  - Done in working tree: RED verification failed before the migration with `flat_routes_imports` current 353 over baseline 348 and `sys_path_mutations` current 108 over baseline 105; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: focused verification for the migrated files reports 13 tests passed and 2 skipped, and `make verify` is green with 1898 backend tests passed/35 skipped, Svelte check 0 errors/0 warnings, 282 frontend Vitest tests passed, and 21 H5P Node tests passed.
  - Open cleanup: continue migrating old tests away from `routes.*`, `identity_access.*`, `teaching.*`, and local `sys.path` blocks, then lower the baseline after each focused batch.

#### PR 10: API Contract Baseline
- Create an OpenAPI baseline with diff/snapshot check.
- Mark public API, BFF/internal, H5P service, auth bridge, health/ops, active UI, and retired legacy UI surfaces.
- Define:
  - Done in working tree: `api/openapi.yml` is documented as the source of truth in `docs/harness/API_CONTRACTS.md`.
  - Done in working tree: `backend.tools.openapi_contract_check` compares live FastAPI Runtime-`/api/*` operations against `api/openapi.yml`.
  - Done in working tree: undocumented `/api/*` endpoints and stale `/api/*` OpenAPI entries are gate failures.
  - Done in working tree: intentionally non-OpenAPI surfaces are classified in `docs/harness/ROUTE_MAP.md` instead of ignored.
  - Done in working tree: breaking changes require an entry in `docs/plan/DECISIONS.md`.
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
  - Done in working tree: `make test-api-contract-baseline` is green and `make verify` runs it as a hard gate.
  - Done in working tree: `make harness-minimum` includes `backend/tests/test_openapi_route_surface_baseline.py`.
  - Open follow-up: H5P service runtime parity and full route-by-route route map remain for later PRs.

#### PR 11: Make Frontend Verification Hard
- Keep the current green Svelte check as the baseline.
- Make `npm run check` a hard gate.
- Add frontend verification to `make verify`.
- Acceptance:
  - Done in working tree as part of PR 7: `make test-frontend-h5p` runs `npm run check`, frontend Vitest, and H5P Node tests.
  - Done in working tree as part of PR 7: `make verify` runs `make test-frontend-h5p`, so platform quality is no longer backend-only.

#### PR 12: Architecture Boundary Rules
- Make architecture rules mechanically checkable where possible.
- Prevent new business logic in routes.
- Inventory DB access paths from web adapters.
- Document the target structure for central security guards and serialization.
- Acceptance:
  - Done in working tree: `backend.tools.architecture_boundary_scan` checks FastAPI imports in Use Cases/Services and web-adapter DB/client debt against `docs/harness/ARCHITECTURE_BOUNDARY_BASELINE.json`.
  - Done in working tree: `make test-architecture-boundaries` is green and `make verify` runs it as a hard gate.
  - Done in working tree: `docs/harness/ARCHITECTURE_RULES.md` documents Security Guards and Serialisierung target rules.
  - Open follow-up: existing web-adapter DB direct access remains inventoried debt to remove in later refactors.

### Month 3: Strangle the Monoliths Safely
Goal: shrink large files, remove retired legacy UI surfaces, and improve DB/runtime boundaries without changing intended product behavior.

#### PR 13: Route Surface Map and Refactor Order
- Create `docs/harness/ROUTE_MAP.md` with:
  - Done in working tree: route/endpoint,
  - Done in working tree: surface classification,
  - Done in working tree: role,
  - Done in working tree: data access,
  - Done in working tree: response model,
  - Done in working tree: existing tests,
  - Done in working tree: risk,
  - Done in working tree: legacy status,
  - Done in working tree: removal or retention decision,
  - Done in working tree: planned target layer.
- Sort monolith strangulation and legacy removal by risk and usage, not by file shape.
- Acceptance:
  - Done in working tree: `backend.tools.route_map_inventory` generates `docs/harness/ROUTE_MAP.md` from Runtime/OpenAPI operations.
  - Done in working tree: `make test-route-map` is green and `make verify` runs it as a hard gate.
  - Done in working tree: removed 410 legacy paths no longer appear in the generated Runtime Route Map; remaining active legacy UI is still marked separately.
  - Open follow-up: H5P asset/runtime patterns and concrete per-route test-file mapping remain to be refined.

#### PR 14: Extract Security Guards
- Add characterization tests for existing guard/authz flows.
- Extract reusable security guards from hotspot files.
- Preserve semantics unless already decided security fixes require deliberate behavior changes.
- Acceptance:
  - Done in working tree: `backend/web/security/guards.py` centralizes reusable role checks.
  - Done in working tree: `app.py`, `users.py`, and `operations.py` use shared role guards instead of local role-check duplicates.
  - Done in working tree: `backend/tests/test_web_security_guards_contract.py` characterizes the shared role guard behavior.
  - Open follow-up: larger Authz/CSRF guard extraction remains for later PR14 slices.

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
  - Done in working tree: `backend/tests/test_app_composition_contract.py` characterizes App-Shell metadata, Static-Mount and representative core route registration.
  - Done in working tree: `backend/web/app_composition.py` owns shell creation, static mounting and core router inclusion.
  - Done in working tree: `backend/web/main.py` exposes a `create_app()` factory for the package-oriented runtime export; it creates the app shell, sets `main_module`, mounts static assets, creates `RUNTIME`, initializes storage, builds `AUTH_WIRING`, installs middleware, and includes routers.
  - Done in working tree: `backend/web/app_composition.py` owns Dotenv loading and deployment startup guards via `bootstrap_runtime_environment()`, so `backend/web/main.py` no longer defines local runtime-bootstrap helpers.
  - Done in working tree: `backend/web/auth_flow.py` owns BFF-bearer surface detection and low-cardinality auth failure classification.
  - Done in working tree: `backend/web/auth_claims.py` owns verified-claim role filtering, primary-role selection, display-name derivation and compact auth-user context construction.
  - Done in working tree: `backend/web/auth_session.py` owns app-session TTL bounds, session-cookie flags and opaque app-session cookie writing.
  - Done in working tree: `backend/web/auth_bridge.py` owns the `/auth/callback` and `/api/me` auth bridge routes with provider-based dependencies so existing main-module test monkeypatches remain effective.
  - Done in working tree: `backend/web/auth_middleware.py` owns auth-context resolution and authentication middleware installation with provider-based dependencies so existing main-module test monkeypatches remain effective.
  - Done in working tree: `backend/web/main_auth_wiring.py` owns the private auth dependency graph for the main app; `backend/web/main.py` exposes only `AUTH_WIRING` for auth composition and no longer exports `_auth_middleware_deps`, `_auth_context_from_request`, or `_roles_for_cli_sub`.
  - Done in working tree: `backend/web/auth_runtime.py` owns Auth settings, OIDC config loading, session-store selection, BFF-session-store selection, CLI-token-store selection, and the explicit `AuthRuntime` object; `backend/web/main.py` creates one `RUNTIME` and exposes it on `app.state.runtime` instead of exporting auth dependency aliases.
  - Done in working tree: the internal Browser-BFF session endpoints in `backend/web/routes/app.py` now read the BFF session store from `request.app.state.runtime.bff_session_store`, with a legacy main-alias fallback only for old import contexts.
  - Done in working tree: `POST /api/app/session-sync` now reads the app session store and settings from `request.app.state.runtime`, with a legacy main-alias fallback only for old import contexts.
  - Done in working tree: the profile routes in `backend/web/routes/app.py` now read OIDC configuration and CLI token storage from `request.app.state.runtime`, with legacy main-alias fallbacks only for old import contexts.
  - Done in working tree: the profile route's second bearer-claims resolution now uses the route module's direct `verify_bearer_token` dependency instead of the `main.verify_bearer_token` compatibility alias.
  - Done in working tree: `/auth/logout` now reads session store, OIDC configuration and settings from `request.app.state.runtime`; `/auth/forgot` reads OIDC configuration from the same runtime path; `/auth/password`, `/auth/login`, and `/auth/register` read PKCE state storage and OIDC configuration from `request.app.state.runtime`, with legacy main-alias fallbacks only for old import contexts.
  - Done in working tree: `backend/web/layout_response.py` owns HTMX-aware Layout-to-HTMLResponse rendering for basic pages and retired legacy notices, so `backend/web/main.py` no longer defines a local Layout response helper.
  - Done in working tree: `backend/web/main_router_wiring.py` owns concrete router composition for the remaining FastAPI shell; `backend/web/main.py` no longer imports each router or calls `include_core_routers()` directly.
  - Done in working tree: `backend/web/main_middleware_wiring.py` owns main middleware installation order for Auth and Security Headers; `create_app()` calls only that focused wiring helper.
  - Done in working tree: `backend/web/main_storage_wiring.py` owns startup storage adapter initialization; `create_app()` calls only that focused storage wiring helper and `backend/web/main.py` no longer imports or aliases the Supabase storage helper directly.
  - Done in working tree: `backend/web/csrf_tokens.py` owns SSR CSRF token TTL bounds, secret resolution, signing and validation.
  - Done in working tree: `backend/web/internal_api.py` owns SSR-internal base URL resolution and ASGI client `Origin` header policy.
  - Done in working tree: `backend/web/ssr_helpers.py` owns small pure SSR helpers for URL encoding, delta cursor timestamp normalization, pagination clamps, HTMX attribute payload escaping, analysis-status checks, and task-submit idempotency tokens.
  - Done in working tree: `backend/web/submission_history_rendering.py` owns Learning submission/history rendering helpers, including status telemetry, artifact previews, feedback failure text, and analysis-in-progress rendering; `backend/web/main.py` no longer imports the component helpers used only by that rendering path.
  - Done in working tree: `backend/web/auth_only_app.py` owns the lightweight auth-only app factory used by auth smoke and contract tests; `backend/web/main.py` keeps only a compatibility export and no longer owns the stub routes.
  - Done in working tree: `backend/storage/verification.py` owns local best-effort storage SHA-256 computation, so `backend/web/main.py` no longer defines Storage filesystem helpers.
  - Done in working tree: removed retired Learning HTML dummy stores, task-submit form rendering, and the unused server-side upload fallback from `backend/web/main.py` after PR16 retired the corresponding legacy routes.
  - Done in working tree: removed retired Teacher-Unit-/Course SSR render/fetch helpers, Teaching-Live matrix cell renderers and Course-Members SSR label/cache/rendering helpers from `backend/web/main.py`; active Teacher, Live and Course-Members surfaces stay covered by API/OpenAPI/Svelte contracts.
  - Done in working tree: `backend/web/cli_authoring.py` owns CLI authoring capability routing and OpenAPI CLI-surface parity.
  - Done in working tree: `backend/web/security/headers.py` owns the testable Security-Header policy via `build_security_header_defaults()` and installs the Security-Header middleware via `install_security_headers_middleware()`, while the existing middleware order remains unchanged.
  - Done in working tree: `backend/web/runtime_config.py` owns the Teaching-Live polling interval parser and clamp behavior.
  - Done in working tree: `backend/web/legacy_retirement.py` owns retired legacy product path decisions and the shared 410/role-redirect response rendering.
  - Done in working tree: `backend/web/routes/basic_pages.py` owns the small `/`, `/about`, and `/health` routes while `backend/web/main.py` only includes the router.
  - Done in working tree: `backend.web.main:app` still imports and starts in tests and Docker image smoke.
  - Done in working tree: additional Runtime-Session-Fixture cleanup migrated Teaching module-section/cache tests, Learning upload-proxy/storage tests, Worker task-context setup, Legacy HTML exit contracts, and one Teaching-Live relation-guard test from direct `main.SESSION_STORE` writes to `install_session_store(monkeypatch, main)`; the focused verification batch reports 29 passed and 13 DB-dependent skipped tests.
  - Done in working tree: the Runtime-Session-Fixture cleanup also migrated Learning internal upload-proxy security tests, modular unlock parity tests, and Teaching modular-edge/unit-phase error-mapping tests away from direct `main.SESSION_STORE` writes; the focused verification batch reports 22 passed and 2 DB-dependent skipped tests.
  - Done in working tree: the Runtime-Session-Fixture cleanup also migrated Teaching units-catalog views, unit-workspace views, and member-semantics tests away from direct `SessionStore`/`main.SESSION_STORE` setup; the focused verification batch reports 6 passed and 14 DB- or repo-capability-dependent skipped tests.
  - Done in working tree: the Runtime-Session-Fixture cleanup also migrated Teaching modular-editor CRUD, modular graph, and units/modules contract tests away from direct `SessionStore`/`main.SESSION_STORE` setup; the focused verification batch reports 2 passed and 31 DB-dependent skipped tests.
  - Done in working tree: the Runtime-Session-Fixture cleanup also migrated Teaching file-material tests away from direct `SessionStore`/`main.SESSION_STORE` setup; the focused verification batch reports 4 passed and 15 DB-dependent skipped tests.
  - Done in working tree: the Runtime-Session-Fixture cleanup also migrated Session-Sync API tests and Supabase storage E2E tests away from direct `SessionStore`/`main.SESSION_STORE` setup; the focused verification batch reports 4 passed and 5 opt-in E2E skipped tests.
  - Done in working tree: the Runtime-Session-Fixture cleanup also migrated Learning modular-unit contract tests away from direct `SessionStore`/`main.SESSION_STORE` setup; the focused verification batch reports 5 passed and 10 DB-dependent skipped tests.
  - Done in working tree: the Runtime-Session-Fixture cleanup also migrated Auth contract reads, Teaching Live detail/overview/delta/summary API tests, the global pytest session reset, and non-alias Auth hardening cases away from accidental `main.SESSION_STORE` use; focused verification reports 39 passed/32 skipped for the migrated Auth+Teaching Live batch and 43 passed for the remaining Auth helper/composition contracts.
  - Done in working tree: the Runtime-Session-Fixture cleanup left no production or test setup dependency on `main.SESSION_STORE`; remaining hits of the old auth alias names are limited to absence contracts that assert they are not exported.
  - Done in working tree: `backend/web/main.py` wires the Auth middleware/bridge session-store and state-store providers directly to `RUNTIME.session_store` and `RUNTIME.state_store`; focused Auth/API verification for the migration reported 88 passed tests before final alias removal.
  - Done in working tree: `backend/web/main.py` wires the Auth middleware/bridge OIDC client and OIDC config providers directly to `RUNTIME.oidc_client` and `RUNTIME.oidc_config`; Runtime helper contracts cover OIDC client/config installation for tests, and the focused Auth/OIDC verification batch reported 117 passed tests before final alias removal.
  - Done in working tree: `backend/web/main.py` wires the Auth middleware CLI-token provider directly to `RUNTIME.cli_token_store`; focused Middleware/Profile helper verification reported 51 passed tests before final alias removal.
  - Done in working tree: `backend/web/main.py` wires Auth bridge, middleware, and auth-only environment providers directly to `RUNTIME.settings.environment`; focused Auth/Cookie/App Composition verification reported 92 passed tests before final alias removal.
  - Done in working tree: `backend/web/auth_only_app.py` now installs an explicit minimal auth runtime for the lightweight auth test app, and `backend/web/routes/auth.py` no longer falls back to main-module service-locator aliases for session store, state store, OIDC config, or settings; the focused Auth route/Auth-only verification batch reports 91 passed tests.
  - Done in working tree: `backend/web/routes/app.py` no longer falls back to main-module service-locator aliases for BFF session store, app session store, settings, OIDC config, or CLI token store, and the unused local CLI token fallback store was removed; the focused BFF/Profile/Session Bootstrap/Session Sync verification batch reports 29 passed tests.
  - Done in working tree: `backend/web/main.py` no longer exports the temporary `SETTINGS`, `OIDC_CFG`, `OIDC`, `STATE_STORE`, `SESSION_STORE`, `BFF_SESSION_STORE`, or `CLI_TOKEN_STORE` compatibility aliases; route and test setup now use `RUNTIME` or explicit provider helpers, `backend/web/routes/learning.py` resolves environment from `RUNTIME.settings`, and alias-specific transition tests were replaced by runtime-only contracts.
  - Done in working tree: focused verification for the alias-removal slice reports 194 passed tests, `make test-route-map` reports `route-map-inventory-ok`, and `make verify` is green with 1888 backend tests passed/35 skipped, Svelte check 0 errors/0 warnings, 282 frontend Vitest tests passed, and 21 H5P Node tests passed.
  - Done in working tree: `backend/web/main.py` no longer exports `_roles_for_cli_sub` or `_auth_context_from_request`; middleware tests now replace `AUTH_WIRING.auth_middleware_dependencies.roles_for_cli_sub` explicitly, and `install_main_middlewares()` receives `AUTH_WIRING.auth_context_from_request` directly.
  - Done in working tree: focused Auth/Composition verification for private Auth helper export removal reports 142 passed tests, `make test-route-map` reports `route-map-inventory-ok`, and `make verify` is green with 1888 backend tests passed/35 skipped, Svelte check 0 errors/0 warnings, 282 frontend Vitest tests passed, and 21 H5P Node tests passed.
  - Done in working tree: `create_app()` now owns runtime, storage, auth-wiring, middleware, and router composition; module-level `RUNTIME` and `AUTH_WIRING` are references to `app.state.runtime` and `app.state.auth_wiring` instead of independently initialized globals.
  - Done in working tree: focused App-Factory verification reports 16 App Composition tests passed, 127 Auth/Profile/BFF/Session tests passed, `make test-route-map` reports `route-map-inventory-ok`, and `make verify` is green with 1889 backend tests passed/35 skipped, Svelte check 0 errors/0 warnings, 282 frontend Vitest tests passed, and 21 H5P Node tests passed.

#### PR 16: Legacy HTML/HTMX Exit Wave 1
- Remove already-retired and unreachable FastAPI product HTML/HTMX code first.
- Confirm SvelteKit ownership or intended 404/410 behavior with tests before deleting handlers.
- Remove unused static assets, templates, and helper functions only after no route references them.
- Acceptance:
  - Done in working tree: `/learning`, `/courses`, `/units`, `/teaching/live`, `/teaching/live/open` and `/teaching/live/units` are no longer registered as local `APIRoute` handlers.
  - Done in working tree: direct backend access to these removed retired product UI paths has an intentional tested 410 or role-redirect result.
  - Done in working tree: `make test-route-map` is green after the Runtime Route Map update.
  - Done in working tree: `POST /courses`, `/courses/{course_id}/modules*`, and `/courses/{course_id}/members*` legacy handlers are no longer registered.
  - Done in working tree: `POST /units`, `/units/{unit_id}`, `/units/{unit_id}/edit`, `/units/{unit_id}/modules`, and `/units/{unit_id}/phases*` legacy handlers are no longer registered.
  - Done in working tree: `/units/{unit_id}/modules/{module_id}*` and `/units/{unit_id}/modular-editor*` legacy handlers are no longer registered.
  - Done in working tree: `/units/{unit_id}/sections*`, material, and task legacy handlers are no longer registered.
  - Done in working tree: retired Teacher-Unit-/Course SSR helper blocks for unit lists, section/material/task lists, module editor, phases, internal SSR API fetches and unit edit rendering were removed from `backend/web/main.py`.
  - Done in working tree: `/learning/courses*` legacy HTML/HTMX handlers are no longer registered; direct backend access is still intentionally answered by the central retirement middleware.
  - Done in working tree: deep Teaching-Live HTML/HTMX handlers (`/teaching/courses/{course_id}/students/{student_sub}/live`, `/teaching/courses/{course_id}/units/{unit_id}/live*`) and the old section-visibility POST helper are no longer registered; direct backend access is still intentionally answered by the central retirement middleware.
  - Done in working tree: unused Teaching-Live SSR helper blocks for matrix, detail, section release panel, and student overview rendering were removed from `backend/web/main.py`.
  - Done in working tree: `make test-route-map` is warning-clean; the contract now asserts no stderr output from the Route Map generator.
  - Done in working tree: Learning submission/history renderer helpers were moved out of `backend/web/main.py` after the related retired Learning HTML routes left the runtime route surface; focused rendering tests now import the dedicated module.
  - Open follow-up: decide the future of the remaining root/about FastAPI HTML pages and continue route-split PRs for the larger FastAPI route modules.

#### PR 17: First Risk-Based Teaching Route Split
- Split `backend/web/routes/teaching.py` according to the Route Map where risk and benefit justify the first cut.
- Keep routes thin and move orchestration into use-case wiring.
- Use contract diff to verify API neutrality.
- Acceptance:
  - Done in working tree: task-centric H5P authoring endpoints were moved from `backend/web/routes/teaching.py` into the dedicated `backend/web/routes/teaching_h5p.py` router and registered through `backend/web/main_router_wiring.py`.
  - Done in working tree: `backend/tests/test_teaching_h5p_route_split_contract.py` asserts that the seven H5P task-authoring paths are still registered but now owned by `backend.web.routes.teaching_h5p`, and that those route decorators no longer live in `teaching.py`.
  - Done in working tree: the same contract now asserts that H5P authoring helper ownership moved with the router: H5P upload limits, internal-auth headers, Web-to-H5P request proxying, rollback deletion, task-owned H5P resolution, upstream error mapping, and `H5PTaskSavePayload` live in `backend/web/routes/teaching_h5p.py`, not `backend/web/routes/teaching.py`.
  - Done in working tree: `backend/web/routes/teaching_shared.py` now owns small shared Teaching response/identity helpers (`_role_in`, `_current_sub`, `_require_teacher`, `_is_uuid_like`, `_json_private`, `_private_error`), and `backend/web/routes/teaching_h5p.py` imports them explicitly instead of calling `teaching._...`.
  - Done in working tree: `backend/web/routes/teaching_task_services.py` now owns the explicit `TasksService` provider boundary; `backend/web/routes/teaching_h5p.py` calls that provider instead of `teaching._get_tasks_service()`.
  - Done in working tree: `backend/web/routes/teaching_guards.py` now owns the shared Teaching unit-author guard, CSRF guard, and strict same-origin helper; `backend/web/routes/teaching_h5p.py` calls that explicit guard module instead of `teaching._guard_unit_author()` or `teaching._csrf_guard()`.
  - Done in working tree: `backend/tests/test_routes_repo_set_repo_contract.py` covers the temporary Teaching route-local guard adapters so legacy `routes.teaching` reload and monkeypatch tests still use the endpoint's active repository accessor while the actual guard logic stays in `teaching_guards.py`.
  - Done in working tree: `backend/web/routes/teaching_authoring.py` now owns module-backed authoring section resolution and signature-compatible module-section lookup; `backend/web/routes/teaching_h5p.py` no longer imports `backend.web.routes.teaching` or calls any `teaching._...` helper.
  - Done in working tree: the largest route hotspot shrank measurably from the prior 7569-line Teaching router to 6835 lines, with the extracted H5P router at 553 lines, the shared helper module at 71 lines, the serializer module at 89 lines, the task-service provider at 32 lines, the guard module at 81 lines, and the authoring boundary at 123 lines.
  - Done in working tree: focused verification reports 25 H5P/authoring/guard tests passed, 4 modular API tests passed with 31 DB-dependent skips, 15 repo-reload/guard-regression tests passed, import-boundary and architecture-boundary scans ok, OpenAPI contract ok, and `make test-route-map` reports `route-map-inventory-ok`.
  - Done in working tree: `make verify` is green with 1897 backend tests passed/35 skipped, Svelte check 0 errors/0 warnings, 282 frontend Vitest tests passed, and 21 H5P Node tests passed.
  - Open follow-up: remove the temporary Teaching route-local guard and authoring adapters after legacy flat route imports are gone, and continue additional Teaching route splits/use-case wiring.

#### PR 18: Separate Serialization and Response Models
- Separate request/response shaping from business logic.
- Stabilize API models for core flows.
- Improve readability for new contributors and students.
- Acceptance:
  - Done in working tree: `backend/web/routes/teaching_serialization.py` now owns `_serialize_task`, including task-kind normalization for native, H5P, visual, Scratch, Calliope, and Filius tasks.
  - Done in working tree: `backend/tests/test_teaching_h5p_route_split_contract.py` asserts that `_serialize_task` no longer lives in `backend/web/routes/teaching.py`, that H5P imports the serializer explicitly, and that legacy flat H5P storage columns are not exposed in serialized task responses.
  - Done in working tree: `backend/web/routes/teaching_serialization.py` also owns the modular graph response serializers (`_serialize_unit_phase`, `_serialize_unit_phase_public`, `_serialize_unit_module`, `_serialize_unit_graph_edge`), including the rule that module responses do not expose backing `section_id` and edges normalize repo keys to `{from, to}`.
  - Done in working tree: `backend/web/routes/teaching_serialization.py` also owns the simple Teaching response serializers (`_serialize_course`, `_serialize_unit`, `_serialize_module`, `_serialize_section`, `_serialize_material`) without changing their dict/dataclass/object response behavior.
  - Done in working tree: `backend/web/routes/teaching_serialization.py` also owns latest-submission analysis normalization and payload building (`_normalise_analysis_json`, `_build_latest_submission_payload`); the route still owns auth, DB access, relation checks, H5P review-token creation, and the file-link builder.
  - Done in working tree: `backend/tests/test_teaching_serialization_contract.py` asserts serializer ownership outside `backend/web/routes/teaching.py` and checks representative response shapes for courses, materials, phases, modules, edges, criteria analysis, PDF file payloads, and latest-submission file links.
  - Done in working tree: the Teaching route hotspot is now 6465 lines, with `backend/web/routes/teaching_serialization.py` at 375 lines.
  - Done in working tree: focused verification reports the serialization contract passed, the OpenAPI Teaching live-detail contract passed, the Teaching live-detail API file passed with DB-dependent skips, 12 course/unit/section/material/module route tests passed with 35 DB-dependent skips, import-boundary and architecture-boundary scans ok, OpenAPI contract ok, and `make test-route-map` reports `route-map-inventory-ok`.
  - Done in working tree: `make verify` is green with 1898 backend tests passed/35 skipped, Svelte check 0 errors/0 warnings, 282 frontend Vitest tests passed, and 21 H5P Node tests passed.
  - Open follow-up: live-dashboard summary/delta response shaping remains broader than the latest-submission slice and should move in a later PR18 slice.

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
  - skill inventory and skill-eval status,
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
- Project skills are part of the supply chain: their instructions, helper scripts, examples, and tool permissions need review because they can steer agent behavior.

## Research Sources
The 2026-06-25 update is based on these sources:
- [AI Harness Engineering: Formalizing Effective Runtime Substrates for LLM Agents](https://arxiv.org/abs/2605.13357): treats a harness as a runtime substrate for context, tools, project memory, verification, permissions, observability, failure attribution, and human intervention.
- [Agent Skills specification](https://agentskills.io/specification): defines skills as directories with `SKILL.md`, optional scripts, references, and assets that are loaded only when relevant.
- [Agent Skills evaluation guide](https://agentskills.io/skill-creation/evaluating-skills): recommends realistic eval prompts, assertions, comparison with and without the skill, and human review before trusting a skill.
- [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents): recommends simple, composable agent workflows, transparent tool use, strong grounding in the environment, and clear human oversight.
- [OpenAI Agents SDK documentation](https://openai.github.io/openai-agents-python/): documents guardrails, tool guardrails, handoffs, and tracing as practical building blocks for controlled agent runs.
- [OpenAI Agents SDK tracing documentation](https://openai.github.io/openai-agents-python/tracing/): describes traces for agent workflows, tool calls, guardrails, handoffs, and custom events.
- [Repo-level instruction study for `AGENTS.md`](https://arxiv.org/abs/2601.20404): suggests repository-level instructions can reduce runtime and output tokens without reducing task success.
- [Skill-utility study](https://arxiv.org/abs/2604.04323): shows that skill usefulness is not automatic under realistic selection conditions and should be measured.
- [Skill supply-chain risk paper](https://arxiv.org/abs/2605.11418): highlights that skill files are operational instructions and should be governed like a supply-chain input.

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
- Skill/harness PRs: skill inventory check, repo-visible `SKILL.md` source check, no unsafe tool permissions, no PII/secrets in examples, and at least one realistic manual forward-test entry in `SKILL_EVALS.md` for each active skill.

## Open Decisions
- Exact technical implementation of gates:
  - pure `make` targets,
  - Python check scripts,
  - GitHub Actions,
  - or a combination.
- Deadline and thresholds for hotspot LOC.
- Whether `TECH_DEBT.md` stays under `docs/harness/` or later moves into ADR/governance documents.
- Later installation path for tool-specific local copies of repo-governed project skills.
- When scripted skill evals should be introduced after the manual forward-test format stabilizes.

Recommended defaults:
- Gate implementation starts locally via `make`; CI runs the same entry point from PR 1 onward.
- Frontend check is a required signal from PR 7 and hard no later than PR 11; the 2026-05-15 green result is the baseline.
- Hotspot Growth Gate becomes hard directly after PR 6.
- Legacy HTML removal is staged: retired/dead paths first, then additional removals only after route-map and parity tests.
- `backend/web/main.py` gets its own PR before deeper route splits.
- Frontend and H5P hotspots are included in the same quality scorecard as backend hotspots.
- `TECH_DEBT.md` initially stays under `docs/harness/` because that is easiest for agents to find.
- `docs/harness/AI_HARNESS.md` is introduced in PR 1 as the central AI harness specification.
- `docs/harness/SKILLS.md`, `docs/harness/SKILL_EVALS.md`, and `docs/harness/skills/<skill>/SKILL.md` are introduced in PR 1 before any tool-specific local installation path is treated as official.
- Initial active skills are `gustav-plan-status`, `gustav-pr-review`, `gustav-pr-fix`, `gustav-api-contract`, `gustav-security-review`, `gustav-route-map`, and `gustav-harness-gardener`.
- PR 1 uses manual skill forward-tests, not scripted evals.
- Level 3 autonomy is allowed only for documentation, review, plan-status, harness-gardening, and tech-debt PR preparation during the first three months.
- Executable project skills require realistic manual forward-test evidence before they become hard workflow dependencies.
- GitHub Actions are introduced with PR 1, at least for security baseline, public-repo hygiene, and Docker/image smoke.

## Next Step After Plan Approval
1. Create a dedicated branch: `feature/harness-engineering-refactor`.
2. Implement PR 1: harness minimum and plan index.
3. Then implement PRs 2 through 4 directly so CSRF, authz/RLS, uploads, and LLM data boundaries do not wait behind documentation work.
4. After every PR: update plan status and reduce open decisions.
