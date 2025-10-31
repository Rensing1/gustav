# Plan: Trennung Login-User von App‑Rolle (`gustav_limited`) und DSN‑Umstellung (2025‑10‑30)

Status: Draft  
Owner: Felix  
Scope: Backend DB‑Zugriff (DSN), Betrieb/CI, Doku

## Kontext
Im Zuge der RLS‑Härtung wurde `gustav_limited` auf NOLOGIN gesetzt. Damit bleiben Rechte/Policies stabil, aber Logins über diese Rolle sind nicht mehr erlaubt. Wir führen einen umgebungsspezifischen Login‑User ein, der nur die Rechte von `gustav_limited` erbt.

## Problem (kurz)
- Bisher: DSNs nutzen `gustav_limited` direkt (mit fest verdrahtetem Passwort in Migrationen) → Sicherheitsrisiko in Stage/Prod.
- Jetzt: `gustav_limited` ist NOLOGIN → bestehende DSNs schlagen fehl; wir benötigen einen sicheren Login‑User pro Umgebung.

## Zielbild
- `gustav_limited`: NOLOGIN, least‑privilege, alle RLS‑Policies/Grants binden auf diese Rolle.
- Login‑User: z. B. `gustav_app` (DEV/CI/PROD je Umgebung), `IN ROLE gustav_limited`, Passwort/Secret ausschließlich per Secret‑Management.
- DSNs zeigen auf den Login‑User, nicht mehr auf `gustav_limited`.
- Startup‑Guard: In PROD/Stage bricht die App ab, wenn die DSN direkt `gustav_limited` nutzt.

## Schritte (minimal‑invasiv)
1) Login‑User je Umgebung anlegen (Out‑of‑Band, einmalig)
   - psql: `create role gustav_app login password '<STRONG_SECRET>' in role gustav_limited;`
   - optional: `comment on role gustav_app is 'Env-specific login; rights via gustav_limited';`
2) DSN/ENV umstellen
   - `DATABASE_URL=postgresql://gustav_app:<STRONG_SECRET>@127.0.0.1:54322/postgres`
   - ggf. `TEACHING_DATABASE_URL`, `RLS_TEST_DSN`, `SESSION_DATABASE_URL` analog.
3) CI/Local Bootstrap
   - Skript/Job, der den Login‑User erstellt (nur lokal/CI), oder Secret für bestehenden User einspielt.
4) Guards/Doku
   - Startup‑Guard (Prod/Stage): Abbruch, wenn DSN‑User `gustav_limited` ist.
   - `.env.example` und `docs/ARCHITECTURE.md` aktualisieren (Rollen‑Trennung dokumentieren).
5) Tests
   - Bereits vorhanden: `backend/tests/test_db_security_roles.py` (assert NOLOGIN für `gustav_limited`).
   - Optional: Test für Startup‑Guard (simulierte PROD‑ENV, DSN‑User = `gustav_limited` → Fehler).

## Akzeptanzkriterien
- App startet in PROD/Stage nur mit Login‑User ≠ `gustav_limited`.
- Alle Tests laufen grün mit DSN auf `gustav_app` (oder analogen Login‑User).
- Doku erklärt das Muster klar; `.env.example` referenziert keinen Login auf `gustav_limited`.

## Rollout/Backout
- Rollout: Login‑User anlegen → ENV/Secrets aktualisieren → Deploy → Tests.  
- Backout: DSN auf alten User zurückdrehen (nicht empfohlen); NOLOGIN für `gustav_limited` bleibt bestehen.

## Risiken
- Vergessene ENV‑Aktualisierung → Startfehler (sichtbar/fail‑fast).  
- CI benötigt einmaliges Bootstrap‑Skript für Login‑User.

## Folgearbeiten
- In separatem Plan: RLS von GUC auf JWT/Claims umstellen (PostgREST/Supabase), Startup‑Guards verfeinern.

