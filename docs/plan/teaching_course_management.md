# Plan: Unterrichten – Kursmanagement (MVP)

Status: Draft for review (updated per feedback)
Autor: Felix & Lehrer/Entwickler-Team
Datum: 2025-10-20

Ziel: Implementierung des Kursmanagements im Bounded Context „Unterrichten“. Lehrkräfte können Kurse anlegen, umbenennen und löschen, Schüler verwalten (hinzufügen/entfernen) und Mitglieder sowie eigene Kurse einsehen. Schüler sehen ihre belegten Kurse. Kontextwissen (LLM-Markdown) wird in dieser Iteration bewusst nicht umgesetzt.

Leitprinzipien
- KISS, Security first, FOSS, lesbarer Code für Lernzwecke
- Clean Architecture: Geschäftslogik vom Web-Framework entkoppelt (Adapter)
- API Contract-First: OpenAPI wird vor Implementierung entworfen
- TDD (Red-Green-Refactor): Erst fehlschlagende Tests, dann minimale Implementierung
- DSGVO: created_at/updated_at Audit-Timestamps, Privacy by Design (keine E-Mail in DTOs)

Scope (MVP)
- Kurse: Anlegen, Listen, Umbenennen, Löschen
- Mitglieder: Auflisten (nur Owner-Lehrer), hinzufügen (per student_sub), entfernen
- Suche: GET /api/users/search (Namespace „User Management“) zur Namenssuche; Backend nimmt `student_sub`
- Kein „Kontextwissen“ (Markdown) in dieser Iteration

Klarstellungen (Feedback eingearbeitet)
- Keine Mehrrollen-Nutzer (teacher+student) – Rollen sind disjunkt.
- Keine Uniqueness-Anforderung für (title, term, teacher_id) – Duplikate sind erlaubt.
- Kein Soft Delete – Hard Delete ist ausreichend für den MVP (mit Audit-Timestamps).

User Stories
- Als Lehrer kann ich Kurse anlegen, umbenennen und löschen.
- Als Lehrer kann ich Schüler über Namenssuche finden und per Auswahl einem Kurs hinzufügen oder entfernen.
- Als Lehrer kann ich sehen, welche Schüler in meinem Kurs sind.
- Als Schüler kann ich sehen, in welchen Kursen ich Mitglied bin.

Domänenregeln
- Keine Klassenebene; Mitgliedschaften ausschließlich pro Kurs.
- Ownership: Nur der Autor (teacher_id == sub) darf Kurs und Mitglieder verwalten.
- Mitglieder-Liste ist nur für den Owner-Lehrer sichtbar (Privacy).
- Namen sind verpflichtend auszugeben, per Directory-Adapter (User Management) aus `sub` aufgelöst.

BDD-Szenarien (Given-When-Then)
1) Kurs anlegen (Happy Path)
- Given Lehrer ist angemeldet (role=teacher)
- When POST /api/teaching/courses {title, subject?, grade_level?, term?}
- Then 201 Created, Body enthält {id, title, subject?, grade_level?, term?, teacher_id, created_at, updated_at}

2) Eigene Kurse listen (Lehrer)
- Given Lehrer ist angemeldet
- When GET /api/teaching/courses?limit=20&offset=0
- Then 200 OK, Liste enthält alle Kurse mit teacher_id == sub (paginierbar)

3) Eigene Kurse listen (Schüler)
- Given Schüler ist angemeldet und Mitglied in Kurs X
- When GET /api/teaching/courses?limit=20&offset=0
- Then 200 OK, Liste enthält Kurs X (paginierbar)

4) Kurs umbenennen
- Given Lehrer ist Owner des Kurses
- When PATCH /api/teaching/courses/{course_id} {title? subject? grade_level? term?}
- Then 200 OK, Felder aktualisiert, updated_at geändert

5) Kurs löschen
- Given Lehrer ist Owner des Kurses
- When DELETE /api/teaching/courses/{course_id}
- Then 204 No Content, Kurs und Memberships gelöscht

6) Mitglieder suchen (separater Namespace)
- Given Lehrer ist angemeldet
- When GET /api/users/search?q=max&role=student&limit=10
- Then 200 OK, Body: [{sub, name}, …]
- And q hat Mindestlänge (≥ 2), limit ist gecappt (z.B. ≤ 50)

7) Mitglied hinzufügen (idempotent)
- Given Lehrer ist Owner des Kurses
- When POST /api/teaching/courses/{course_id}/members {student_sub}
- Then 201 Created bei neuem Mitglied ODER 204 No Content wenn bereits Mitglied

8) Mitglieder auflisten (Owner-only)
- Given Lehrer ist Owner des Kurses
- When GET /api/teaching/courses/{course_id}/members
- Then 200 OK, Body: [{sub, name, joined_at}, …]

9) Mitglied entfernen (idempotent)
- Given Lehrer ist Owner des Kurses
- When DELETE /api/teaching/courses/{course_id}/members/{student_sub}
- Then 204 No Content (auch wenn nicht Mitglied)

10) Autorisierung/Fehlerfälle
- Schüler versucht POST /api/teaching/courses → 403 Forbidden
- Nicht-Owner-Lehrer versucht PATCH/DELETE/Members → 403 Forbidden
- Ungültiger Titel (leer/zu lang > 200) → 400 Bad Request
- Ungültige/fehlende student_sub → 400 Bad Request
- DELETE unbekannte course_id: Owner → 404 Not Found; Nicht-Owner → 403 (keine Informationsoffenlegung)

API Contract (Entwurf OpenAPI 3.0, Auszug)

Schemas
- CourseCreate: {title: string[1..200], subject?: string[<=100], grade_level?: string[<=32], term?: string[<=32]}
- CourseUpdate: alle Felder optional, gleiche Limits
- Course: {id: uuid, title, subject?, grade_level?, term?, teacher_id: string, created_at: date-time, updated_at: date-time}
- CourseMember: {sub: string, name: string, joined_at: date-time}

Paths (alle mit cookieAuth, 401/403/404/400 wie beschrieben)
- GET /api/teaching/courses?limit&offset → 200 [Course]
- POST /api/teaching/courses → 201 Course (teacher-only)
- PATCH /api/teaching/courses/{course_id} → 200 Course (owner)
- DELETE /api/teaching/courses/{course_id} → 204 (owner)
- GET /api/teaching/courses/{course_id}/members?limit&offset → 200 [CourseMember] (owner)
- POST /api/teaching/courses/{course_id}/members → 201|204 (owner)
- DELETE /api/teaching/courses/{course_id}/members/{student_sub} → 204 (owner)
- GET /api/users/search?q=&role=student&limit=20 → 200 [{sub, name}] (nur teacher/admin; q min length ≥ 2; limit ≤ 50)

Beispiel (YAML-Snippet für /api/teaching/courses – POST)

```yaml
  /api/teaching/courses:
    post:
      tags: [Teaching]
      summary: Create course
      security:
        - cookieAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CourseCreate'
      responses:
        '201':
          description: Created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Course'
        '400': { description: Invalid input, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '401': { description: Unauthenticated, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: Forbidden, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
```

Datenmodell (PostgreSQL)
- courses
  - id uuid primary key default gen_random_uuid()
  - title text not null (App validiert Länge 1..200)
  - subject text null (<=100)
  - grade_level text null (<=32)
  - term text null (<=32)
  - teacher_id text not null (OIDC `sub`)
  - created_at timestamptz default now()
  - updated_at timestamptz default now()
  - index (teacher_id)
- course_memberships
  - course_id uuid not null references courses(id) on delete cascade
  - student_id text not null (OIDC `sub`)
  - created_at timestamptz default now()
  - primary key (course_id, student_id)
  - index (student_id)
  - Hinweis: API gibt `joined_at` = `created_at` aus

RLS & Sicherheit
- Tabellen sind nur über Service-Role zugreifbar (Server-seitig). App erzwingt Owner-/Mitgliedsprüfungen.
- Keine E-Mail-Adressen in API-DTOs; Identität über `sub`.
- Mitgliederliste nur für den Owner-Lehrer.
- Paginierung für Listen-Endpunkte; harte Obergrenze für `limit` (z.B. 50).
- Suche: Mindestlänge `q` (≥ 2), nur für teacher/admin zugelassen.

Migration (Entwurf – Supabase/PostgreSQL)
- Neue Migration: `supabase/migrations/<timestamp>_teaching_courses.sql`
- Enthält Tabellen `courses`, `course_memberships`, Trigger für `updated_at` (ON UPDATE NOW()).
- `create extension if not exists pgcrypto;` (für gen_random_uuid())
- Trigger-Funktion für `updated_at` falls nicht vorhanden (z.B. `set_updated_at()`)
- RLS ENABLE auf Tabellen; keine Grants an `anon`/`authenticated`.

Testplan (TDD)
1) Failing Tests (Pytest, AnyIO/Async, echte Test-DB wenn verfügbar)
   - `test_create_and_list_courses_teacher()`
   - `test_student_lists_membership_courses()`
   - `test_manage_members_add_list_remove()` (mit gemockter UserDirectory-Auflösung)
   - `test_authorization_rules()` (403/401/404 Pfade)
   - `test_validation_errors()` (zu kurzer/zu langer Titel, fehlendes/invalides student_sub, Suche q zu kurz)
   - `test_members_list_bulk_directory_lookup()` (N+1 vermeiden: ein Bulk-Call für viele Mitglieder)
2) Minimal-Implementierung
   - Web-Router `backend/web/routes/teaching.py`
   - Service/Use-Case Layer (einfach, KISS) mit DB-Adapter
   - UserDirectory-Adapter (Mock in Tests)
3) Refactor & Hardening
   - Validierung, Limits, Idempotenz, Fehlertexte konsistent mit OpenAPI

Implementierungsschritte
1) OpenAPI ergänzen (Contract-First) – Pfade und Schemas wie oben
2) SQL-Migration erzeugen (Supabase) – Tabellen/Trigger/Index
3) Failing Pytests für Kernfälle schreiben
4) Minimale Endpoints implementieren, um Tests grün zu machen
5) Review gegen Prinzipien (Klarheit, Performance, Sicherheit) und ggf. Refactor
6) Dokumentation ergänzen:
   - `/docs/references/teaching.md` (API/Schema/RLS)
   - `docs/CHANGELOG.md` Eintrag

Notes
- Kontextwissen (Markdown) ist bewusst out-of-scope in dieser Iteration und wird später mit Versionierung/Storage diskutiert.
