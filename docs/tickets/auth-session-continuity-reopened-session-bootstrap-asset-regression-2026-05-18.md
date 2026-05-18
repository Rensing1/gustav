# Ticket: Auth-Session-Continuity erneut offen nach Session-Bootstrap- und Asset-Regression

Status: Open / Reopened after 2026-05-14 closure

## Summary

Die Auth-Session-Continuity-Fixes vom Mai haben das Unterrichtsproblem nicht vollständig behoben. In einer aktuellen Unterrichtssitzung am 2026-05-18 traten weiterhin gehäufte `401` auf `GET /api/app/session-bootstrap` auf. Gleichzeitig wurden SvelteKit-Assets unter falschen verschachtelten Pfaden angefragt, z. B. unter `/auth/_app/immutable/...` und unter tiefen `/learning/.../units/_app/...` Pfaden.

Das aktuelle Fehlerbild ist kein reiner Keycloak-Login-Fehler. Keycloak zeigte im geprüften Zeitraum nur normale Login-Eingabefehler. Die sichtbare Störung liegt weiterhin an der GUSTAV-Grenze zwischen Browser-BFF, App-Session, `session-bootstrap`, Recovery-Flow und Client-Hydration.

Dieses Ticket ersetzt nicht die geschlossenen Arbeiten, sondern öffnet den systemischen Auth-Continuity-Blocker erneut mit engerer Diagnose: Die bisherigen Fixes verbessern einzelne Server- und Loader-Pfade, decken aber offenbar nicht alle realen Browserpfade in Unterrichtssituationen ab.

## Current Evidence

PII-freie Auswertung der letzten 60 Minuten am 2026-05-18:

- Web/API:
  - `458x GET /api/app/session-bootstrap -> 401 Unauthorized`
  - `165x GET /api/app/session-bootstrap -> 200 OK`
  - `2x GET /api/me -> 401 Unauthorized`
  - `1x GET /backend-internal/app/bff-session -> 204 No Content`
  - `24x POST /api/app/session-sync -> 204 No Content`
- Repräsentatives Muster:
  - `/backend-internal/app/bff-session -> 204 No Content`
  - direkt danach `session-bootstrap -> 401`
  - direkt danach `/api/me -> 401`
  - später Recovery über `PUT /backend-internal/app/bff-session` und `POST /api/app/session-sync`
- Frontend:
  - `44x` fehlende SvelteKit-Assets unter falschen verschachtelten Pfaden
  - davon `22x` unter `/auth/_app/immutable/...`
  - davon `22x` unter `/learning/.../units/_app/immutable/...`
- Keycloak:
  - nur vereinzelte normale `LOGIN_ERROR`-Ereignisse für falsche oder nicht vorhandene Zugangsdaten
  - keine Hinweise auf einen systemischen Token-, Callback- oder IdP-Ausfall
- Infrastruktur:
  - relevante Container liefen stabil
  - keine Caddy-5xx im geprüften Zeitraum

Diese Zahlen sind bewusst aggregiert. Das Ticket enthält keine E-Mail-Adressen, IP-Adressen, Tokens, Cookies, Session-IDs, User-IDs oder privaten Ops-Logzeilen.

## Related History

Frühere Tickets und Pläne zeigen, dass das Problem schrittweise enger gefasst wurde:

- `docs/tickets/learning-upload-intents-401-session-expired-2025-12-16.md` dokumentierte frühe `401` im Upload-Intent-Flow und fehlende Recovery-UX.
- `docs/tickets/session-expired-on-submit-students-logout-2026-01-13.md` identifizierte die alte 1h-App-Session-TTL als Ursache für Abbrüche nach länger offenem Tab.
- `docs/tickets/auth-hardening-bff-lifetime-oidc-callback-and-keycloak-error-pages-2026-04-10.md` fasste strukturelle Auth-Probleme nach dem SvelteKit-Rollout zusammen: BFF-Lifetime, OIDC-Callback-Stabilität, Keycloak-Error-Pages und Observability.
- `docs/tickets/session-bootstrap-hard-reload-forces-relogin-with-active-sso-2026-04-21.md` isolierte den harten Reload mit aktiver Keycloak-SSO-Session als `session-bootstrap`-/BFF-Continuity-Problem.
- `docs/tickets/auth-session-continuity-classroom-regression-2026-05-11.md` wurde am 2026-05-14 geschlossen, nachdem zentrale 401-Recovery, `/auth/continue`, Keycloak-Template-Härtung und diagnostische Logs umgesetzt und getestet wurden.
- `docs/plan/2026-04-11-auth-hardening-after-svelte-refactor.md` modellierte getrennte BFF-Session-Lebensdauer und Access-Token-Lebensdauer.
- `docs/plan/2026-04-25-session-bootstrap-silent-continuity.md` plante Silent Continuation bei fehlendem Bootstrap und aktiver App-/SSO-Session.
- `docs/plan/2026-05-12-auth-session-continuity-classroom-regression.md` konkretisierte zentrale BFF-Recovery für geschützte Loader, Actions und Learning-History-Zustände.
- `docs/references/auth_sessions_and_cookies.md` beschreibt den aktuellen dreischichtigen Auth-Stack aus Keycloak, SvelteKit-BFF und FastAPI-App-Session.

## What Was Already Tried

1. App- und BFF-Session-TTL wurden aus dem alten 1h-Modell herausgelöst und auf unterrichtstaugliche 24h-Defaults gebracht.
2. BFF-Session und Access-Token-Ablauf wurden fachlich getrennt, damit ein abgelaufener Access Token nicht automatisch Logout bedeutet.
3. `session-bootstrap` blieb bewusst bearer-only, um keine unsichere Cookie-Fallback-Authentifizierung in einen Bearer-Endpunkt einzubauen.
4. SvelteKit erhielt zentrale Recovery-Semantik: einmaliger Refresh/Retry nach Backend-`401`, danach `/auth/continue` für recoverbare Mischzustände.
5. Protected Loader und Actions wurden auf diese Recovery-Semantik angepasst.
6. Keycloak-Error-, Info- und Expired-Templates wurden gegen fehlende optionale Werte wie `pageRedirectUri` gehärtet.
7. Diagnostische Logs wurden ergänzt, ohne Tokens oder Sessionmaterial zu protokollieren.
8. Tests wurden für zentrale Auth-/Session-Pfade, Keycloak-Templates und ausgewählte protected routes ergänzt.

## Why Those Attempts Were Insufficient

- Die TTL-Fixes adressierten das alte harte Ablaufen der App-Session. Das aktuelle Fehlerbild tritt aber trotz DB-backed Sessions und 24h-Modell auf.
- Silent Continuation deckte den bekannten Hard-Reload-Fall ab, aber die neuen Logmuster zeigen weiterhin `session-bootstrap`-401-Bursts, bevor Recovery zuverlässig greift.
- Die zentrale BFF-Recovery verbessert geschützte Server-Loader und Actions, deckt aber offenbar nicht alle Browserphasen ab: post-callback Hydration, SvelteKit data requests, clientseitige History-/Submission-Fetches und Asset-Fehler nach tiefen Routen.
- Die Keycloak-Template-Härtung war notwendig, erklärt aber das aktuelle Fehlerbild nicht. Keycloak war im geprüften Zeitraum nicht der primäre Auslöser.
- Die bisherigen Tests modellieren nicht ausreichend den realen Unterrichtspfad aus tiefer Learning-URL, Reload oder Callback, fehlerhafter Asset-Auflösung, transientem BFF-Session-`204`, `session-bootstrap`-401 und späterer Recovery.
- Die falschen `_app/immutable`-Pfade deuten auf ein separates Frontend-Build- oder Base-Path-/Link-Problem hin. Wenn Hydration-Assets fehlen, kann clientseitige Auth-Recovery nicht zuverlässig laufen, selbst wenn die serverseitigen Loader korrekt sind.

## Required Fix

### 1. Root-correct SvelteKit asset paths

SvelteKit-Assets müssen auf allen öffentlichen Routen root-korrekt ausgeliefert und angefragt werden.

Required behavior:

- `/auth` und `/auth/*` dürfen keine Assets unter `/auth/_app/immutable/...` anfordern.
- Tiefe Learning-Routen dürfen keine Assets unter `/learning/.../units/_app/immutable/...` anfordern.
- Asset-Links müssen stabil als `/_app/immutable/...` oder äquivalenter korrekt gerouteter Root-Pfad erscheinen.
- Der Fix darf keine Caddy- oder Backend-Sonderroute für falsch erzeugte Assetpfade als Primärlösung einführen; die Ursache muss in SvelteKit-Output, Base-Path, Link-Generierung oder HTML-Rewrite-Konfiguration behoben werden.

### 2. Auth recovery across all browser surfaces

Die Auth-Recovery darf nicht nur in repräsentativen Loadern funktionieren, sondern muss alle geschützten Browserpfade abdecken.

Required behavior:

- SSR-Loader und SvelteKit data requests verwenden dieselbe zentrale Recoverability-Entscheidung.
- Clientseitige Fetches für Submission-History, Feedback, Teaching-Live-Polling und verwandte Read-Modelle dürfen recoverbare `401` nicht in generische Fachfehler wie fehlendes Feedback oder fehlende Abgabe umwandeln.
- Nach einem erfolgreichen `/auth/callback` muss die erste Hydration denselben Sessionzustand sehen, den der Callback gerade eingerichtet hat.
- Non-idempotente POSTs dürfen weiterhin nicht automatisch erneut abgespielt werden. Nach sicherem Token-Refresh ist Recovery/Login statt Doppel-Submit erforderlich.

### 3. Treat BFF-session 204 as an explicit recoverable diagnostic state

`GET /backend-internal/app/bff-session -> 204` darf im Unterricht nicht als undifferenzierter Logout verschwinden.

Required behavior:

- Wenn die BFF-Session fehlt oder nicht lesbar ist, aber eine aktive App-Session oder aktive Keycloak-SSO plausibel ist, startet GUSTAV loop-geschützt `/auth/continue`.
- Wenn weder BFF- noch App-/SSO-Recovery möglich ist, bleibt der normale Login-Redirect fail-closed.
- Recovery-Loops müssen mit einem niedrigen, tokenfreien Reason-Code abbrechen und dann kontrolliert zum normalen Login gehen.

### 4. Token-free observability

Die Logs müssen die neue Fehlerklasse klar unterscheidbar machen.

Required reason codes:

- `bff_session_missing`
- `bff_session_read_empty`
- `bff_session_token_refresh_failed`
- `session_bootstrap_missing_bearer`
- `session_bootstrap_invalid_bearer`
- `app_session_active_bff_bearer_unavailable`
- `continuation_started`
- `continuation_loop_guard_triggered`
- `frontend_asset_path_misresolved`

Logging constraints:

- Keine Access Tokens, Refresh Tokens, ID Tokens.
- Keine Cookies, Session-IDs, User-IDs, E-Mail-Adressen oder IP-Adressen.
- Keine vollständigen URLs mit sensitiven Query-Parametern.
- Niedrig-kardinale Reason-Codes bevorzugen.

## Acceptance Criteria

1. Ein harter Reload auf einer tiefen Learning-Route lädt alle SvelteKit-Assets vom korrekten Root-Pfad und erzeugt keine verschachtelten `_app/immutable` 404s.
2. Ein recoverbarer `session-bootstrap`-401 nach Reload oder Callback führt zu `/auth/continue` oder erfolgreichem Retry, nicht zu generischer Fehlerseite, fehlenden Modulen, fehlender Abgabe oder sichtbarem Login-Bounce.
3. `bff-session -> 204` mit noch recoverbarem Zustand wird deterministisch behandelt und in Logs unterscheidbar.
4. Keycloak-SSO-aktive Nutzer müssen nicht erneut Credentials eingeben, wenn GUSTAV den Zustand sicher silent recovern kann.
5. Wirklich abgelaufene oder ungültige Sessions bleiben fail-closed und gehen kontrolliert zum normalen Login.
6. Die neuen Logs reichen zur Ursachenanalyse, ohne PII oder Secret-adjacent Daten zu enthalten.
7. Die Regression ist in Tests durch einen realistischen Browserpfad abgedeckt: Deep Link, Reload oder Callback, Asset-Hydration, `session-bootstrap`, clientseitige Daten-Fetches und Recovery.

## Test Scenarios

### Frontend

- Render `/auth` and verify all generated SvelteKit asset URLs point to `/_app/immutable/...` or another valid root-correct path.
- Render a deep `/learning/courses/:courseId/units/:unitId` route and verify no asset URL is relative to the learning path.
- Simulate a final recoverable `session-bootstrap` `401`; expect redirect to `/auth/continue?redirect=<current-path>`.
- Simulate post-callback hydration and verify immediate data requests use the freshly synchronized app/BFF session state.
- Simulate a recoverable `401` in Submission-History or Feedback fetches and verify the UI starts central recovery instead of showing missing feedback or generic load failure.
- Simulate a non-recoverable auth state and verify normal login redirect.

### Backend and BFF

- `session-bootstrap` remains bearer-only for invalid or missing bearers.
- Missing bearer, invalid bearer, BFF-session read empty, token-refresh failed and app-session-active/BFF-bearer-unavailable paths emit only reason codes.
- `session-sync` still replaces stale app sessions and remains `private, no-store`.
- BFF-session `204` with active app-session signal starts controlled continuation instead of falling through as anonymous state.
- Continuation loop guard prevents repeated silent redirects.

### Manual prod-like verification

1. Login as learner, open a deep modular learning route, reload, and verify the page hydrates without asset 404s or login bounce.
2. Submit work, open review/history, reload during or shortly after feedback generation, and verify submission state remains coherent.
3. Login as teacher, open live/teaching views with polling, reload, and verify polling continues without recoverable 401 surfacing as UI failure.
4. Let the access token become stale while app/BFF sessions remain valid, then reload and verify silent recovery.
5. Delete or expire both app and BFF sessions in a test environment and verify normal login redirect still happens.

## Rollout Notes

- This is an upstream product/auth fix, not a production-only patch.
- Do not push private ops paths, runbooks, scripts, `.env*`, infra deltas or secret-adjacent material.
- Keep evidence public-safe and aggregated.
- Validate with Safari/iPad-style browser behavior if possible, because several historical reports clustered around classroom browser reload and callback behavior.
