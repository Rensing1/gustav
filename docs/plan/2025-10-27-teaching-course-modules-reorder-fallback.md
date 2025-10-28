Title: Teaching — Course Modules Reorder Fallback (DB-independent)

Context
- Report: Reordering modules on /courses/{course_id}/modules intermittently fails.
- Root cause hypothesis: Target DB lacks the deferrable unique constraint on (course_id, position). The current implementation in DB repo performs a single UPDATE relying on `SET CONSTRAINTS ... DEFERRED`.
- Observation: API reorder works on migrated DB; UI forwarder masks DB errors as generic 400.

Goals
- Make reorder robust without relying on deferrable constraints by using a two-phase position update inside one transaction.
- Minor UI hardening: avoid variable shadowing in the reorder forwarder.
- Add a UI test that exercises the reorder flow against the DB-backed repo to catch migration/config regressions.

User Story
- As a course owner (teacher), I want to reorder attached units in my course via drag-and-drop so that the new order persists reliably, regardless of specific DB constraint settings.

BDD Scenarios
- Given a course with modules A,B,C When I submit order C,A,B Then positions become 1,2,3 and GET returns C,A,B in that order.
- Given an empty module list When I attempt to reorder Then I receive 400 empty_reorder.
- Given module ids with duplicates When I attempt to reorder Then I receive 400 duplicate_module_ids.
- Given module ids not matching the course's modules When I attempt to reorder Then I receive 400 module_mismatch.
- Given a non-owner When I attempt to reorder Then I receive 403 (or 404) and no change happens.
- Given the DB constraint is not deferrable When I attempt to reorder Then the two-phase update still succeeds.

Design
- Persistence (DBTeachingRepo):
  - Replace the single UPDATE guarded by `SET CONSTRAINTS ... DEFERRED` with a two-step approach:
    1) Bump all positions in the target course by `n` (number of modules). This guarantees uniqueness during the change (positions move to n+1..2n).
    2) Apply final positions 1..n based on requested order via `UPDATE ... FROM (unnest(uuid[], int[]))`.
  - Keep existing validation (exact id set match) and RLS engagement via `set_config('app.current_sub', ...)`.

- Web (SSR forwarder):
  - Rename inner list-comprehension variable in `courses_modules_reorder` from `sid` to `elem_id` to avoid confusion with session id.

Testing
- Add a UI test that:
  - Requires DB, sets the teaching repo to DBTeachingRepo, creates course + units, attaches as modules, loads CSRF token, posts reorder to `/courses/{id}/modules/reorder` and verifies order via a follow-up GET.

Out of Scope
- API shape remains unchanged; no OpenAPI modifications required.

