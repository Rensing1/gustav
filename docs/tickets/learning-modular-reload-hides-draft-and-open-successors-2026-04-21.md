# Ticket: Modular reload hides existing draft and open successor modules

## Summary
In the modular student workspace, a learner can have an existing persisted draft and already unlocked successor modules on the server, yet after a browser reload the UI no longer shows the draft and may not expose the now-open successors.

This creates a visible mismatch between persisted learning progress and what the learner can access after reloading the page.

## Impact
- Learners can appear blocked after reload even though their work was saved.
- Existing draft submissions can become inaccessible from the current UI state.
- Server-side unlock progression can look broken although unlock state is already correct.
- Teachers may see persisted work that learners cannot reach from their own workspace.

## Reproduction (PII-free)
1. Open a modular unit where one module unlocks one or more successors.
2. Create a text draft for a task and wait until feedback has completed successfully.
3. Reload the browser page.
4. Observe that the learner may no longer see the existing draft in the workspace.
5. Observe that successor modules that are already `open` server-side may still not be reachable in the reloaded workspace.

## Verified Findings
- A persisted draft submission exists server-side for the affected learner and task.
- The modular unlock state is already correct server-side after the persisted draft/progress.
- Multiple successor modules can already be `open` in the modular state helper while the learner UI still fails to expose them after reload.
- The core problem is therefore not data loss and not unlock computation, but reload/hydration behavior in the modular learner workspace.

## Root Cause
The modular learner workspace derives visible task/detail state from a combination of:
- server-loaded active module content,
- client-restored open module tabs,
- optional task history context in the URL,
- client-side review/history state.

After reload, this composition can fail closed:
- module content is only server-loaded for the active module context,
- submission history is only loaded when explicit task history context is present or fetched later,
- the modular restore path can fall back to overview mode when open modules cannot be restored cleanly,
- that fallback clears review/history context and leaves persisted submissions undiscoverable from the visible workspace state.

Result: the learner sees neither the existing draft nor the expected successor modules, although both remain present server-side.

## Fix Specification
### Scope
Frontend learner workspace behavior, with any minimal supporting server-load adjustments required to make reload state deterministic.

### Required changes
1. Harden modular reload/hydration so persisted open modules remain reachable after reload.
2. Ensure an existing persisted draft remains visible or reliably re-openable after reload without depending on fragile transient client state.
3. Prevent overview fallback from silently hiding persisted learner work.
4. Keep server-side unlock semantics unchanged.

### Non-goals
- No changes to unlock rules (`k-of-n`, `open`, `done`).
- No changes to scoring semantics.
- No migration or schema changes unless a minimal follow-up becomes strictly necessary.

## Files of interest
- `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte`
- `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.server.ts`
- `frontend/src/lib/components/learning-unit/LearningTaskCard.svelte`
- `frontend/src/lib/learning-unit/workspace.ts`

## Acceptance Criteria
1. Given a persisted draft exists in a modular unit, when the learner reloads the page, then the draft remains visible or can be reopened reliably from the current workspace.
2. Given successor modules are already `open` server-side, when the learner reloads the page, then those successors are shown as open/reachable in the modular workspace.
3. Reload must not require hidden URL state to preserve access to existing learner work.
4. Teacher-visible persisted submissions and learner-visible persisted submissions remain consistent after reload.

## Test Scenarios
1. **Persisted draft survives reload**
- Given a modular task with a completed feedback draft
- When the learner reloads the page
- Then the draft is still visible or directly reopenable

2. **Unlocked successor survives reload**
- Given module A already unlocks module B server-side
- When the learner reloads the page
- Then module B is still shown as open

3. **Restore fallback safety**
- Given module restore fails or times out during reload
- When the workspace falls back to overview
- Then persisted learner work is still discoverable and not silently hidden

4. **Regression**
- Given linear units or non-modular learner flows
- When the learner reloads
- Then existing behavior remains unchanged

## Risk Assessment
Medium. The issue sits in workspace composition and reload restoration, so the fix must avoid introducing new inconsistencies between overview/content state, local storage restoration, and task review visibility.

## Rollout Notes
- Validate in a modular unit with at least one persisted draft and at least one dependency edge.
- Verify both immediate post-submit reload and later revisit reload.
- Confirm consistency between learner workspace, modular graph state, and teacher-visible persisted submissions.
