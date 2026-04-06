# Plan: Teacher Units Course Token Abbrev

Status: completed

## Summary

- Shorten course names in the teacher units catalog to the first token before the first space.
- Keep the existing three-column table and inline course list.
- Leave backend contracts unchanged.

## Decisions

- Example: `9L Informatik` renders as `9L`.
- Names without spaces stay unchanged.
- Empty course lists still render as `Ohne Kurs`.

## Verification

- Update the row component tests for first-token rendering.
- Run targeted frontend tests.
- Run `npm run check`.
- Rebuild the frontend container.
