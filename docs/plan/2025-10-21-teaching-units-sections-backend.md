# Plan: Unterricht – Backend foundation für Lehrmodule (S → M)

Goal: Iterativ den Unterrichten-Kontext über Kurse hinaus ausbauen. Wir halten uns strikt an die Aggregatsgrenzen aus `docs/bounded_contexts.md` (Kurs enthält Kursmodule, Lerneinheit ist eigenständig) und verwenden Begriffe gemäß `docs/glossary.md`.

## Iteration 1 (Small): Lerneinheiten + Kursmodule

User Story  
Als Lehrkraft möchte ich wiederverwendbare `Lerneinheiten` erstellen und sie als `Kursmodule` in meinen Kurs einordnen, damit ich Unterrichtsabläufe vorbereiten kann, ohne Inhalte doppelt anzulegen.

BDD Scenarios
- Given ich bin Besitzer eines Kurses, When ich eine Lerneinheit erstelle, Then die API liefert 201 mit Autor-ID und Timestamps.
- Given eine Lerneinheit existiert, When ich sie einem Kurs hinzufüge, Then entsteht ein Kursmodul mit Position am Ende.
- Given ein Kurs mehrere Module hat, When ich die Reihenfolge per Reorder-API ändere, Then alle Positionen werden atomar neu gesetzt.
- Given ich kein Besitzer bin, When ich versuche ein Modul zu ändern, Then kommt 403.
- Given eine Lerneinheit in mehreren Kursen genutzt wird, When ich sie lösche, Then nur meine Zuordnungen fallen weg (falls keine andere Referenz, cascade via module).

### Follow-up XS (Bugfix): Robuste Eingabevalidierung

User Story  
Als Lehrkraft möchte ich bei Tippfehlern in Modul- oder Lerneinheit-IDs eine verständliche Fehlermeldung erhalten, damit ich den Fehler korrigieren kann, ohne dass die Plattform abstürzt.

BDD Scenarios
- Given ich sende `module_ids` mit einem ungültigen UUID-String, When ich die Reorder-API aufrufe, Then erhalte ich 400 `bad_request`.
- Given ich sende `unit_id="foo"` beim Anlegen eines Moduls, When die API das verarbeitet, Then erhalte ich 400 `bad_request`.
- Given ich sende eine fremde aber gültige Modul-ID, When ich reorder aufrufe, Then erhalte ich 404 statt 500.

API Contract (contract-first)
- `POST /api/teaching/units` (create), `GET /api/teaching/units` (list own, optional filters).
- `PATCH /api/teaching/units/{unit_id}`, `DELETE /api/teaching/units/{unit_id}` (Autor-only).
- `POST /api/teaching/courses/{course_id}/modules` (payload: `unit_id`, optional `context_notes`), `GET` list modules (`position`).
- `POST /api/teaching/courses/{course_id}/modules/reorder` (body: array von Kursmodul-IDs in Zielreihenfolge).
- Response-Objekte: nutzen Glossarbegriffe (`unit`, `course_module`), enthalten `position`, `title`, `author_id`, `created_at`.

Database & Migration Draft
- Tabelle `units`: `id uuid pk`, `author_id text not null`, `title text not null`, `summary text null`, Audit timestamps. Kein `course_id`.
- Tabelle `course_modules`: `id uuid pk`, `course_id uuid fk courses(id) on delete cascade`, `unit_id uuid fk units(id)`, `position int not null`, `context_notes text null`, Audit timestamps.
- Index & Constraint: `unique(course_id, position)`, `unique(course_id, unit_id)` (damit Unit im Kurs nur einmal vorkommt).
- RLS:
  - `units`: Autor darf lesen/schreiben, Admin optional.
  - `course_modules`: Nur Kursbesitzer darf lesen/schreiben (via `app.current_sub` + helper `course_exists_for_owner`).

Tests (TDD)
- Neues Modul `backend/tests/test_teaching_units_modules_api.py`.
- Szenarien für Units: Auth-Guards (401/403), happy-path CRUD für Autor, Validierung (`title` fehlt/zu lang), Pagination, Fremdzugriff 404, Löschen cascaded Module des Autors.
- Szenarien für Module: Owner-only Zugriff, Unit muss Autor gehören, Duplicate (`unique(course_id, unit_id)` → 409), Positionsvergabe am Ende, Kontext-Notizen Validierung, Liste wird positionssortiert geliefert.
- Szenarien für Reorder: Permutation aller Module → neue Reihenfolge (200), fehlende/zusätzliche IDs → 400, Fremdmodule → 404, Duplicates → 400, Kurs ohne Module → 400.
- Regression XS: ungültige UUID-Strings → 400 (statt psycopg DataError/500), DataError wird gezielt abgefangen.
- Fokus: DB-backed Repo, Policies via `app.current_sub`, 404 für fremde IDs, 403 für Nicht-Owner, Constraints überprüft.

## Iteration 2 (Small): Abschnitte innerhalb Lerneinheit

User Story  
Als Lehrkraft möchte ich Abschnitte in einer Lerneinheit strukturieren und deren Reihenfolge steuern, damit Inhalte logisch aufgebaut sind. Ein Abschnitt hat einen `title` und eine `position` innerhalb der Lerneinheit.

Design-Entscheidung (position)
- Position ist ein Attribut der Section (Kind des Aggregats „Lerneinheit“).
- Gründe: KISS, identisches Modell zu `course_modules`, einfache RLS/Constraints, keine Mehrfachverwendung vorgesehen.
- Konsequenz: `unique(unit_id, position)` erzwingt eindeutige Positionen je Lerneinheit; Reorder aktualisiert Positionen atomar.

BDD Scenarios
- Given Autor, When GET sections, Then 200 `[Section]` sortiert nach `position`.
- Given Autor, When POST valid `title`, Then 201 `Section` mit `position = next`.
- Given Autor, When POST invalid `title` (leer/zu lang), Then 400.
- Given Nicht‑Autor, When POST/PATCH/DELETE, Then 403.
- Given Autor, When PATCH valid `title`, Then 200 Section aktualisiert.
- Given Autor, When DELETE section, Then 204 und resequencing auf 1..n.
- Given Autor, When POST reorder mit exakt derselben ID‑Menge, Then 200 neue Reihenfolge.
- Given Reorder mit Duplikaten/fehlenden/invaliden UUIDs, Then 400.
- Given unbekannte `unit_id`, When irgendeine Operation, Then 404.

API Contract Updates (Contract‑First)
- Schemas
  - `Section { id: uuid, unit_id: uuid, title: string[1..200], position: int>=1, created_at, updated_at }`
  - `SectionCreate { title: string[1..200] }`
  - `SectionUpdate { title?: string[1..200] }`
  - `SectionReorder { section_ids: uuid[] uniqueItems: true, minItems: 1 }`
- Endpunkte (Author‑only, `security: cookieAuth`):
  - `GET /api/teaching/units/{unit_id}/sections`
  - `POST /api/teaching/units/{unit_id}/sections`
  - `PATCH /api/teaching/units/{unit_id}/sections/{section_id}`
  - `DELETE /api/teaching/units/{unit_id}/sections/{section_id}`
  - `POST /api/teaching/units/{unit_id}/sections/reorder`
- Responses (alle Endpunkte konsistent): 401 (unauthenticated), 403 (nicht Autor), 404 (unknown unit/section), 400 (Validierung). Reorder 200 liefert Liste in neuer Reihenfolge.
- Permissions-Metadaten: `x-permissions: { requiredRole: teacher, authorOnly: true }` (analog `ownerOnly` bei Modulen).
- Security-Hinweis: Reorder als atomare Transaktion; Sperre der betroffenen Rows via `SELECT ... FOR UPDATE` (x-security-notes).

Database & Migration Draft (Supabase/PostgreSQL)
- Tabelle `public.unit_sections`:
  - `id uuid pk default gen_random_uuid()`
  - `unit_id uuid not null references public.units(id) on delete cascade`
  - `title text not null check (length(title) between 1 and 200)`
  - `position integer not null check (position > 0)`
  - `created_at/updated_at timestamptz` + Trigger `set_updated_at()`
  - Unique `(unit_id, position) DEFERRABLE INITIALLY IMMEDIATE`
- Rechte & RLS
  - `REVOKE ALL ON TABLE public.unit_sections FROM PUBLIC;`
  - `GRANT SELECT, INSERT, UPDATE, DELETE ON public.unit_sections TO gustav_limited;`
  - RLS aktiviert; vier Policies (SELECT/INSERT/UPDATE/DELETE) mit `USING`/`WITH CHECK` via Join: `exists (select 1 from public.units u where u.id = unit_sections.unit_id and u.author_id = app.current_sub)`
  - Reorder: innerhalb einer Transaktion `SET LOCAL app.current_sub = ...; SET CONSTRAINTS ALL DEFERRED;` betroffene Zeilen per `SELECT ... FOR UPDATE` sperren.
  - Keine SECURITY DEFINER-Funktion nötig (Ownership via Join + vorhandene `unit_exists_for_author`).

Tests (TDD)
- Dateien
  - `backend/tests/test_teaching_sections_api.py`
  - `backend/tests/test_teaching_sections_reorder_api.py`
- Fälle
  - Titel-Grenzen: Länge 1 und 200 okay; 0/201 → 400
  - UUID-Validierung: ungültige `unit_id`/`section_id`/`section_ids[]` → 400
  - AuthZ: Nicht‑Autor → 403; unbekannte Unit/Section → 404; Unauth → 401
  - Delete resequencing: Positionen werden zu 1..n verdichtet
  - Reorder Happy Path; Single‑Item Reorder 200; fehlende/zusätzliche/duplizierte IDs → 400; leere Liste → 400
  - Optional: RLS mit limited DSN (403/404) gegen Test‑DB

Implementierung (Minimal)
- OpenAPI ergänzen (contract-first, vor Tests anpassen).
- Routen in `backend/web/routes/teaching.py` analog `units`/`modules` (Guards via `_guard_unit_author`).
- DB‑Repo in `backend/teaching/repo_db.py`: CRUD + `reorder_unit_sections_owned` mit DEFERRABLE Unique, `SET LOCAL app.current_sub` pro Transaktion; Rows der Unit via `FOR UPDATE` sperren.
- Hinweis: Kein In‑Memory‑Repo (vermeidet Drift/duplizierte Pfade); Tests laufen gegen echte Test‑DB (Supabase/Postgres) mit Migrationsstand.

> **Hinweis (2025-10-24):** Die Umsetzung dieser Iteration wird im neuen Plan `docs/plan/2025-10-24-teaching-section-release.md` verfolgt. Dieses Dokument bleibt als Ausgangsskizze bestehen.

## Iteration 3 (Medium): Abschnittsfreigaben pro Kurs

User Story  
Als Lehrkraft möchte ich Abschnitte aus einem Kursmodul gezielt freigeben oder sperren, damit Schüler immer nur passende Inhalte sehen.

BDD Scenarios
- Toggle Visibility: 201/200 bei Release (`visible=true`), 200 bei Sperre (`visible=false`).
- Freigabe wirkt nur innerhalb meines Kurses (Freigabe anderer Kurse bleibt unangetastet).
- Fremder Kurs → 403, Nicht-existenter Abschnitt im Kurs → 404.
- Deleting Module cascades releases.

API Contract Updates
- `PATCH /api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility` (body `{ "visible": bool }`).
- Optional `released_at`, `released_by` im Response.

Database & Migration Draft
- Tabelle `module_section_releases`: `course_module_id uuid fk course_modules(id) on delete cascade`, `section_id uuid fk unit_sections(id)`, `is_released boolean not null`, `released_at timestamptz`, `released_by text`.
- PK `(course_module_id, section_id)`.
- RLS: Owner-only über Join `course_modules.course_id`.

Tests
- Ergänzung in neuem Modul `backend/tests/test_teaching_section_releases_api.py`.
- Szenarien: release/unrelease, cross-course 404, non-owner 403, cascade on module delete.

## Implementation & Architektur
- Clean Architecture: Use-Case Layer getrennt vom FastAPI Adapter (z. B. `teaching/services/units.py`).
- Repos: Interface-orientiert; DB-Implementierung in `teaching/repo_db.py` erweitern.
- KISS: Content zunächst auf Textfelder begrenzen; Material/Aufgaben werden später in eigenem Iterationsplan entworfen.
- TDD-Workflow je Iteration: User Story → BDD → OpenAPI → Migration (Draft + `supabase migration new`) → failing pytest → minimal Implementation → Review/Refactor → Doku (Docstrings + Inline-Kommentare).
- Dokumentation: Glossar ggf. ergänzen (z. B. `Kursmodul`). Architekturhinweis, dass Units mehrfach nutzbar sind, Kurs aggregiert nur Zuordnungen + Freigaben, konform zu `docs/bounded_contexts.md`.

## Open Questions
- Wie viel Kontextwissen pro Modul? (Start: `context_notes` als Text, optional JSON später).
- Sollen Schüler-APIs (verfügbare Einheiten/Abschnitte) parallel entstehen oder eigener Plan?
- Brauchen wir Versionierung/Drafts für Einheiten vor Freigabe?

## Out of Scope
- SSR UI, Material/Aufgaben-Submodelle, Analytics-Anpassungen, Echtzeit-Events.

## Next Steps
1. Feedback von Felix einholen zur Iterationsreihenfolge & offenen Fragen.
2. Iteration 1 starten: OpenAPI-Vertrag aktualisieren, Migration entwerfen, Tests schreiben.
3. Nach jeder Iteration Review, ggf. Glossar/Bounded Context Dokumente erweitern.
