# Plan: Teacher Units Create Dialog Fix

Status: completed

## Summary

The "Neue Lerneinheit" action on `/teaching/units` should open a reliable local dialog without changing the URL.
The dialog must use the shared centered modal shell so it appears in the middle of the viewport.

## Decisions

- Open the dialog locally in the page component instead of using `?create=1`.
- Keep the existing create action and failed-submit reopen behavior.
- Reuse the global `workspace-modal` / `workspace-modal-backdrop` / `workspace-modal-card` pattern.

## Verification

- Frontend route interaction tests for local open and close behavior
- Route contract test for removal of URL-driven dialog state
- `cd frontend && npm run check`
- `docker compose up -d --build frontend`
