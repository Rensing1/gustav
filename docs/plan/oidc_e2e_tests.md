# Plan: Automatisierte Keycloak-E2E-Tests

Stand: 15.10.2025, erweitert um Supabase-Integration und zusätzliche Szenarien.

## User Story
Als Produktverantwortlicher (Felix) möchte ich, dass die OIDC-Anmeldung über Keycloak im CI reproduzierbar getestet wird, damit wir Regressionen beim Zusammenspiel von Frontend-Adapter, Keycloak und Session-Management frühzeitig entdecken.

## Testidee
- End-to-End-Pytest-Session, die docker-compose nutzt (Keycloak + Webdienst).
- Fokus auf Login mit echtem Token-Austausch, Session-Cookie-Prüfung, Logout und Fehlerpfad bei gestoppter IdP-Instanz.
- Tests laufen optional (Marker `e2e`) und werden nur in Pipelines mit Docker-Unterstützung aktiviert.

## BDD-Szenarien (Given-When-Then)
1. **Keycloak Happy Path (Teacher)**
   - Given Keycloak läuft und Demo-User `teacher1` existiert (Realm-Import)  
   - When `/auth/login` aufgerufen, Authorization Code Flow vollständig durchlaufen  
   - Then `/api/me` liefert 200 inkl. Rolle `["teacher"]`, Session-Cookie besitzt produktive Flags.

2. **Keycloak Falsche Credentials**
   - Given Keycloak läuft  
   - When Login mit falschem Passwort versucht wird  
   - Then Keycloak liefert Fehler, `/api/me` bleibt 401 und es existiert kein Session-Cookie.

3. **Keycloak Mehrrollen-User**
   - Given User `admin1` mit Rollen `["teacher", "admin"]`  
   - When Login erfolgreich  
   - Then `/api/me` enthält beide Rollen; unbekannte Rollen werden verworfen.

4. **Logout**
   - Given gültige Session nach erfolgreichem Login  
   - When `/auth/logout` (POST) aufgerufen  
   - Then Cookie wird gelöscht und `/api/me` liefert 401.

5. **IdP-Ausfall während Callback**
   - Given Keycloak wird nach Erhalt des Codes gestoppt  
   - When Callback erneut aufgerufen  
   - Then FastAPI antwortet mit 400, keine Cookies werden gesetzt.

6. **Session-Reuse**
   - Given Login erfolgreich durchgeführt  
   - When `/auth/login` ohne Logout erneut aufgerufen  
   - Then Redirect geht direkt nach `/` (kein erneuter Keycloak-Loop).

7. **Supabase Email/Password Login**
   - Given Supabase Auth-Service läuft mit Testuser `student1`  
   - When Supabase-Login durchgeführt (GoTrue API) und Session in GUSTAV übernommen  
   - Then `/api/me` liefert 200, Session enthält Supabase-Token, RLS-Probe (z.B. geschütztes API) funktioniert.

8. **Supabase Fehlgeschlagener Login**
   - Given Supabase läuft  
   - When falsche Credentials verwendet werden  
   - Then Supabase liefert 400/401, GUSTAV setzt keine Session.

9. **Supabase/Keycloak Fallback**
   - Given Keycloak ist gestoppt, Supabase läuft  
   - When Benutzer meldet sich über Supabase an  
   - Then GUSTAV erlaubt Login via Supabase, `/api/me` zeigt Supabase-Rolle (`student`).

10. **Supabase Token Refresh**
    - Given Supabase Session kurz vor Ablauf  
    - When Refresh-Endpoint aufgerufen  
    - Then neues Token wird gespeichert, alte Session invalidiert.

## Technische Umsetzung
- Neue Pytest-Datei `backend/tests_e2e/test_identity_end_to_end.py`.
- Marker `@pytest.mark.e2e` (Tests laufen standardmäßig immer, aber Marker erlaubt gezieltes Ausführen).
- `docker compose` startet Services: `web`, `keycloak`, `supabase-auth`, `supabase-db`, `supabase-studio` (falls nötig), zusätzlich ein `tests`-Service, der Pytest im selben Compose-Netzwerk ausführt.
- Dienste werden per Service-Namen adressiert (`http://web:8000`, `http://keycloak:8080`, `http://supabase-auth:9999`). Kein Host-Rewrite mehr nötig.
- Health-Check-Fixture prüft Liveness (Keycloak `/realms/master/.well-known/openid-configuration`, Supabase `/auth/v1/health`, Web `/health`) mit Retries.
- Testnutzer werden via Infrastruktur-Seed angelegt:
  - Keycloak: Demo-Accounts (`teacher1`, `admin1`) direkt im Realm-JSON ohne Required Actions.
  - Supabase: SQL-Seed in `supabase/seed/e2e_identity.sql` (erstellt `student1` inkl. Rolle, RLS-Testdaten).
- Nach jedem Szenario: Sessions invalidieren (`/auth/logout` + Supabase `sign_out`), Dienste ggf. zurücksetzen (Keycloak `start` nach Ausfalltest).
- Relevante Supabase-Dokumente (Auth API, PostgREST, RLS) unter https://supabase.com/docs/auth, https://supabase.com/docs/guides/database, werden im Plan verlinkt.

## Offene Fragen / TODO
- Supabase CLI in CI: Wird `supabase start` genutzt oder individuelle Container?  
- Wie werden Supabase-Service-Secrets sicher verwaltet (GitHub Actions Secrets vs. `.env.e2e`)?  
- Token-Refresh-Test: realer Ablauf (Timer vs. künstliches Manipulieren der `expires_at`-Claims).  
- Logging/Artefakte: Keycloak- und Supabase-Logs bei Testfehlern sammeln.

## Nächste Schritte
1. Supabase-Architektur studieren (Auth, RLS, CLI) und erforderliche Seeds/Config definieren.
2. docker-compose-Datei um Supabase-Services und Test-Runner erweitern; Health-Wait-Skripte hinzufügen.
3. E2E-Pytest implementieren (Szenarien 1–10), inklusive Fixtures für Keycloak/Supabase Sessions.
4. Pipeline (GitHub Actions) erweitern: Compose hochfahren, Tests ausführen, Logs sichern.
5. Dokumentation (README, ARCHITECTURE, CI-Anleitung) aktualisieren, Hinweise zu Secrets und Laufzeiten ergänzen.
