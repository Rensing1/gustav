Title: Schüler werden beim Abgeben abgemeldet (App-Session läuft nach 1h ab trotz Keycloak-SSO=1 Tag)

Status: Open

Problem:
- Schüler:innen berichten, dass sie beim Absenden von Aufgabenlösungen (insb. nach länger offenem Tab/Unterricht) „abgemeldet“ werden und der aktuelle Fortschritt/Entwurf verloren geht.
- In Keycloak sind `SSO Session Idle` und `Client Session Idle` auf 1 Tag gesetzt; trotzdem tritt das Problem deutlich früher auf.

Root Cause (wahrscheinlich):
- GUSTAV nutzt neben der Keycloak-Session eine eigene App-Session (Cookie `gustav_session`, serverseitig in `public.app_sessions` bei `SESSIONS_BACKEND=db`).
- Diese App-Session hat derzeit eine harte Standard-TTL von 3600s (1h) und läuft unabhängig von Keycloak ab:
  - `backend/identity_access/stores.py` → `ttl_seconds: int = 3600`
  - `backend/identity_access/stores_db.py` → `ttl_seconds: int = 3600`, `expires_at = now + ttl_seconds`
  - `backend/web/main.py` → beim Login Callback wird `max_age = sess.ttl_seconds` gesetzt (in `prod`), d. h. Cookie und DB-Session enden nach ~1h.
- Wenn die App-Session abläuft, beantwortet die Auth-Middleware geschützte Requests mit `401` bzw. Redirect auf `/auth/login`. Bei Submit/Upload führt das zu Abbruch und Verlust des UI-Zustands.

Beobachtung / Evidenz:
- Web-Logs zeigen `401 Unauthorized` bei `POST /learning/.../submit` (korreliert mit „Tab lange offen → Abgabe“).
- Keycloak-Realm-Settings sind nicht der Engpass (aus dem laufenden System ausgelesen):
  - `ssoSessionIdleTimeout=86400` (1 Tag)
  - `clientSessionIdleTimeout=86400` (1 Tag)
  - `ssoSessionMaxLifespan=604800` (7 Tage)
  - `accessTokenLifespan=300` (5 Minuten; hier sekundär, da App keinen Refresh nutzt)

Impact:
- Abgaben gehen verloren oder müssen neu erstellt werden.
- Supportaufwand steigt, Frust im Unterricht (typischer Use-Case: lange offene Tabs).

Workaround:
- Seite neu laden bzw. neu einloggen und erneut abgeben (falls Entwurf nicht verloren).

Proposed Fix (Upstream; Code + UX):
1) App-Session-TTL erhöhen und konfigurierbar machen (z. B. `APP_SESSION_TTL_SECONDS`, Default 8–24h für Schule).
2) Optional: Sliding Sessions (TTL bei Aktivität verlängern) statt fixem Ablauf.
3) Frontend/UX: Bei `401` im Upload-/Submit-Flow klarer Hinweis „Sitzung abgelaufen“ + Auto-Redirect auf `/auth/login` mit Rücksprung; Entwürfe lokal puffern (localStorage) und nach Re-Login wiederherstellen/resubmitten.
   - Implementation detail: prefer `sessionStorage` (tab-scoped) for privacy and to avoid stale drafts on shared devices.
   - Return-to detail: for non-HTMX POSTs, prefer the `Referer` page path (not the POST endpoint path) to avoid a 405 after login.
4) Observability: Metrik/Logfilter für `401` bei `POST /learning/**/submit` und `POST /api/learning/**/upload-intents`.

Acceptance Criteria:
- Nach >2h in geöffnetem Tab kann ein:e Schüler:in weiterhin abgeben, ohne Loginverlust (oder erhält eine klare Re-Login-Recovery ohne Datenverlust).
- `401`-Fehler führen nicht mehr zu „stillem“ Abbruch; UI zeigt handlungsfähige Recovery.

Related:
- `docs/tickets/learning-upload-intents-401-session-expired-2025-12-16.md` (401 im Upload-Intent-Flow; gleiche Grundursache: App-Session-TTL/Recovery)
