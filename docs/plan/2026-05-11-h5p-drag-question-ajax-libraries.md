# H5P Drag Question Ajax Libraries Fix

## User Story

As a teacher, I want to create an H5P Drag and Drop task with a background image, so that I can place drop zones in the Task step without the editor getting stuck.

## BDD Scenarios

- Given a teacher edits an H5P Drag and Drop task, when the editor opens the Task step, then the H5P ajax `libraries` request returns the requested element libraries.
- Given the H5P editor sends URL-encoded fields as `libraries[]`, when the H5P sidecar handles `/h5p/ajax?action=libraries`, then the body is normalized to `libraries`.
- Given the H5P editor uploads a background image, when the teacher switches to Task, then the temporary file remains accessible and no parser change breaks multipart uploads.

## Implementation

- Document `/h5p/ajax` support for H5P-style URL-encoded arrays in `api/openapi.yml`.
- Add a failing Node contract test for normalizing `libraries[]` into `libraries`.
- Add a small helper in `h5p-service/server.mjs` before `h5pAjax.postAjax(...)`.
- Keep auth, CSRF checks, role checks, and upload handling unchanged.

## Verification

- `cd h5p-service && npm test`
- `.venv/bin/pytest -q backend/tests/test_openapi_h5p_runtime_endpoints_contract.py`
- Manual UAT: Drag and Drop with image → Task step shows the editor surface instead of the loader.
