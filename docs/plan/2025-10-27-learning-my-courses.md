# Plan — Learning: „Meine Kurse“ (Studenten‑UI + API)

Ziel: Schüler sehen unter `/learning` ihre Kurse (alphabetisch) und können in die Kurs‑Detailansicht `/learning/courses/{course_id}` wechseln, wo die Lerneinheiten des Kurses in der festgelegten Kursreihenfolge angezeigt werden. Abschnittsfreigaben werden später auf der Ebene der Abschnitte berücksichtigt; jetzt werden nur Einheiten gelistet.

Scope (Iteration)
- UI (SSR): `/learning`, `/learning/courses/{course_id}` – rein lesend, keine Schreibaktionen.
- API (Learning, getrennt vom Teaching‑Kontext):
  - GET `/api/learning/courses` – Kurse für eingeloggten Schüler, alphabetisch.
  - GET `/api/learning/courses/{course_id}/units` – Einheiten eines Kurses mit Positionswert.
- DB: Helper (SECURITY DEFINER) für Units‑Liste implementiert; keine Schemaänderung an Tabellen notwendig.

Nicht‑Ziele (spätere Iterationen)
- Anzeige freigegebener Abschnitte inkl. Material/Aufgaben (siehe docs/references/learning.md).
- Fortschrittsindikator/Analytics.
- Suche/Filter über “Meine Kurse”.

## User Story
Als Schüler möchte ich auf der Seite „Meine Kurse“ eine Liste meiner Kurse sehen, um schnell in einen Kurs zu springen. Klicke ich einen Kurs an, sehe ich die Lerneinheiten des Kurses in der vom Lehrer festgelegten Reihenfolge.

## BDD‑Szenarien (Given‑When‑Then)

Happy Path — Kursliste
- Given ich bin als Schüler angemeldet und Mitglied in mindestens einem Kurs,
  When ich `GET /api/learning/courses?limit=20&offset=0` aufrufe,
  Then erhalte ich 200 und eine alphabetisch nach `title` sortierte Liste meiner Kurse.

Happy Path — Kursdetail (Einheiten)
- Given ich bin als Schüler im Kurs K Mitglied und der Kurs enthält Kursmodule (Einheiten) in einer festgelegten Reihenfolge,
  When ich `GET /api/learning/courses/{K}/units` aufrufe,
  Then erhalte ich 200 und eine Liste der Einheiten, sortiert nach `position` (1..n), sekundär stabil nach `unit_id`.

Leerer Zustand — keine Kurse
- Given ich bin als Schüler angemeldet, aber in keinem Kurs Mitglied,
  When ich `GET /api/learning/courses` aufrufe,
  Then erhalte ich 200 mit einer leeren Liste `[]`.

Pagination — Grenzen
- Given gültige Mitgliedschaften,
  When ich `limit` < 1 oder > 50 übergebe,
  Then wird auf [1..50] geklemmt (Default 20), `offset ≥ 0` (Default 0).

Fehler — nicht angemeldet
- Given ich habe keine gültige Session,
  When ich `GET /api/learning/courses` oder `GET /api/learning/courses/{id}/units` aufrufe,
  Then erhalte ich 401 `{ error: unauthenticated }`.

Fehler — Kurs nicht gefunden oder nicht Mitglied
- Given ich bin nicht Mitglied im Kurs K oder K existiert nicht,
  When ich `GET /api/learning/courses/{K}/units` aufrufe,
  Then erhalte ich 404 `{ error: not_found }`.

Fehler — ungültige UUID
- Given ich bin angemeldet,
  When ich `GET /api/learning/courses/{id}/units` mit einem ungültigen `id` rufe,
  Then erhalte ich 400 `{ error: bad_request, detail: invalid_uuid }`.

Determinismus — Sortierung
- Given mehrere Kurse/Einheiten mit gleichen Sortierschlüsseln,
  When ich die Endpunkte aufrufe,
  Then ist die Reihenfolge stabil (Kurse: `title asc, id asc`; Einheiten: `position asc, unit_id asc`).

## API‑Vertrag (OpenAPI‑Ausschnitt)

Hinweis: Contract‑First – Änderungen zuerst in `api/openapi.yml` pflegen.

```yaml
components:
  schemas:
    LearningCourse:
      type: object
      required: [id, title]
      properties:
        id:
          type: string
          format: uuid
        title:
          type: string
        subject:
          type: string
          nullable: true
        grade_level:
          type: string
          nullable: true
        term:
          type: string
          nullable: true
    UnitPublic:
      type: object
      required: [id, title]
      properties:
        id:
          type: string
          format: uuid
        title:
          type: string
        summary:
          type: string
          nullable: true

  parameters:
    LimitParam:
      in: query
      name: limit
      schema:
        type: integer
        minimum: 1
        maximum: 50
        default: 20
    OffsetParam:
      in: query
      name: offset
      schema:
        type: integer
        minimum: 0
        default: 0

paths:
  /api/learning/courses:
    get:
      tags: [Learning]
      summary: List courses for the current student (alphabetical)
      security:
        - cookieAuth: []
      parameters:
        - $ref: '#/components/parameters/LimitParam'
        - $ref: '#/components/parameters/OffsetParam'
      responses:
        '200':
          description: Student's courses ordered by title asc
          headers:
            Cache-Control:
              description: Security — responses must not be cached
              schema:
                type: string
                example: private, max-age=0
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/LearningCourse'
        '401':
          description: Unauthenticated
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Error' }

  /api/learning/courses/{course_id}/units:
    get:
      tags: [Learning]
      summary: List learning units of a course for the current student
      description: Requires membership in the course; returns units ordered by course module position.
      security:
        - cookieAuth: []
      parameters:
        - in: path
          name: course_id
          required: true
          schema: { type: string, format: uuid }
      responses:
        '200':
          description: Units for the course
          headers:
            Cache-Control:
              description: Security — responses must not be cached
              schema:
                type: string
                example: private, max-age=0
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
                  required: [unit, position]
                  properties:
                    unit:
                      $ref: '#/components/schemas/UnitPublic'
                    position:
                      type: integer
        '400':
          description: Invalid UUID
          content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } }
        '401':
          description: Unauthenticated
          content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } }
        '404':
          description: Course not found or not visible to the student
          content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } }
```

## DB‑Entwurf / Migration

Bestehende Tabellen genügen: `public.courses`, `public.course_memberships`, `public.units`, `public.course_modules` (+ RLS). Zur Vereinfachung und Härtung schlagen wir einen SECURITY‑DEFINER‑Helper vor:

```sql
-- Datei: supabase/migrations/20251027114908_learning_course_units_helper.sql
set check_function_bodies = off;

drop function if exists public.get_course_units_for_student(text, uuid);
create or replace function public.get_course_units_for_student(
  p_student_sub text,
  p_course_id uuid
)
returns table (
  unit_id uuid,
  title text,
  summary text,
  module_position integer
)
language sql
security definer
set search_path = public, pg_temp
as $$
  select u.id, u.title, u.summary, m.position as module_position
    from public.course_memberships cm
    join public.course_modules m on m.course_id = cm.course_id
    join public.units u on u.id = m.unit_id
   where cm.course_id = p_course_id
     and cm.student_id = p_student_sub
   order by m.position asc, u.id asc;
$$;

grant execute on function public.get_course_units_for_student(text, uuid) to gustav_limited;

set check_function_bodies = on;
```

UI‑Hinweis
- Navigationseintrag für Schüler „Meine Kurse“ verlinkt auf `/learning`.

Optional (Performance spätere Iteration): Index `create index idx_courses_title on public.courses(title);` für alphabetische Sortierung.

## Tests (pytest) — Contract Validation

Datei(en):
- `backend/tests/test_learning_my_courses_api.py`

Setup:
- Lokale Test‑DB (Supabase) mit `gustav_limited` DSN (siehe bestehende Tests).
- Testdaten: 2–3 Kurse, Mitgliedschaften für `sub_student`; mehrere Units über `course_modules` mit Positionen.
- Session: Test setzt eine gültige `gustav_session` mit Rollen [`student`].

Fälle:
- test_list_courses_alphabetical_ok → 200, sortiert nach `title asc`, Feldermenge ist minimiert (kein `teacher_id`).
- test_list_courses_empty → 200, leeres Array.
- test_list_units_ordered_ok → 200, Reihenfolge nach `position`, Struktur `{ unit: {id,title,summary?}, position }`.
- test_units_404_not_member → 404 für fremden Kurs.
- test_units_400_invalid_uuid → 400 bei ungültiger `course_id`.
- test_courses_401_unauthenticated und test_units_401_unauthenticated → 401 ohne Session.

Mocking:
- Keine externen Netzwerkanrufe; DB real, OIDC/Directory nicht benötigt.

## Minimaler Implementierungsschnitt (Red‑Green‑Refactor)

1) Contract (openapi.yml) erweitern: Schemas `LearningCourse`, `UnitPublic`; Pfade `GET /api/learning/courses`, `GET /api/learning/courses/{course_id}/units` (Header `Cache-Control: private, no-store`).
2) Migration für Helper `get_course_units_for_student` hinzufügen; `supabase migration up`.
3) Learning‑Webroute implementieren (`backend/web/routes/learning.py`):
   - `GET /api/learning/courses`: prüft Rolle `student`, clamped pagination, query: Kurse des Studenten alphabetisch, reduziert auf Felder.
   - `GET /api/learning/courses/{course_id}/units`: prüft Rolle `student`, UUID, Mitgliedschaft → sonst 404; nutzt Helper, liefert geordnete Liste.
4) Tests schreiben (fehlschlagend), dann minimalen Code implementieren, bis grün.
5) SSR‑Seiten ergänzen (`backend/web/main.py`): `/learning` und `/learning/courses/{id}` rufen interne API (ASGITransport) auf, rendern Listen. Nur lesen, daher kein CSRF nötig. Private/no‑store Caching.

## Sicherheits- und Qualitätscheck (nach Green)
- RLS‑Denken: DB‑Helper prüft Mitgliedschaft über `course_memberships`; `search_path` gehärtet, vollqualifizierte Tabellen.
- Fehlersemantik: 404 statt 403 bei Nicht‑Mitgliedschaft/fehlendem Kurs.
- Datenminimierung: Keine Lehrer‑IDs in Learning‑Antworten; nur benötigte Felder.
- Pagination‑Clamping; stabile Sortierung (secondary key id).
- Performance: vorhandene Indizes auf `course_modules(course_id)` und `courses(teacher_id)`; optional `courses(title)` index.
- Clean Architecture: Use‑Cases bleiben framework‑agnostisch; Web‑Adapter dünn; Repo isoliert DB.

## Dokumentation/Kommentare (bei Implementierung)
- Funktions‑Docstrings (englisch) mit: Intention (why), Parameter, Behavior, erforderliche Berechtigungen (Caller must be student; must be course member), Fehlerfälle/HTTP‑Codes.
- Inline‑Kommentare an nicht‑offensichtlichen Stellen (z. B. CSRF nicht nötig bei GET; Sortier‑Stabilität; 404‑Entscheidung statt 403).

## Ausführung lokal
- `supabase migration up`
- `.venv/bin/pytest -q`

## Implementierung (Stand)

- Vertrag (OpenAPI): `api/openapi.yml`
  - Schemas: `LearningCourse`, `UnitPublic`
  - Pfade: `GET /api/learning/courses`, `GET /api/learning/courses/{course_id}/units`
- Web‑Adapter (API): `backend/web/routes/learning.py`
  - `list_my_courses` (alphabetisch, minimale Felder, private Cache‑Header)
  - `list_course_units` (geordnet nach Kursmodul‑Position, 404‑Semantik, private Cache‑Header)
  - Docstrings (Why/Parameters/Behavior/Permissions) ergänzt
- Use‑Cases: `backend/learning/usecases/courses.py`
  - `ListCoursesUseCase`, `ListCourseUnitsUseCase`
- Repository (DB): `backend/learning/repo_db.py`
  - `list_courses_for_student` (JOIN auf `course_memberships`, `title asc, id asc`)
  - `list_units_for_student_course` (Helper‑Funktion, 404 bei Nicht‑Mitgliedschaft)
- DB‑Helper (SECURITY DEFINER): `supabase/migrations/20251027114908_learning_course_units_helper.sql`
  - `get_course_units_for_student(p_student_sub, p_course_id)`; Rückgabespalte `module_position`
- SSR‑Seiten: `backend/web/main.py`
  - `/learning` (Meine Kurse, Schüler)
  - `/learning/courses/{id}` (Lerneinheitenliste pro Kurs, Schüler)
- Navigation: `backend/web/components/navigation.py`
  - Schüler‑Eintrag „Meine Kurse“ → `/learning`
- Tests: `backend/tests/test_learning_my_courses_api.py` (alphabetical, 404/400/401, ordering; grün)
- UI‑Copy‑Feinschliff:
  - Lehrer‑Kursliste H1 „Kurse“ (statt „Meine Kurse“)
  - Schüler‑Kursdetail: „Zurück zu „Meine Kurse““

Bekannte Grenzen (MVP)
- Kein Fortschrittsindikator in Listen
- Keine Anzeige freigegebener Abschnitte/Materialien/Aufgaben (folgt in späterer Iteration)
