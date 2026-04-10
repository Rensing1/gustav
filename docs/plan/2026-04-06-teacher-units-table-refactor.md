# Plan: Teacher Units Table Refactor

Status: completed

## Summary

- Refactor `/teaching/units` from the current card-in-card catalog into a flatter Mistral-style table.
- Keep `PageActionHead`, live search and sort.
- Remove the inner catalog header and the mixed `meta` string.
- Extend the catalog read-model with structured status and course data so the frontend does not parse UI strings.

## Decisions

- Only the unit title links to the unit workspace.
- The course cell is a separate interactive cell that reveals the assigned courses.
- `modular` and `linear` are removed from the catalog UI.
- No new `Abschnitte` column is introduced in this pass.
- The implementation must stay aligned with `docs/DESIGN.md`.

## Planned Changes

- Update `api/openapi.yml` and backend catalog payload for the new item shape.
- Replace `meta` with `status_label`, `status_tone`, `courses_count` and `courses`.
- Simplify the route loader and frontend types to the reduced catalog contract.
- Rebuild the catalog list as a flat table-like workspace without nested cards.
- Keep the existing create dialog and route action flow.

## Verification

- Backend contract tests for the new catalog schema.
- API tests for the structured item payload.
- Svelte tests for toolbar, list and row interaction.
- `npm run check`
- `docker compose up -d --build frontend`
