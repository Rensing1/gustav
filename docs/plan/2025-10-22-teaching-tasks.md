# Plan: Unterrichten – Aufgaben in Abschnitten (Tasks)

Goal: Aufgaben (Tasks) als eigenständige Entität innerhalb eines Abschnitts einführen. Lehrkräfte können Aufgaben mit Aufgabenstellung (Markdown), optionalen Kriterien (0–10 Strings), optionalem Lösungshinweis (Markdown), sowie Metadaten `due_at` und `max_attempts` anlegen, bearbeiten, löschen und in der Reihenfolge verändern. Aufgaben werden über die Abschnitts-Freigabe sichtbar (keine separate Aufgaben-Freigabe).

## Scope & Prinzipien
- KISS, Security-first, FOSS; Clean Architecture (Use-Case-Layer frameworkfrei).
- Contract-First & TDD: OpenAPI-Anpassungen und failing pytest-Tests gehen der Implementierung voraus.
- RLS-first: Alle DB-Zugriffe author-gebunden über `SET LOCAL app.current_sub = '<sub>'`, App nutzt limited-role DSN (`gustav_limited`).
- Reihenfolge: Eigene Positionsspalte für Aufgaben pro Abschnitt (analog zu Materialien), Reorder atomar und lückenlos (1..n).
- Begriffe gemäß `docs/glossary.md` (Task/Aufgabe im Unterrichten-Kontext).
 - Request-Body-Limits: instruction_md/hints_md werden serverseitig begrenzt (z. B. 1–2 MB) und im Vertrag dokumentiert.
 - Wiederverwendbarkeit: Gemeinsame Reorder-Utility für Validierung (Array-Form, Duplikate, UUIDs, exakte Permutation) und konsistentes Error-Mapping.

## User Story
Als Lehrkraft möchte ich in einem Abschnitt Aufgaben mit einer Aufgabenstellung (Markdown), optionalen Kriterien (0–10 Zeilen), einem optionalen Lösungshinweis (Markdown) und Metadaten `due_at`/`max_attempts` anlegen, bearbeiten, löschen und deren Reihenfolge steuern, damit Schüler strukturiert arbeiten können. Aufgaben werden mit dem Abschnitt freigegeben.

## BDD-Szenarien (Given–When–Then)
- Happy Path
  - Given ich bin Autor der Lerneinheit, When ich `GET /tasks` aufrufe, Then 200 und eine positionssortierte Liste (ggf. leer).
  - Given ich bin Autor, When ich `POST /tasks` mit gültiger `instruction_md` (nicht leer) und optionalen `criteria` (0–10 Strings), optional `hints_md`, optional `due_at`, optional `max_attempts>=1`, Then 201 mit `position=next` und Timestamps.
  - Given Aufgaben existieren, When ich `PATCH /tasks/{task_id}` mit gültigen Feldern sende, Then 200 mit aktualisiertem Datensatz.
  - Given Aufgaben existieren, When ich `DELETE /tasks/{task_id}` sende, Then 204 und verbleibende Positionen werden 1..n resequenziert.
  - Given drei Aufgaben existieren, When ich `POST /tasks/reorder` mit exakter Permutation der IDs sende, Then 200 und Positionen entsprechen der Reihenfolge.
- Edge Cases
  - Given `PATCH` ohne Felder, Then 400 `empty_payload`.
  - Given `POST` mit leerer/nicht-String `instruction_md`, Then 400 `invalid_instruction_md`.
  - Given `criteria` nicht Array oder mit >10 Einträgen oder mit Nicht‑Strings/leerem String, Then 400 `invalid_criteria`.
  - Given `max_attempts<=0`, Then 400 `invalid_max_attempts`.
  - Given `due_at` nicht ISO‑8601 (date-time), Then 400 `invalid_due_at`.
  - Given `reorder` mit leerer Liste, Then 400 `empty_task_ids`.
  - Given `reorder` mit Nicht‑Array, Then 400 `task_ids_must_be_array`.
  - Given `reorder` mit Duplikaten, Then 400 `duplicate_task_ids`.
  - Given `reorder` mit Nicht‑UUID in der Liste, Then 400 `invalid_task_ids`.
  - Given `reorder` mit Menge ≠ bestehende IDs, Then 400 `task_mismatch`.
- Fehlerfälle/Autorisierung
  - Given unauthentifiziert, When ich Aufgaben-Endpunkte nutze, Then 401.
  - Given ich bin Lehrer aber nicht Autor, When ich `GET/POST/PATCH/DELETE/reorder` aufrufe, Then 403.
  - Given ich nutze gültige UUIDs, die mir nicht gehören, Then 404 (RLS blendet aus).

## API Contract (OpenAPI – Auszug)
Hinweis: Vertrag wird in `api/openapi.yml` ergänzt. Alle Endpunkte sind Teacher‑only und `authorOnly`.

```yaml
components:
  schemas:
    Task:
      type: object
      required: [id, unit_id, section_id, instruction_md, criteria, position, created_at, updated_at]
      properties:
        id: { type: string, format: uuid }
        unit_id: { type: string, format: uuid }
        section_id: { type: string, format: uuid }
        instruction_md:
          type: string
          minLength: 1
          description: Aufgabenstellung als Markdown
        criteria:
          type: array
          items: { type: string }
          minItems: 0
          maxItems: 10
          description: "Kriterien, frei benannt; eine Zeile pro Kriterium."
        hints_md:
          type: string
          nullable: true
          description: Optionaler Lösungshinweis (Markdown)
        position:
          type: integer
          minimum: 1
        due_at:
          type: string
          format: date-time
          nullable: true
        max_attempts:
          type: integer
          minimum: 1
          nullable: true
        created_at: { type: string, format: date-time }
        updated_at: { type: string, format: date-time }
    TaskCreate:
      type: object
      required: [instruction_md]
      properties:
        instruction_md:
          type: string
          minLength: 1
          description: "Aufgabenstellung (Markdown). Serverseitige Body-Limits ~1–2 MB."
        criteria:
          type: array
          items: { type: string }
          minItems: 0
          maxItems: 10
        hints_md:
          type: string
          nullable: true
          description: "Optionaler Lösungshinweis (Markdown). Serverseitige Body-Limits ~1–2 MB."
        due_at: { type: string, format: date-time, nullable: true }
        max_attempts: { type: integer, minimum: 1, nullable: true }
    TaskUpdate:
      type: object
      properties:
        instruction_md:
          type: string
          minLength: 1
          description: "Aufgabenstellung (Markdown). Serverseitige Body-Limits ~1–2 MB."
        criteria:
          type: array
          items: { type: string }
          minItems: 0
          maxItems: 10
        hints_md:
          type: string
          nullable: true
          description: "Optionaler Lösungshinweis (Markdown). Serverseitige Body-Limits ~1–2 MB."
        due_at: { type: string, format: date-time, nullable: true }
        max_attempts: { type: integer, minimum: 1, nullable: true }
    TaskReorder:
      type: object
      required: [task_ids]
      properties:
        task_ids:
          type: array
          items: { type: string, format: uuid }
          minItems: 1
          uniqueItems: true

paths:
  /api/teaching/units/{unit_id}/sections/{section_id}/tasks:
    get:
      tags: [Teaching]
      summary: List tasks of a section (author only)
      security: [ { cookieAuth: [] } ]
      x-permissions: { requiredRole: teacher, authorOnly: true }
      parameters:
        - in: path; name: unit_id; required: true; schema: { type: string, format: uuid }
        - in: path; name: section_id; required: true; schema: { type: string, format: uuid }
      responses:
        '200': { description: List of tasks, content: { application/json: { schema: { type: array, items: { $ref: '#/components/schemas/Task' } } } } }
        '401': { description: Unauthenticated, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: Forbidden (not the author), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: Unit/section not found, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
    post:
      tags: [Teaching]
      summary: Create a task in a section (author only)
      security: [ { cookieAuth: [] } ]
      x-permissions: { requiredRole: teacher, authorOnly: true }
      parameters:
        - in: path; name: unit_id; required: true; schema: { type: string, format: uuid }
        - in: path; name: section_id; required: true; schema: { type: string, format: uuid }
      requestBody:
        required: true
        content: { application/json: { schema: { $ref: '#/components/schemas/TaskCreate' } } }
      responses:
        '201': { description: Task created, content: { application/json: { schema: { $ref: '#/components/schemas/Task' } } } }
        '400':
          description: |
            Invalid input. detail codes:
              - invalid_instruction_md
              - invalid_criteria
              - invalid_due_at
              - invalid_max_attempts
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Error' }
              examples:
                invalid_instruction_md: { value: { error: bad_request, detail: invalid_instruction_md } }
                invalid_criteria: { value: { error: bad_request, detail: invalid_criteria } }
                invalid_due_at: { value: { error: bad_request, detail: invalid_due_at } }
                invalid_max_attempts: { value: { error: bad_request, detail: invalid_max_attempts } }
        '401': { description: Unauthenticated, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: Forbidden (not the author), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: Unit/section not found, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }

  /api/teaching/units/{unit_id}/sections/{section_id}/tasks/{task_id}:
    patch:
      tags: [Teaching]
      summary: Update a task (author only)
      security: [ { cookieAuth: [] } ]
      x-permissions: { requiredRole: teacher, authorOnly: true }
      parameters:
        - in: path; name: unit_id; required: true; schema: { type: string, format: uuid }
        - in: path; name: section_id; required: true; schema: { type: string, format: uuid }
        - in: path; name: task_id; required: true; schema: { type: string, format: uuid }
      requestBody:
        required: true
        content: { application/json: { schema: { $ref: '#/components/schemas/TaskUpdate' } } }
      responses:
        '200': { description: Updated task, content: { application/json: { schema: { $ref: '#/components/schemas/Task' } } } }
        '400':
          description: |
            Invalid input. detail codes:
              - empty_payload
              - invalid_instruction_md
              - invalid_criteria
              - invalid_due_at
              - invalid_max_attempts
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Error' }
              examples:
                empty_payload: { value: { error: bad_request, detail: empty_payload } }
                invalid_instruction_md: { value: { error: bad_request, detail: invalid_instruction_md } }
                invalid_criteria: { value: { error: bad_request, detail: invalid_criteria } }
                invalid_due_at: { value: { error: bad_request, detail: invalid_due_at } }
                invalid_max_attempts: { value: { error: bad_request, detail: invalid_max_attempts } }
        '401': { description: Unauthenticated, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: Forbidden (not the author), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: Task not found, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
    delete:
      tags: [Teaching]
      summary: Delete a task (author only)
      security: [ { cookieAuth: [] } ]
      x-permissions: { requiredRole: teacher, authorOnly: true }
      parameters:
        - in: path; name: unit_id; required: true; schema: { type: string, format: uuid }
        - in: path; name: section_id; required: true; schema: { type: string, format: uuid }
        - in: path; name: task_id; required: true; schema: { type: string, format: uuid }
      responses:
        '204': { description: Deleted (no content) }
        '400': { description: Invalid path, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '401': { description: Unauthenticated, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: Forbidden, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: Not found, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }

  /api/teaching/units/{unit_id}/sections/{section_id}/tasks/reorder:
    post:
      tags: [Teaching]
      summary: Reorder tasks of a section (author only)
      description: Atomically updates positions based on the provided task order.
      security: [ { cookieAuth: [] } ]
      x-permissions: { requiredRole: teacher, authorOnly: true }
      parameters:
        - in: path; name: unit_id; required: true; schema: { type: string, format: uuid }
        - in: path; name: section_id; required: true; schema: { type: string, format: uuid }
      requestBody:
        required: true
        content: { application/json: { schema: { $ref: '#/components/schemas/TaskReorder' } } }
      responses:
        '200': { description: Tasks reordered, content: { application/json: { schema: { type: array, items: { $ref: '#/components/schemas/Task' } } } } }
        '400':
          description: |
            Invalid task list. detail codes:
              - task_ids_must_be_array
              - empty_task_ids
              - duplicate_task_ids
              - invalid_task_ids
              - task_mismatch
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Error' }
              examples:
                task_ids_must_be_array: { value: { error: bad_request, detail: task_ids_must_be_array } }
                empty_task_ids: { value: { error: bad_request, detail: empty_task_ids } }
                duplicate_task_ids: { value: { error: bad_request, detail: duplicate_task_ids } }
                invalid_task_ids: { value: { error: bad_request, detail: invalid_task_ids } }
                task_mismatch: { value: { error: bad_request, detail: task_mismatch } }
        '401': { description: Unauthenticated, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: Forbidden (not the author), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: Unit/section not found, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
```

## Datenbank & Migration Draft
Datei: `supabase/migrations/YYYYMMDDHHMMSS_teaching_unit_tasks.sql`

- Tabelle `public.unit_tasks`
  - `id uuid primary key default gen_random_uuid()`
  - `unit_id uuid not null references public.learning_units(id) on delete cascade`
  - `section_id uuid not null references public.unit_sections(id) on delete cascade`
  - `instruction_md text not null`
  - `criteria text[] not null default '{}'` (0..10)
  - `hints_md text null`
  - `due_at timestamptz null`
  - `max_attempts integer null check (max_attempts > 0)`
  - `position integer not null check (position > 0)`
  - `created_at timestamptz default now()`, `updated_at timestamptz default now()`
- Constraints & Indizes
  - `unique(section_id, position) DEFERRABLE INITIALLY IMMEDIATE`
  - `create index idx_unit_tasks_unit on public.unit_tasks(unit_id)`
  - `create index idx_unit_tasks_section on public.unit_tasks(section_id, position)`
  - `alter table public.unit_tasks add constraint unit_tasks_criteria_len check (array_length(criteria,1) is null or array_length(criteria,1) <= 10)`
- Trigger
  - `trg_unit_tasks_updated_at` → `set_updated_at()`
  - `trg_unit_tasks_section_match` → `unit_tasks_section_unit_match()` (stellt sicher, dass `section_id` zu `unit_id` gehört; analog zu Materialien)
- RLS
  - `alter table public.unit_tasks enable row level security;`
  - Grants für limited-role
  - Policies `unit_tasks_select/insert/update/delete_author`: via Join auf `learning_units.author_id = current_setting('app.current_sub', true)` und `unit_sections.unit_id = unit_tasks.unit_id`

## Tests (pytest – failing zuerst)
Datei: `backend/tests/test_teaching_tasks_api.py`
- Guards: 401 ohne Login; 403 für Lehrer ohne Autorenschaft (GET/POST/PATCH/DELETE/reorder).
- CRUD: list leer; create (position=1); patch Felder (instruction_md, criteria, hints_md, due_at, max_attempts); delete + resequencing.
- Validierung:
  - POST: leere/nicht-String `instruction_md` → 400 `invalid_instruction_md`
  - POST/PATCH: `criteria` nicht Array / >10 / Elemente nicht-String oder leer → 400 `invalid_criteria`
  - POST/PATCH: `max_attempts<=0` → 400 `invalid_max_attempts`
  - POST/PATCH: `due_at` invalid → 400 `invalid_due_at`
  - PATCH: leerer Body → 400 `empty_payload`
- Reorder: korrekte Permutation → 200; `task_ids_must_be_array` / `empty_task_ids` / `duplicate_task_ids` / `invalid_task_ids` / `task_mismatch` → 400; Non‑Author → 403.
- Pfad-UUIDs: `unit_id`/`section_id` nicht-UUID → 400; unbekannte `task_id` bei PATCH/DELETE → 404.
- Performance: Listenabruf in einer Query; keine N+1‑Probleme.

## Implementation & Architektur
- Service-Layer: `teaching/services/tasks.py` kapselt Use Cases (list/create/update/delete/reorder). Keine Framework-Kenntnis.
- Repo: `backend/teaching/repo_db.py` erweitern um `list_tasks_for_section_owned`, `create_task`, `update_task`, `delete_task`, `reorder_section_tasks` (transaktional mit Row Locks + DEFERRABLE Unique für stabile Reorder).
- Reorder-Utility (shared): Wiederverwendbare Helper-Funktion (analog Materials) für Payload-Validierung (Array-Form, leer, Duplikate, UUID-Format, exakte Permutation) und einheitliches Mapping auf 400-Detailcodes.
- Web-Adapter: `backend/web/routes/teaching.py` ergänzt Endpunkte; 400/403/404 konsistent zu Materials. Pfad‑UUIDs und Payload‑Validierung wie im bestehenden Code. Serverseitige Body-Limits für `instruction_md`/`hints_md` per Request-Guard enforced (z. B. 1–2 MB) und im Vertrag beschrieben.
- Sichtbarkeit: Aufgaben folgen der Abschnittsfreigabe (keine separate Release‑Tabelle für Tasks).

## Sicherheits- & Datenschutznotizen
- RLS schützt Ownership strikt; App setzt `app.current_sub` pro Anfrage.
- Kein Service‑DSN im App‑Pfad; nur limited‑role.
- Eingaben werden serverseitig validiert (Strings, Arrays, Längen, Typen, ISO‑Timestamps). Fehler als `400 bad_request` mit kompakten Detailcodes.

## Open Questions (klein)
- `due_at` Zeitzone: Speicherung als `timestamptz` (UTC). UI zeigt lokalisiert – OK.
- Keine Validierung „Fälligkeit in der Vergangenheit“ nötig im MVP? (Derzeit: nein.)

## Next Steps
1) OpenAPI in `api/openapi.yml` gemäß Auszug ergänzen.  
2) Failing Tests in `backend/tests/test_teaching_tasks_api.py` schreiben.  
3) DB‑Migration entwerfen und anwenden (`supabase migration new`, `supabase migration up`).  
4) Minimalimplementation im Repo + Routes, sodass Tests grün werden (Red → Green → Refactor).  
5) Review: Clean Code, RLS‑Robustheit, Performance; Docstrings/Inline‑Kommentare ergänzen.

