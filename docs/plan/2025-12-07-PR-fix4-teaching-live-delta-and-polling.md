# 2025-12-07 – PR-Fix 4: Teaching-Live-Delta-Errorhandling & Polling-Status

## Kontext

Der bestehende PR für die Teaching-Live-Ansicht (Auto-Polling, Tabs ohne Inline-JS, Cursor-Semantik) wurde im Review überprüft. Das aktuelle Follow-up zielt darauf ab, kleinere Robustheits- und UX-Punkte nachzuziehen, ohne den API-Vertrag oder das DB-Schema zu ändern.

Betroffene Bereiche:

- `backend/web/main.py`
  - `_normalize_changed_at_to_utc`
  - `teaching_unit_live_matrix_delta_partial`
- `backend/web/static/js/gustav.js`
  - Live-Statusanzeige (`updateLiveStatusTimestamp`)
  - Fehleranzeige bei HTMX-Events
- Tests:
  - `backend/tests/test_teaching_live_delta_utils.py`
  - `backend/tests/test_teaching_live_unit_ui_ssr.py`
  - `backend/tests/test_teaching_live_js_behaviour.py`

## Ziele

- Delta-SSR-Fragment:
  - Fehler im internen JSON-Delta-Endpoint nicht mehr als „keine Änderungen“ (204) verschleiern.
  - Klare, private Cache-Header auch auf Fehlerpfaden sicherstellen.
  - Cursor-Timestamp-Normalisierung defensiv, aber klar typisiert halten.
- Live-Status-UI:
  - Fehlerzustand („Verbindung unterbrochen“) visuell zurücksetzen, sobald wieder ein gültiger Cursor ankommt.
  - Verhalten über JS-Unit-Tests (Node-VM) abdecken.

## Änderungen (High-Level)

1. **Delta-Endpoint – Errorhandling**
   - `httpx.RequestError` beim Aufruf des internen JSON-Delta-Endpoints führt zu `502 Bad Gateway` mit `Cache-Control: private, no-store` und `Vary: Origin`.
   - Nicht-200-Upstream-Statuscodes (z. B. 503) werden durchgereicht, ebenfalls mit privaten Cache-Headern.
   - JSON-Decode-Fehler (`ValueError`) im Delta-Response führen zu `502` statt stummem 204.
   - Timestamp-Normalisierung `_normalize_changed_at_to_utc` fängt gezielt `TypeError`/`ValueError` ab.

2. **Live-Status – Polling-Recovery**
   - `updateLiveStatusTimestamp` entfernt die Klasse `text-danger`, sobald ein neuer, parsebarer Cursor verarbeitet wurde.
   - Status-Text bleibt weiterhin deutsch („Letzte Aktualisierung: …“); Toaster-Meldungen bleiben vorerst englisch (bewusste Inkonsistenz, bis i18n geklärt ist).

3. **Tests**
   - Neue JS-Behaviour-Unit: `test_teaching_live_status_clears_error_on_success` (Node-VM).
   - Neue SSR-Tests:
     - `test_delta_fragment_propagates_upstream_http_error_with_private_cache`
     - `test_delta_fragment_returns_502_on_upstream_request_error`

## Nicht-Ziele

- Keine Änderung am API-Vertrag (`api/openapi.yml`) oder an Supabase-Migrationen.
- Keine Anpassung der CSP-Policy selbst; Frontend verhält sich nur robuster innerhalb der bestehenden Policy.

