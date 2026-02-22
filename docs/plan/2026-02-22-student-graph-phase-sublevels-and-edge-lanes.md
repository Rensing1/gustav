# Plan: Student Graph - Dense Same-Phase Dependencies as Strict Two Levels (2026-02-22)

Status: implemented (2026-02-22, revised after UX feedback)

## Goal
- Improve readability in the student modular graph when many dependencies exist
  inside the same phase.
- Keep API and DB unchanged (frontend-only rendering change).

## User Story
As a student, I want dependency-heavy phases to show a clear top/bottom
structure so I can instantly see which module unlocks the others.

## Final decisions
- Trigger for level mode: only when a same-phase node has
  `direct indegree >= 3` or `direct outdegree >= 3`.
- For degree 2, keep one-row layout and separate only by edge lanes.
- In level mode, use **strict two levels only**:
  - top row (source-like nodes)
  - bottom row (target-like nodes)
- Keep edge style visually consistent with existing student graph edges (same
  cubic style + marker), no special orthogonal mode.

## Why this revision
- The first implementation used generic local topological sublevels.
- In real usage this looked visually noisy for dense phases.
- UX feedback requested a cleaner and more predictable structure:
  one centered top row over one bottom row for dense fan-out/fan-in.

## Non-goals
- No OpenAPI changes.
- No migration or backend unlock logic changes.
- No teacher-editor behavior changes.

## Design overview

### 1) Two-level assignment in workspace model
- Build same-phase adjacency for each phase from `edges`.
- Detect phase-local connected components.
- For components that include a threshold node (>=3 in/out):
  - score nodes for `top` / `bottom` placement (seed + direct neighbors),
  - resolve ties deterministically using degree and stable ordering,
  - enforce non-empty top and bottom rows.
- Compute row positions:
  - `yTop = baseY - TWO_LEVEL_GAP_Y / 2`
  - `yBottom = baseY + TWO_LEVEL_GAP_Y / 2`

### 2) Horizontal recentering per conflict component
- Recenter top and bottom rows around the component center X so a single top
  source appears centered above bottom targets.
- Keep deterministic ordering by original module order (`position_in_phase`, id).

### 3) Edge routing (same style, clearer separation)
- Keep existing cubic path style and marker.
- Keep count-aware symmetric lane offsets.
- For same-phase top->bottom edges, apply lane offset horizontally to avoid
  overlap.

## BDD scenarios
1. Fan-out (`A -> B,C,D,E`) in one phase
- Given `A` has direct outdegree 4
- When graph renders
- Then `A` is on top row, `B,C,D,E` are on bottom row
- And edges are visually distinct

2. Degree-2 split (`A -> B,C`)
- Given direct outdegree is 2
- When graph renders
- Then modules remain one-row
- And lane-separated edges avoid overlap

3. Fan-in (`B,C,D -> A`)
- Given `A` has direct indegree 3
- When graph renders
- Then incoming sources are on top row and `A` is on bottom row

4. Mixed component
- Given chain + fan-out in one connected same-phase component
- When threshold is crossed
- Then only two levels are used (no third level)

5. Stability
- Given refresh/polling updates runtime
- When graph rerenders
- Then node placement remains deterministic

## Files changed
- `backend/web/static/js/student_modular_workspace.js`
- `backend/web/static/js/student_graph_view.js`
- `backend/tests/test_student_modular_workspace_js_contract.py`
- `backend/tests/test_student_graph_view_sync_contract.py`

## Test strategy (Red-Green-Refactor)
1. Red
- Updated workspace JS contract assertions for:
  - `TWO_LEVEL_GAP_Y`
  - two-level function name and yTop/yBottom formulas
  - degree-3 trigger checks

2. Green
- Replaced generic multi-level logic with strict two-level component logic.
- Kept edge style, improved lane offset behavior for stacked same-phase edges.

3. Refactor
- Deterministic ordering/tie-breakers preserved.
- Minimal scoped comments for non-obvious routing behavior.

## Validation
- `.venv/bin/pytest -q backend/tests/test_student_modular_workspace_js_contract.py`
  - result: 8 passed
- `.venv/bin/pytest -q backend/tests/test_student_graph_view_sync_contract.py`
  - result: 3 passed
- `.venv/bin/pytest -q backend/tests/test_learning_modular_unit_page_ui.py`
  - result: 4 passed, 3 skipped

## Risks and mitigations
- Risk: two-level assignment in unusual mixed graphs can still be imperfect.
  - Mitigation: deterministic scoring + tie-breakers + stable rows.
- Risk: edge overlap in dense top->bottom sets.
  - Mitigation: horizontal lane offsets for stacked same-phase edges.
