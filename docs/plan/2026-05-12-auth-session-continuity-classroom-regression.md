# Auth Session Continuity Classroom Regression

## User Story

Als lernende Person oder Lehrkraft möchte ich geschützte GUSTAV-Seiten nach Reloads, abgelaufenen Access Tokens oder transienten BFF-Session-Problemen ohne generische Fehlerseite weiter nutzen, solange Keycloak-SSO, BFF-Session oder App-Session den Zustand sicher wiederherstellen können.

## BDD-Szenarien

- Given ein abgelaufener Access Token und ein gültiger Refresh Token, When ein geschützter Backend-Request zuerst `401` liefert, Then refresht die BFF einmal, wiederholt den Request und zeigt keine Login- oder Fehlerseite.
- Given ein Parent-Bootstrap ist vorhanden, aber ein späterer Page-Loader-Request endet nach Retry mit `401`, When BFF- oder App-Session ein Recovery-Signal liefern, Then redirectet SvelteKit nach `/auth/continue?redirect=<current-path>`.
- Given eine gültige `gustav_session`, aber kein nutzbarer BFF-Bearer, When `session-bootstrap` oder ein BFF-Read-Model nicht authentifiziert werden kann, Then wird Silent Continuation gestartet.
- Given keine BFF-Session, keine gültige App-Session und kein recoverbares Signal, When ein geschützter Request `401` liefert, Then bleibt der normale Login-Redirect fail-closed aktiv.
- Given ungültige Bearer Tokens, When `/api/app/session-bootstrap` aufgerufen wird, Then bleibt die Antwort `401` und `private, no-store`; Logs enthalten nur einen Reason-Code, keine Tokens, Cookies, Session-IDs, User-IDs oder E-Mails.
- Given Keycloak rendert Error-, Info- oder Expired-Seiten ohne `pageRedirectUri`, Then die Templates rendern Recovery-Links ohne HTTP 500.
- Given eine abgeschlossene Nicht-H5P-Abgabe ist persistiert, aber die clientseitige Submission-History ist nach einem Reload leer, When die lernende Person den Review-Bereich öffnet, Then lädt die UI die History nach und zeigt Arbeit, Feedback und strukturierte Auswertung statt eines Missing-Feedback-Zustands.
- Given ein Submission-History-Request erhält einen recoverbaren Auth-`401`, When zentrale Session-Continuity möglich ist, Then folgt die UI dem `/auth/continue`-Pfad statt `Die Abgabe konnte nicht geladen werden.` als generische Lernfehlermeldung zu setzen.

## Contract-First-Entwurf

- `api/openapi.yml` dokumentiert für `/api/app/session-bootstrap` die nicht-wire-brechenden Auth-Failure-Reason-Codes: `missing_bearer`, `invalid_bearer`, `bff_session_missing`, `token_refresh_failed`, `app_session_active_bff_bearer_unavailable`.
- Der Response-Body bleibt kompatibel: `{"error": "unauthenticated"}`.
- `GET /auth/continue` bleibt der zentrale Browser-BFF-Recovery-Einstieg mit sicherem In-App-`redirect`, PKCE, `state`, `nonce` und `prompt=none`.
- Keine Supabase/PostgreSQL-Migration ist nötig, weil keine Schemaänderung erfolgt.

## Umsetzung

- Das neue Ticket `docs/tickets/learning-feedback-history-reload-generic-error-2026-05-12.md` ist Teil dieses Auth-Continuity-Plans, soweit es recoverbare Auth-Fehler und Reload-History-Zustände der Learning-UI betrifft. Upload-Signature-Validation und Provider-Rate-Limit-Handling bleiben eigene Folgearbeiten.
- In `frontend/src/lib/server/api.ts` die Optionen von `backendRequest()` und `requireBackendJson()` um `authRedirectPath?: string` erweitern.
- Nach dem bestehenden einmaligen Force-Refresh-Retry entscheidet ein zentraler Helper:
  - BFF-Session-Cookie vorhanden oder `readAppSessionActive()` true: `302` zu `/auth/continue?redirect=...`
  - kein recoverbares Signal: `302` zu `/?redirect=...`
  - kein `authRedirectPath`: bisheriges Verhalten unverändert, wichtig für interne Proxy- und H5P-Routen.
- Geschützte SvelteKit-Loader und Actions geben `authRedirectPath: currentPath(url)` an ihre Backend-Aufrufe weiter.
- Lokale Catch-Blöcke dürfen `401` nicht mehr in generische `error(...)`-Seiten oder `fail(...)`-Meldungen umwandeln; nicht-Auth-Fehler wie `404`, `403`, `409` und `5xx` behalten ihre bestehende Semantik.
- In `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte` die Submission-History-Reload-Logik absichern: `toggleReviewPanel(...)` und `loadSubmissionHistory(...)` dürfen leere lokale `submissionHistoryByTask`-State nicht als fehlendes Feedback interpretieren, wenn Aufgaben-/Submission-Metadaten auf eine abgeschlossene Abgabe hindeuten. Sie laden die History nach, zeigen währenddessen einen Lade- oder Retry-Zustand und unterscheiden anschließend zwischen `not_loaded`, `pending`, `failed` und wirklich `unavailable`.
- `syncModularWorkspaceUrl(...)` darf einen bewusst geöffneten Review-/History-Zustand nicht versehentlich beim Workspace-Sync verlieren. Wenn eine History-Ansicht per URL oder UI geöffnet ist, bleibt der relevante `history`-Kontext so erhalten, dass ein Reload die Review-Daten wieder laden kann.
- Clientseitige History-Fetches müssen recoverbare Auth-Antworten zentral behandeln. Wenn ein History-Request nach Token-Refresh weiterhin Auth-Recovery braucht, navigiert die UI kontrolliert in den Continuation-Flow und setzt keine generische Learning-Fehlermeldung.
- Non-idempotente POST-Actions werden nicht automatisch erneut abgespielt. Es gibt nur den bestehenden sicheren Request-Retry nach Token-Refresh; ein danach verbleibendes `401` startet Recovery oder Login, um Doppelabgaben zu vermeiden.
- Auth-Observability loggt tokenfreie, niedrig-kardinale Reason-Codes. Keine Rohwerte aus `Authorization`, Cookies, Session-IDs, User-Claims oder Request-URLs mit Query loggen.
- `keycloak/themes/gustav/login/error.ftl`, `keycloak/themes/gustav/login/info.ftl` und `keycloak/themes/gustav/login/login-page-expired.ftl` normalisieren `pageRedirectUri` über lokale, `??`-geschützte Variablen, bevor Werte an `_gustav_error_components.ftl` übergeben werden.
- Shared Keycloak-Helper bleiben defensiv bei fehlenden Argumenten.

## Testplan

- Frontend unit tests zuerst rot schreiben:
  - `backendRequest()` refresht bei erstem `401` und liefert danach Erfolg.
  - finaler `401` mit BFF-Cookie oder aktiver App-Session redirectet zu `/auth/continue`.
  - finaler `401` ohne recoverbares Signal redirectet zum Login.
  - ohne `authRedirectPath` bleibt ein `401` als Response erhalten.
- Frontend route/action regression tests:
  - Learning course/unit loader: späterer `requireBackendJson()`-`401` nach Parent-Bootstrap führt zu `/auth/continue`, nicht zu generischer Lernraum-Fehlerseite.
  - Learning submission action: finaler Auth-`401` redirectet zur Continuation statt `fail()` mit Abgabefehler.
  - Learning unit UI: abgeschlossene Filius- oder andere Nicht-H5P-Abgabe, `submissionHistoryByTask` nach Reload leer, Review-Panel lädt History nach und rendert Feedback sowie strukturierte Auswertung.
  - Learning unit UI: recoverbarer Auth-Fehler beim History-Fetch startet den zentralen Continuation-Pfad und setzt nicht `Die Abgabe konnte nicht geladen werden.`.
  - Learning unit UI: nicht recoverbarer History-Fehler zeigt eine spezifische Lade-/Retry-Meldung und behauptet nicht, persistiertes Feedback sei nicht vorhanden.
  - Profile/teaching/live/diagnostics smoke tests sichern die neue Option auf repräsentativen geschützten Loadern.
- Backend tests:
  - `/api/app/session-bootstrap` bleibt bearer-only, auch mit `gustav_session`.
  - missing/invalid bearer loggt passende Reason-Codes und keine sensiblen Werte.
  - `session-sync` ersetzt stale App-Sessions weiterhin.
  - DB-backed BFF-Sessions mit abgelaufenem Access Token und nicht abgelaufener Session bleiben refreshbar.
- Keycloak tests:
  - Templates enthalten nur guarded references auf `pageRedirectUri`.
  - Helper tolerieren fehlende Argumente.
  - Error-, Info- und Expired-Templates behalten Recovery-Links und locale footer.

## Verifikation

- `npm test -- --run <focused frontend auth/session route tests>`
- `.venv/bin/pytest -q backend/tests/test_session_bootstrap_api.py backend/tests/test_session_sync_api.py backend/tests/test_bff_session_internal_api.py backend/tests/test_db_bff_session_store.py backend/tests/test_keycloak_theme_files.py`
- `make verify`

## Annahmen

- Umsetzung erfolgt als ein vollständiger PR, weil der Ticketzuschnitt als finaler Systemblocker definiert ist.
- Keine Secrets, PII, Ops-Logs oder produktionsspezifischen Artefakte werden in Repo-Dateien übernommen.
- Recovery-Signale bleiben konservativ: Ein vorhandenes BFF-Cookie darf Silent Continuation auslösen, aber nicht Backend-Zugriff authentifizieren.
- Öffentliche API-Responses bleiben kompatibel; Observability läuft über Logs und OpenAPI-Beschreibung, nicht über neue Fehlerdetails im Client-Response.
- Das neue Feedback-History-Ticket wird nur in seinem Auth-/Reload-Anteil in diesem Plan umgesetzt. Validierung falscher Upload-Inhalte und Provider-Rate-Limit-Behandlung bleiben getrennte Tickets, damit der Auth-Fix nicht mit Worker- oder Upload-Policy-Änderungen vermischt wird.
