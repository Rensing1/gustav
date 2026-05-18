# Auth-Session-Continuity Reopened Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` and either `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GUSTAV stellt geschützte Browser-Sessions nach Reloads, Token-Ablauf und kurzzeitig fehlender BFF-Session wieder konsistent her, ohne Fachfehler anzuzeigen oder unsichere Auth-Fallbacks einzubauen.

**Architecture:** Der Fix bleibt ein kleiner Boundary-Refactor statt eines Auth-Service-Neubaus. SSR/BFF-Recovery läuft weiter über `backendRequest()` und `/auth/continue`; direkte Browser-`fetch()`-Aufrufe erhalten einen kleinen gemeinsamen 401-Helper. SvelteKit-Assets werden root-korrekt erzeugt, damit Hydration und Recovery überhaupt zuverlässig starten.

**Tech Stack:** SvelteKit, Vitest, Python/FastAPI-Backend, OpenAPI, pytest.

Referenz-Ticket: `docs/tickets/auth-session-continuity-reopened-session-bootstrap-asset-regression-2026-05-18.md`

## User Story

Als lernende Person oder Lehrkraft möchte ich geschützte GUSTAV-Seiten auch nach Reloads, Callback-Rückkehr, abgelaufenen Access Tokens oder kurzzeitig fehlender BFF-Session weiter nutzen können, solange Keycloak-SSO, BFF-Session oder App-Session den Zustand sicher wiederherstellen können. SvelteKit-Assets müssen dabei immer root-korrekt geladen werden, damit Hydration und Auth-Recovery überhaupt zuverlässig laufen.

## BDD-Szenarien

- Given eine geschützte `/auth`- oder tiefe `/learning/...`-Route, When SvelteKit HTML rendert, Then alle `_app/immutable/...`-Assets werden root-korrekt als `/_app/immutable/...` oder äquivalenter gültiger Root-Pfad referenziert.
- Given ein recoverbarer finaler Backend-`401` in einem SvelteKit-BFF-Proxy, When ein Browser-Referer oder aktueller Requestpfad sicher als In-App-Pfad ableitbar ist, Then startet GUSTAV `/auth/continue?redirect=<path>` statt den `401` als Fachfehler an den Browser zurückzugeben.
- Given ein Browser-Fetch für Learning-History, Modul-Content, Graph-Refresh, Upload-Intent oder Live-Polling erhält `401`, When der Browser noch auf einer geschützten GUSTAV-Seite steht, Then navigiert die UI kontrolliert nach `/auth/continue` und setzt keine generische Lern- oder Live-Fehlermeldung.
- Given ein non-idempotenter POST bleibt nach sicherem Token-Refresh unauthentifiziert, When Recovery nötig ist, Then wird der Request nicht automatisch erneut abgespielt; GUSTAV startet Recovery oder Login fail-closed.
- Given weder BFF- noch App-/SSO-Recovery möglich ist, When Auth fehlt oder ungültig ist, Then bleibt der normale Login-Redirect fail-closed aktiv.
- Given ein fehlerhafter verschachtelter Asset-Pfad wie `/auth/_app/...` oder `/learning/.../_app/...` entstehen würde, When Contract-Tests laufen, Then schlagen sie vor dem Release fehl.

## Recovery-Regel

Ein `401` ist in diesem Plan nur dann recoverbar, wenn alle Bedingungen erfüllt sind:

- Der Request stammt aus einem Browser-Kontext: SSR-Seitenaufruf, browser-facing BFF-Proxy oder direkter Browser-`fetch()` auf einer geschützten GUSTAV-Seite.
- Der Redirect-Zielpfad ist ein lokaler In-App-Pfad und wird aus `url.pathname + url.search`, aus `window.location.pathname + window.location.search` oder aus einem geprüften same-origin Referer abgeleitet.
- Die Recovery ist eine Navigation nach `/auth/continue?redirect=<path>` und kein automatisches erneutes Abspielen non-idempotenter Requests.
- Der Request befindet sich nicht bereits in einer erkannten Continuation-Schleife.

Alle anderen `401` bleiben API-artige Fehler: H5P-/Maschinenrouten, interne Jobs, externe oder unklare Referer, fehlender Browser-Kontext und nicht sicher ableitbare Redirects.

## Contract-First-Entwurf

- `api/openapi.yml` bleibt wire-kompatibel. Response-Bodies für `401` bleiben `{"error": "unauthenticated"}`.
- Für `/api/app/session-bootstrap` werden nur die direkt benötigten Auth-Failure-/Diagnose-Codes ergänzt oder konsolidiert:
  - `bff_session_missing`
  - `bff_session_read_empty`
  - `bff_session_token_refresh_failed`
  - `session_bootstrap_missing_bearer`
  - `session_bootstrap_invalid_bearer`
  - `continuation_loop_guard_triggered`
- Kein neuer Produktiv-Reason-Code für falsch erzeugte SvelteKit-Asset-Pfade. Die Asset-Regressionsursache wird über Konfiguration und Contract-Tests verhindert; Logging für tatsächliche 404-Assets bleibt niedrig-kardinal und tokenfrei, aber ohne neue Auth-Diagnosefläche.
- Keine Supabase/PostgreSQL-Migration ist nötig.
- Keine neue öffentliche Auth-API wird eingeführt. `/auth/continue` bleibt der zentrale Browser-BFF-Recovery-Einstieg.

## Umsetzung

### Arbeitspaket 1: Root-korrekte SvelteKit-Assets absichern

- Dateien: `frontend/svelte.config.js`, neuer oder bestehender Contract-Test in `frontend/src/routes/*contract.test.ts` oder `backend/tests/packaging/test_sveltekit_platform_contract.py`.
- Test-first:
  - Ein Contract-Test liest `frontend/svelte.config.js` und erwartet `paths: { relative: false }` im `kit`-Block.
  - Optional ein SSR-/Build-naher Test rendert oder prüft Build-Output so, dass keine Asset-Referenz mit `auth/_app/` oder `learning/.../_app/` akzeptiert wird.
- Minimaler Fix:
  - In `kit` `paths.relative = false` setzen.
  - Keine Caddy-Sonderroute für falsch erzeugte Assetpfade als Primärfix einführen.
- Acceptance:
  - `/auth` und tiefe Learning-Routen erzeugen root-korrekte SvelteKit-Asset-URLs.
  - Der Test schlägt ohne `paths.relative = false` fehl und ist danach grün.

### Arbeitspaket 2: BFF-Proxy-Recovery vervollständigen

- Dateien: `frontend/src/lib/server/bff-proxy.ts`, `frontend/src/lib/server/bff-proxy.test.ts`, BFF-Proxy-Routen unter `frontend/src/routes/live/.../+server.ts` und `frontend/src/routes/teaching/units/[unitId]/graph/.../+server.ts`.
- Test-first:
  - `proxyBackendRead()` ruft `backendRequest()` mit `authRedirectPath` auf, wenn ein sicherer Browserpfad gemäß Recovery-Regel übergeben wird.
  - `proxyBackendWrite()` gibt bei nicht-idempotenten Writes höchstens einen Recovery-Kontext weiter, löst aber kein zusätzliches automatisches Replay aus.
  - H5P-/interne Maschinenrouten ohne Browser-Kontext behalten API-artige `401`-Antworten.
- Minimaler Fix:
  - Proxy-Argumente um `authRedirectPath?: string` erweitern.
  - In Browser-facing Proxy-Routen bevorzugt `currentPath(url)` übergeben; Referer nur nutzen, wenn er same-origin ist und nur sein lokaler Pfad weitergereicht wird.
  - Keine vollständigen URLs loggen.
- Acceptance:
  - Live-Summary, Live-Detail, Live-Delta und Teaching-Graph-Proxies können finalen recoverbaren `401` über den bestehenden zentralen `backendRequest()`-Pfad nach `/auth/continue` schicken.

### Arbeitspaket 3: Zentrale Browser-Fetch-Recovery einführen

- Dateien: neuer Helper `frontend/src/lib/utils/browser-auth-recovery.ts` mit Test `frontend/src/lib/utils/browser-auth-recovery.test.ts`.
- Test-first:
  - Bei `Response.status === 401` und Browser-Kontext baut der Helper `/auth/continue?redirect=<pathname+search>` und ruft eine injizierbare Navigation-Funktion auf.
  - Der Helper gibt ein eindeutiges Ergebnis zurück, damit Caller danach keine generische Fehlermeldung setzen.
  - Nicht-401 bleibt unverändert.
- Minimaler Fix:
  - Helper ohne Abhängigkeit auf Tokens oder Cookies implementieren.
  - Redirect-Pfad nur aus `window.location.pathname + window.location.search` bilden.
- Acceptance:
  - Alle Browser-Fetch-Caller können 401 einheitlich behandeln.

### Arbeitspaket 4: Learning-Browser-Fetches umstellen

- Dateien: `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte`, `frontend/src/lib/utils/browser-storage-upload.ts`, zugehörige Tests `page-contract.test.ts`, `page.server.test.ts`, `browser-storage-upload.test.ts`.
- Test-first:
  - Learning-Graph-Fetch `401` startet Browser-Recovery statt `graph_fetch_failed_401`.
  - Modul-Content-Fetch `401` startet Browser-Recovery statt `Das Modul konnte nicht geladen werden.`.
  - Submission-History-Fetch `401` bleibt beim bisherigen Recovery-Verhalten, aber nutzt den zentralen Helper.
  - Upload-Intent-`401` startet Recovery und wird nicht als `Die Rückmeldung konnte nicht angefordert werden.` oder Upload-Fachfehler angezeigt.
- Minimaler Fix:
  - Direkte `fetch()`-Antworten vor Fachfehler-Mapping mit dem zentralen Recovery-Helper prüfen.
  - `prepareBrowserStorageUpload()` optional mit einem `onAuthRecovery`-Callback oder zentralem Helper ausstatten.
- Acceptance:
  - Recoverbare Auth-Fehler werden nicht mehr als fehlendes Modul, fehlende Abgabe, fehlendes Feedback oder Upload-Fachfehler angezeigt.

### Arbeitspaket 5: Live-Polling umstellen

- Dateien: `frontend/src/routes/live/+page.svelte`, `frontend/src/routes/live/page-interaction.test.ts`.
- Test-first:
  - `fetchSummaryState()`, `fetchDetailState()` und `fetchLiveDeltaState()` behandeln `401` über zentrale Browser-Recovery.
  - Controller-State bleibt bei Auth-Recovery unverändert; Cursor und Detail werden nicht als fachlich defekt markiert.
- Minimaler Fix:
  - Nach jedem Live-Fetch vor `throw new Error(...)` den Recovery-Helper aufrufen.
  - Bestehendes Verhalten für `204` Delta beibehalten.
- Acceptance:
  - Live-Polling verliert bei recoverbarem Auth-`401` nicht den bisherigen Dashboard-Zustand und navigiert kontrolliert zur Continuation.

### Arbeitspaket 6: Minimale tokenfreie Observability und Loop-Guard ergänzen

- Dateien: nur die bereits betroffenen Auth-Dateien anfassen: `frontend/src/lib/server/backend-auth.ts`, `frontend/src/lib/server/session.ts`, `frontend/src/lib/server/api.ts`, `backend/web/routes/app.py`, passende Tests in `frontend/src/lib/server/*.test.ts` und `backend/tests/test_session_bootstrap_api.py`.
- Test-first:
  - Missing bearer und invalid bearer werden als `session_bootstrap_missing_bearer` bzw. `session_bootstrap_invalid_bearer` klassifiziert.
  - BFF-session `204` wird als `bff_session_read_empty` oder `bff_session_missing` unterscheidbar.
  - Token-refresh-Fehler loggen `bff_session_token_refresh_failed`, ohne Tokenmaterial.
  - `/auth/continue` nutzt den bereits vorhandenen Continuation-Zustand oder einen kleinen neuen Guard, falls noch keiner existiert; erneuter Loop triggert `continuation_loop_guard_triggered` und fällt kontrolliert zum normalen Login zurück.
- Minimaler Fix:
  - Bestehende Logs nur dort auf die Ticket-Codes normalisieren, wo die Implementierung ohnehin angefasst wird.
  - Keine PII, keine Cookies, keine Session-IDs, keine vollständigen Query-URLs loggen.
- Acceptance:
  - Die neuen Fehlerklassen sind im Log unterscheidbar, ohne Secret- oder PII-Risiko.

### Arbeitspaket 7: OpenAPI und Dokumentation aktualisieren

- Dateien: `api/openapi.yml`, `docs/references/auth_sessions_and_cookies.md`, dieses Plandokument mit Ergebnisabschnitt nach Umsetzung.
- Test-first:
  - OpenAPI-Test erwartet die neuen `x-gustav-auth-failure-reason-codes`.
  - Referenz-/Contract-Test stellt sicher, dass die Recoverability-Regel und der Continuation-Loop-Guard dokumentiert sind.
- Minimaler Fix:
  - Nur Diagnose- und Referenztexte ändern; keine Response-Shape-Änderung.
- Acceptance:
  - API-Vertrag und Auth-Referenz beschreiben den neuen stabilisierten Zustand.

## Verifikation

Fokussiert:

- `npm test -- --run src/lib/server/api.test.ts src/lib/server/session.test.ts src/lib/server/bff-proxy.test.ts src/lib/utils/browser-auth-recovery.test.ts src/lib/utils/browser-storage-upload.test.ts src/routes/protected-page-bootstrap-contract.test.ts src/routes/learning/courses/[courseId]/units/[unitId]/page-contract.test.ts src/routes/live/page-interaction.test.ts`
- `.venv/bin/pytest -q backend/tests/test_session_bootstrap_api.py backend/tests/test_bff_session_internal_api.py backend/tests/test_openapi_session_bootstrap_contract.py backend/tests/packaging/test_sveltekit_platform_contract.py`

Abschluss:

- `npm run check`
- `make verify`

## Annahmen

- Dies ist ein stabilisierender Fix mit kleinem Boundary-Refactor, kein vollständiger Auth-Service-Neubau.
- Ein großer Auth-Refactor wird erst geplant, wenn die neuen Tests und Logs nach diesem Fix weiterhin neue systemische Bruchstellen zeigen.
- `session-bootstrap` bleibt bearer-only; keine unsichere Cookie-Fallback-Authentifizierung wird eingebaut.
- H5P- und interne Maschinenrouten behalten bewusst API-artige Fehlersemantik, solange sie keinen sicheren Browser-Redirect-Kontext haben.
- Non-idempotente POSTs werden nach finalem `401` nicht automatisch erneut abgespielt.
- Falls ein geplanter Reason-Code im bestehenden Code bereits gleichwertig vorhanden ist, wird er wiederverwendet statt umbenannt.
- Falls sich beim Testdesign zeigt, dass ein Arbeitspaket nur Dokumentation ohne Verhaltensänderung erzeugen würde, wird es nicht umgesetzt.

## Ergebnis

- SvelteKit erzeugt Assets root-relativ (`paths.relative = false`), damit geschützte Routen keine verschachtelten `_app`-Pfade mehr erhalten.
- Browser-facing BFF-Proxies reichen einen sicheren lokalen Redirect-Kontext an `backendRequest()` weiter; H5P-/Maschinenrouten bleiben API-artig.
- Direkte Browser-`fetch()`-Aufrufe in Learning und Live nutzen eine gemeinsame 401-Recovery nach `/auth/continue`.
- Auth-Diagnosecodes sind konsolidiert, tokenfrei dokumentiert und durch Tests abgesichert; der Continuation-Loop-Guard fällt kontrolliert zum sichtbaren Login zurück.
- Verifikation: fokussierte Frontend-/Backend-Tests grün, `npm run check` grün, `make verify` grün mit `OPENAI_E2E_ROOT=http://100.80.221.81:11434/api/v1 OPENAI_E2E_MODEL=Ministral-3-3B-Instruct-2512-GGUF`.
