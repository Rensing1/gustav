# DB Provisioning Guide

Status: Stable
Owner: DB/Ops

## Ziel
Sichere Bereitstellung der Datenbankrollen gemäss RLS‑Modell.

## Rollenmodell
- `gustav_limited`: App‑Rolle (NOLOGIN), RLS/Grants binden auf diese Rolle.
- `gustav_app`: Login‑User je Umgebung, `IN ROLE gustav_limited`.

## SQL (DEV/Stage)
```sql
-- Als Superuser (z. B. postgres)
create role gustav_limited NOLOGIN;  -- falls noch nicht vorhanden
create role gustav_app login password 'CHANGE_ME_DEV' in role gustav_limited;
comment on role gustav_limited is 'Least-Privilege App Role (NOLOGIN)';
comment on role gustav_app is 'Env-specific login; rights via gustav_limited';
```

## Verifikation
```sql
select pg_has_role('gustav_app','gustav_limited','member');  -- t
\du gustav_limited  -- No Login
```

## DSNs
- Host: `postgresql://gustav_app:<secret>@127.0.0.1:54322/postgres`
- Container: `postgresql://gustav_app:<secret>@supabase_db_gustav-alpha2:5432/postgres`

## Hinweise
- Keine Passwörter in Migrations oder Repo.
- Rotation über Secret‑Management; pro Umgebung eigenes Secret.

