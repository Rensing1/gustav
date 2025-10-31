# DB Login-User für die App (DEV/CI/PROD)

Warum: Die App-Rolle `gustav_limited` ist NOLOGIN (Least Privilege, keine festen Passwörter im Repo). Anwendungen verbinden sich mit einem umgebungsspezifischen Login, der nur die Rechte der App-Rolle erbt.

## Anlegen (lokal/CI)
1) Secret setzen:
   - `export APP_DB_USER=gustav_app`
   - `export APP_DB_PASSWORD=CHANGE_ME_DEV`
2) Skript ausführen:
   - `psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -v ON_ERROR_STOP=1 -f scripts/dev/create_login_user.sql`
3) DSNs konfigurieren (z. B. in `.env`):
   - `DATABASE_URL=postgresql://$APP_DB_USER:$APP_DB_PASSWORD@127.0.0.1:54322/postgres`
   - optional: `TEACHING_DATABASE_URL`, `RLS_TEST_DSN`, `SESSION_DATABASE_URL`

## Produktion/Staging
- Login-User out-of-band per Secret-Management anlegen (kein Skriptlauf im Deploy).  
- DSNs per Secret injizieren.  
- Startup-Guard verhindert direkte Logins als `gustav_limited`.

## Verifikation
- `\du | grep gustav_app` (psql), `select rolcanlogin from pg_roles where rolname='gustav_limited';` → false.

