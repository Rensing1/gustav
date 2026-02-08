# Ticket: Modular Unlock not refreshed immediately after H5P submission

## Summary
In the modular student workspace, completing an H5P task can update backend unlock state correctly, but the graph UI may remain stale until a manual reload. The next module is already open server-side, yet still appears locked client-side.

This ticket documents the root cause and the implementation spec for a UI-only fix.

## Impact
- Students can be blocked by stale UI feedback in modular units.
- Progression appears inconsistent (server state vs. visible graph state).
- Instructors may misinterpret unlock logic as broken.

## Reproduction (PII-free)
1. Open a modular unit where module A (H5P) unlocks module B.
2. Complete module A with a full H5P score (`score_raw == score_max`).
3. Observe that module B may still display as locked in the current view.
4. Reload the page; module B is then shown as open.

## Verified Findings
- SQL unlock state calculation reports the expected module as `open`.
- Learning graph API returns the expected module status as `open`.
- H5P submission persistence is present with a full-score record.
- Therefore, the discrepancy is in client refresh behavior, not unlock computation.

## Root Cause
The modular workspace refreshes graph/runtime only when it receives a `modularGraphRefresh` event. This event is emitted in the HTMX submit flow, but not in the H5P player `fetch` submit flow.

Consequence: H5P completion updates backend state but does not trigger workspace refresh in-place.

## Fix Specification
### Scope
Frontend only. No API or DB schema changes.

### Required changes
1. Update `backend/web/static/js/h5p_task_player.js`:
- After successful `submitAttempt(...)`, dispatch a `modularGraphRefresh` event with payload:
  - `courseId`
  - `unitId`

2. Ensure event delivery to modular workspace listener:
- Either dispatch on the modular workspace root element, or
- Dispatch a bubbling/composed custom event such that the listener on the workspace root receives it.

3. Keep existing idempotency behavior unchanged:
- Do not alter statement-id dedup logic.
- Emit refresh event only on successful submission persistence.

### Non-goals
- No changes to unlock rules (`k-of-n`, H5P completion semantics).
- No backend route changes.
- No migration changes.

## Files of interest
- `backend/web/static/js/h5p_task_player.js`
- `backend/web/static/js/student_modular_workspace.js`
- (reference path already emitting event) `backend/web/main.py` in HTMX submit handling

## Acceptance Criteria
1. After successful full-score H5P completion in a modular unit, dependent modules become visible as open without page reload.
2. If H5P submission fails (non-2xx), no unlock refresh event is emitted.
3. Existing HTMX submission refresh flow continues to work unchanged.

## Test Scenarios
1. **H5P unlock refresh**
- Given module A (H5P) unlocks module B
- When full score is submitted in A
- Then module B status changes to open in the same view (no reload)

2. **Failure safety**
- Given failed H5P submit
- When submission response is non-2xx
- Then no modular graph refresh is dispatched

3. **Regression**
- Given non-H5P task submission via HTMX
- Then existing `modularGraphRefresh` behavior remains intact

## Risk Assessment
Low. The change is local to event emission after successful H5P submit and does not alter persistence or unlock logic.

## Rollout Notes
- Deploy with normal frontend asset cache-busting/versioning process.
- Validate in a modular unit using one H5P prerequisite edge and one dependent module.
