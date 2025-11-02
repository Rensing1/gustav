Title: Security hardening for Teaching Live detail + contract sync

- Enforce strict relation: task ∈ unit ∈ course (404 on mismatch)
- Use SECURITY DEFINER helper with unit_id; no unsafe direct-table fallback; keep RLS-safe fallback under strict relation
- OpenAPI: add date-time format for TeachingModuleSection.released_at, additionalProperties:false, include 204 headers
- Tests: add relation-guard 404 case; all tests green locally (550 passed)
- Makefile: silence import targets to avoid secret leaks in logs
- Docs updated: CHANGELOG, teaching_live reference, plan

DB migration required:
- Apply 20251102154144_teaching_latest_submission_owner_unit_guard.sql (supabase migration up)

Risk/Blast radius:
- Low and scoped to Teaching Live detail + helper. Rollback by re-creating old helper signature if needed.
