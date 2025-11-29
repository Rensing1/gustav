Title: Registrierung erlaubt fremde E-Mail-Domains trotz Gymalf-Restriktion

Status: Open

Problem:
- Erwartet ist, dass neue Konten nur mit `@gymalf.de` angelegt werden können.
- Die FastAPI-Route `GET /auth/register` prüft Domains ausschließlich, wenn sie über den Query-Parameter `login_hint` hereinkommt (`backend/web/routes/auth.py:286-303`). Das eigentliche Keycloak-Formular (`keycloak/themes/gustav/login/register.ftl`) sammelt die E-Mail jedoch direkt auf der IdP-Seite und hat keine Verbindung zur Env-Variable `ALLOWED_REGISTRATION_DOMAINS`.
- Unsere produktive `.env` setzt `ALLOWED_REGISTRATION_DOMAINS` nicht (in `.env.example` wäre der Eintrag dokumentiert), daher ist selbst die vorgelagerte Guardrail deaktiviert.
- Zusätzlich validiert die Keycloak-User-Profile-Konfiguration (`keycloak/realm-gustav.json`) nur das generelle E-Mail-Format. Es existiert kein Regex oder Script-Validator, der `@gymalf.de` erzwingt.

Impact:
- Jede Person mit Zugriff auf `/auth/register` (bzw. direkt auf die Keycloak-Registrierung) kann Fremddomains wie `@gmail.com` nutzen und erhält sofort Zugang zur Lernplattform.
- Automatisierte oder missbräuchliche Registrierungen können ohne weitere Prüfung stattfinden; Support muss Accounts manuell sperren/löschen.

Workaround:
- Neue Registrierungen manuell im Keycloak-Adminbereich prüfen und fremde Domains deaktivieren. Das ist fehleranfällig und hält Spam nur rückwirkend auf.

Vorschlag:
1. **Keycloak erzwingen**: Im declarative user profile einen Regex-Validator für `email` ergänzen (z. B. `^.+@gymalf\\.de$`) oder einen Custom-Validator verwenden. Dadurch schlägt jede Registrierung mit fremden Domains direkt im IdP fehl, auch wenn Nutzer die Registrierung-URL ohne die App aufrufen.
2. **App-Guardrail reaktivieren**: `ALLOWED_REGISTRATION_DOMAINS=@gymalf.de` in `.env` setzen und eine kleine Vorschaltmaske oder HTMX-Form einführen, die vor dem Redirect die E-Mail sammelt und als `login_hint` an `/auth/register` übergibt. Dann greift die vorhandene 400-Validierung (`invalid_email_domain`) schon auf App-Ebene.
3. **Dokumentation/Tests**: Referenz-Konfiguration (`docs/references/user_management.md`) sowie Realm-Export aktualisieren; automatisierte Tests (z. B. neues e2e) ergänzen, die sicherstellen, dass Keycloak eine Fremddomain ablehnt.

Offene Fragen:
- Soll zusätzlich eine Admin-Genehmigung oder Freischaltung nötig sein, falls mehrere Schulen/Partner hinzukommen?
- Wer übernimmt das Updaten des Realm-Exports nach dem Regex-Validator (Deployment-Prozess)?
