# DB Login-User für die App (DEV/CI/PROD)

Warum: Die App-Rolle `gustav_limited` ist NOLOGIN (Least Privilege, keine festen Passwörter im Repo). Anwendungen verbinden sich mit einem umgebungsspezifischen Login, der nur die Rechte der App-Rolle erbt.

## App-Login anlegen (lokal/CI)
1) Secret setzen:
   - `export APP_DB_USER=gustav_app`
   - `export APP_DB_PASSWORD=CHANGE_ME_DEV`
2) Login-User anlegen/aktualisieren:
   - `make db-login-user`
3) DSNs konfigurieren (z. B. in `.env`):
   - `DATABASE_URL=postgresql://$APP_DB_USER:$APP_DB_PASSWORD@127.0.0.1:54322/postgres`
   - optional: `TEACHING_DATABASE_URL`, `RLS_TEST_DSN`, `SESSION_DATABASE_URL`

## Learning-Worker-Login anlegen (lokal/CI)
1) Secret setzen:
   - `export LEARNING_WORKER_DB_USER=gustav_worker`
   - `export LEARNING_WORKER_DB_PASSWORD=CHANGE_ME_DEV`
2) Login-User anlegen/aktualisieren:
   - `make learning-worker-db-login-user`
3) DSN konfigurieren:
   - `LEARNING_WORKER_DATABASE_URL=postgresql://$LEARNING_WORKER_DB_USER:$LEARNING_WORKER_DB_PASSWORD@127.0.0.1:54322/postgres`

## Produktion/Staging
- Login-User out-of-band per Secret-Management anlegen (kein Skriptlauf im Deploy).  
- DSNs per Secret injizieren.  
- Startup-Guard verhindert direkte Logins als `gustav_limited`.
- Achtung: In `GUSTAV_ENV=prod|stage` existiert kein Dev-Fallback – `TEACHING_DATABASE_URL`
  und `LEARNING_DATABASE_URL` müssen explizit gesetzt sein.

## Verifikation
- `\du | grep gustav_app` (psql), `select rolcanlogin from pg_roles where rolname='gustav_limited';` → false.
