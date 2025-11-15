Title: Learning uploads — lazy storage wiring to survive Supabase startup timing

Context
- Symptom: Selecting a file immediately shows “Upload fehlgeschlagen …” in the UI.
- Root cause: On app start, Supabase wiring throws an exception; storage adapter stays Null.
- Result: Upload‑intent endpoint returns 503 service_unavailable; client aborts before final submit.

Goals
- Make upload‑intents robust against transient Supabase unavailability at startup.
- Preserve security (same‑origin CSRF, student role, RLS at DB boundary).
- Keep changes minimal and consistent with Clean Architecture and KISS.

Plan
- Extract startup storage wiring into a reusable helper `backend/web/storage_wiring.py`.
- Call the helper at app start (unchanged behavior) and lazily from the first
  upload‑intent if the adapter is still Null.
- Improve logging to include exception messages to aid diagnosis.
- Add an integration test that simulates a failing first `create_client` call at
  startup and succeeding on the first request, asserting the endpoint succeeds.

Non‑goals
- No API shape changes; OpenAPI remains valid for upload‑intents.
- No material upload (teaching) behavior change beyond shared wiring.

Risks & Mitigations
- Risk: Repeated wiring attempts. Mitigation: helper is idempotent; costs are negligible.
- Risk: Secret leakage via logs. Mitigation: log only exception type and message; no secrets.

Testing
- New pytest exercising lazy rewire path: startup wiring fails → first
  upload‑intent succeeds and returns a usable URL (or proxy URL).

