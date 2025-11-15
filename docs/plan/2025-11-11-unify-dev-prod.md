# Plan: Einheitliche Umgebung (dev = prod)

Datum: 2025-11-11
Owner: Felix / GUSTAV Team
Status: Geplant (vor Umsetzung)

Ziel
- Alle Laufzeitbedingungen sind prod-like, auch lokal: HTTPS, strikte CSRF, sichere Cookies, konsequente Guards. Keine „Dev-Sonderwege“.

Nicht-Ziele
- Keine Schema-/RLS-Änderungen. Keine große Refaktorierung der Domain-Logik.

Rahmenprinzipien
- Security-first, Contract-First, TDD minimal, KISS, Lokal = Prod.

Änderungspakete (geplant)
1) Reverse Proxy & HTTPS lokal
   - Caddy auf TLS umstellen (`tls internal`), Hosts: `https://app.localhost:8100`, `https://id.localhost:8100`.
   - `.env.example` und `docker-compose.yml` auf HTTPS-URLs für `WEB_BASE`, `KC_PUBLIC_BASE_URL` anheben.

2) CSRF konsequent strikt
   - Alle Schreib-Endpoints nutzen nur noch „strict same-origin“: Origin/Referer Pflicht und Host/Port/Scheme-Match.
   - Feature-Toggles wie `STRICT_CSRF_*` entfernen oder standardmäßig strikt.

3) Cookies immer strikt
   - `Secure` und `SameSite=Strict` immer setzen, keine lokalen Relax-Ausnahmen.

4) Prod-Guard immer aktiv
   - Start bricht bei riskanten Settings ab: Dummy Service-Role-Key, fehlendes KC-Secret, `sslmode=disable`, Login als `gustav_limited`, `AI_BACKEND=stub`, `REQUIRE_STORAGE_VERIFY!=true`.
   - `AUTO_CREATE_STORAGE_BUCKETS=true` grundsätzlich verbieten.

5) Dev-Features deaktiviert
   - `ENABLE_DEV_UPLOAD_STUB=false` und `ENABLE_STORAGE_UPLOAD_PROXY=false` per Default. Nutzung nur explizit in Tests.
   - OpenAPI: Dev-only Pfade mit `x-internal: true` markieren (Public-Export filtert sie aus).

6) Compose & ENV auf Prod-Parität
   - Entferne Host-Sonderpfade (z. B. `host.docker.internal`), nutze interne Service-Hosts.
   - Standard-Ports/Secrets/Timeouts prod-like.
   - AI-Defaults vereinheitlicht (Vision=`qwen2.5vl:3b`, Feedback=`gpt-oss:latest`).

Tests (TDD-Mindestumfang)
- CSRF strikt
  - Given kein Origin/Referer; When POST/PUT auf Schreib-Endpoint; Then 403 mit `detail=csrf_violation` (https-Origin im Test).
  - Given `Origin=https://app.localhost:8100`; When POST/PUT; Then 200.
- Cookies
  - Given Login; When Set-Cookie; Then enthält `Secure; SameSite=Strict` (auch in Tests mit `base_url=https://local`).
- Prod-Guard
  - Given riskante Env (Dummy Service-Role, KC-Secret Placeholder, sslmode=disable, AI stub, REQUIRE_STORAGE_VERIFY=false, AUTO_CREATE_STORAGE_BUCKETS=true); When Startup-Guard; Then `SystemExit`.
- Dev-Features aus
  - Given Upload-Stub/Proxy deaktiviert; When Aufruf; Then 404.
- Diagnose-Header entfernt
  - Given Fehler (CSRF/Permission); When Response; Then keine `X-*-Diag`-Header; optional File-Logging via `CSRF_DIAG_LOG`.
- Compose-Validierung
  - `make docker-validate` läuft fehlerfrei.

Schritte/Sequenz
1) TLS lokal: Caddyfile anpassen, Compose/ENV auf HTTPS; Doku aktualisieren.
2) CSRF vereinheitlichen: `_require_strict_same_origin` überall erzwingen; Toggles entfernen/ignorieren. Tests anpassen (https-Origin).
3) Cookies härten: lokale Relax-Logik entfernen; Tests auf `https`-BaseURL umstellen; HSTS überall aktivieren.
4) Prod-Guard verschärfen: Dev-Ausnahmen entfernen; AUTO_CREATE_STORAGE_BUCKETS in Guard verbieten. Tests ergänzen. Diagnose-Header aus Responses entfernen.
5) Dev-Features standardmäßig aus: Defaults angleichen; bestehende Tests setzen Flags explizit.
6) Compose säubern: interne Hosts statt `host.docker.internal`; DSN-Fehler fix; docker-validate in CI nutzen.

Akzeptanzkriterien
- App startet lokal nur mit sicheren Settings (Guard). 
- Alle Schreib-APIs erfordern Origin/Referer (403 sonst). 
- Cookies immer Secure/Strict; Tests nutzen `https`-BaseURL. 
- Dev-Endpunkte liefern 404 ohne expliziten Toggle. 
- `docker compose config` erfolgreich; OpenAPI dev-only = `x-internal`.

Risiken & Mitigation
- HTTPS lokal: Browser-Zertifikate (Caddy `tls internal`) → kurzer Onboarding-Hinweis. 
- Tests: Anpassung BaseURL auf `https` nötig → planmäßig umstellen. 
- Compose-Netz: Umstellung auf Service-Hosts → Smoke-Test der Services.

Rollback-Plan
- Toggles kurzfristig reaktivieren, falls Blocker auftreten (nur lokal). 
- Caddy zurück auf HTTP (nur zur Fehlersuche) – nicht empfohlen.

---

Erweiterung: BDD-Szenarien (Given-When-Then)

1) CSRF strikt (alle Schreib-Endpoints)
- Given kein Origin/Referer-Header; When POST auf `/api/learning/.../submissions`; Then 403 + `{detail: csrf_violation}`.
- Given `Origin=https://app.localhost:8100` (match); When POST; Then 200.
- Given `Origin=https://evil.localhost:8100`; When POST; Then 403.

2) Cookies immer sicher
- Given erfolgreicher Login; When Response setzt Session-Cookie; Then `Set-Cookie` enthält `HttpOnly; Secure; SameSite=Strict`.
- Given lokaler Test-Client; When Login; Then Cookie bleibt `Secure; SameSite=Strict` (keine lokalen Ausnahmen).

3) Prod-Guard immer aktiv
- Given `SUPABASE_SERVICE_ROLE_KEY=DUMMY_DO_NOT_USE`; When App-Start; Then `SystemExit` mit klarer Fehlermeldung.
- Given `DATABASE_URL=...sslmode=disable...`; When App-Start; Then `SystemExit`.
- Given `AI_BACKEND=stub`; When App-Start; Then `SystemExit`.
- Given `AUTO_CREATE_STORAGE_BUCKETS=true`; When App-Start; Then `SystemExit`.
- Given `ENABLE_DEV_UPLOAD_STUB=true` oder `ENABLE_STORAGE_UPLOAD_PROXY=true`; When App-Start; Then `SystemExit`.

4) Dev-Features aus
- Given Upload-Stub/Proxy disabled; When Aufruf Dev-only Pfad; Then 404.

5) HTTPS lokal (Caddy)
- Given Caddy mit `tls internal`; When Aufruf `https://app.localhost:8100/health`; Then 200 mit HSTS gesetzt (immer aktiv, dev = prod).

Konkrete Änderungen (Dateien, exemplarisch)
- reverse-proxy/Caddyfile:1 ff. — VHosts auf TLS umstellen (`app.localhost:443`, `id.localhost:443`, `tls internal`).
- docker-compose.yml: caddy.ports → `8100:443`; web.env `WEB_BASE`, `KC_PUBLIC_BASE_URL` → `https`; Keycloak `KC_HOSTNAME_URL/_ADMIN_URL` → `https`.
- .env.example: `WEB_BASE`, `KC_PUBLIC_BASE_URL` → `https`; Hinweis „lokal = prod“ ergänzen.
- backend/web/config.py: `ensure_secure_config_on_startup()` ohne `GUSTAV_ENV`-Unterscheidung; Guard für `AUTO_CREATE_STORAGE_BUCKETS` ergänzen.
- backend/web/main.py: `_set_session_cookie()` lokale Relax-Logik entfernen; HSTS immer setzen; Tests aktualisieren.
- backend/web/routes/teaching.py: `_csrf_guard()` immer strikt; `STRICT_CSRF_TEACHING` ignorieren/entfernen.
- backend/web/routes/learning.py: `STRICT_CSRF_SUBMISSIONS` entfernen; immer `_require_strict_same_origin()`; Dev-Fallback löschen; Diagnose-Header nur intern oder entfernen.
- api/openapi.yml: Dev-only Pfade `x-internal: true` (bereits begonnen, prüfen).
- Makefile: `docker-validate` in CI verwenden (bereits vorhanden).

TDD-Fahrplan (Sequenz der Tests zuerst)
1) Tests für Prod-Guard erweitern (AUTO_CREATE_STORAGE_BUCKETS, AI_BACKEND, Service-Role, sslmode, Upload-Flags, REQUIRE_STORAGE_VERIFY) → `backend/tests/test_config_security.py`.
2) CSRF-Tests umstellen auf https + strikt → `backend/tests/test_learning_submissions_prod_csrf.py`, `backend/tests/test_teaching_csrf.py`.
3) Cookie-Header-Tests anpassen → `backend/tests/test_auth_cookies.py` (neu/erweitern): prüfe `Secure; SameSite=Strict`.
4) Reverse-Proxy Smoke-Test (optional) → kleiner `requests`-Test gegen `https://app.localhost:8100/health` in `docs/tests` oder als Make-Check.
5) Compose-Validierung in CI (Make-Target) sicherstellen.

Risikoeinschätzung (Test-/Bug-Impact)
- Gesamt: Mittel. Größte Änderungen betreffen Header/HTTPS-Annamen in Tests.
- Betroffen: CSRF- und Cookie-Tests (moderate Anpassungen); lokale HTTP-BaseURLs.
- Backend-Logik selbst: geringes Risiko (keine DB/Schemas), aber Start-Guards können fehlschlagen → frühe, klare Fehlermeldungen.

Offene Punkte/Fragen (kurz)
1) Sollen wir HSTS auch lokal immer setzen (empfohlen), trotz selbstsigniertem Cert? 
2) Sollen Diagnose-Header (`X-CSRF-Diag`) komplett entfernt werden (empfohlen) oder nur in Testläufen aktivierbar bleiben?
3) Keycloak: HTTPS-Forward ausschließlich über Caddy oder zusätzlich KC-intern TLS (komplexer)? Empfehlung: nur Caddy TLS.

Definition of Done (erweitert)
- Alle oben genannten Tests grün; kein Test nutzt mehr `http://`-BaseURLs.
- App startet lokal nur mit sicheren Settings (Guard) und Caddy TLS.
- Cookies sind strikt; CSRF strikt; Dev-only Pfade sind intern/404.
- `make docker-validate` sauber; OpenAPI-Export ohne Dev-only für Public.
