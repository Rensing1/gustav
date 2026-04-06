# Plan: Teacher Units Course Column Refactor

Status: completed

## Summary

- Refactor the teacher units table so the course column shows compact course names instead of course counts.
- Remove the status column to free horizontal space.
- Keep the table flat and aligned with `docs/DESIGN.md`.

## Decisions

- Only the unit title remains clickable.
- Course names are rendered as compact inline text, not as links or popovers.
- Empty course assignments render as `Ohne Kurs`.
- Description text under the title is visually smaller than the title.

## Verification

- Update the row and list component tests for the new three-column layout.
- Run the targeted units catalog frontend tests.
- Run `npm run check`.
- Rebuild the frontend container.
