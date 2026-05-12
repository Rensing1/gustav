# Ticket: Learner feedback history reload and generic error state

## Summary

On 2026-05-12, a learner reported that a Filius feedback submission showed the
evaluation but not the written feedback in the learner UI. After reloading the
page, both feedback and evaluation were no longer visible and the UI showed a
generic error or missing-state message.

The teacher live view and persisted learning data showed the submission as
completed with both `feedback_md` and `analysis_json`. The Filius feedback
pipeline itself completed successfully. This ticket is therefore scoped to the
learner-facing learning UI and its reload/history/auth-recovery behavior, not
to missing persisted feedback data.

No learner names, user IDs, session IDs, object paths, or other PII are included
in this ticket.

## Observed Context

- The affected submission was a Filius task submission.
- The backend state showed completed feedback and completed structured
  evaluation for the same task.
- Teacher live view could display feedback and evaluation.
- The learner UI did not reliably display the same data during the classroom
  session.
- Reloading did not restore a coherent completed-submission view for the
  learner.
- No direct evidence points to lost database rows or storage loss.

## Relationship To Existing Auth Ticket

This issue must be checked against:

- `docs/tickets/auth-session-continuity-classroom-regression-2026-05-11.md`

That ticket tracks the systemic classroom auth/session-continuity problem where
recoverable auth states can surface as missing modules, missing submissions,
missing feedback, stale learning state, or generic page errors. This ticket
should not duplicate the central auth fix. Instead, it should verify that the
learning feedback/history UI behaves correctly when auth recovery is available
or when history data has to be reloaded after a page reload.

The main risk is that a recoverable history request failure or missing
client-side history state is presented as "no feedback" or a generic learning
error, even though the persisted submission is complete.

## Files Of Interest

- `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte`
  - `historyForTask(...)` and `setTaskHistory(...)` hold per-task submission
    history only in client-side state.
  - `syncModularWorkspaceUrl(...)` removes the `history` query parameter when
    syncing modular workspace state, so a reload may not preserve an open
    history/review view.
  - `loadSubmissionHistory(...)` fetches
    `/api/learning/courses/:courseId/tasks/:taskId/submissions?limit=10&offset=0`.
  - `pollFeedbackSubmission(...)` updates task history after feedback polling.
  - `toggleReviewPanel(...)` loads history only when no local history is
    present; on failure it sets the generic message
    `Die Abgabe konnte nicht geladen werden.`
- `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/page-contract.test.ts`
  - Existing contract tests already assert the presence of
    `toggleReviewPanel`, `pollFeedbackSubmission`, and `historyForTask`.
  - Extend or complement these tests with reload/history recovery expectations.
- `frontend/src/lib/server/api.ts`
- `frontend/src/lib/server/session.ts`
- `frontend/src/lib/server/guards.ts`
  - These are the auth/session recovery files referenced by the existing auth
    continuity ticket and should be considered when a history fetch returns
    `401` or another recoverable auth response.

## Required Behavior

- A learner with a completed non-H5P submission can reload a modular learning
  unit and still open the task's submission review to see:
  - submitted work,
  - written feedback,
  - structured evaluation.
- If task metadata says a completed submission exists but local history is
  empty, the UI must load history or show a loading/retry state. It must not
  present the situation as missing feedback.
- If history loading receives a recoverable auth/session response, it must use
  the centralized auth-continuation behavior from the auth-session ticket
  instead of surfacing a generic learning error.
- Empty states must distinguish:
  - history not loaded yet,
  - feedback still pending,
  - feedback generation failed,
  - feedback/evaluation genuinely unavailable.
- The learner and teacher views must agree once the same completed submission
  data is available.

## Test Scenarios

- Completed Filius submission, reload modular learning page, open the task's
  submission review, and verify feedback and evaluation are visible.
- Completed submission metadata present but `submissionHistoryByTask` initially
  empty; verify opening the review panel fetches and renders history.
- Simulated recoverable `401` or session-continuity response during history
  load; verify the route follows the auth recovery path instead of showing a
  generic missing-feedback state.
- Simulated non-recoverable history failure; verify the user-facing message is
  specific to loading failure and does not imply that persisted feedback is
  absent.

## Acceptance Criteria

1. Reloading a completed Filius task does not make learner feedback or
   evaluation disappear.
2. The learner UI does not show "no feedback" merely because history has not
   been loaded into client-side state yet.
3. Recoverable auth/session failures during history loading are handled through
   the central auth-continuity path.
4. Generic learning errors are replaced with state-specific messages for
   loading, pending, failed, and unavailable feedback.
5. Tests cover reload/history recovery for at least one completed non-H5P file
   submission.
