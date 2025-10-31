# Plan: RLS-Härtung — Entfernung der GUC‑Abhängigkeit und Minimal‑Fixes (2025‑10‑30)

Status: Draft (Plan vor Umsetzung)  
Owner: Felix  
Betroffene Bereiche: supabase/migrations, backend/teaching (repo_db), docs

## Ziel
Minimale, schnell wirksame Reduktion des Sicherheitsrisikos durch RLS‑Policies, die eine anwendungsseitig gesetzte GUC (`app.current_sub`) als Identität verwenden. Gleichzeitig Entfernung einer riskanten LOGIN‑Rolle mit bekanntem Passwort aus Migrationen. Architektur‑Wechsel (JWT/Claims) folgt separat.

## Hintergrund & Historie
- 2025‑10‑20: Einführung GUC‑basiertes RLS im Teaching‑Kontext  
  Evidenz: `supabase/migrations/20251020154107_teaching_rls_policies.sql` (Commit 80b263e…) — Policies lesen `current_setting('app.current_sub', true)`.
- 2025‑10‑20: Dokumentation des Musters  
  Evidenz: `docs/ARCHITECTURE.md:217–220` (Commit 4698c84…) — „Jede DB‑Operation setzt SET LOCAL app.current_sub …“.
- 2025‑10‑29: Ausweitung auf Learning‑RLS (Schüler)  
  Evidenz: `supabase/migrations/20251029124213_learning_student_rls_policies.sql:79–113` (Commit 64a277e…).

## Problemstatement
- RLS‑Identität hängt an einer durch die Anwendung pro Transaktion setzbaren Konfigurationsvariablen (GUC).  
  → Falsche Trust‑Boundary: Jede SQL‑Ausführungsstelle in derselben Transaktion kann `set_config('app.current_sub', …, true)` setzen/ändern.  
  → Bei künftigem SQL‑Injection‑Fehler oder unsauberer Query‑Zusammensetzung kann Identität umgebogen werden → Fremddatenzugriff.
- Zusätzlich legt eine Migration eine LOGIN‑Rolle mit bekanntem Passwort an (`gustav_limited login password 'gustav-limited'`).  
  → Gefahr versehentlicher Nutzung in Stage/Prod und unautorisierter DB‑Zugriffe.

## Risikoanalyse (konkret)
- Impact: Hoch (potenzielles Lesen personenbezogener Schülerdaten; Verletzung DSGVO/Schulrecht).  
- Likelihood: Mittel (Code ist überwiegend parametrisiert, aber das Muster ist repo‑weit verankert; ein einzelner zukünftiger Bug genügt).  
- Blast Radius: Steigend (Teaching + Learning).

## Scope & Nicht‑Ziele
- Scope (dieser Plan):
  1) Keine weitere Ausweitung der GUC‑basierten RLS‑Policies (Learning),
  2) Entfernen des LOGIN‑Aspekts der App‑Rolle aus Migrationen,  
  3) Minimal‑Umstellung der Learning‑Reads auf geprüfte DB‑Funktionen (ohne GUC in Policies),
  4) Regressionstests (RLS) und Startup‑Guards schärfen.
- Nicht‑Ziele: Vollständige Umstellung auf JWT/Claims (`request.jwt.claims`/PostgREST). Das wird in einem Folge‑Plan umgesetzt.

## Lösungsansatz (minimal‑invasiv, schnell)
Phase A — Sofortmaßnahmen (XS–S, ≤ 1 Arbeitstag)
1) App‑Rolle härtet: `gustav_limited` auf `NOLOGIN` umstellen (keine Passwörter in Migrationen).  
   - Separaten Login‑User out‑of‑band provisionieren (Infra), der lediglich `IN ROLE gustav_limited` ist.
2) Learning‑RLS nicht mit GUC ausstatten:  
   - Option 2a (bevorzugt minimal): Statt Tabellen‑RLS für Schüler unmittelbar zu nutzen, werden für Schüler‑Reads ausschließlich bereits vorhandene/ergänzte, parametrisierte View/Function‑Schnittstellen verwendet, die Mitgliedschaft/Visibility per Join prüfen und keine GUC benötigen.  
   - Policies für diese Funktionen sind nicht nötig (Invoke: Limited‑Role), da der Filter in der Funktion liegt und Input streng parametrisiert wird.
3) Python‑SQL‑Härte: Entferne verbleibende f‑string‑Fallbacks (eine bekannte Stelle in `backend/identity_access/stores_db.py`) und erzwinge `sql.Identifier`/Parametrisierung.
4) Startup‑Guard schärfen: In PROD darf `SUPABASE_SERVICE_ROLE_KEY` nicht DUMMY/leer sein; `DATABASE_URL` darf kein `sslmode=disable` enthalten (bereits dokumentiert, prüfen und ggf. testen).

Phase B — Saubere Lösung (M, 2–4 Tage; eigener Plan)  
RLS‑Policies auf verifizierbare Identität umstellen (JWT‑Claims via PostgREST/Supabase). Backend gibt JWT weiter, kein `set_config` mehr. Einheitliche Typenstrategie (`sub` als `text` oder Mapping auf `uuid`).

## Änderungen im Detail (Phase A)
- Migrationen:
  - Ändere `supabase/migrations/20251020154107_teaching_rls_policies.sql`:  
    `create role gustav_limited login password 'gustav-limited';` → `create role gustav_limited NOLOGIN;`  
    und entferne alle passwortbezogenen Artefakte; Hinweis im Kommentar ergänzen (Login out‑of‑band).
  - Lerne‑RLS‑Migration `20251029124213_learning_student_rls_policies.sql`:  
    nicht weiter auf GUC stützen; stattdessen Helper‑Funktionen (z.B. `get_released_sections_for_student(text, uuid, int, int)`) für API‑Reads einsetzen. Policies auf Tabellen können temporär entfallen, wenn ausschließlich diese Funktionen genutzt werden.  
    Alternativ: Policies nur über stabile Kriterien (Joins auf Mitgliedschaften) ohne `current_setting('app.current_sub', …)` referenzieren und die Identität per Funktionsparameter (student_sub) erzwingen.
- Backend:
  - Learning‑Endpoints rufen diese Funktionen explizit auf (psycopg, strikt parametrisiert). Kein `set_config` nötig.  
  - Teaching bleibt unverändert (kein Scope‑Creep), bis Phase B geplant ist.
- Tests:
  - Pytest:  
    - Given kein Mitglied — When Read — Then 0 Zeilen.  
    - Given Mitglied, nicht released — Then 0 Zeilen.  
    - Given Mitglied, released — Then Datensatz(e).  
  - Security Smoke: Startup‑Guard schlägt in PROD bei Dummy‑Key/`sslmode=disable` fehl.

## Rollout‑Plan
1) PR 1: Plan + Migrations‑Patch (NOLOGIN) + Testanpassungen (grün).  
2) PR 2: Learning‑Reads auf Funktions‑API umstellen + RLS‑Tests (Schüler).  
3) Nachziehen der Doku (`ARCHITECTURE.md`, References).  
4) Monitoring: Logs prüfen (verbotene PROD‑Starts), DB‑Connections nur über den out‑of‑band Login‑User.

## Backout‑Plan
- Migrationen sind idempotent gehalten; bei Problemen: Rollback auf vorherigen Stand (Git Revert), LOGIN‑User in der DB manuell sperren/entfernen.

## Offene Punkte / Folge‑Plan (Phase B)
- JWT‑/Claims‑basierte RLS mit PostgREST.  
- Entscheidung: `student_id/teacher_id` bleiben `text` (OIDC `sub`) oder Migration auf UUIDs + Mapping.  
- Rate‑Limiting/CSRF‑Checks auditieren (separat dokumentieren).

## Akzeptanzkriterien (Phase A)
- Es existiert kein durch Migrationen angelegter DB‑Login mit bekanntem Passwort.  
- Learning‑Reads funktionieren ausschließlich über parametrisierte DB‑Funktionen ohne GUC‑Abhängigkeit.  
- Tests decken die Sichtbarkeitslogik (Mitgliedschaft/Release) ab und laufen grün.  
- Doku beschreibt den Zwischenstand und verweist auf Phase B.

## Validierung
- `.venv/bin/pytest -q`  
- Manuelle Smoke‑Tests gegen lokale Test‑DB (Member/Non‑Member, Released/Unreleased).  
- `supabase migration up` in DEV; `supabase status` prüfen.

## Risiken & Mitigation
- Kurzfristige Abweichung von „reiner“ RLS (Filter in Funktionen) → bewusst akzeptiert, da sicherer als GUC‑Policies; wird mit Phase B bereinigt.  
- Technische Schulden: Teaching weiter GUC‑basiert → bleibt isoliert, kein Ausbau bis Phase B.

