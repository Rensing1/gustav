# Plan: Kurs-Module (Lerneinheiten im Kurs zuordnen und sortieren)

Datum: 2025-10-27
Autor: Felix & Lehrer-Entwickler

Ziel:
- Lehrkräfte können Lerneinheiten (Units) einem Kurs zuordnen (als Module) und die Reihenfolge im Kurs ändern.
- Umsetzung als einfache SSR-Ansicht analog zu Abschnitten (HTMX Sortable), Reuse bestehender Teaching-API.
- Zusätzlich: Entfernen eines Moduls (Unit vom Kurs lösen).

Kontext und bestehende Bausteine:
- API vorhanden: `GET/POST /api/teaching/courses/{course_id}/modules`, `POST /api/teaching/courses/{course_id}/modules/reorder`.
- DB: `public.course_modules` mit deferrable Unique `(course_id, position)`.
- Pattern vorhanden: Reorder für Abschnitte/Materialien/Aufgaben (SSR-Forwarder + HTMX Sortable).

Scope (Option A – Minimal SSR):
- Neue SSR-Seite: `GET /courses/{course_id}/modules` mit zwei Bereichen:
  - „Im Kurs“: sortierbare Liste der Module (Positions-Badge, Unit-Titel, Entfernen-Button).
  - „Verfügbare Lerneinheiten“: Liste der eigenen Units (Autor), je Eintrag „Hinzufügen“.
- SSR-Forwarder:
  - `POST /courses/{course_id}/modules/create` → API `POST …/modules`
  - `POST /courses/{course_id}/modules/reorder` → API `POST …/modules/reorder`
  - `POST /courses/{course_id}/modules/{module_id}/delete` → API `DELETE …/modules/{module_id}`
- Navigation: Zusatz-Button „Lerneinheiten“ auf Kurskarte (`/courses/{id}/modules`).

Nicht-Scope (später optional):
- Suche/Filter für verfügbare Units (Server-side `q`), Bulk-Add, Kontextnotizen inline bearbeiten, Team-Freigaben.

User Stories:
- Als Lehrkraft möchte ich auf einer Kursseite Lerneinheiten hinzufügen, damit ich den Kursinhalt plane.
- Als Lehrkraft möchte ich die Reihenfolge per Drag-and-drop ändern, damit Schüler die gewünschte Reihenfolge sehen.
- Als Lehrkraft möchte ich Module wieder entfernen können, wenn ich mich umentscheide.

BDD-Szenarien (Given-When-Then):
- Given Kurs gehört mir und hat 0 Module, When ich füge meine Unit U hinzu, Then sehe ich U als Position 1.
- Given Kurs hat Module [A,B], When ich reorder [B,A], Then Positionen sind B=1, A=2.
- Given Kurs hat Module [A,B,C], When ich entferne B, Then verbleiben [A,C] mit Positionen A=1, C=2.
- Given ich bin nicht Owner, When ich versuche Module zu listen/erstellen/reordern/löschen, Then erhalte ich 403/404 (kein 400).
- Given ungültige UUID im Reorder/Delete, When ich poste, Then 400 `invalid_*_id`.

API Contract-First:
- Ergänzung: `DELETE /api/teaching/courses/{course_id}/modules/{module_id}`
  - 204 bei Erfolg
  - 400 `invalid_course_id`/`invalid_module_id`
  - 403/404 laut Owner-Guard/RLS
  - Resequenzierung `position = 1..n` im Kurs

DB Migration:
- Keine notwendig. Tabelle `public.course_modules` bereits vorhanden; Resequenzierung erfolgt in Repo-Methode.

TDD-Ansatz:
1) Failing Tests: API-Tests für DELETE (Resequenzierung, Guards, 400-Validierung).
2) Minimal Implementierung: Route + Repo-Methode `delete_course_module_owned`.
3) SSR: Seite + Forwarder, analog zu Abschnitten (keine neuen API-Tests nötig).

Security/Privacy:
- Owner-Guard vor tiefer Payload-Validierung (Error-Oracle vermeiden).
- CSRF an SSR-Grenze; API bleibt Cookie-Auth `cookieAuth`.

Risiken & Mitigation:
- Datenrennen bei Reorder/Delete → DEFERRABLE Unique + Resequencing in Transaktion.
- Große Listen → Pagination für verfügbare Units (später).

Implementierung (Stand):
- Dieser Plan ist die Grundlage; folgende Dateien werden ergänzt/angepasst:
  - `api/openapi.yml` (DELETE-Endpoint)
  - `backend/teaching/repo_db.py` (Repo-Löschmethode + Resequenzierung)
  - `backend/web/routes/teaching.py` (DELETE-Route)
  - `backend/tests/test_teaching_units_modules_api.py` (neue Tests)
  - `backend/web/main.py` (SSR Seite/Forwarder + Navigation)

