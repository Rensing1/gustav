# Plan: Automatisierte Keycloak-E2E-Tests

Stand: 15.10.2025, erstellt nach manueller Validierung des Login-/Logout-Flows.

## User Story
Als Produktverantwortlicher (Felix) möchte ich, dass die OIDC-Anmeldung über Keycloak im CI reproduzierbar getestet wird, damit wir Regressionen beim Zusammenspiel von Frontend-Adapter, Keycloak und Session-Management frühzeitig entdecken.

## Testidee
- End-to-End-Pytest-Session, die docker-compose nutzt (Keycloak + Webdienst).
- Fokus auf Login mit echtem Token-Austausch, Session-Cookie-Prüfung, Logout und Fehlerpfad bei gestoppter IdP-Instanz.
- Tests laufen optional (Marker `e2e`) und werden nur in Pipelines mit Docker-Unterstützung aktiviert.

## BDD-Szenarien (Given-When-Then)
1. **Happy Path Login**
   - Given Keycloak läuft und Demo-User `teacher1` existiert  
   - When `/auth/login` aufgerufen, Login-Form ausgefüllt und Callback abgewartet  
   - Then `/api/me` liefert 200 inkl. Rolle, Session-Cookie besitzt erwartete Flags.

2. **Logout**
   - Given gültige Session nach erfolgreichem Login  
   - When `/auth/logout` (POST) aufgerufen  
   - Then Cookie wird gelöscht und `/api/me` liefert 401.

3. **IdP-Ausfall während Callback**
   - Given Keycloak wird nach Login-Redirect gestoppt  
   - When Callback mit `code`/`state` erneut aufgerufen  
   - Then FastAPI antwortet mit 400 und löscht keine Cookies.

4. **Session-Reuse**
   - Given Login erfolgreich durchgeführt  
   - When `/auth/login` ohne Logout erneut aufgerufen  
   - Then Redirect geht direkt nach `/` (kein erneuter Keycloak-Loop).

## Technische Umsetzung
- Neue Pytest-Datei `backend/tests_e2e/test_auth_end_to_end.py`.
- Marker `@pytest.mark.e2e` und Skip, falls Umgebungsvariable `E2E_AUTH` nicht gesetzt.
- Setup-Fixture, die docker-compose-Services hochfährt (idealerweise über vorhandene Infrastruktur-Skripte).
- Requests-Session nutzt Host-Rewriting (wie im manuellen Skript) für Keycloak-Aufrufe.
- Cleanup-Fixture sorgt für Logout und ggf. Neustart des IdP.

## Offene Fragen / TODO
- Automatisches Anlegen des Demo-Users: per `kcadm.sh` im Test oder dauerhaft in Realm-JSON?  
- Wo wird docker-compose im CI gestartet (GitHub Actions Workflow anpassen)?  
- Wie lange darf der Test dauern (Timeout-Fenster berücksichtigen)?

## Nächste Schritte
1. Stakeholder-Abstimmung, ob E2E-Tests Pflicht im CI oder nur Nightly laufen.
2. PoC-Test lokal umsetzen, Fläche für Host-Rewrite/Callback-Rewrite generalisieren.
3. Nach erfolgreichem PoC Pipeline-Integration und Dokumentation ergänzen.
