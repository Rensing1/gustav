# Members Directory Hardening (2026-02-14)

## Why
- Remove a cancellation pattern (`wait_for(to_thread(...))`) that can leave blocking directory work running after timeout.
- Reduce members-search load by avoiding full-roster fetches on every keypress.
- Replace per-user Keycloak lookups for login labels with bounded bulk scanning.
- Restrict iPad-specific CSS overrides so they do not affect desktop layouts.

## Scope
- `backend/web/main.py`
- `backend/identity_access/directory.py`
- `backend/web/static/css/student_modular_unit.css`
- Targeted tests under `backend/tests/`

## Constraints
- Keep existing API contracts unchanged (`api/openapi.yml` unaffected).
- Preserve fallback behavior: when login labels are unavailable, keep existing names.
- Security-first defaults: bounded scans, no token leakage, no cache of sensitive values beyond process-local short TTL member-sub sets.

## TDD Plan
1. Add failing tests for:
   - no timeout-cancel wrapper in member label overlay path
   - members search short-term cache behavior
   - bulk login-label resolution and fallback token retry
   - CSS media-query guard for iPad-only compact profile
2. Implement minimum code to pass tests.
3. Refactor for readability and re-run focused regression suite.

## Risks / Mitigation
- Risk: behavioral drift in members sorting/filtering.
  - Mitigation: keep existing output semantics and update stale comments.
- Risk: cache staleness after membership changes.
  - Mitigation: explicit invalidation on add/remove and short TTL.
