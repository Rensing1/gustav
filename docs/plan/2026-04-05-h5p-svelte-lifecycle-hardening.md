# H5P Svelte Lifecycle Hardening

## Summary
- Fix the teacher-side H5P editor so it initializes reliably when teachers switch
  between multiple H5P tasks in the Svelte unit editor.
- Harden the learner-side H5P player with the same lifecycle discipline to avoid
  similar mount/unmount bugs later.
- Replace HTMX-style global bootstrap hooks with explicit Svelte-owned mount and
  cleanup logic.

## Implementation
- Add frontend lifecycle tests that cover repeated mount, unmount, and remount
  for the teacher editor and learner player.
- Refactor the shipped H5P editor runtime asset to export an explicit mount API
  with a matching destroy function.
- Introduce small Svelte-side runtime loaders so dynamic imports can be mocked in
  tests without changing production asset URLs.
- Keep the backend/frontend static editor asset copies byte-identical.

## Verification
- Run targeted Vitest component tests for the new lifecycle scenarios.
- Run the existing packaging and source-level contract tests for H5P editor and
  player integration.

## Assumptions
- The unreliable editor is caused by the current HTMX-oriented bootstrap logic
  colliding with Svelte mount/unmount behavior.
- No API or database changes are required for this fix.
