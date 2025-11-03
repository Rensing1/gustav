# Plan: Fix "Mitglied entfernen" persists (RLS delete policy)

## User Story
- As a teacher (course owner), I want to remove a student from my course so that the student no longer appears in the roster after reloading the page.

## BDD Scenarios
- Given I am the owner, When I click Entfernen for a student, Then the API deletes the membership and the student is absent after reload (Happy Path).
- Given I am not the owner, When I attempt to delete a membership, Then I get a 403/owner-guard behavior and the member stays in the roster (Authorization Failure).
- Given I click Entfernen twice for the same student, When the second request runs, Then it remains idempotent (204) and the student remains absent (Idempotency).

## API Contract
- No new endpoints. We reuse DELETE `/api/teaching/courses/{course_id}/members/{student_sub}`. Default pagination for the roster remains.

## Database Migration
- Problem: RLS drift removed the `memberships_delete_owner_only` policy, preventing deletes for owners when using the limited role.
- Solution: Add a migration to (re)create `memberships_delete_owner_only` with `using (exists(select 1 from public.courses ... teacher_id = app.current_sub))`.

## Tests
- Add `backend/tests/test_teaching_memberships_delete_rls_policy.py` — disables service-DSN fallback, creates owner+membership via DB repo, deletes under RLS, asserts the member is absent via helper-backed listing.
- Existing UI/API tests already verify SSR flow; this test pins the DB policy specifically.

## Notes
- No UI changes required. After migration, SSR remove reflects true backend state.
