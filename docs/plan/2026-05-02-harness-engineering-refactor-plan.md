# Harness Engineering and Code Quality Refactor Plan

## Status
- Date: 2026-05-02
- Last updated: 2026-07-05
- Status: Completed v1.0; Closeout v1.1 open. The harness refactor is implemented in the working tree with hard gates for security, import boundaries, architecture boundaries, DB/RLS test inventory, API contracts, route maps, frontend/H5P checks, Docker image parity, quality scorecard, public-repo safety, and full verification. The v1 closeout removes the remaining flat import aliases, retires the active FastAPI shell pages `/` and `/about`, zeroes the architecture-boundary and import-boundary baselines, and marks the harness documents as active. The refactor is not fully closed until Closeout v1.1 either modularizes the remaining large source hotspots or records deliberately accepted residual debt with owner, review date, risk, and exit criterion in `docs/harness/TECH_DEBT.md`.
- Time horizon: 3 months
- Strategy: harness first, then refactor in small PRs
- Gate strategy: security, public-repo hygiene, import boundaries, architecture boundaries, route map, API contract, DB inventory, Docker image parity, frontend/H5P, and full verification run as hard gates; `make harness-signals` remains advisory telemetry.
- Scope decision: broad quality refactor with staged, test-protected removal of legacy FastAPI HTML/HTMX product paths
- Agentic harness decision: agent-first execution with human review; PR 1 delivers orientation and minimum gates; safety gates block immediately, structure gates start as warnings
- Current check: PR-1 harness artifacts, repo-governed skill sources, `docs/plan/INDEX.md`, `docs/plan/MILESTONES.md`, `docs/plan/DECISIONS.md`, `make harness-minimum`, `make harness-signals`, `make test-import-boundaries`, `make test-frontend-h5p`, `make test-docker-image-smoke`, `make test-route-map`, `make quality-scorecard`, `make verify`, `make test-full-prod-like`, and the GitHub Actions harness workflow are present in the working tree.

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

The most important initial findings and v1 closure state are:
- The backend web adapter still contains large modules, but `backend/web/main.py` is a small app-composition entry point and Teaching/H5P/serialization responsibilities are split behind tested router and helper boundaries.
- Docker and import behavior are guarded by image-only smoke checks, package-oriented app startup, hard import-boundary scans, and removal of legacy flat import aliases.
- Frontend verification is part of `make verify`; `npm run check`, Frontend-Vitest, and H5P Node tests run in the hard deterministic gate.
- API contract-first is enforced by `make test-api-contract-baseline` and a generated Route Map that separates public API, BFF-internal, H5P service routes, auth bridges, health checks, and retired surfaces.
- FastAPI no longer registers active product HTML/HTMX shell pages; retired direct-backend product paths are covered by tested 410 or role-redirect behavior.
- Web-adapter direct DB and Supabase-client creation debt is zero in the architecture-boundary baseline; approved infrastructure lives in dedicated adapter modules.
- Frontend, H5P, CSS, web-route, and repository hotspots are tracked in `docs/harness/HOTSPOTS.md` and the monthly quality scorecard; relevant growth needs tests or a concrete Tech-Debt entry.
- Security and GDPR/privacy boundaries are executable through hard security, CSRF, privacy logging, DB/RLS inventory, data-inventory, and public-repo safety checks.

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
- SvelteKit is the canonical product UI. FastAPI keeps API, BFF/internal, health, H5P integration, and required auth bridge behavior; retired product HTML/HTMX surfaces are not kept as long-term compatibility code.
- Legacy HTML removal is staged: first inventory and tests, then removal of already-retired/dead paths, then further removals only after parity or redirect behavior is covered.
- The target runtime entry point is package-oriented (`backend.web.main:app`) rather than relying on flat `main:app` imports from copied directories.
- DB performance work is part of the refactor scope: introduce a small shared connection/transaction boundary before replacing scattered direct DB calls.
- CSP and CSRF hardening is part of the executable security baseline as legacy HTMX and inline-style dependencies are removed.
- `AGENTS.md` remains the concise top-level map. Detailed, versioned agent rules live under `docs/harness/`.
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
- Done in working tree: direct DB/RLS test inventory is generated by `backend.tools.db_test_inventory`, checked by `make test-db-inventory`, wired into `make verify`, and written to `docs/harness/DB_TEST_INVENTORY.md`; current baseline reports 0 real DB/RLS candidates without `db_read`/`db_write`, 86 `db_read`/`db_write`-marked DB candidates, 9 real DB/RLS candidates covered by existing opt-in markers, and pytest DB infrastructure classified as `test-infra`, so marker hardening no longer remains a follow-up batch task.
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
  - Done in working tree: Cache header test import cleanup batch 2 migrated `backend/tests/test_api_cache_headers.py`, `backend/tests/test_api_cache_headers_write_endpoints.py`, and `backend/tests/test_api_cache_headers_materials_tasks.py` to dynamic package-oriented imports and removed three more local `sys.path` mutations.
  - Done in working tree: Auth test import cleanup batch 3 migrated `backend/tests/test_api_auth_unauthenticated.py`, `backend/tests/test_auth_cache_headers.py`, and `backend/tests/test_auth_default_app_base.py` to package-oriented dynamic imports and removed three more local `sys.path` mutations.
  - Done in working tree: Auth callback test import cleanup batch 4 migrated `backend/tests/test_auth_cookie_policies.py`, `backend/tests/test_auth_display_name.py`, and `backend/tests/test_auth_email_verification.py` to package-oriented imports and removed three more local `sys.path` mutations.
  - Done in working tree: Auth flow test import cleanup batch 5 migrated `backend/tests/test_auth_forgot_flow.py`, `backend/tests/test_auth_login_htmx.py`, `backend/tests/test_auth_login_register_redirect_302.py`, and `backend/tests/test_auth_logout_success.py` to package-oriented imports and removed four more local `sys.path` mutations.
  - Done in working tree: Bearer/BFF test import cleanup batch 6 migrated `backend/tests/test_bearer_jwt_auth_api.py`, `backend/tests/test_bff_authorization_session_api.py`, and `backend/tests/test_bff_session_internal_api.py` to package-oriented imports and removed three more local `sys.path` mutations.
  - Done in working tree: Legacy retirement test import cleanup batch 7 migrated `backend/tests/test_learning_legacy_entry_retired.py`, `backend/tests/test_learning_legacy_unit_routes_retired.py`, and `backend/tests/test_teaching_legacy_routes_retired.py` to package-oriented dynamic `backend.web.main` imports and removed three more local `sys.path` mutations.
  - Done in working tree: View test import cleanup batch 8 migrated `backend/tests/test_app_home_views_api.py`, `backend/tests/test_concern_box_views_api.py`, `backend/tests/test_diagnostics_course_matrix_view_api.py`, and `backend/tests/test_diagnostics_learner_profile_view_api.py` to package-oriented dynamic imports and removed four flache `routes.*` imports plus four local `sys.path` mutations.
  - Done in working tree: Profile/live view test import cleanup batch 9 migrated `backend/tests/test_profile_view_api.py`, `backend/tests/test_teaching_course_context_view_api.py`, and `backend/tests/test_live_view_api.py` to package-oriented dynamic imports and removed three flache `routes.*` imports plus three local `sys.path` mutations.
  - Done in working tree: Auth nonce/password test import cleanup batch 10 migrated `backend/tests/test_auth_password_flow.py`, `backend/tests/test_auth_phase2_hardening.py`, `backend/tests/test_auth_register_nonce.py`, and `backend/tests/test_auth_register_redirect.py` to package-oriented imports and removed four more local `sys.path` mutations.
  - Done in working tree: Auth/navigation sys-path cleanup batch 11 migrated `backend/tests/test_auth_smoke.py`, `backend/tests/test_auth_ui_nav_and_links.py`, `backend/tests/test_identity_access_directory_name_formatting.py`, and `backend/tests/test_navigation_roles_ui.py` to package-oriented imports and removed four more local `sys.path` mutations.
  - Done in working tree: Auth middleware test import cleanup batch 12 migrated `backend/tests/test_api_me_with_db_session_store.py`, `backend/tests/test_auth_hardening.py`, and `backend/tests/test_auth_middleware.py` to package-oriented imports, removed three more local `sys.path` mutations, and removed one flacher `routes.*` import.
  - Done in working tree: Auth registration domain test import cleanup batch 13 migrated `backend/tests/test_auth_register_domain_whitelist.py` to one package-oriented app import and removed five repeated local `sys.path` mutations.
  - Done in working tree: Sidebar/security header test import cleanup batch 14 migrated `backend/tests/test_navigation_sidebar_toggle.py` and `backend/tests/test_security_headers_middleware.py` to package-oriented app imports and removed two more local `sys.path` mutations.
  - Done in working tree: Session/profile contract test import cleanup batch 15 migrated `backend/tests/test_session_bootstrap_api.py`, `backend/tests/test_session_sync_api.py`, and `backend/tests/test_openapi_profile_contract.py` to package-oriented app imports and removed three more local `sys.path` mutations.
  - Done in working tree: Users API test import cleanup batch 16 migrated `backend/tests/test_users_list_api.py` and `backend/tests/test_users_search_api.py` to package-oriented app and users-route imports, removed three flache `routes.*` imports, and removed two more local `sys.path` mutations.
  - Done in working tree: Learning upload-intent test import cleanup batch 17 migrated `backend/tests/test_learning_upload_intent_response_shape.py`, `backend/tests/test_learning_upload_intent_config_limit.py`, `backend/tests/test_learning_upload_intent_public_host.py`, and `backend/tests/test_learning_upload_content_signature_validation.py` to package-oriented learning-route imports, removed four flache `routes.*` imports, and replaced old `teaching.*` Kurzimporte in the touched files.
  - Done in working tree: Learning Spezialformate test import cleanup batch 18 migrated `backend/tests/test_learning_filius_fls_submission_api.py`, `backend/tests/test_learning_filius_fls_upload_intent.py`, `backend/tests/test_learning_sb3_repo_capability_guard.py`, and `backend/tests/test_learning_submission_payload_mime_casing.py` to package-oriented learning-route imports, removed four flache `routes.*` imports, and replaced old `teaching.*` Kurzimporte in the touched files.
  - Done in working tree: Legacy Live SSR test import cleanup batch 19 migrated `backend/tests/test_teaching_live_detail_ssr.py`, `backend/tests/test_teaching_live_nav_ssr.py`, `backend/tests/test_teaching_live_section_release_ssr.py`, `backend/tests/test_teaching_live_student_overview_ssr.py`, and `backend/tests/test_teaching_live_unit_ui_ssr.py` to package-oriented app imports while preserving required environment setup before app import, and removed five more local `sys.path` mutations.
  - Done in working tree: OpenAI Health test import cleanup batch 20 migrated `backend/tests/test_openai_health_endpoint.py` to package-oriented app and operations-route imports, removed seven flache `routes.*` imports, and removed one more local `sys.path` mutation while keeping the required `sys.modules` monkeypatch path intact.
  - Done in working tree: Learning Calliope Hex test import cleanup batch 21 migrated `backend/tests/test_learning_calliope_hex_upload_only_api.py` to package-oriented app, learning-route, teaching-route, and teaching storage/repository imports, and removed two flache `routes.*` imports.
  - Done in working tree: Learning H5P test import cleanup batch 22 migrated `backend/tests/test_learning_h5p_access_check_api.py` and `backend/tests/test_learning_h5p_scoring_api.py` to package-oriented app, learning-route, teaching-route, and teaching repository imports, and removed six flache `routes.*` imports.
  - Done in working tree: Learning config test import cleanup batch 23 migrated `backend/tests/test_learning_bucket_uses_central_config.py` and `backend/tests/test_learning_internal_proxy_limit_config.py` to package-oriented app and learning-route imports, and removed two flache `routes.*` imports.
  - Done in working tree: Learning Internal Proxy Prod-Parity test import cleanup batch 24 migrated `backend/tests/test_learning_internal_proxy_prod_parity.py` to dynamic package-oriented app and learning-route imports, removed five flache `routes.*` imports, and removed five static `backend.web.routes.*` imports from the test boundary inventory.
  - Done in working tree: Learning Internal Proxy Security test import cleanup batch 25 migrated `backend/tests/test_learning_internal_proxy_security.py` to dynamic package-oriented app and learning-route imports, removed eleven flache `routes.*` imports, and removed eleven static `backend.web.routes.*` imports from the test boundary inventory.
  - Done in working tree: Learning submission route test import cleanup batch 26 migrated `backend/tests/test_learning_create_submission_fail_closed.py`, `backend/tests/test_learning_csrf_diag_log_redaction.py`, and `backend/tests/test_learning_h5p_submission_status_code.py` to dynamic package-oriented app and learning-route imports, and removed three static `backend.web.routes.*` imports from the test boundary inventory.
  - Done in working tree: Learning PDF/upload proxy test import cleanup batch 27 migrated `backend/tests/test_learning_pdf_processing_hook.py` and `backend/tests/test_learning_upload_proxy_fallback.py` to dynamic package-oriented app and learning-route imports, removed two flache `routes.*` imports, removed the final three static `backend.web.routes.*` imports from the test boundary inventory, and fixed route-global monkeypatch cleanup so the PDF tests no longer leak `_get_repo` into later upload-intent tests.
  - Done in working tree: Learning lazy storage wiring test import cleanup batch 28 migrated `backend/tests/test_learning_lazy_storage_wiring.py` to dynamic package-oriented app, learning-route, teaching-route, and storage imports, replaced local path bootstrap with explicit `sys.modules` cleanup, removed three flache `routes.*` imports, and removed one local `sys.path` mutation.
  - Done in working tree: Teaching/Learning small API test import cleanup batch 29 migrated `backend/tests/test_teaching_sections_memory_repo_smoke.py`, `backend/tests/test_teaching_units_get_api.py`, and `backend/tests/test_learning_submissions_default_strict_csrf.py` to package-oriented app, route, and test-helper imports, removed one flacher `routes.*` import, and removed two local `sys.path` mutations.
  - Done in working tree: No-DB helper/fallback test import cleanup batch 30 migrated `backend/tests/test_learning_routes_helpers.py`, `backend/tests/test_learning_material_file_batching.py`, `backend/tests/test_teaching_unit_phases_error_mapping.py`, `backend/tests/test_teaching_modular_unit_edge_error_mapping.py`, `backend/tests/test_teaching_live_student_overview_memory_repo.py`, and `backend/tests/test_routes_repo_set_repo_contract.py` to package-oriented imports while preserving dynamic alias reload coverage in the route repo contract tests, removed nine flache `routes.*` imports, and removed one local `sys.path` mutation.
  - Done in working tree: No-DB upload/storage test import cleanup batch 31 migrated `backend/tests/test_learning_upload_stub_route.py`, `backend/tests/test_learning_upload_intents_behavior.py`, `backend/tests/test_app_storage_wiring.py`, `backend/tests/test_learning_upload_intents_limits_and_keys.py`, and `backend/tests/test_teaching_upload_intents_limits_and_keys.py` to package-oriented imports, removed five flache `routes.*` imports, removed three local `sys.path` mutations, and made the upload-intent behavior tests explicitly no-DB by using route-level repo test doubles.
  - Done in working tree: Learning small API/worker test import cleanup batch 32 migrated `backend/tests/test_learning_submission_artifact_reload_removed.py`, `backend/tests/test_learning_submissions_strict_csrf.py`, `backend/tests/test_learning_submissions_idempotency_header.py`, `backend/tests/test_learning_sections_api_edges.py`, `backend/tests/test_learning_unit_sections_api.py`, `backend/tests/test_learning_modular_unlock_parity.py`, and `backend/tests/test_learning_worker_health_endpoint.py` to package-oriented app, route, repo, and test-helper imports, removed twenty flache `routes.*` imports, and removed one local `sys.path` mutation.
  - Done in working tree: Teaching sections test import cleanup batch 33 migrated `backend/tests/test_teaching_sections_api.py`, `backend/tests/test_teaching_sections_concurrency_edge.py`, `backend/tests/test_teaching_sections_reorder_api.py`, and `backend/tests/test_teaching_units_sections_guard_order.py` to package-oriented app, route, repo, and test-helper imports, removed fourteen flache `routes.*` imports, and removed four local `sys.path` mutations.
  - Done in working tree: Learning Scratch SB3 test import cleanup batch 34 migrated `backend/tests/test_learning_scratch_sb3_upload_only_api.py` to package-oriented app, learning-route, teaching-route, teaching repo, storage, and DB-helper imports, and removed two flache `routes.*` imports.
  - Done in working tree: Learning API Contract cleanup batch 35 migrated `backend/tests/test_learning_api_contract.py` to package-oriented imports and removed three flache `routes.*` imports, no additional `sys.path` mutations.
  - Done in working tree: Learning Modular/Courses + Conftest API Fixture cleanup batch 36 migrated `backend/tests/test_learning_modular_units_api_contract.py`, `backend/tests/test_learning_my_courses_api.py`, and `backend/tests/conftest.py` to package-oriented route imports, with no `sys.path`-mutation regressions.
  - Done in working tree: Import-Cleanup Batch 37 migrated `backend/tests/test_learning_submission_storage_verification.py`, `backend/tests/test_learning_worker_task_context.py`, `backend/tests/test_learning_visual_upload_only_api.py`, `backend/tests/test_supabase_storage_e2e.py`, `backend/tests/test_teaching_courses_api.py`, and `backend/tests/test_teaching_courses_update_delete_api.py` to package-oriented import patterns and removed remaining `routes.*` and `utils.*` test debts plus four `sys.path` mutations.
  - Done in working tree: `docs/harness/IMPORT_BOUNDARY_BASELINE.json` now pins `flat_routes_imports` at 165 and `sys_path_mutations` at 33; `backend_web_routes_imports` is reduced to 0.
  - Done in working tree: RED verification failed before the migration with `flat_routes_imports` current 353 over baseline 348 and `sys_path_mutations` current 108 over baseline 105; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 2 failed before the migration with `flat_routes_imports` current 348 over baseline 344 and `sys_path_mutations` current 105 over baseline 102; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 3 failed before the migration with `flat_routes_imports` current 344 over baseline 343 and `sys_path_mutations` current 102 over baseline 99; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 4 failed before the migration with `sys_path_mutations` current 99 over baseline 96; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 5 failed before the migration with `sys_path_mutations` current 96 over baseline 92; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 6 failed before the migration with `sys_path_mutations` current 92 over baseline 89; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 7 failed before the migration with `sys_path_mutations` current 89 over baseline 86; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 8 failed before the migration with `flat_routes_imports` current 343 over baseline 339 and `sys_path_mutations` current 86 over baseline 82; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 9 failed before the migration with `flat_routes_imports` current 339 over baseline 336 and `sys_path_mutations` current 82 over baseline 79; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 10 failed before the migration with `sys_path_mutations` current 79 over baseline 75; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 11 failed before the migration with `sys_path_mutations` current 75 over baseline 71; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 12 failed before the migration with `flat_routes_imports` current 336 over baseline 335 and `sys_path_mutations` current 71 over baseline 68; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 13 failed before the migration with `sys_path_mutations` current 68 over baseline 63; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 14 failed before the migration with `sys_path_mutations` current 63 over baseline 61; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 15 failed before the migration with `sys_path_mutations` current 61 over baseline 58; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 16 failed before the migration with `flat_routes_imports` current 335 over baseline 332 and `sys_path_mutations` current 58 over baseline 56; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 17 failed before the migration with `flat_routes_imports` current 332 over baseline 328; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 18 failed before the migration with `flat_routes_imports` current 328 over baseline 324; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 19 failed before the migration with `sys_path_mutations` current 56 over baseline 51; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 20 failed before the migration with `flat_routes_imports` current 324 over baseline 317 and `sys_path_mutations` current 51 over baseline 50; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 21 failed before the migration with `flat_routes_imports` current 317 over baseline 315; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 22 failed before the migration with `flat_routes_imports` current 315 over baseline 309; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 23 failed before the migration with `flat_routes_imports` current 309 over baseline 307; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 24 failed before the migration with `flat_routes_imports` current 307 over baseline 302 and `backend_web_routes_imports` current 22 over baseline 17; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 25 failed before the migration with `flat_routes_imports` current 302 over baseline 291 and `backend_web_routes_imports` current 17 over baseline 6; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 26 failed before the migration with `backend_web_routes_imports` current 6 over baseline 3; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 27 failed before the migration with `flat_routes_imports` current 291 over baseline 289 and `backend_web_routes_imports` current 3 over baseline 0; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 28 failed before the migration with `flat_routes_imports` current 289 over baseline 286 and `sys_path_mutations` current 50 over baseline 49; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 29 failed before the migration with `flat_routes_imports` current 286 over baseline 285 and `sys_path_mutations` current 49 over baseline 47; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 30 failed before the migration with `flat_routes_imports` current 285 over baseline 276 and `sys_path_mutations` current 47 over baseline 46; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 31 failed before the full migration with `flat_routes_imports` current 275 over baseline 271 and `sys_path_mutations` current 45 over baseline 43; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 32 failed before completing the migration with `flat_routes_imports` current 261 over baseline 251; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 33 failed before the migration with `flat_routes_imports` current 251 over baseline 237 and `sys_path_mutations` current 42 over baseline 38; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 34 failed before the migration with `flat_routes_imports` current 237 over baseline 235; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 35 failed before the migration because `flat_routes_imports` and `sys_path_mutations` remained above the target baseline of 224/36; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: RED verification for batch 36 failed before the migration because `flat_routes_imports` and `sys_path_mutations` remained above the target baseline of 191/36; after migration `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` reports `import-boundary-scan-ok`.
  - Done in working tree: focused verification for batch 37 reports 3 passed and 26 skipped for migrated files.
  - Done in working tree: Import-Cleanup Batch 38 migrated `backend/tests/test_teaching_live_unit_summary_api.py`, `backend/tests/test_teaching_live_detail_api.py`, `backend/tests/test_teaching_materials_files_api.py`, and `backend/tests/test_teaching_units_modules_api.py` to package-oriented route/module and bounded-context imports.
  - Done in working tree: `docs/harness/IMPORT_BOUNDARY_BASELINE.json` now pins `flat_routes_imports` at 73 and `sys_path_mutations` at 27; `backend_web_routes_imports` is still 0.
  - Done in working tree: focused verification for the migrated files reports 13 tests passed and 2 skipped, and `make verify` is green with 1898 backend tests passed/35 skipped, Svelte check 0 errors/0 warnings, 282 frontend Vitest tests passed, and 21 H5P Node tests passed.
  - Done in working tree: focused verification for batch 38 reports 7 passed and 58 skipped for migrated files.
  - Done in working tree: Import-Cleanup Batch 39 migrated `backend/tests/test_teaching_live_detail_relation_guard.py`, `backend/tests/test_teaching_live_student_overview_api.py`, `backend/tests/test_teaching_live_unit_delta_api.py`, `backend/tests/test_teaching_live_unit_summary_legacy_email_fallback.py`, `backend/tests/test_teaching_live_unit_summary_names_humanized.py`, `backend/tests/test_teaching_materials_markdown_api.py`, and `backend/tests/test_teaching_members_pagination_contract.py` to package-oriented app/route/repo/test-helper imports; updated baseline counts accordingly.
- Done in working tree: `docs/harness/IMPORT_BOUNDARY_BASELINE.json` now pins `flat_routes_imports` at 48 and `sys_path_mutations` at 20; `backend_web_routes_imports` remains 0.
- Done in working tree: focused verification for batch 39 includes `python -m py_compile` for migrated files (passing), `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` (passing), and `.venv/bin/pytest ...` reports 5 passed and 16 skipped.
- Done in working tree: Import-Cleanup Batch 40 migrated `backend/tests/test_teaching_members_semantics.py`, `backend/tests/test_teaching_modular_unit_editor_crud_api_contract.py`, and `backend/tests/test_teaching_modular_unit_graph_api_contract.py` to package-oriented app/route/repo imports, removed remaining flat `routes.*` imports in these files, and removed `sys.path` hacks from them.
- Done in working tree: `docs/harness/IMPORT_BOUNDARY_BASELINE.json` now pins `flat_routes_imports` at 23 and `sys_path_mutations` at 17; `backend_web_routes_imports` remains 0.
- Done in working tree: focused verification for batch 40 includes `python -m py_compile` for migrated files (passing), `python -m backend.tools.import_boundary_scan --json` (23 flat routes, 17 sys_path mutations), and `.venv/bin/pytest` for the three migrated files reports 25 skipped.
- Done in working tree: Import-Cleanup Batch 41 migrated `backend/tests/test_teaching_module_sections_list_api.py`, `backend/tests/test_teaching_section_visibility_api.py`, `backend/tests/test_teaching_unit_phases_api.py`, `backend/tests/test_teaching_tasks_h5p_visual_api.py`, and `backend/tests/test_teaching_visibility_csrf.py` to package-oriented imports and removed residual flat `routes.*`/`teaching.*`/`utils.db`-style imports, and removed `sys.path` hacks from them.
- Done in working tree: `docs/harness/IMPORT_BOUNDARY_BASELINE.json` now pins `flat_routes_imports` at 0 and `sys_path_mutations` at 11; `backend_web_routes_imports` remains 0.
- Done in working tree: `docs/harness/IMPORT_INVENTORY.md` reflects the new import-boundary counts and remaining focus.
- Done in working tree: focused verification for batch 41 includes `python -m backend.tools.import_boundary_scan --json` (0 flat routes, 11 sys.path mutations), `.venv/bin/pytest -q backend/tests/test_teaching_unit_phases_api.py backend/tests/test_teaching_tasks_h5p_visual_api.py backend/tests/test_teaching_visibility_csrf.py` (15 skipped), plus full-package verification for already touched files in batch 40/41.
- Done in working tree: Import-Cleanup/Path-Cleanup Batch 42 removed remaining localized `sys_path` mutations from `backend/tests/test_auth_contract.py`, `backend/tests/test_learning_submissions_idempotency_header_validation.py`, `backend/tests/run_auth_smoke_async.py`, `backend/tests/test_teaching_course_existence_helpers_optional.py`, `backend/tests/test_teaching_courses_get_api.py`, `backend/tests/test_teaching_members_api_default_limit.py`, `backend/tests/test_teaching_units_cache_headers.py`, and `backend/tests_e2e/conftest.py`.
- Done in working tree: `docs/harness/IMPORT_BOUNDARY_BASELINE.json` now pins `flat_routes_imports` at 0 and `sys_path_mutations` at 2; `backend_web_routes_imports` remains 0.
- Done in working tree: `docs/harness/IMPORT_INVENTORY.md` updated to document the new baseline and remaining two `sys_path`-mutation exceptions.
- Done in working tree: focused verification for batch 42 includes `python -m backend.tools.import_boundary_scan --json` (`flat_routes_imports: 0`, `sys_path_mutations: 2`) and `python -m backend.tools.import_boundary_scan --baseline docs/harness/IMPORT_BOUNDARY_BASELINE.json` (`import-boundary-scan-ok`).
- Done in working tree: focused verification for batch 2 reports 7 cache-header tests passed and 1 DB-dependent test skipped.
  - Done in working tree: focused verification for batch 3 reports 7 auth/API tests passed.
  - Done in working tree: focused verification for batch 4 reports 8 auth-callback tests passed.
  - Done in working tree: focused verification for batch 5 reports 10 auth-flow tests passed.
  - Done in working tree: focused verification for batch 6 reports 8 bearer/BFF tests passed.
  - Done in working tree: focused verification for batch 7 reports 9 legacy-retirement tests passed.
  - Done in working tree: focused verification for batch 8 reports 20 app/diagnostics/concern view tests passed.
  - Done in working tree: focused verification for batch 9 reports 28 profile/live/course-context view tests passed.
  - Done in working tree: focused verification for batch 10 reports 14 auth nonce/password/register tests passed.
  - Done in working tree: focused verification for batch 11 reports 11 auth/navigation/identity tests passed.
  - Done in working tree: focused verification for batch 12 reports 66 auth DB-session/hardening/middleware tests passed.
  - Done in working tree: focused verification for batch 13 reports 5 auth registration-domain whitelist tests passed.
  - Done in working tree: focused verification for batch 14 reports 5 sidebar/security-header tests passed.
  - Done in working tree: focused verification for batch 15 reports 19 session/profile contract tests passed.
  - Done in working tree: focused verification for batch 16 reports 4 users API tests passed.
  - Done in working tree: focused verification for batch 17 reports 11 learning upload-intent/content-signature tests passed.
  - Done in working tree: focused verification for batch 18 reports 8 learning Spezialformate tests passed.
  - Done in working tree: focused verification for batch 19 reports 12 legacy Live SSR retirement tests passed.
  - Done in working tree: focused verification for batch 20 reports 7 OpenAI Health endpoint tests passed.
  - Done in working tree: focused verification for batch 21 reports 10 DB-backed Calliope Hex tests passed when run outside the sandbox against the local Supabase Postgres instance; the same tests skip inside the sandbox because `127.0.0.1:54322` is not reachable there.
  - Done in working tree: focused verification for batch 22 reports 11 DB-backed H5P access/scoring tests passed when run outside the sandbox against the local Supabase Postgres instance; inside the sandbox, the 5 non-DB checks pass and 6 DB checks skip because `127.0.0.1:54322` is not reachable there.
  - Done in working tree: focused verification for batch 23 reports 3 learning config tests passed.
  - Done in working tree: focused verification for batch 24 reports 5 internal upload proxy prod-parity tests passed.
  - Done in working tree: focused verification for batch 25 reports 13 internal upload proxy security tests passed.
  - Done in working tree: focused verification for batch 26 reports 5 learning submission route tests passed.
  - Done in working tree: focused verification for batch 27 reports 4 learning PDF/upload proxy fallback tests passed, including the previously failing order `test_pdf_submission_does_not_trigger_processing_in_prod` before `test_upload_proxy_flow`.
  - Done in working tree: focused verification for batch 28 reports 3 learning lazy storage wiring tests passed.
  - Done in working tree: focused verification for batch 29 reports 7 small Teaching/Learning API tests passed.
  - Done in working tree: focused verification for batch 30 reports 30 no-DB helper/fallback tests passed.
  - Done in working tree: focused verification for batch 31 reports 19 no-DB upload/storage tests passed.
  - Done in working tree: focused verification for batch 32 reports 10 small Learning API/worker tests passed and 13 DB-dependent tests skipped in the sandbox.
  - Done in working tree: focused verification for batch 33 reports 1 Teaching sections test passed and 15 DB-dependent tests skipped in the sandbox.
  - Done in working tree: focused verification for batch 34 reports 7 DB-dependent Scratch SB3 tests skipped in the sandbox.
  - Done in working tree: focused verification for batch 35 reports 8 tests passed and 57 skipped for `backend/tests/test_learning_api_contract.py`, and import-boundary checks are still `import-boundary-scan-ok`.
  - Done in working tree: focused verification for batch 36 reports 5 tests passed and 19 skipped for `backend/tests/test_learning_modular_units_api_contract.py` and `backend/tests/test_learning_my_courses_api.py`.
- Open cleanup: continue migrating older tests away from local `sys.path` blocks and legacy alias paths, then lower the `sys_path_mutations` baseline in future batches.

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
  - Done in working tree: H5P service routes are represented in the generated Route Map as H5P-service surfaces, and `make test-route-map` keeps Runtime/OpenAPI classification synchronized.

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
  - Done in working tree: PR19 moved web-adapter direct DB access into intentional shared infrastructure (`backend/web/db_cursor.py`) and the architecture-boundary baseline now reports zero web-adapter violations.

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
  - Done in working tree: removed 410 legacy paths no longer appear in the generated Runtime Route Map; no active legacy UI surface remains registered by FastAPI.
  - Done in working tree: `backend.tools.route_map_inventory` maps active runtime surfaces to concrete or pattern-based test files and regenerated `docs/harness/ROUTE_MAP.md`.
  - Done in working tree: H5P asset/runtime surfaces are classified in the Route Map with H5P-service ownership and test patterns; v1 treats the generated synchronized map as the authoritative route inventory.

#### PR 14: Extract Security Guards
- Add characterization tests for existing guard/authz flows.
- Extract reusable security guards from hotspot files.
- Preserve semantics unless already decided security fixes require deliberate behavior changes.
- Acceptance:
  - Done in working tree: `backend/web/security/guards.py` centralizes reusable role checks.
  - Done in working tree: `app.py`, `users.py`, and `operations.py` use shared role guards instead of local role-check duplicates.
  - Done in working tree: `backend/tests/test_web_security_guards_contract.py` characterizes the shared role guard behavior.
  - Done in working tree: reusable role and teaching guards are centralized for the v1 boundary, and architecture/import gates prevent new guard duplication from becoming silent debt.

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
  - Done in working tree: `/` and `/about` are no longer registered as FastAPI product shell pages; authenticated direct backend access now returns 404, while `/health` remains the basic runtime route.
  - Done in working tree: larger FastAPI route modules are split where required for v1, and remaining hotspots are governed by `docs/harness/HOTSPOTS.md`, `docs/harness/QUALITY_SCORECARD.md`, import gates, architecture gates, and zero-open `TECH_DEBT.md`.

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
  - Done in working tree: `backend/tests/test_routes_repo_set_repo_contract.py` now validates endpoint-level repo-aware guard wiring by calling `teaching_guards._guard_unit_author()` with `repo_provider=endpoint.__globals__["_get_repo"]` directly, removing dependence on temporary route-local wrappers.
  - Done in working tree: `backend/web/routes/teaching_authoring.py` now owns module-backed authoring section resolution and signature-compatible module-section lookup; `backend/web/routes/teaching_h5p.py` no longer imports `backend.web.routes.teaching` or calls any `teaching._...` helper.
  - Done in working tree: the largest route hotspot shrank measurably from the prior 7569-line Teaching router to 6835 lines, with the extracted H5P router at 553 lines, the shared helper module at 71 lines, the serializer module at 89 lines, the task-service provider at 32 lines, the guard module at 81 lines, and the authoring boundary at 123 lines.
  - Done in working tree: focused verification reports 25 H5P/authoring/guard tests passed, 4 modular API tests passed with 31 DB-dependent skips, 15 repo-reload/guard-regression tests passed, import-boundary and architecture-boundary scans ok, OpenAPI contract ok, and `make test-route-map` reports `route-map-inventory-ok`.
  - Done in working tree: `make verify` is green with 1897 backend tests passed/35 skipped, Svelte check 0 errors/0 warnings, 282 frontend Vitest tests passed, and 21 H5P Node tests passed.
  - Done in working tree: the temporary Teaching route-local guard and authoring adapters were removed from `backend/web/routes/teaching.py`.
  - Done in working tree: extracted live dashboard read endpoints from `backend/web/routes/teaching.py` into dedicated `backend/web/routes/teaching_live.py` and wired it in `backend/web/main_router_wiring.py`:
    - `/api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary`
    - `/api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta`
    - `/api/teaching/courses/{course_id}/students/{student_sub:path}/submissions/overview`
    - `/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub:path}/submissions/latest`
    - `/api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub:path}/submissions/latest/file`
  - Done in working tree: `backend/tests/test_teaching_live_route_split_contract.py` verifies ownership by module, path registration, and delegation of these endpoints through the new live router.
  - Done in working tree: focused verification for PR-17 route split passed with `2` new contract checks and the existing live route tests remaining in DB-skip state (`19 skipped`) when run without DB.
  - Done in working tree: extracted course-module endpoints (`/api/teaching/courses/{course_id}/modules*`) into dedicated `backend/web/routes/teaching_course_modules.py` and wired it in `backend/web/main_router_wiring.py`.
  - Done in working tree: `backend/tests/test_teaching_course_modules_route_split_contract.py` asserts ownership by module, path registration, and delegation for course-module endpoints through the new router.
  - Done in working tree: extracted course-members endpoints (`/api/teaching/courses/{course_id}/members*`) into dedicated `backend/web/routes/teaching_course_members.py` and wired it in `backend/web/main_router_wiring.py`.
  - Done in working tree: `backend/tests/test_teaching_course_members_route_split_contract.py` asserts ownership by module, path registration, and delegation for course-members endpoints.
  - Done in working tree: extracted unit-section endpoints (`/api/teaching/units/{unit_id}/sections*`) into dedicated `backend/web/routes/teaching_unit_sections.py` and wired it in `backend/web/main_router_wiring.py`.
  - Done in working tree: `backend/tests/test_teaching_unit_sections_route_split_contract.py` asserts ownership by module, path registration, and delegation for unit-section endpoints.
  - Done in working tree: extracted unit-task endpoints (`/api/teaching/units/{unit_id}/.../tasks*`) into dedicated `backend/web/routes/teaching_unit_tasks.py` and wired it in `backend/web/main_router_wiring.py`.
  - Done in working tree: `backend/tests/test_teaching_unit_tasks_route_split_contract.py` asserts ownership by module, path registration, and delegation for unit-task endpoints.
  - Done in working tree: extracted unit-material endpoints (`/api/teaching/units/{unit_id}/sections/{section_id}/materials*` and module-material aliases) into dedicated `backend/web/routes/teaching_unit_materials.py` and wired it in `backend/web/main_router_wiring.py`.
  - Done in working tree: `backend/tests/test_teaching_unit_materials_route_split_contract.py` asserts ownership by module, path registration, and real handler ownership without delegation for unit-material endpoints.
  - Done in working tree: extracted unit phase and module endpoints (`/api/teaching/units/{unit_id}/phases*`, `/api/teaching/units/{unit_id}/modules*`) into dedicated `backend/web/routes/teaching_unit_modules.py` and wired it in `backend/web/main_router_wiring.py`.
  - Done in working tree: `backend/tests/test_teaching_unit_modules_route_split_contract.py` asserts ownership by module, path registration, and real handler ownership without delegation for unit phase/module endpoints.
  - Done in working tree: extracted course CRUD endpoints (`/api/teaching/courses*`) into dedicated `backend/web/routes/teaching_courses.py` and wired it in `backend/web/main_router_wiring.py`.
  - Done in working tree: `backend/tests/test_teaching_courses_route_split_contract.py` asserts ownership by module, path registration, and delegation for course CRUD endpoints.
  - Done in working tree: extracted unit CRUD endpoints (`/api/teaching/units*`) into dedicated `backend/web/routes/teaching_units.py` and wired it in `backend/web/main_router_wiring.py`.
  - Done in working tree: `backend/tests/test_teaching_units_route_split_contract.py` asserts ownership by module, path registration, and delegation for unit CRUD endpoints.
  - Done in working tree: unused `backend.web.routes.teaching.teaching_router` has been removed from app wiring (`backend/web/main_router_wiring.py`) because all `/api/teaching` routes are now explicitly registered in split routers.
  - Done in working tree: removed the remaining legacy `routes.teaching` module alias compatibility handling from `backend/web/routes/teaching.py`; route-storage/reset tests now use `backend.web.routes.teaching` consistently.
  - Done in working tree: course-owner guard ownership and invocation moved out of `backend/web/routes/teaching.py`; all teaching and app call-sites now use `backend/web/routes/teaching_guards._guard_course_owner`, and guard monkeypatch points in affected tests were moved accordingly.
  - Done in working tree: reload-heavy route tests are stable again after `backend/web/app_composition.py` started tracking live app shells and the Learning/Teaching route setters synchronize repo/storage state across those shells; the backend failfast suite reports 1917 passed and 35 skipped tests.
  - Done in working tree: all `/api/teaching` routes are registered through explicit split routers, and legacy route/compatibility aliases that were no longer needed were removed.

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
  - Done in working tree: live-dashboard response shaping for summary and delta moved to `backend/web/routes/teaching_serialization.py` via `_build_live_summary_rows` and `_build_live_delta_cells`, keeping `backend/web/routes/teaching.py` thinner and focused on guards + repo access.

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
- Done in working tree: introduced `backend/web/db_cursor.py` with a shared `open_repo_cursor()` helper and migrated representative teaching/app/material routes from direct `psycopg.connect` blocks to this boundary:
  - `backend/web/routes/teaching.py` submission/latest and submission/latest/file query paths
  - `backend/web/routes/app.py::_list_submission_pairs_for_students`
  - `backend/web/material_file_access.py::_load_student..._metadata_batch`
- Done in working tree: updated `docs/harness/ARCHITECTURE_BOUNDARY_BASELINE.json` target for web direct DB connections from 9 to 1, keeping `backend/web/db_cursor.py` as the only permitted web-adapter connection site.
- Done in working tree: fixed remaining boundary scan regressions by replacing two remaining test-side static imports of `backend.web.routes.*` with dynamic `importlib` loading, keeping `backend_web_routes_imports` at the target baseline `0`.
- Done in working tree: completed the PR-19 teacher-dashboard live-analytics sweep:
  - `backend/web/routes/teaching.py` live summary/delta endpoints now delegate repository reads to dedicated `repo_db` read-model methods for helper rows, latest submission state, changed timestamps, and fallback paths.
  - `backend/web/routes/app.py::_list_submission_pairs_for_students` now uses `repo_db.list_submission_pairs_for_students` (with legacy fallback to safe default on repository mismatch).

#### PR 20: Frontend and H5P Hotspot Split
- Add hotspot baselines for large Svelte pages/components, large CSS files, and `h5p-service/server.mjs`.
- Split only after behavior or component tests cover the selected area.
- For H5P, separate security/auth/session concerns, route handlers, storage integration, and response helpers without changing public H5P behavior.
- For frontend pages, extract state/data-loading/view components according to existing SvelteKit patterns.
- Acceptance:
  - H5P and frontend hotspots stop growing and at least one high-value hotspot shrinks with tests.
  - `npm run check` and relevant H5P/frontend tests remain green.
- Done in working tree: `docs/harness/HOTSPOTS.md` now records concrete LOC baselines for backend, frontend, CSS, and H5P hotspots.
- Done in working tree: extracted H5P Finished-Data forwarding context helpers from `h5p-service/server.mjs` into `h5p-service/lib/finished_submission_context.mjs`, covering Origin/Referer forwarding metadata and Learning-compatible idempotency keys.
- Done in working tree: extracted signed H5P review-token parsing from `h5p-service/server.mjs` into `h5p-service/lib/review_tokens.mjs`, keeping token signature, expiry, and required-claim validation covered outside the server hotspot.
- Done in working tree: extracted H5P CSP/security-header policy from `h5p-service/server.mjs` into `h5p-service/lib/security_headers.mjs`, keeping default CSP, debug-page CSP, and response-header overrides covered outside the server hotspot.
- Done in working tree: extracted H5P response model helpers from `h5p-service/server.mjs` into `h5p-service/lib/model_helpers.mjs`, keeping Gustav theme-style ordering and `div` embed-type preference covered outside the server hotspot.
- Done in working tree: extracted H5P cookie parsing from `h5p-service/server.mjs` into the existing `h5p-service/lib/cookies.mjs`, keeping session-cookie decoding and malformed-value fallback behavior covered outside the server hotspot.
- Done in working tree: extracted H5P JSON/HTML response sending helpers from `h5p-service/server.mjs` into `h5p-service/lib/response_helpers.mjs`, keeping Security-Header defaults, private cache headers, and explicit header overrides covered outside the server hotspot.
- Done in working tree: extracted H5P storage directory layout, storage readiness probing, and Content-Disposition filename sanitizing from `h5p-service/server.mjs` into `h5p-service/lib/storage_helpers.mjs`.
- Done in working tree: extracted H5P auth and H5P content-access forwarding from `h5p-service/server.mjs` into `h5p-service/lib/auth_forwarding.mjs`, keeping backend-first session validation, SvelteKit-BFF fallback, cookie minimization, URL encoding, and fail-closed access checks covered outside the server hotspot.
- Done in working tree: `h5p-service/test/finished_submission_context.test.mjs`, `h5p-service/test/review_tokens.test.mjs`, `h5p-service/test/security_headers.test.mjs`, `h5p-service/test/model_helpers.test.mjs`, `h5p-service/test/cookies.test.mjs`, `h5p-service/test/response_helpers.test.mjs`, `h5p-service/test/storage_helpers.test.mjs`, and `h5p-service/test/auth_forwarding.test.mjs` protect the extracted H5P forwarding, review-token, security-header, model-helper, cookie, response-helper, storage-helper, and auth-forwarding behavior; `npm test` in `h5p-service` reports 14 passing Node test files.
- Done in working tree: `h5p-service/server.mjs` shrank from 1942 to 1633 LOC across the first eight PR20 H5P slices.
- Done in working tree: extracted Learning-Unit viewport bucket, workspace chrome defaults, layout preference defaults, layout normalization, submission focus normalization, and modular/linear workspace-state normalization from `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte` into `frontend/src/lib/learning-unit/layout.ts`.
- Done in working tree: `frontend/src/lib/learning-unit/layout.test.ts` protects compact/medium/wide/xwide breakpoints, workspace width clamping, modular/linear workspace defaults, default layout preferences, legacy `singlePaneWidth` migration behavior, pane focus normalization, openable module-tab filtering, and default TOC behavior.
- Done in working tree: `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte` shrank from 1846 to 1644 LOC; targeted verification reports Svelte check 0 errors/0 warnings and 41 focused Learning workspace tests passed.
- Done in working tree: v1 hotspot work shrank both H5P and Learning workspace hotspots with focused tests; ongoing hotspot control is now handled by the active Hotspots document, quality scorecard, and zero-open Tech-Debt policy.

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
- Done in working tree: added `backend/tools/quality_scorecard.py` as a monthly report generator.
- Done in working tree: added `make quality-scorecard` target and documented it in `docs/harness/QUALITY_GATES.md` and `docs/harness/INDEX.md`.
- Done in working tree: generated baseline artifacts `docs/harness/QUALITY_SCORECARD.md` and `docs/harness/QUALITY_SCORECARD_HISTORY.json`.
- Done in working tree: `make quality-scorecard` runs `docker-image-smoke` by default and records pass/fail status in `docs/harness/QUALITY_SCORECARD.md` and `docs/harness/QUALITY_SCORECARD_HISTORY.json`.

### Closeout v1.1: Repo wirklich sauber und wartbar machen
Dieser Abschnitt ist der verbindliche Abschlussauftrag für den Befehl `/goal Setz bitte den Plan docs/plan/2026-05-02-harness-engineering-refactor-plan.md vollständig um.` Er soll verhindern, dass der Harness-Refactor nur formal grün ist, während die größten Wartbarkeitsrisiken als Monolithen weiterbestehen.

Der Auftrag ist kein Feature-Stream. Während Closeout v1.1 werden keine neuen Produktfeatures gebaut, keine API-Semantik verändert und keine großen Rewrite-Aktionen gestartet. Jede Änderung beginnt testgetrieben mit einem Charakterisierungs-, Contract- oder gezielten Regressionstest. Eine Extraktion gilt nur als erledigt, wenn produktive Logik aus dem Hotspot in ein fokussiertes Modul mit klarer Verantwortung verschoben wurde. Reine Wrapper-Router, die nur an den alten Hotspot delegieren, zählen als Übergang, aber nicht als Abschluss.

#### C1: Teaching-Web-Adapter wirklich modularisieren
- Problem: `backend/web/routes/teaching.py` ist mit mehr als 6000 Zeilen weiterhin der größte echte Quellcode-Hotspot. Der bisherige Split hat die Route-Registrierung verbessert, aber mehrere neue Router delegieren noch direkt zurück in `teaching.py`.
- Ziel: `teaching.py` wird von einem Sammelpunkt für API-Routen, In-Memory-Repo, Payload-Modelle, Storage-Helfer, Live-Dashboard, Materialien, Aufgaben, Kursmodule und Unit-Graph-Logik zu einer kleinen Fassade oder einem schrittweise abbaubaren Kompatibilitätsmodul.
- Vorgehen:
  - Zuerst die vorhandenen route-split-contract-Tests lesen und je Teilbereich einen fehlenden Charakterisierungstest ergänzen, bevor Logik verschoben wird.
  - Course-, Unit-, Section-, Material-, Task-, Module- und Live-Flächen nacheinander bearbeiten; nie mehrere fachliche Flächen in einem Commit mischen.
  - Pydantic-Payload-Modelle und reine Validierungshelfer in fachlich passende Module verschieben, damit Router-Module nicht aus `teaching.py` importieren müssen.
  - Repo-Provider, Storage-Adapter und Guard-Funktionen über explizite kleine Provider-Module führen, nicht über mutable Modulglobals in `teaching.py`.
  - Bestehende direkte Delegationsrouter wie `teaching_courses.py`, `teaching_unit_materials.py` und `teaching_live.py` so umbauen, dass sie die jeweilige Logik selbst oder über fokussierte Service-/Adaptermodule besitzen.
- Akzeptanz:
  - `backend/web/routes/teaching.py` ist deutlich kleiner und enthält keine fachlich gemischten Route-Handler-Blöcke mehr für alle Teaching-Flächen.
  - Neue oder angepasste Tests belegen, dass die ausgelagerten Module die bestehenden Response-Shapes, Cache-Header, Authz-Fehler und Storage-Fehlerpfade unverändert halten.
  - `make test-route-map`, `make test-api-contract-baseline`, `make test-architecture-boundaries` und die betroffenen Teaching-Tests sind grün.
- Done in working tree: `backend/web/routes/teaching_payloads.py` übernimmt die Pydantic-Request-Payloads für Courses, Units, Modules, Sections, Materials, Tasks und Course Members; `backend/web/routes/teaching.py` importiert diese Namen zurück, damit bestehende `teaching_routes.*Payload`-Aufrufer kompatibel bleiben.
- Done in working tree: Ein Contract-Test schützt, dass Payload-Modelle nicht wieder in den Teaching-Hotspot zurückwandern; `backend/web/routes/teaching.py` ist durch diesen Schnitt auf 5790 LOC gesunken.
- Done in working tree: `backend/web/routes/teaching_validation.py` übernimmt reine UUID-, Integer- und Pagination-Helfer; ein Contract-Test schützt die Kompatibilitätsaliase in `teaching.py`. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 5756 LOC.
- Done in working tree: `backend/web/routes/teaching_storage_cleanup.py` übernimmt die Unit-delete-Storage-Ermittlung, das Page-Key-Metadaten-Parsing und die fail-closed Storage-Löschung; `backend/web/routes/teaching.py` behält nur kleine Kompatibilitätswrapper für bestehende Tests und Monkeypatch-Punkte. Ein Contract-Test schützt, dass diese Helfer nicht wieder in den Teaching-Hotspot zurückwandern. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 5671 LOC.
- Done in working tree: `backend/web/routes/teaching_submission_files.py` übernimmt Dateinamen-Sanitizing, begrenztes Download-Fetching und den Teaching-Submission-File-Href-Builder; ein Contract-Test schützt Alias-Kompatibilität und bestehende Sanitizing-/Href-Regeln. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 5634 LOC.
- Done in working tree: Die doppelte Live-Score-Normalisierung wurde aus `backend/web/routes/teaching.py` entfernt; `backend/teaching/repo_row_mappers.py` besitzt `compute_average_score_from_analysis`, und `teaching.py` re-exportiert die Funktion nur noch für bestehende Tests. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 5591 LOC.
- Done in working tree: `backend/web/routes/teaching_inmemory_repo.py` übernimmt das In-Memory-Fallback-Repository inklusive Teaching-Fallback-Datenklassen; `backend/web/routes/teaching.py` behält `_Repo`, Datenklassen und `_UNSET` nur noch als Kompatibilitätsaliase für bestehende Tests und Offline-Fallbacks. Ein Contract-Test schützt Modulbesitz und Fallback-Verhalten. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 4477 LOC.
- Done in working tree: `backend/web/routes/teaching_courses.py` besitzt die Course-Handler für List/Create/Get/Patch/Delete selbst statt nur an `teaching.py` zu delegieren; `backend/web/routes/teaching_course_state.py` übernimmt den kurzlebigen Course-Deletion-Marker, der von Course-Delete und Course-Members gemeinsam genutzt wird. Der Course-Route-Split-Contract verlangt jetzt echten Handler-Besitz ohne Delegation. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 4241 LOC.
- Done in working tree: `backend/web/routes/teaching_units.py` besitzt die Unit-Handler für List/Create/Get/Patch/Delete selbst statt nur an `teaching.py` zu delegieren. Der Unit-Route-Split-Contract verlangt jetzt echten Handler-Besitz ohne Delegation; bestehende Storage-Cleanup-Monkeypatch-Punkte bleiben über dynamische Kompatibilitätsauflösung erhalten. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 4040 LOC.
- Done in working tree: `backend/web/routes/teaching_unit_sections.py` besitzt die Section-Handler für List/Create/Patch/Delete/Reorder selbst statt nur an `teaching.py` zu delegieren. Der Unit-Sections-Route-Split-Contract verlangt jetzt echten Handler-Besitz ohne Delegation. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 3864 LOC.
- Done in working tree: `backend/web/routes/teaching_unit_tasks.py` besitzt die Task-Handler für Section- und Module-Task-Authoring selbst statt nur an `teaching.py` zu delegieren; die eigentliche Task-Geschäftslogik bleibt im bestehenden `TasksService`. Der Unit-Tasks-Route-Split-Contract verlangt jetzt echten Handler-Besitz ohne Delegation. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 3566 LOC.
- Done in working tree: `backend/web/routes/teaching_course_modules.py` besitzt die Course-Module- und Module-Section-Visibility-Handler selbst statt nur an `teaching.py` zu delegieren. Der Course-Modules-Route-Split-Contract verlangt jetzt echten Handler-Besitz ohne Delegation. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 3140 LOC.
- Done in working tree: `backend/web/routes/teaching_course_members.py` besitzt die Course-Member-Handler selbst statt nur an `teaching.py` zu delegieren. Der Course-Members-Route-Split-Contract verlangt jetzt echten Handler-Besitz ohne Delegation. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 3002 LOC.
- Done in working tree: `backend/web/routes/teaching_unit_modules.py` besitzt die Unit-Phase-, Unit-Module-, Unit-Module-Edge-, Content-Target- und Unit-Module-Reorder-Handler selbst statt nur an `teaching.py` zu delegieren. Der Unit-Modules-Route-Split-Contract verlangt jetzt echten Handler-Besitz ohne Delegation; der Test-Reset für Teaching-Route-Globals stellt Helper aus dem jeweiligen Endpoint-Modul wieder her, damit Split-Router ihre eigenen dynamischen Repo-Provider behalten. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 2424 LOC.
- Done in working tree: `backend/web/routes/teaching_unit_materials.py` besitzt die Section-Material-, Module-Material-, Upload-Intent-, Finalize-, Download-URL- und Reorder-Handler selbst statt nur an `teaching.py` zu delegieren. Der Unit-Materials-Route-Split-Contract verlangt jetzt echten Handler-Besitz ohne Delegation; Storage-Adapter und MaterialsService bleiben über dynamische Teaching-Fassade-Auflösung kompatibel mit bestehenden Overrides. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 1815 LOC.
- Done in working tree: `backend/web/routes/teaching_live.py` besitzt die Live-Summary-, Live-Delta-, Student-Overview-, Latest-Submission-Detail- und Teaching-Submission-File-Handler selbst statt nur an `teaching.py` zu delegieren. Der Teaching-Live-Route-Split-Contract verlangt jetzt echten Handler-Besitz ohne Delegation; gemeinsame Live-Read-Model- und Download-Helfer bleiben zunächst explizit aus der Teaching-Fassade importiert und gehören in C2/C13 weiter reduziert. `backend/web/routes/teaching.py` liegt nach diesem Schnitt bei 782 LOC.

#### C2: Teaching-Repository nach Verantwortlichkeiten trennen
- Problem: `backend/teaching/repo_db.py` ist mit knapp 5000 Zeilen ein zweiter Teaching-Monolith. Er mischt Schreibfälle, Read-Models, Live-/Dashboard-Abfragen, Material-/Task-Zugriffe und Hilfsserialisierung.
- Ziel: Das Teaching-Repository wird in kleine Module mit stabiler öffentlicher Fassade zerlegt. Bestehende RLS- und Migrationstests bleiben maßgeblich.
- Vorgehen:
  - Vor jedem Split einen Repo-Contract- oder DB/RLS-Test identifizieren, der den betroffenen Query-Pfad schützt.
  - Live-/Dashboard-Read-Models zuerst auslagern, weil sie besonders groß und fehleranfällig sind.
  - Material-/Task-Zugriffe danach auslagern, weil sie eng mit Storage- und Teaching-Route-Splits verbunden sind.
  - Schreibfälle erst verschieben, wenn die Read-Model-Splits stabil sind.
  - Transaktions- und Cursor-Grenzen über bestehende DB-Helfer führen; keine neue direkte Route-DB-Verbindung einführen.
- Akzeptanz:
  - `backend/teaching/repo_db.py` ist eine Fassade oder klarer Aggregator statt ein Query-Sammelmodul.
  - `make test-db-security`, `make test-db-inventory` und betroffene Teaching-Repo-/Migrationstests sind grün.
- Done in working tree: `backend/teaching/repo_row_mappers.py` übernimmt reine Material-/Task-Row-Mapper und die Live-Score-Normalisierung; `backend/teaching/repo_db.py` importiert die bisherigen Unterstrich-Namen als Kompatibilitätsaliase. Ein Contract-Test schützt, dass diese DB-freie Mapping-Logik nicht wieder in den Repository-Hotspot zurückwandert. `backend/teaching/repo_db.py` liegt nach diesem Schnitt bei 4716 LOC.
- Done in working tree: `backend/teaching/repo_live_queries.py` übernimmt die Live-/Dashboard-Read-Model-Queries für Unit-Summary, Unit-Delta, Helper-Rows, Submission-State, Average-Scores, Fallback-Rows, Changed-At-Paare und Live-Cursor. `DBTeachingRepo` bleibt öffentliche Fassade und delegiert diese Methoden mit DSN + psycopg weiter. Ein Contract-Test schützt, dass die SQL-Implementierungen nicht in den Repository-Hotspot zurückwandern. `backend/teaching/repo_db.py` liegt nach diesem Schnitt bei 4463 LOC.
- Done in working tree: `backend/teaching/repo_material_queries.py` übernimmt Material-CRUD, Upload-Intent-Record, Upload-Intent-Finalize und Material-Reorder-SQL. `DBTeachingRepo` bleibt öffentliche Fassade und delegiert diese Methoden mit DSN + psycopg weiter. Ein Contract-Test schützt, dass die Material-/Upload-Intent-SQL-Implementierungen nicht in den Repository-Hotspot zurückwandern. `backend/teaching/repo_db.py` liegt nach diesem Schnitt bei 4060 LOC.
- Done in working tree: `backend/teaching/repo_task_queries.py` übernimmt Section-Task-CRUD, Task-Reorder, Course-Unit-Task-Read-Models und Latest-Submission-Aggregate. `DBTeachingRepo` bleibt öffentliche Fassade und delegiert diese Methoden mit DSN + psycopg weiter; der Modul-Sentinel akzeptiert auch die bestehende `DBTeachingRepo`-Unset-Markierung, damit partielle Updates unverändert funktionieren. Ein Contract-Test schützt, dass die Task-SQL-Implementierungen nicht in den Repository-Hotspot zurückwandern. `backend/teaching/repo_db.py` liegt nach diesem Schnitt bei 3697 LOC.
- Done in working tree: `backend/teaching/repo_unit_module_queries.py` übernimmt Unit-Phasen, Unit-Module, Graph-Edges, Modul-Reorder, k-of-n-Unlock-Updates, Delete-Clamping und den modularen Section-zu-Module-Helfer. `DBTeachingRepo` bleibt öffentliche Fassade und delegiert diese Methoden mit DSN + psycopg weiter; die Teaching-Web-Fassade exportiert die bestehenden Serializer-Aliase weiter, damit `backend/web/routes/app.py` stabil bleibt. Ein Contract-Test schützt, dass Unit-Module- und Unit-Module-Edge-SQL nicht in den Repository-Hotspot zurückwandert. `backend/teaching/repo_db.py` liegt nach diesem Schnitt bei 2630 LOC.
- Done in working tree: `backend/teaching/repo_course_module_queries.py` übernimmt Course-Module-CRUD, Course-Unit-Read-Modelle und Module-Section-Release-Queries. `DBTeachingRepo` bleibt öffentliche Fassade und delegiert diese Methoden mit DSN + psycopg weiter; Unique-Violation-Mapping, UUID-Normalisierung und Release-Zeitformatierung bleiben im neuen Query-Modul explizit erhalten. Ein Contract-Test schützt, dass Course-Module- und Module-Section-Release-SQL nicht in den Repository-Hotspot zurückwandert. `backend/teaching/repo_db.py` liegt nach diesem Schnitt bei 2237 LOC.
- Done in working tree: `backend/teaching/repo_section_queries.py` übernimmt Unit-Section-Existenz, Liste, Create, Rename, Delete und Reorder. `DBTeachingRepo` bleibt öffentliche Fassade und delegiert diese Methoden mit DSN + psycopg weiter; modulare Section-Erstellung nutzt weiter den Unit-Module-Helfer für den 1:1-Graph-Knoten. Ein Contract-Test schützt, dass Unit-Section-SQL nicht in den Repository-Hotspot zurückwandert. `backend/teaching/repo_db.py` liegt nach diesem Schnitt bei 1932 LOC.
- Done in working tree: `backend/teaching/repo_unit_queries.py` übernimmt Unit-Liste, Unit-Create, partielles Unit-Update, Get/Delete und Unit-Existenzchecks. `DBTeachingRepo` bleibt öffentliche Fassade und delegiert diese Methoden mit DSN + psycopg weiter; der Modul-Sentinel akzeptiert weiter die bestehende `DBTeachingRepo`-Unset-Markierung, damit partielle Updates unverändert funktionieren. Ein Contract-Test schützt, dass Unit-SQL nicht in den Repository-Hotspot zurückwandert. `backend/teaching/repo_db.py` liegt nach diesem Schnitt bei 1740 LOC.
- Done in working tree: `backend/teaching/repo_member_queries.py` übernimmt studentische Course-Listen, Course-Membership-Roster, Add/Remove, Student-Course-Checks und den Service-DSN-Delete-Fallback. `DBTeachingRepo` bleibt öffentliche Fassade und delegiert diese Methoden mit DSN + psycopg weiter; der test/dev-only Service-DSN-Fallback wird als explizite Abhängigkeit übergeben. Ein Contract-Test schützt, dass Course-Membership-SQL nicht in den Repository-Hotspot zurückwandert. `backend/teaching/repo_db.py` liegt nach diesem Schnitt bei 1604 LOC.
- Done in working tree: `backend/teaching/repo_concern_box_queries.py` übernimmt Concern-Box-Create, Teacher-Listing, Archive und Restore. `DBTeachingRepo` bleibt öffentliche Fassade und delegiert diese Methoden mit DSN + psycopg weiter. Ein Contract-Test schützt, dass Concern-Box-SQL nicht in den Repository-Hotspot zurückwandert. `backend/teaching/repo_db.py` liegt nach diesem Schnitt bei 1540 LOC.
- Done in working tree: `backend/teaching/repo_ai_usage_queries.py` übernimmt das owner-scoped AI-Usage-Read-Model mit Zeitraum-, Unit-, Task- und Student-Filterung. `DBTeachingRepo` bleibt öffentliche Fassade und delegiert diese Methode mit DSN + psycopg weiter. Ein Contract-Test schützt, dass AI-Usage-SQL nicht in den Repository-Hotspot zurückwandert. `backend/teaching/repo_db.py` liegt nach diesem Schnitt bei 1487 LOC.

#### C3: Learning-Web-Adapter splitten
- Problem: `backend/web/routes/learning.py` ist mit knapp 3000 Zeilen ein großer Adapter, der Course/Unit-Reads, Upload-Intent, Upload-Proxy, Storage-Verifikation, Submissions und Material-Dateien bündelt.
- Ziel: Learning-Routen werden nach fachlichen Oberflächen getrennt: Course/Unit-Read, Submission, Upload/Storage, Material/File und interne Upload-Helfer.
- Vorgehen:
  - Upload-/Storage-Logik zuerst bearbeiten, weil sie sicherheitskritisch ist und bereits viele Boundary-Tests hat.
  - Submission-Create/Finalize/List danach trennen, weil dort Authz, CSRF, Idempotency und Worker-Anbindung zusammenlaufen.
  - Material-/Datei-Download-Helfer in ein fokussiertes Modul verschieben und Download-Disposition, Cache-Header und Größenlimits testen.
- Akzeptanz:
  - `backend/web/routes/learning.py` enthält keine gemischten Upload-, Submission- und Material-Datei-Helfer mehr.
  - Upload-, Submission-, H5P-Access-, Material-File- und CSRF-Tests bleiben grün.
- Done in working tree: `backend/web/routes/learning_downloads.py` übernimmt den SSRF-geschützten, größenbegrenzten Download-Fetcher inklusive Public-to-Internal-Supabase-Rewrite; `backend/web/routes/learning.py` behält nur den alten privaten Wrapper für bestehende Monkeypatch-Punkte. Die bestehenden Rewrite-/SSRF-Tests schützen diesen Schnitt. `backend/web/routes/learning.py` liegt nach diesem Schnitt bei 2764 LOC.
- Done in working tree: `backend/web/routes/learning_upload_proxy.py` übernimmt Presign-Header-Encoding/-Decoding, Header-Allowlisting, URL-Part-Normalisierung und den patchbaren Upstream-PUT-Forwarder für den Learning-Upload-Proxy; `backend/web/routes/learning.py` behält Endpoint, Auth, CSRF, Body-Limit und kleine Kompatibilitätswrapper. Die bestehenden Upload-Proxy-Security- und Prod-Parity-Tests schützen diesen Schnitt. `backend/web/routes/learning.py` liegt nach diesem Schnitt bei 2690 LOC.
- Done in working tree: `backend/web/routes/learning_upload_config.py` übernimmt Upload-Intent-TTL-, Dev-Stub-, Upload-Proxy- und Proxy-Timeout-Env-Parser; bestehende Helper- und Upload-Intent-Tests schützen Clamp-, Boolean- und Response-Regeln. `backend/web/routes/learning.py` liegt nach diesem Schnitt bei 2670 LOC.
- Done in working tree: `backend/web/routes/learning_material_files.py` übernimmt learner-seitige Material-File-URL-Anreicherung, sichtbarkeitsgeprüfte Batch-Metadatenauflösung und modulare Material-Datei-Helfer. `backend/web/routes/learning.py` behält nur Kompatibilitätsaliase für bestehende Tests und Aufrufer. Ein Contract-Test schützt, dass diese Helfer nicht wieder in den Learning-Hotspot zurückwandern. `backend/web/routes/learning.py` liegt nach diesem Schnitt bei 2533 LOC.
- Done in working tree: `backend/web/routes/learning_material_file_routes.py` besitzt die kanonische Material-File-Download-Route und die legacy Section-Alias-Route selbst. Das Modul löst Repo-, Student-Guard-, Download- und Storage-Abhängigkeiten dynamisch über die Learning-Fassade auf, damit bestehende Monkeypatch- und Runtime-Overrides kompatibel bleiben. Ein Contract-Test schützt, dass diese Handler nicht wieder in den Learning-Hotspot zurückwandern. `backend/web/routes/learning.py` liegt nach diesem Schnitt bei 2420 LOC.
- Done in working tree: `backend/web/routes/learning_upload_intents.py` besitzt den studentischen Upload-Intent-Endpoint inklusive CSRF, Taskkind-MIME-Policy, Storage-Key-Erzeugung, Lazy-Storage-Wiring und optionaler Upload-Proxy-URL-Erzeugung. Das Modul löst Repo-, Config- und Storage-Abhängigkeiten dynamisch über die Learning-Fassade auf, damit bestehende Monkeypatch- und Runtime-Overrides kompatibel bleiben. Ein Contract-Test schützt, dass der Handler nicht wieder in den Learning-Hotspot zurückwandert. `backend/web/routes/learning.py` liegt nach diesem Schnitt bei 2142 LOC.
- Done in working tree: `backend/web/routes/learning_internal_upload_routes.py` besitzt die internen Upload-Stub- und Upload-Proxy-Routen inklusive Same-Origin-Prüfung, URL-Host-Allowlisting, Upload-Limit und Proxy-Telemetrie. Das Modul löst Forwarder, Telemetrie, Config und Helper dynamisch über die Learning-Fassade auf, damit bestehende Monkeypatch- und Runtime-Overrides kompatibel bleiben. Ein Contract-Test schützt, dass diese Handler nicht wieder in den Learning-Hotspot zurückwandern. `backend/web/routes/learning.py` liegt nach diesem Schnitt bei 1942 LOC.
- Done in working tree: `backend/web/routes/learning_storage_validation.py` übernimmt Storage-Integrity-Prüfung, lokale Validierungsbytes, begrenzten Presign-Download und Storage-Bytes-Laden für Submission-Validierung. `backend/web/routes/learning.py` behält Kompatibilitätsaliase für bestehende Tests und Monkeypatch-Punkte. Ein Contract-Test schützt, dass diese Helfer nicht wieder in den Learning-Hotspot zurückwandern. `backend/web/routes/learning.py` liegt nach diesem Schnitt bei 1850 LOC.

#### C4: Browser-BFF- und App-Routen trennen
- Problem: `backend/web/routes/app.py` ist mit knapp 2500 Zeilen ein großer Browser-BFF-Hotspot.
- Ziel: Session-Bootstrap, Session-Sync, Profil, View-Modelle und BFF-interne Hilfsfunktionen liegen in getrennten Modulen mit expliziten Provider-Abhängigkeiten.
- Vorgehen:
  - Session-Endpunkte zuerst isolieren, weil sie sicherheitsrelevant für Cookies, SameSite, Secure, HttpOnly und Cache-Control sind.
  - Profil-Endpunkte danach isolieren, inklusive OIDC-/CLI-Provider-Abhängigkeiten.
  - View-Model-Builder zuletzt trennen, damit reine Datenformung ohne FastAPI-Abhängigkeit testbar wird.
- Akzeptanz:
  - `backend/web/routes/app.py` ist nicht mehr Sammelpunkt für Session, Profil und View-Modelle.
  - Session-, Profil-, BFF-, Auth- und Cache-Header-Tests bleiben grün.
- Done in working tree: `backend/web/routes/app_session_helpers.py` übernimmt Runtime-/Session-Store-Auflösung, private App-Header, BFF-Shared-Secret-Prüfung und kleine Session-/User-Payload-Builder; `backend/web/routes/app.py` behält Kompatibilitätsaliase und die Route-Handler. Ein Contract-Test schützt, dass diese Session-Helfer nicht wieder in den App-Hotspot zurückwandern. `backend/web/routes/app.py` liegt nach diesem Schnitt bei 2412 LOC.
- Done in working tree: `backend/web/routes/app_profile_helpers.py` übernimmt reine Profil-Claims-, Namens-, Lock-Timestamp- und Identity-Attribute-Normalisierung; `backend/web/routes/app.py` behält die Keycloak-Admin-Schreibfunktionen und Kompatibilitätsaliase. Ein Contract-Test schützt, dass diese Profil-Normalisierung nicht wieder in den App-Hotspot zurückwandert. `backend/web/routes/app.py` liegt nach diesem Schnitt bei 2362 LOC.

#### C5: Learning-Repository strukturieren
- Problem: `backend/learning/repo_db.py` ist mit mehr als 2400 Zeilen groß genug, um Query-Gruppen und Schreibfälle schwer überprüfbar zu machen.
- Ziel: Learning-DB-Zugriffe werden nach Submission-Jobs, Course/Unit-Reads, Materials und Worker-Schreibfällen getrennt, ohne die öffentliche Repo-Fassade abrupt zu brechen.
- Vorgehen:
  - Zuerst Read-Model- oder Query-Gruppen auslagern, die von Learning-Routen genutzt werden.
  - Danach Worker-nahe Schreibfälle auslagern, wenn die Worker-Tests den Pfad abdecken.
  - RLS-relevante Zugriffspfade bleiben durch DB/RLS-Tests geschützt.
- Akzeptanz:
  - `backend/learning/repo_db.py` wird kleiner und enthält eine klare Aggregations- oder Fassadenrolle.
  - Learning-Worker-, Submission-, Material-, RLS- und Migrationstests bleiben grün.
- Done in working tree: `backend/learning/repo_submission_mapping.py` übernimmt Submission-Row-Mapping, öffentliche Fehler-Sanitizer und deterministische MVP-Analyse-/Feedback-Stubs; `backend/learning/repo_db.py` hängt diese Funktionen als Kompatibilitäts-staticmethods an `DBLearningRepo`. Existing Submission-Mapping-, Sanitizer- und Worker-Fehlercode-Tests schützen diesen Schnitt. `backend/learning/repo_db.py` liegt nach diesem Schnitt bei 2249 LOC.

#### C6: CSS, Legacy-Static und Frontend-Hotspots klassifizieren
- Problem: `frontend/src/lib/styles/app.css`, `frontend/src/lib/styles/design-system.css`, `backend/web/static/css/gustav.css` und große Legacy-JS-Dateien sind groß genug, um unklare aktive und retired UI-Regeln zu vermischen.
- Ziel: Jede große Styling- oder Static-Datei hat einen Status: aktiv modularisiert, bewusst eingefroren, oder nach Legacy-Retirement entfernbar.
- Vorgehen:
  - Zuerst prüfen, welche `backend/web/static/*`-Assets noch von aktiven FastAPI- oder H5P-Flächen referenziert werden.
  - Nicht mehr referenzierte Legacy-Assets nur mit Test oder Suchnachweis entfernen.
  - Aktive Frontend-CSS-Regeln nach Design-System, Layout, Komponenten und Legacy-Kompatibilität trennen.
  - Große Svelte-Routen weiter entlasten, indem Loader-/State-Normalisierung und View-Komposition in `frontend/src/lib/*`-Module wandern.
- Akzeptanz:
  - `docs/harness/HOTSPOTS.md` enthält für jede große CSS-/Static-/Svelte-Fläche einen aktuellen Status.
  - `npm run check`, relevante Vitest-Tests und `make test-frontend-h5p` bleiben grün.

#### C7: H5P-Sidecar weiter stabilisieren, aber nicht überoptimieren
- Problem: `h5p-service/server.mjs` wurde bereits verkleinert, bleibt aber ein sichtbarer Hotspot.
- Ziel: Weitere Extraktionen erfolgen nur dort, wo Route-Handler dadurch klarer und sicherer werden. H5P-Vendor-Dateien sind kein Refactor-Ziel.
- Vorgehen:
  - Keine Vendor-Dateien unter `h5p-service/vendor/` refactoren.
  - Nur eigene Service-Logik aus `server.mjs` verschieben, wenn ein Node-Test das Verhalten schützt.
  - Auth, CSP, Storage, Response und Forwarding bleiben in den bereits eingeführten `h5p-service/lib/*`-Modulen.
- Akzeptanz:
  - H5P-Node-Tests bleiben grün.
  - `server.mjs` wächst nicht ohne Hotspot- oder Tech-Debt-Begründung.

#### C8: Test-Harness und sehr große Tests entrümpeln
- Problem: `backend/tests/conftest.py` enthält viele autouse-Fixtures, die globale Route- und Repo-Zustände reparieren. Einige sehr große Testdateien schützen wichtige Flächen, sind aber schwer zu lesen.
- Ziel: Testisolation wird expliziter und verständlicher. Große Tests werden nur dort geteilt oder gebündelt, wo dadurch kein Sicherheits- oder Contract-Schutz verloren geht.
- Vorgehen:
  - `conftest.py` nur schrittweise verkleinern; jede entfernte autouse-Reparatur braucht einen gezielten Test, der die neue explizite Testoberfläche absichert.
  - Große Security-, API- und DB-Tests nicht löschen, nur weil sie groß sind.
  - Redundante dokumentnahe Harness-Tests auf strukturierte Zustände umstellen, statt Begriffe wie `follow-up` pauschal zu verbieten.
- Akzeptanz:
  - `conftest.py` ist kleiner oder seine verbliebenen globalen Reparaturen sind als bewusst akzeptierte Test-Harness-Schuld in `TECH_DEBT.md` dokumentiert.
  - `make verify` bleibt grün.

#### C9: Scorecard, Hotspots und Tech Debt ehrlich schließen
- Problem: Der v1.0-Status meldet aktuell null offene Tech-Debt-Einträge, obwohl mehrere große Hotspots nur überwacht und noch nicht vollständig modularisiert sind.
- Ziel: Der Abschlussstatus ist ehrlich: Entweder sind Hotspots bearbeitet oder bewusst akzeptiert.
- Vorgehen:
  - `docs/harness/HOTSPOTS.md` nach jedem Closeout-Schnitt aktualisieren.
  - `make quality-scorecard` nach relevanten Hotspot-Änderungen laufen lassen.
  - Für jeden verbleibenden echten Quellcode-Hotspot über ca. 1500 LOC entweder eine erledigte Modularisierung dokumentieren oder einen `TECH_DEBT.md`-Eintrag mit Risiko, Owner, Review date und Exit criterion anlegen.
  - Generated, vendored und binäre Dateien nicht als Refactor-Hotspots behandeln. Dazu zählen insbesondere `frontend/build/*`, `h5p-service/vendor/*`, Lockfiles und Testfixtures wie PDF/JPG-Beispiele.
- Akzeptanz:
  - `TECH_DEBT.md`, `HOTSPOTS.md`, `QUALITY_SCORECARD.md` und dieser Plan widersprechen einander nicht.
  - Der Status darf erst auf `Completed v1.1 / closeout verified` gesetzt werden, wenn alle Closeout-Akzeptanzkriterien erfüllt sind.

#### C10: Statische Qualitätsbasis einführen
- Problem: Die Harness-Gates schützen bereits viele Architektur- und Vertragsgrenzen, aber es gibt noch keine klar dokumentierte Python-Lint-, Format- und Type-Baseline. Dadurch können Refactor-Commits neue einfache Wartbarkeitsprobleme einführen, ohne dass ein Gate anschlägt.
- Ziel: Closeout v1.1 ergänzt eine kleine, niedrigschwellige statische Qualitätsbasis, die verständlichen Code fördert, ohne den Refactor durch tausende Altbefunde zu blockieren.
- Vorgehen:
  - Ruff als Python-Lint- und Format-Baseline über eine zentrale Projektkonfiguration einführen.
  - Einen expliziten Make-Target wie `make lint-backend` dokumentieren und erst dann als hartes Gate behandeln, wenn die Baseline ohne große False-Positive-Last grün ist.
  - Keine große automatische Massenformatierung mit fachlichen Extraktionen mischen.
  - Type-Checking nicht als sofortiges Full-Repo-Hartgate erzwingen. Stattdessen neu extrahierte Modulgrenzen mit klaren Typen, kleinen DTOs oder Protokollen versehen und später gezielt mit Pyright oder Mypy absichern.
- Akzeptanz:
  - Die statische Qualitätsbasis ist in `docs/harness/QUALITY_GATES.md` dokumentiert.
  - Neu extrahierte Module verletzen die gewählte Lint-Baseline nicht.
  - Wenn Type-Checking noch nicht hart aktiviert wird, ist der Restzustand mit Exit-Kriterium in `docs/harness/TECH_DEBT.md` dokumentiert.
- Done in working tree: `pyproject.toml` definiert eine zentrale Ruff-Konfiguration; `backend/web/requirements.txt` installiert Ruff über die bestehende Python-Requirements-Datei.
- Done in working tree: `make lint-backend` prüft zunächst Pyflakes (`F`) für den gesamten Backend-Baum inklusive Tests und E2E-Tests, damit Syntax-, Namens- und ungenutzte Import-/Variablenprobleme nicht weiter anwachsen.
- Done in working tree: 38 produktive Pyflakes-Befunde wurden bereinigt oder als bewusst benötigter Kompatibilitätsalias markiert; `backend.web.main.SESSION_COOKIE_NAME` bleibt mit `# noqa: F401` als öffentlicher Test-/Kompatibilitätsalias erhalten.

#### C11: Dead Code, Legacy-Reste und ungenutzte Assets entfernen
- Problem: Nach Monolith-Splits bleiben leicht Wrapper, alte Helper, nicht mehr referenzierte Static-Dateien oder Legacy-Kompatibilitätspfade zurück. Solche Reste machen das Repo größer und schwerer erklärbar.
- Ziel: Jede Extraktion endet mit einer kurzen Referenzprüfung, damit tatsächlich überflüssiger Code entfernt oder bewusst als Restschuld dokumentiert wird.
- Vorgehen:
  - Nach jeder größeren Route-, Repository- oder Frontend-Extraktion Import-, Route-Map- und Static-Asset-Referenzen prüfen.
  - Alte Wrapper nur behalten, wenn sie für Kompatibilität, schrittweise Migration oder klare öffentliche Fassaden nötig sind.
  - Nicht mehr referenzierte Legacy-Assets nur entfernen, wenn Suchnachweis oder Testabdeckung zeigen, dass keine aktive Oberfläche sie nutzt.
  - Vendor-Code, generierte Builds, Lockfiles und externe Testfixtures bleiben von Dead-Code-Aufräumarbeiten ausgenommen.
- Akzeptanz:
  - Entfernte Altpfade sind durch Tests oder nachvollziehbare Referenzsuche abgesichert.
  - Verbleibende Legacy-Reste haben Status, Risiko und Exit-Kriterium in `docs/harness/HOTSPOTS.md` oder `docs/harness/TECH_DEBT.md`.

#### C12: API- und Fehlervertrag stärker absichern
- Problem: Die vorhandene OpenAPI-Baseline schützt Runtime-`/api/*`-Pfade bereits gegen groben Drift, prüft aber nicht in jedem Fall Security-Anforderungen, Statuscodes und Error-Shapes so tief, wie es für einen großen Refactor wünschenswert ist.
- Ziel: Refactor-Änderungen dürfen API-Verhalten nicht unbemerkt verändern. Wenn ein Endpoint berührt wird, müssen Security, Statuscodes, Response-Shape und Fehlerabbildung bewusst abgesichert sein.
- Vorgehen:
  - Bei berührten Endpunkten zuerst prüfen, ob `api/openapi.yml` Security-Schemes, Statuscodes, Request-/Response-Schemas und Fehlerfälle ausreichend beschreibt.
  - Fehlende Contract-Tests ergänzen, bevor Handler- oder Adapterlogik verschoben wird.
  - Generische Contract-Gates bevorzugen, wenn mehrere Endpunkte denselben Fehler- oder Security-Vertrag teilen.
  - Breaking Changes bleiben außerhalb von Closeout v1.1. Falls ein bestehender Bug im Vertrag sichtbar wird, wird die Abweichung dokumentiert und gezielt als Bugfix behandelt.
- Akzeptanz:
  - Geänderte API-Flächen bestehen `make test-api-contract-baseline` und ihre fokussierten Contract-Tests.
  - Fehlerantworten bleiben für Nutzer und Clients stabil oder sind bewusst dokumentiert.

#### C13: Logging, Datenschutz und Fehlerdiagnose vereinheitlichen
- Problem: Refactors an Auth-, Upload-, H5P-, Teaching- und Learning-Flows können Logging und Fehlerdiagnose unbeabsichtigt verschlechtern. Gleichzeitig darf GUSTAV wegen des Bildungskontexts keine personenbezogenen Daten, Tokens oder Schülerantworten in Logs schreiben.
- Ziel: Kritische Flows liefern verständliche technische Diagnose, ohne Datenschutz- oder Security-Grenzen zu verletzen.
- Vorgehen:
  - Bei jeder Extraktion sicherheitsrelevanter Flows prüfen, ob Logs datensparsam bleiben.
  - Keine Tokens, Cookies, Dateiinhalte, Schülerantworten, echten Namen, E-Mail-Adressen oder schulbezogenen Identifikatoren loggen.
  - Wiederkehrende Fehlerfälle mit stabilen Fehlertypen oder Fehlercodes modellieren, soweit dies ohne API-Semantikänderung möglich ist.
  - Privacy-Logging-Contracts für Upload-, Feedback-, H5P- und Auth-Flows erhalten oder ergänzen.
- Akzeptanz:
  - Bestehende Privacy-, Upload-, Auth- und H5P-Tests bleiben grün.
  - Neue Logs in refactored Code sind datensparsam und fachlich nachvollziehbar.

#### C14: Modul-Dokumentation als Lernmaterial verbessern
- Problem: Modularisierung allein reicht nicht, wenn neue Module für Felix, Schüler oder externe FOSS-Mitwirkende nicht verständlich sind.
- Ziel: Neu extrahierte Module erklären ihre Verantwortung klar und knapp. Dokumentation hilft beim Lernen, ohne den Code mit trivialen Kommentaren zu überfrachten.
- Vorgehen:
  - Neue fachliche Module erhalten kurze englische Modul-Docstrings oder Kopfkommentare zu Zweck, Verantwortung und erlaubten Abhängigkeiten.
  - Komplexe Funktionen erhalten Docstrings zu Absicht, Parametern, erwarteter Wirkung und Berechtigungsannahmen.
  - Inline-Kommentare nur an Stellen setzen, deren Logik für Lernende nicht offensichtlich ist.
  - Architektur- und Harness-Dokumente nachziehen, wenn sich Modulgrenzen oder Gate-Verantwortungen ändern.
- Akzeptanz:
  - Neu extrahierte Module sind ohne Kenntnis des alten Monolithen verständlich.
  - Dokumentation und Code verwenden die Begriffe aus `GLOSSARY.md` konsistent.

#### C15: Testqualität statt Testmenge absichern
- Problem: Eine große grüne Testsuite kann trotzdem schwer wartbar sein, wenn sie viele globale Fixtures, Wrapper-Tests oder strukturfragile Dokumenttests enthält.
- Ziel: Closeout v1.1 verbessert die Aussagekraft der Tests. Gute Tests schützen fachliche Regeln, öffentliche Verträge, Sicherheitsgrenzen oder produktionsnahe Integrationen.
- Vorgehen:
  - Sehr große Testdateien nach Verhalten, Risiko und Testebene prüfen, bevor sie geteilt oder zusammengeführt werden.
  - Wrapper-Tests ohne fachlichen Wert entfernen oder durch Contract-, Regression- oder Boundary-Tests ersetzen.
  - Dokumentationsnahe Tests auf stabile strukturierte Aussagen prüfen, nicht auf fragile Stichwortverbote.
  - Große Security-, RLS-, API- und Upload-Tests nicht löschen, nur weil sie groß sind.
  - `docs/harness/TEST_STRATEGY.md` aktualisieren, wenn neue Regeln für `keep`, `merge`, `rewrite` oder `retire-later` entstehen.
- Akzeptanz:
  - Die Testsuite enthält keine neu eingeführten rein mechanischen Tests ohne fachlichen, vertraglichen oder sicherheitsbezogenen Nutzen.
  - Bereinigte Testbereiche bleiben durch fokussierte Verifikation grün.
- Done in working tree: Pyflakes läuft über die Testsuite; 62 Test-/E2E-Befunde wurden bereinigt, darunter ungenutzte Imports, wirkungslose lokale Variablen und ein fehlender Typname in einem Vision-Adapter-Test.

#### C16: Performance- und N+1-Risiken bei großen Read-Flows prüfen
- Problem: Teaching-Dashboards, Learning-Analytics, Submission-Übersichten und H5P-Statusflüsse können durch gut gemeinte Modul-Splits unbemerkt mehr Datenbankabfragen, Storage-Aufrufe oder Netzwerkübergänge auslösen.
- Ziel: Der Refactor verschlechtert kritische Read-Flows nicht offensichtlich. Es geht nicht um Mikrooptimierung, sondern um Schutz vor N+1-Fehlern und teuren Schleifen.
- Vorgehen:
  - Bei ausgelagerten Read-Models prüfen, ob Query-Grenzen, Batch-Reads und vorhandene Aggregationen erhalten bleiben.
  - Wo sinnvoll, kleine Regressionstests oder Messpunkte für Query-Anzahl, Repository-Aufrufe oder Storage-Zugriffe ergänzen.
  - Performance-Dokumentation nur dort ergänzen, wo ein Flow fachlich kritisch oder schwer durchschaubar ist.
  - Keine neuen Caches einführen, wenn ein sauberer Query- oder Aggregationsschnitt ausreicht.
- Akzeptanz:
  - Dashboard-, Analytics-, Submission- und H5P-Read-Flows behalten ihre bestehenden Query- und Zugriffsmuster oder dokumentieren bewusst akzeptierte Änderungen.
  - Offensichtliche N+1-Risiken werden vor Abschluss von Closeout v1.1 beseitigt oder mit Exit-Kriterium als Tech Debt erfasst.

#### Closeout Verification
Vor Abschluss von Closeout v1.1 müssen diese Befehle erfolgreich sein:
- `git diff --check`
- `make test-import-boundaries`
- `make test-api-contract-baseline`
- `make test-architecture-boundaries`
- `make test-route-map`
- `make test-db-inventory`
- `make quality-scorecard`
- `make verify`

Zusätzlich muss der Abschlussbericht festhalten, ob ein hartes Backend-Lint-Gate bereits aktiv ist. Falls `make lint-backend` oder ein gleichwertiger Target eingeführt wurde, muss er vor dem Abschluss ebenfalls grün sein. Falls das Lint- oder Type-Gate bewusst nur als Follow-up aktiviert wird, braucht der Restzustand einen Eintrag in `docs/harness/TECH_DEBT.md` mit Owner, Review date, Risiko und Exit criterion.

Wenn ein Befehl wegen lokaler Infrastruktur nicht ausführbar ist, muss der Agent die Ursache konkret dokumentieren, darf den Plan aber nicht als vollständig umgesetzt markieren. Ein fehlender lokaler Dienst ist nur dann ein akzeptierter Restzustand, wenn derselbe Schritt nicht Teil der Abschlusskriterien ist oder ein gleichwertiger, dokumentierter Nachweis vorliegt.

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

## Closed Decisions
- Gates use stable `make` targets backed by focused Python check scripts where static inventories are useful; CI runs the same entry points.
- Hotspot growth is monitored by `docs/harness/HOTSPOTS.md`, `docs/harness/QUALITY_SCORECARD.md`, and zero-open `TECH_DEBT.md`: relevant growth needs tests or a concrete Tech-Debt entry with Exit-Kriterium.
- `TECH_DEBT.md` stays under `docs/harness/` as the active zero-debt inventory for this harness.
- Repo-governed project skills live in `docs/harness/skills/*/SKILL.md`; local tool-specific installation copies are non-authoritative.
- Manual skill forward-tests in `docs/harness/SKILL_EVALS.md` are the v1 evidence mechanism; scripted skill evals are not an Abschlusskriterium dieses Refactor-Plans.
- Legacy HTML removal is test- and route-map-driven; retired/dead paths and former FastAPI shell pages are removed or intentionally answered by tested retirement behavior.
- `backend/web/main.py` is a small app-composition entry point before deeper route splits.
- Frontend and H5P hotspots are included in the same quality scorecard as backend hotspots.
- `TECH_DEBT.md` stays under `docs/harness/` because that is easiest for agents to find.
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
