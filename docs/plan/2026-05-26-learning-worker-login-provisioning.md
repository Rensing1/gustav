# Learning-Worker-Login-Provisionierung bei lokalem Reset

## Ausgangslage
Der lokale `learning-worker` hing im Restart-Loop, weil er sich mit `gustav_worker` und dem Compose-Fallback-Passwort anmelden wollte. Die Migration legt `gustav_worker` aus Sicherheitsgründen ohne Login und ohne Passwort an; der lokale Login muss danach separat provisioniert werden.

## User Story
Als Entwickler möchte ich nach `make reset-local` ein lokales Setup erhalten, in dem Web-App und Learning-Worker mit ihren vorgesehenen Least-Privilege-Login-Rollen starten, damit der Worker nicht direkt nach dem Reset an der DB-Authentifizierung scheitert.

## BDD-Szenarien
- Given die lokale Supabase-DB wurde zurückgesetzt, when `make reset-local` läuft, then wird zuerst der App-Login `gustav_app` provisioniert.
- Given die lokale Supabase-DB wurde zurückgesetzt, when `make reset-local` läuft, then wird danach der Worker-Login `gustav_worker` provisioniert.
- Given beide Login-Rollen sind provisioniert, when `make reset-local` die Services neu erstellt, then kann der `learning-worker` mit dem dedizierten Worker-Login starten.

## Umsetzung
- `reset-local` ruft nach `$(MAKE) db-login-user` zusätzlich `$(MAKE) learning-worker-db-login-user` auf.
- Der Service-Recreate bleibt danach unverändert.
- Es gibt keine API-, OpenAPI- oder Migrationsänderung, weil die Datenbankrolle bereits existiert und nur der lokale Login nach einem Reset wiederhergestellt wird.

## Test und Verifikation
- Regressionstest: `backend/tests/test_makefile_targets.py::test_reset_local_provisions_worker_login_before_recreating_worker`
- Lokale Reparatur: `make learning-worker-db-login-user`
- Laufzeitcheck: `docker compose up -d --force-recreate learning-worker` und danach prüfen, dass `gustav-learning-worker` nicht mehr im Restart-Loop hängt.
