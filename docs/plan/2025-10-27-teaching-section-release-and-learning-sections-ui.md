# Plan: Abschnittsfreigabe (Lehrer) und Schüler‑UI für freigegebene Abschnitte (2025‑10‑27)

## Kontext
- Ziel: Lehrkräfte können pro Kursmodul einzelne Abschnitte freigeben/ausblenden; Schüler sehen nur Material/Aufgaben aus freigegebenen Abschnitten.
- Architektur‑Anker: Contract‑First (OpenAPI), TDD (pytest), Clean Architecture (Use Cases getrennt von Web), Security‑first (RLS, Cache‑Header).
- Stand: API + DB für Sichtbarkeit existieren (Teaching‑PATCH + `module_section_releases`), Learning‑Read aggregiert freigegebene Abschnitte via SQL‑Helper. Dieser Plan präzisiert den Lehrer‑Workflow (UX) und die Schüler‑Darstellung (UI) und ergänzt Tests.

Referenzen:
- OpenAPI Teaching PATCH: `api/openapi.yml:3362` (updateModuleSectionVisibility)
- Route: `backend/web/routes/teaching.py:2712` (PATCH Visibility)
- Repo Teaching: `backend/teaching/repo_db.py:1953` (Upsert mit RLS)
- DB‑Schema: `supabase/migrations/20251022135746_teaching_module_section_releases.sql`
- Learning Sections API: `api/openapi.yml:909` (listLearningSections), Route `backend/web/routes/learning.py:217`, Repo `backend/learning/repo_db.py:175`, Helper `supabase/migrations/20251023093417_learning_helpers.sql:65`
- NEU: Unit‑spezifischer Endpoint: `GET /api/learning/courses/{course_id}/units/{unit_id}/sections` (Server‑Filter, 200 + leere Liste), Route `backend/web/routes/learning.py`, Repo‑Methode mit DB‑Helper.

## User Stories
1) Als Lehrkraft (Kurs‑Owner) möchte ich pro Kursmodul einzelne Abschnitte ein‑/ausblenden, damit meine Klasse schrittweise Inhalte bearbeitet.
2) Als Schüler möchte ich innerhalb eines Kurses nur freigegebene Inhalte sehen, logisch in Abschnitte gruppiert, ohne Abschnittstitel, getrennt durch horizontale Linien.

## BDD‑Szenarien

Lehrer‑Workflow (Sichtbarkeit)
- Given ich bin Kurs‑Owner, When ich `PATCH /api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility` mit `{visible:true}` sende, Then wird der Abschnitt freigegeben (200, `visible=true`, `released_by`, `released_at!=null`).
- Given freigegeben, When `{visible:false}`, Then wird die Freigabe aufgehoben (200, `visible=false`, `released_at=null`).
- Given nicht Owner/Schüler/unauthentisch, When PATCH, Then 403/401.
- Given ungültige UUIDs, When PATCH, Then 400 (`invalid_*`).
- Given Abschnitt gehört nicht zur Unit des Moduls, When PATCH, Then 404 (`section_not_in_module`).

Schüler‑UI (Darstellung freigegebener Abschnitte)
- Given Kursmitglied und freigegebene Abschnitte existieren, When `GET /api/learning/courses/{course_id}/sections?include=materials,tasks`, Then Response enthält nur freigegebene Abschnitte in Positionsreihenfolge (stabil bei Ties nach id asc), mit eingebetteten Materialien/Aufgaben.
- Given mehrere freigegebene Abschnitte, When UI rendert, Then Inhalte je Abschnitt untereinander, zwischen Abschnitten genau eine horizontale Trennlinie <hr>; Abschnittstitel werden nicht angezeigt.
- Given keine freigegebenen Abschnitte, Then API 404 (`not_found`) und UI zeigt eine neutrale Meldung „Noch keine Inhalte freigeschaltet“.
- Given Pagination offset >= total, Then API liefert leere Liste oder 404 gemäß aktueller Semantik; UI zeigt keine Inhalte, aber bleibt funktionsfähig.

## API‑Vertrag (Review)
- Teaching: PATCH Sichtbarkeit ist bereits im Vertrag spezifiziert; keine Änderung nötig.
- Learning: `GET /api/learning/courses/{course_id}/sections` deckt Anforderung ab (optional `include=materials,tasks`). Kleine Ergänzung im Vertrag umgesetzt: `LearningSectionCore` enthält jetzt `unit_id` zur UI‑Filterung (api/openapi.yml:601); Repo liefert das Feld mit (backend/learning/repo_db.py).
- Cache‑Header: Alle Learning‑Antworten mit `Cache-Control: private, no-store` (bereits ausgerichtet).

## Status der Implementierung (2025‑10‑27)
- Implementiert
  - Schüler‑Unit‑Unterseite ohne Abschnittstitel, Gruppen getrennt durch `<hr>`: Route `GET /learning/courses/{course_id}/units/{unit_id}` (backend/web/main.py:493).
  - API‑Contract erweitert (`unit_id` in `LearningSectionCore`) und Backend‑Repo liefert es.
  - Tests: Kantenfälle Sortier‑Tie‑Break + Pagination‑404 (backend/tests/test_learning_sections_api_edges.py) und SSR‑Unit‑Seite ohne Titel (backend/tests/test_learning_unit_sections_ui.py).
  - Teststand: 411 passed.
- Entscheidung: Vorschlag A (Sofort‑Speichern pro Toggle)
  - Persistenz: `public.module_section_releases` via UPSERT (PK: `(course_module_id, section_id)`), `released_by` = aufrufender Lehrer, `released_at` = UTC‑Zeitstempel wenn sichtbar, sonst `null`.
  - Security: RLS schützt Kurs‑Owner‑Semantik. SSR nutzt CSRF‑Token pro Session.
  - Semantik: Fehler aus dem PATCH‑API werden in der SSR‑Toggle‑Route als HTTP‑Status 400/403/404 durchgereicht (keine stillen Teil‑Updates).

- Offen
  - Lehrer‑UI im Modul‑Detail: HTMX‑Toggles für Abschnittsfreigaben und Statusanzeige (CSRF via `hx-headers` mit Session‑gebundenem Token). Label deutsch: „Freigegeben“.
  - Referenz‑Doku aktualisieren (docs/references/learning.md/teaching.md) und Verlinkung von der Kurs‑Unit‑Liste zur neuen Unit‑Unterseite.

## Datenbank (Review)
- `public.module_section_releases` mit PK `(course_module_id, section_id)`, `visible boolean not null`, `released_at timestamptz`, `released_by text not null` (+RLS) existiert. Keine zusätzlichen Migrationen nötig.
- SQL‑Helper nutzen die Tabelle bereits: `get_released_sections_for_student`, `get_released_materials_for_student`, `get_released_tasks_for_student`.

## Tests (TDD‑Erweiterungen)
- Learning API — stabile Ordnung bei gleichen Positionswerten: When zwei Abschnitte haben gleiche `position`, Then Sortierung sekundär nach `section_id` asc. Ziel: `backend/tests/test_learning_my_courses_api.py` oder neues Testfile in Learning‑Bereich.
- Learning API — Pagination‑Edge: When `offset >= total`, Then Response behandelt korrekt (leer oder 404 je Semantik) und setzt `Cache-Control: private, no-store`.
- SSR‑Fragment‑Test (leichtgewichtig, falls vorhanden): Renderfunktion für Schüler‑Abschnittsliste erzeugt <hr> zwischen Gruppen und enthält keine Abschnittstitel im HTML. Alternativ: Snapshot‑Test der generierten HTML‑Partial.

## Lehrer‑Workflow (UX‑Skizze)
- Ort: Kursmodule‑Seite (Owner). Ergänze pro Modul einen Link „Abschnittsfreigaben verwalten“.
- Modul‑Detail „Abschnittsfreigaben“: Liste aller Abschnitte der verknüpften Unit mit Toggle (HTMX/PATCH auf den Teaching‑Endpoint). Statusanzeige „Freigegeben“/„Versteckt“, Zeitstempel, letzter Bearbeiter.
- Fehlerfeedback: Bei 403/404/400 oberhalb der Liste eine kompakte Fehlermeldung; Aktionen idempotent.
- Security: CSRF‑Tokens bei SSR‑Formen; Antworten `no-store`.

## Schüler‑UI (Darstellung)
- Ort: Unterseite zur Lerneinheit: `/learning/courses/{course_id}/units/{unit_id}` (pro Unit), nicht kursweite Liste.
- Datenquelle: `GET /api/learning/courses/{course_id}/units/{unit_id}/sections?include=materials,tasks` (serverseitiger Filter nach Unit; keine Client‑Side‑Filter nötig).
- Rendering:
  - Für jeden Abschnitt: rendere alle Materialien (Markdown → HTML sicher sanitize; Dateien als Links mit presigned URL) und Aufgaben (Instruction + Kriterien/Meta).
  - Unterdrücke Abschnittstitel. Zwischen Abschnitten genau eine <hr> (kein <hr> am Anfang/Ende).
  - Zugänglichkeit: <section role="group"> je Abschnitt optional; Fokusreihenfolge logisch.
- Fehlerfälle: 200 + leere Liste → Hinweis „Noch keine Inhalte freigeschaltet“; 401/403 → Redirect/Fehlermeldung gemäß globalem Learning‑Flow; 404 → `unit_id` gehört nicht zum Kurs.

## Umsetzungsschritte
1) Tests ergänzen (Learning: Ordnung/Tie‑Break; Pagination‑Edge; Unit‑Endpoint 200+leer; Cross‑Course‑404; SSR‑Header/`<hr>`‑Zählung). Rot.
2) Backend/Repo: Sekundäre Sortierung in SQL‑Helper absichern (`order by s.position, s.id`). Unit‑Helper ergänzen.
3) API/Adapter: Neuer Endpoint `/api/learning/courses/{course_id}/units/{unit_id}/sections` (Server‑Filter, `private, no-store`).
4) SSR (Student): Renderfunktion existiert; an neuen Endpoint anbinden; HTML ohne Abschnittstitel, mit <hr>‑Trennung. `Cache-Control: private, no-store` setzen.
5) Teaching‑UI: Modul‑Detail zum Toggeln (HTMX‑PATCH, CSRF via `hx-headers`), Statusindikator, Fehlerbehandlung.
6) Doku: Referenzen aktualisieren (`docs/references/learning.md`/`teaching.md`), CHANGELOG.

## Definition of Done
- TDD‑Tests grün (inkl. neuen Edge‑Tests).
- Lehrkraft kann Abschnitte pro Modul toggeln; UI zeigt Zustand.
- Schüler‑Ansicht zeigt nur freigegebene Inhalte, ohne Abschnittstitel, mit <hr>‑Trennung.
- Security: RLS greift, Antworten `private, no-store`, keine PII‑Leaks.
- Dokumentation aktualisiert.

## Offene Fragen
1) Soll die Schüler‑Ansicht alle freigegebenen Abschnitte kursweit aneinanderreihen (empfohlen für Einfachheit) oder pro Unit gruppieren?
2) Sollen Aufgaben in der Schüler‑Ansicht direkt lösbar sein oder nur verlinkt (MVP: direkt lösbar wie bisher über Tasks‑Endpoints)?
3) Benötigen wir ein Planungsfenster (start_at/end_at) für Freigaben in dieser Iteration? (Aktuell nicht, Erweiterung möglich.)
