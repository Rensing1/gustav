# Plan: Live‑Unterricht – Einheitenweite Live‑Ansicht (Teacher)

Goal: Lehrkräfte sehen in der Seite „Unterricht“ für einen gewählten Kurs und eine Lerneinheit die Live‑Aktivität auf Einheitenebene: Eine kompakte Übersicht (Schüler × Aufgaben der Einheit) zeigt minimal, wer bereits eingereicht hat (✅) bzw. nicht (—). Bei Bedarf lässt sich unterhalb der Übersicht eine Detailansicht (inkl. Analyse/Feedback) für einen Schüler und eine Aufgabe einblenden. Realtime‑Aktualisierung via SSE (mit Polling‑Fallback) ohne PII‑Leckage.

## Scope & Prinzipien
- KISS, Security‑first (RLS + Same‑Origin + private Cache), FOSS, Clean Architecture (Use‑Cases frameworkfrei).
- Contract‑First & TDD: OpenAPI‑Anpassungen und failing pytest‑Tests vor Implementierung.
- DSGVO: Namen (Display Name) dürfen Lehrern angezeigt werden. Keine Inhalte (Text/Images) in Events; Inhalte nur via expliziter API‑Abfrage.
- Begriffe: Abschnitt = Section; Aufgabe = Task; Einreichung = Submission.

## User Story
Als Lehrkraft möchte ich in der Live‑Ansicht einer Lerneinheit meines Kurses in Echtzeit sehen, welche Schüler (mit Namen) bereits zu den Aufgaben der Einheit eingereicht haben, damit ich im Unterricht schnell erkenne, wer fertig ist. Aus der Übersicht möchte ich bei Bedarf eine Detailansicht unterhalb öffnen, die mir Analyse/Feedback zur letzten Einreichung zeigt – ohne Seitenwechsel.

## BDD‑Szenarien (Given–When–Then)
- Sichtbarkeit toggeln (bestehend, Referenz)
  - Given ich bin Kurs‑Owner, When ich PATCH `/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility` mit `{"visible": true}` sende, Then 200 mit `{ visible: true, released_at != null, released_by = sub }`.
  - Fehler: unbekanntes Modul/Abschnitt → 404; nicht Owner → 403; CSRF (Origin mismatch) → 403 `csrf_violation`.
- Live‑Übersicht pro Lerneinheit (Happy Path)
  - Given ich bin Kurs‑Owner, die Lerneinheit gehört zum Kurs, When ich GET `/api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary` aufrufe, Then 200: Liste aller Kursteilnehmer mit Name und je Aufgabe der Einheit ein Minimalstatus `has_submission` (true/false). Keine Feedback‑Previews in der Übersicht.
- Live‑Übersicht (Edge Cases)
  - Keine Einreichungen: Zellen zeigen „—“.
  - Keine Aufgaben in der Lerneinheit: Rückgabe enthält `tasks=[]` und `students` mit leeren Zellen.
  - Schüler ohne Kursmitgliedschaft erscheinen nicht.
- Live‑Übersicht (Fehlerfälle)
  - Ungültige UUID → 400 `invalid_uuid`.
  - Lerneinheit gehört nicht zum Kurs → 404.
  - Nicht Owner/keine Lehrerrolle → 403.
- Realtime (SSE)
  - Given aktive Lehrer‑Live‑Seite, When ein Schüler eine neue Einreichung erstellt oder sich der Status ändert, Then via `text/event-stream` kommt ein Event (`submitted|status_changed`) mit IDs (ohne Inhalte). Die UI ruft daraufhin `summary` (inkrementell: `updated_since`) nach.

## High‑Level‑Architektur & Realtime
- UI
  - Unterricht → Kurs wählen → Lerneinheit wählen → Tabs: „Freigaben“ (bestehend), „Live“.
  - Live‑Tab (Einheit): Tabelle, Zeilen = Schüler (Name), Spalten = Aufgaben der Einheit in Positionsreihenfolge. Zellen zeigen minimal ✅ (eingereicht) oder — (nicht eingereicht). Keine Filter/Heatmap/Kennzahlen. Klick auf Schülername oder Zelle blendet unten eine Detailansicht ein (vollständiges Feedback/Analyse der letzten Einreichung). Sticky Kopfzeile und erste Spalte; optimiert für Laptop und iPad.
- Datenfluss
  - Initial: `GET summary` liefert Schüler×Aufgaben‑Matrix mit Minimalstatus `has_submission` pro (Schüler, Aufgabe) und die Task‑Liste (`id`, `instruction_md`, `position`).
  - Realtime: SSE `/events` sendet nur IDs/Status; Client nutzt `updated_since` (Cursor = max(created_at, completed_at)) zum Nachladen. Implementiert: SSE mit Heartbeats (Test‑Kurzschluss). Polling‑Fallback optional.
- Sicherheit
  - Owner‑Only (RLS + WHERE teacher_id = sub), private/no‑store Cache, Vary: Origin. SSE‑Kanal pro Kurs+Einheit geprüft.
  - Events enthalten keine Inhalte (keine Texte/Bilder), nur IDs/Status/Zeiten. Namen sind für Lehrkräfte sichtbar (DSGVO‑konform im Klassenkontext).

### UI‑Skizze (ASCII, Einheitenebene)

```
+------------------------------------------------------------------------------------+
| Unterricht › Kursname › Lerneinheit                                  [ Hilfe ]    |
| Tabs: [ Freigaben ] [ Live (aktiv) ]                                              |
+------------------------------------------------------------------------------------+
| ● Live verbunden   Seit 8s   [ ⟳ Aktualisieren ]                                   |
+--------------------------- Übersicht: Schüler × Aufgaben (Einheit) ----------------+
| Schüler                 | A1 | A2 | A3 | A4 | A5 | A6 |                            |
+------------------------ +----+----+----+----+----+----+---------------------------+
| Anna Müller            | ✅ | ✅ | —  | —  | —  | —  |                            |
| Ben Schmidt            | ✅ | —  | —  | —  | —  | —  |                            |
| Cem Kaya               | —  | —  | —  | —  | —  | —  |                            |
| … (20–30 Schüler)      |    |    |    |    |    |    |  Sticky Kopf/erste Spalte  |
+------------------------------------------------------------------------------------+
| [ Details – erscheint bei Klick auf Schülername oder Zelle ]                       |
| Schüler: Anna Müller  · Aufgabe: A2 · Abgabe #3 · 2025‑11‑01 10:12 · Status: ✅    |
| Feedback (Markdown, vollständig)                                                   |
| Analyse/Scores (falls vorhanden)                                                   |
| [ Zurück zur Übersicht ]                                                           |
+------------------------------------------------------------------------------------+
```

## API Contract (OpenAPI – Auszug)
Ergänzungen in `api/openapi.yml` (Contract‑First)

### OpenAPI (einheitenweit)
Die Live‑Übersicht bezieht sich auf die gesamte Lerneinheit, mit Minimalstatus in der Übersicht. Frühere Abschnitts‑Skizze wurde entfernt (Archiv), um Verwechslungen zu vermeiden.

```yaml
components:
  schemas:
    TeachingStudentRef:
      type: object
      required: [sub, name]
      properties:
        sub: { type: string }
        name: { type: string }
    TeachingUnitTaskCell:
      type: object
      required: [task_id, has_submission]
      properties:
        task_id: { type: string, format: uuid }
        has_submission: { type: boolean }
    TeachingUnitLiveRow:
      type: object
      required: [student, tasks]
      properties:
        student: { $ref: '#/components/schemas/TeachingStudentRef' }
        tasks:
          type: array
          items: { $ref: '#/components/schemas/TeachingUnitTaskCell' }
    TeachingUnitLiveEvent:
      type: object
      description: Event für Live‑Updates (SSE). Keine Inhalte der Einreichung.
      required: [type, course_id, unit_id, task_id, submission_id, student_sub, at]
      properties:
        type: { type: string, enum: [submitted, status_changed] }
        course_id: { type: string, format: uuid }
        unit_id: { type: string, format: uuid }
        task_id: { type: string, format: uuid }
        submission_id: { type: string, format: uuid }
        student_sub: { type: string }
        at: { type: string, format: date-time }

paths:
  /api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary:
    get:
      summary: Live‑Übersicht je Lerneinheit (Owner)
      description: Liste aller Kursteilnehmer × Aufgaben (Positionsreihenfolge); Minimalstatus je Zelle via `has_submission`.
      tags: [Teaching]
      security: [ { cookieAuth: [] } ]
      x-permissions: { requiredRole: teacher, ownerOnly: true }
      x-security-notes:
        - "RLS: Kurs‑Ownership + Unit zu Kurs zugeordnet."
        - "Cache: private, no-store; Vary: Origin."
      parameters:
        - in: path
          name: course_id
          required: true
          schema: { type: string, format: uuid }
        - in: path
          name: unit_id
          required: true
          schema: { type: string, format: uuid }
        - in: query
          name: updated_since
          required: false
          schema: { type: string, format: date-time }
          description: Optionaler ISO‑Zeitpunkt; nur Änderungen nach diesem Zeitpunkt.
        - in: query
          name: limit
          required: false
          schema: { type: integer, minimum: 1, maximum: 200, default: 100 }
          description: Maximale Anzahl von Schülerzeilen.
        - in: query
          name: offset
          required: false
          schema: { type: integer, minimum: 0, default: 0 }
      responses:
        '200':
          headers:
            Cache-Control: { schema: { type: string, example: 'private, no-store' } }
            Vary: { schema: { type: string, example: 'Origin' } }
          content:
            application/json:
              schema:
                type: object
                required: [tasks, rows]
                properties:
                  tasks:
                    type: array
                    items:
                      type: object
                      required: [id, instruction_md, position]
                      properties:
                        id: { type: string, format: uuid }
                        instruction_md: { type: string }
                        position: { type: integer }
                  rows:
                    type: array
                    items: { $ref: '#/components/schemas/TeachingUnitLiveRow' }
        '400': { description: Invalid identifiers or timestamp, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '401': { description: Unauthenticated, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: Forbidden (not owner), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: Not found (course/unit), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }

  /api/teaching/courses/{course_id}/units/{unit_id}/submissions/events:
    get:
      summary: Realtime‑Events für Lerneinheit (Owner) – SSE
      description: Server‑Sent Events (text/event-stream). Events enthalten IDs/Status ohne Inhalts‑PII. Client lädt Details via `summary` nach.
      tags: [Teaching]
      security: [ { cookieAuth: [] } ]
      x-permissions: { requiredRole: teacher, ownerOnly: true }
      x-security-notes:
        - "SSE: keep-alive; Owner‑Check bei Verbindungsaufbau."
        - "Event‑Payload ohne Inhalte; nur IDs/Status."
      responses:
        '200':
          content:
            text/event-stream:
              schema: { type: string, description: SSE‑Stream (JSON jedes Events als TeachingUnitLiveEvent) }
        '400': { description: Invalid identifiers, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '401': { description: Unauthenticated, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: Forbidden (not owner), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: Not found (course/unit), content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
```

## DB/Migrations (SQL‑Entwurf)
Ziel: Effiziente Owner‑Queries und Events ohne Inhalte.

1) Indizes (falls noch nicht vorhanden)
- `create index if not exists idx_ls_task_student_created on public.learning_submissions(task_id, student_sub, created_at desc);`
  (Distinct‑on je (student_sub, task_id) performant; ergänzend zu vorhandenen Indizes.)

2) Owner‑sichtbare Helper‑Funktion (SECURITY DEFINER)

```sql
create or replace function public.get_unit_latest_submissions_for_owner(
  p_owner_sub text,
  p_course_id uuid,
  p_unit_id uuid,
  p_updated_since timestamptz default null,
  p_limit integer default 100,
  p_offset integer default 0
)
returns table (
  student_sub text,
  task_id uuid,
  submission_id uuid,
  created_at_iso text,
  completed_at_iso text
)
language sql
security definer
set search_path = public, pg_temp
as $$
  with owner as (
    select 1 from public.courses c where c.id = p_course_id and c.teacher_id = p_owner_sub
  ), tasks_in_unit as (
    select t.id as task_id
      from public.unit_tasks t
      join public.unit_sections s on s.id = t.section_id
      join public.course_modules m on m.unit_id = s.unit_id and m.course_id = p_course_id
     where s.unit_id = p_unit_id
  ), latest as (
    select distinct on (ls.student_sub, ls.task_id)
           ls.student_sub,
           ls.task_id,
           ls.id as submission_id,
           ls.created_at,
           ls.completed_at
      from public.learning_submissions ls
      join tasks_in_unit tiu on tiu.task_id = ls.task_id
     where ls.course_id = p_course_id
       and (p_updated_since is null or greatest(ls.created_at, coalesce(ls.completed_at, ls.created_at)) > p_updated_since)
     order by ls.student_sub, ls.task_id, ls.created_at desc
  )
  select l.student_sub,
         l.task_id,
         l.submission_id,
         to_char(l.created_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"') as created_at_iso,
         case when l.completed_at is null then null else to_char(l.completed_at at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"') end as completed_at_iso
    from owner, latest l
   order by l.student_sub asc, l.task_id asc
   offset greatest(coalesce(p_offset,0),0)
   limit case when coalesce(p_limit,0) < 1 then 100 when p_limit > 200 then 200 else p_limit end;
$$;

grant execute on function public.get_unit_latest_submissions_for_owner(text, uuid, uuid, timestamptz, integer, integer) to gustav_limited;
```

3) Event‑Trigger (OPTIONAL, MVP‑SSE reicht auch mit Polling)

```sql
create or replace function public.notify_learning_submission_change()
returns trigger language plpgsql security definer as $$
begin
  -- Nur Meta‑Daten, keine Inhalte senden
  perform pg_notify(
    'learning_submissions',
    json_build_object(
      'submission_id', new.id,
      'course_id', new.course_id,
      'task_id', new.task_id,
      'student_sub', new.student_sub,
      'at', to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS"+00:00"')
    )::text
  );
  return new;
end; $$;

drop trigger if exists trg_notify_learning_submission_change on public.learning_submissions;
create trigger trg_notify_learning_submission_change
  after insert or update of analysis_status, completed_at on public.learning_submissions
  for each row execute function public.notify_learning_submission_change();
```

## Testplan (pytest, TDD)
- Vertrags‑Tests (Teacher‑only, Owner‑Only)
  - 401/403/404/400 für `summary` und `events` (Einheitenebene).
  - 200: `summary` liefert vollständige Matrix mit Minimalstatus (✅/— via `has_submission`).
  - `updated_since`: Nur Zellen, die sich nach T geändert haben.
- Realtime
  - SSE: Bei Insert/Status‑Änderung erscheinen Events (mit DB‑Notify Fake/Mock) und Client lädt per `updated_since` nach.
- RLS/Owner
  - Nicht‑Owner sieht weder `summary` noch Events (403/404 gemäß Vertrag).
  - Sicherheit (Kursbezug): Einreichungen aus anderen Kursen mit derselben Unit erscheinen nicht (Filter `ls.course_id = :course_id`).

## Sicherheits- & Datenschutz‑Überlegungen
- Private, no‑store Caching; Vary: Origin. Same‑Origin für mutierende Routen (bestehend); SSE ist read‑only, prüft Ownership.
- Events enthalten keine Inhalte (keine `text_body`, keine binären Metadaten). Inhalte nur auf Nachfrage via Detailabruf (letzte Submission pro Schüler×Aufgabe).
- RLS: Owner‑Aggregator ist `security definer` (expliziter Owner‑Check, Filter auf Kurs/Unit), Student‑Helper bleiben `security invoker`. Web‑Adapter setzt weiterhin `app.current_sub` defensiv vor DB‑Zugriffen.

## Schritte / Meilensteine
1) OpenAPI in `api/openapi.yml` ergänzen (einheitenweite summary + events + Schemas, Minimalstatus). — ERLEDIGT
2) Failing pytest‑Tests: `test_teaching_live_unit_summary_api.py` (200/4xx, updated_since, Pagination), `test_teaching_live_unit_events_api.py` (Verbindungsaufbau/Filter). — ERLEDIGT (grün)
3) Minimal‑Implementierung:
   - Web‑Adapter (Teaching): `GET /units/{unit_id}/submissions/summary` (MVP, mit robustem Fallback bei strenger RLS), `GET /.../events` (SSE mit Heartbeats; Tests brechen nach erstem Heartbeat ab).
   - Repo/DB: Migration mit Index, `get_unit_latest_submissions_for_owner` (SECURITY DEFINER, EXECUTE an `gustav_limited`), Notify‑Trigger angelegt.
   — ERLEDIGT
4) Refactor & Hardening (NÄCHSTES):
   - SSE: DB‑Notify → Weiterleitung in den Stream (Filter auf Kurs/Unit‑Tasks), Heartbeats/Backpressure/Timeouts.
   - Live‑Summary: Use‑Case + Repo‑Port extrahieren, Fallback vereinfachen (primär Helper nutzen).
5) Doku & UI (TEILWEISE ERLEDIGT): SSR‑Seite „Live“ (Einheit), Tabelle (Matrix) und Detail‑Pane vorhanden; Polling noch offen; Hilfetexte folgen.

## Stand der Implementierung (kurz)
- OpenAPI aktualisiert; `summary` + `delta` (Polling) vertraglich definiert; zusätzlicher Detail‑Endpunkt `…/tasks/{task_id}/students/{student_sub}/submissions/latest` ergänzt.
- Migrationen: Index + Helper `get_unit_latest_submissions_for_owner` (SECURITY DEFINER) vorhanden; zusätzlicher Helper `get_latest_submission_for_owner` (SECURITY DEFINER) für Detail‑API implementiert; EXECUTE‑Grants gesetzt.
- Backend API: Summary/Delta mit EPS‑Fenster (1s) grün; Detail‑API liefert Textkörper (RLS‑sicher via Helper) und setzt `private, no-store` + `Vary: Origin`.
- UI (SSR): Live‑Matrix (sticky Kopf/erste Spalte, kompakt) vorhanden; Detail‑Pane unter der Tabelle lädt letzte Einreichung per Klick; Delta‑Polling noch offen.
- Namensanzeige: Directory‑Humanizer implementiert (E‑Mail/legacy → „Vorname Nachname“), Summary ruft humanisierte Namen; erste Tests grün. Produktions‑Verhalten wird weiter gehärtet (siehe Iteration „Namen“).

## Iteration 7 — Abschnitte freigeben in „Unterricht“ (WIP)

Warum:
- Lehrkräfte möchten in der Unterrichtsansicht (Kurs → Lerneinheit) dieselbe granulare Steuerung wie in der Kursansicht: Abschnitte einzeln freischalten/sperren, ohne Kontextwechsel.

Ziele (DoD):
- Auf der Seite „Unterricht – Live“ erscheint ein Panel „Abschnitte freigeben“ mit einer geordneten Liste aller Abschnitte der gewählten Lerneinheit und einem Toggle pro Abschnitt.
- API liefert vollständige Abschnittsliste inkl. Sichtbarkeit für das Modul des Kurses:
  - GET `/api/teaching/courses/{course_id}/modules/{module_id}/sections` → `[{ id, unit_id, title, position, visible, released_at }]` (Owner‑only, private/no‑store).
- Umschalten nutzt bestehenden Endpunkt:
  - PATCH `/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility`.
- Tests (pytest) decken Owner‑Pfad, 4xx‑Fälle und Sortierung ab.

API/Contract (neu):
- Pfad GET `/api/teaching/courses/{course_id}/modules/{module_id}/sections` (nur Owner). Response: sortierte Liste (position ↑) mit kombinierter Sichtbarkeit. Fehler: 400 `invalid_uuid`, 403 (nicht Owner), 404 (Modul unbekannt oder gehört nicht zum Kurs).

Implementierungsskizze:
- Web‑Adapter verknüpft Abschnitte (unit‑weit) mit `module_section_releases` für das Modul; für DB‑Repo optional später ein SQL‑Helper, zunächst Python‑Kombination aus `list_sections_for_author` + `list_module_section_releases_owned` (keine Inhalte, nur Meta).
- SSR: Panel in der Live‑Seite unterhalb des Titels. Toggle als `hx-patch` mit Same‑Origin‑Schutz (bestehend). Optional Bulk‑Aktionen („bis hierhin freigeben“) in späterer Iteration.

Risiken/Performance:
- Erste Version macht zwei DB‑Runden (Abschnitte + Releases). Für typische Klassengrößen unkritisch. Späterer SQL‑Helper kann das bündeln.

Nächste Schritte:
1) OpenAPI ergänzen (Pfad + Schema TeachingModuleSection).
2) Failing Tests schreiben (API Happy/Fehlerfälle).
3) Minimalen Handler implementieren (Green).
4) SSR‑Panel skizzieren, danach optional Bulk‑Aktionen.
- Tests: OpenAPI‑Vertrag, Delta‑Semantik (200→204), SSR‑Nav/Picker, SSR‑Matrix/Delta/Detail, Name‑Humanizer.

## Kritische Reflexion (Komplexität, Wartbarkeit, Sicherheit)
- Komplexität: Der per‑Student‑Fallback in der Summary erhöht Komplexität (N‑Queries). Wird nach SSE‑Forwarding und DEF‑Helper stabilisierung vereinfacht.
- Wartbarkeit: Web‑Route enthält aktuell DB‑Fallbacks; mittelfristig in Use‑Case auslagern.
- Performance: Für 20–30 Schüler akzeptabel; langfristig Helper/Join bevorzugen.
- Sicherheit: Owner‑Check in Helper, Kurs‑/Unit‑Filter, keine Inhalte in Events, `private, no‑store` + `Vary: Origin` überall.

## Iteration 2 – Polling & Deltas (Pivot)

### User Story
Als Lehrkraft möchte ich die Live-Übersicht meiner Einheit offen haben und ohne manuelles Reload sehen, welche Schüler eine Aufgabe gerade eingereicht haben. Dabei genügt mir ein Update alle paar Sekunden, solange nur die geänderten Zellen übertragen werden und der Überblick konsistent bleibt.

### BDD-Szenarien (Given–When–Then)
- Delta-Abruf (Happy Path)  
  Given ich bin Kurs-Owner und habe zuletzt um `T0` synchronisiert, When ich `GET …/summary/delta?updated_since=T0` aufrufe, Then erhalte ich nur neue/aktualisierte Zellen (`student_sub`, `task_id`, `has_submission`, `changed_at`).
- Keine Änderungen  
  Given seit `T0` ist nichts passiert, When ich `delta` abfrage, Then bekomme ich `204 No Content` oder `{cells: []}` (implementation defined) und kann mein UI unverändert lassen.
- Erste Synchronisation  
  Given ich öffne die Seite neu, When ich `GET …/summary` ohne `updated_since` aufrufe, Then bekomme ich die komplette Matrix (`tasks` + `rows`). Anschließend nutze ich `delta`.
- Fehlerfall – Ungültiger Timestamp  
  Given ich übergebe einen defekten ISO-Wert, When ich `delta` abfrage, Then erhalte ich `400 invalid_timestamp`.
- Autorisierung  
  Given ich bin nicht Owner, When ich `delta` abfrage, Then bekomme ich `403 forbidden` (wie beim Vollabruf).

### Vertrag & Migration
- OpenAPI: Neuer Pfad `/api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta` (GET) mit Query `updated_since` (required), optional `limit`/`offset`. Antwort enthält `cells` (Liste von `student_sub`, `task_id`, `has_submission`, `changed_at`).
- `GET /…/summary` akzeptiert optional `include_students=false`, um nur task-Liste zu laden (kann UI beim Start optimieren).
- Keine neue Migration nötig: Delta nutzt bestehende Helper-Funktion.

### Aktueller Stand (Pause)
- OpenAPI wurde angepasst (`summary` + neuer `delta`-Pfad, neues Schema `TeachingUnitDeltaCell`). Alte SSE-Pfade/Schema entfernt.
- Backend: `GET /summary` unterstützt `include_students=false`; neuer Endpoint `GET /submissions/delta` liefert Änderungen über den Helper bzw. Fallback.
- Fix eingebaut: Im Delta-Fallback werden `changed_at`-Timestamps jetzt mit Mikrosekundenpräzision (UTC) erzeugt, um doppelte Zellen beim zweiten Poll zu vermeiden.
- Tests: `test_teaching_live_unit_summary_api` grün (`include_students`-Variante). `test_teaching_live_unit_delta_api::test_delta_returns_cells_after_submission` sollte damit grün werden; lokale Verifikation steht aus (DB-Services starten).
- Forwarder/SSE-Code entfernt (`backend/web/services/submission_events.py`, Startup-Hooks). Plan ist auf Polling fokussiert.

### To-do nach der Pause
- [Erledigt] Delta-Test reparieren: DB‑Clock‑Skew behoben durch EPS‑Fenster (1s). Inklusion: `changed_dt > (cursor - EPS)`. Emittiertes `changed_at`: `changed_dt` oder `cursor + EPS` (Skew‑Fall). Folgepoll liefert 204.
- UI/Client-Anpassungen (Polling-Intervalle, Cursor-Verwaltung).
- Dokumentation aktualisieren (`docs/references/learning.md` etc., WIP).

## Iteration 3 – Use‑Case & Repo‑Port (Entwurf)

Ziel: Web‑Routen „Live Summary“ und „Delta“ schlank halten und Clean‑Architecture konform machen. Geschäftslogik in Use‑Cases kapseln; DB‑Zugriff über Ports (Interfaces) abstrahieren.

### API bleibt unverändert
- Keine Vertragsänderung; vorhandene Tests validieren weiterhin das Verhalten.

### Ports (Interfaces)
- `TeachingLiveRepoProtocol` (Application‑Layer):
  - `list_unit_tasks_for_owner(course_id, unit_id, owner_sub) -> list[TaskDto]`
  - `list_members_for_owner(course_id, owner_sub, limit, offset) -> list[(sub, name)]`
  - `unit_belongs_to_course_for_owner(course_id, unit_id, owner_sub) -> bool`
  - `latest_submissions_for_owner(course_id, unit_id, owner_sub, updated_since, limit, offset) -> list[DeltaCellDto]`

### Use‑Cases
- `GetUnitLiveSummaryUseCase(repo: TeachingLiveRepoProtocol)`
  - Input: `course_id, unit_id, owner_sub, include_students, limit, offset`
  - Output: `{ tasks: [...], rows?: [...] }`
- `GetUnitLiveDeltaUseCase(repo: TeachingLiveRepoProtocol, eps: timedelta = 1s)`
  - Input: `course_id, unit_id, owner_sub, updated_since, limit, offset`
  - Output: `{ cells: [...] }` oder leeres Array
  - Enthält die EPS/Cursor‑Logik (inkl. Monotonie der `changed_at`).

### Adapter/Repo (DB)
- DB‑Adapter implementiert das Protocol (nutzt bestehenden Helper `get_unit_latest_submissions_for_owner` + Fallback).
- RLS bleibt aktiv; `app.current_sub` wird je Query gesetzt.

### TDD‑Plan (Refactor ohne Verhaltensänderung)
1) Charakterisierungstests belassen (bestehende API‑Tests decken Verhalten ab).
2) Use‑Cases + Ports als reines Python implementieren (keine FastAPI/HTTP‑Kenntnis).
3) Routen minimal umbauen: Nur DTO‑Mapping, Aufruf Use‑Case, Rückgabe.
4) Tests erneut ausführen (sollten unverändert grün bleiben).

### Risiken & Gegenmaßnahmen
- Risiko: Fallback‑Komplexität wandert in Use‑Case. Gegenmaßnahme: Fallback in DB‑Repo kapseln; Use‑Case bleibt auf Delta/Summary‑Logik fokussiert.
- Risiko: EPS‑Semantik versehentlich verändert. Gegenmaßnahme: Unit‑Test für EPS‑Logik auf Use‑Case‑Ebene hinzufügen.

## Iteration 4 – UI (SSR) Live‑Matrix

Ziel: Eine minimalistische, performante und DSGVO‑konforme Live‑Oberfläche auf Einheitenebene, die ohne schweres Frontend‑Framework auskommt. Initialer Abruf via `summary`, danach periodisches Polling über `delta` (alle 3–5 s). DOM‑Aktualisierung per OOB‑Fragmenten (HTMX) ohne clientseitige Geschäftslogik.

### UI‑Anforderungen
- Lehrer‑only: Seite unter `/teaching/courses/{course_id}/units/{unit_id}/live` (SSR), Tab „Live“ neben „Freigaben“.
- Tabelle: Zeilen = Schüler (Anzeigename), Spalten = Aufgaben (Positionsreihenfolge). Zellen zeigen `✅` (mind. 1 Einreichung) oder `—` (keine Einreichung).
- Sticky Kopfzeile + erste Spalte (CSS), horizontales Scrollen bei vielen Aufgaben.
- Statusleiste: „Verbunden“/„Letztes Update: HH:MM:SS“, Poll‑Intervall 3–5 s.
- Fehler/Empty‑States: Keine Aufgaben, keine Mitglieder, keine Einreichungen — klare Hinweise.
- Barrierefreiheit: `<table>` mit `scope="col|row"`, sinnvolle `aria-label`/`title` auf Zellen.
- Security/Cache: `Cache-Control: private, no-store` und `Vary: Origin` für alle SSR‑Antworten, Same‑Origin beibehalten.

### BDD‑Szenarien (UI)
- Zugriff (Happy Path)
  - Given ich bin Kurs‑Owner, When ich `/teaching/courses/{cid}/units/{uid}/live` öffne, Then sehe ich eine Tabelle mit Kopfzeile (Aufgaben) und mindestens 0 Zeilen (Schülerliste), sowie eine Statusleiste mit letzter Aktualisierung.
- Zugriff (Fehlerfälle)
  - Given ich bin nicht Owner, When ich die Live‑Seite aufrufe, Then werde ich umgeleitet oder erhalte 403/404 (wie API, teacher‑only).
  - Given `cid`/`uid` existieren nicht oder gehören nicht zusammen, Then 404.
- Initial‑Render
  - Given es gibt 2 Aufgaben und 1 Schüler ohne Einreichungen, When ich die Seite lade, Then sehe ich `—` in allen Zellen und die Spaltenüberschriften „A1/A2“ (oder gekürzte Instruktion, wie definiert).
- Polling‑Update (Happy Path)
  - Given die Seite ist offen und `updated_since=T0` gesetzt, When eine Einreichung erzeugt wird, Then liefert `delta` innerhalb ≤ 5 s geänderte Zellen (OOB‑Fragmente), und die korrespondierende Tabellenzelle zeigt danach `✅`.
- Keine Änderungen
  - Given seit `T0` gab es keine Änderungen, When der Delta‑Abruf erfolgt, Then Antwort ist `204 No Content` und es ändert sich nichts am DOM.
- Leere Aufgabenliste
  - Given die Einheit hat keine Aufgaben, When ich die Live‑Seite öffne, Then sehe ich eine leere‑Zustandskarte statt einer Tabelle.
- Resilienz
  - Given temporärer Serverfehler im Delta‑Abruf, When ein Poll 5xx liefert, Then zeigt die Statusleiste eine Warnung und das UI versucht im nächsten Intervall erneut.

### SSR‑Routen (UI, keine OpenAPI‑Änderung)
- `GET /teaching/courses/{cid}/units/{uid}/live` — vollständige Seite; eingebettetes Fragment für die Matrix; `hx-trigger` zum zeitgesteuerten Poll.
- `GET /teaching/courses/{cid}/units/{uid}/live/matrix` — SSR‑Fragment: komplette Tabelle (Initialzustand) auf Basis `summary`.
- `GET /teaching/courses/{cid}/units/{uid}/live/matrix/delta?updated_since=…` — SSR‑Fragmente nur für geänderte Zellen (OOB‑Swap). Keine Inhalte, nur `✅`/`—` und Daten‑IDs für Zuordnung.

Hinweis: Die SSR‑Delta‑Routen nutzen intern die existierenden Anwendungsfälle/Repos (Iteration 3), nicht die HTTP‑API, um Overhead zu vermeiden. So bleiben Clean‑Architecture‑Grenzen gewahrt.

### Tests (TDD)
- `backend/tests/test_teaching_live_unit_ui_ssr.py`
  - `test_live_page_teacher_only_and_renders_table` — 401/403 Redirects, 200 OK für Owner, HTML mit Tabelle/IDs/Statusleiste vorhanden; Header prüfen: `private, no-store` und `Vary: Origin`.
  - `test_matrix_fragment_renders_initial_summary` — Fragment liefert `<table>` mit korrekten Spalten/Zeilen; Zellen haben deterministische IDs `cell-{student_sub}-{task_id}`.
  - `test_delta_fragment_returns_changed_cells_or_204` — Vor `T0` → 204; nach Submission → 200 mit OOB‑Fragmenten für genau die geänderten Zellen; Folgeruf mit neuem Cursor → 204.
  - `test_empty_states_render_help` — Keine Aufgaben/keine Mitglieder → verständliche Hinweise statt leerer Tabelle.

### Minimal‑Implementierung (Green)
- HTML‑Struktur in `backend/web/main.py` (Route `teaching_unit_live_page`):
  - Render Tabelle mit `id="live-matrix"` und Zellen `id="cell-{sub}-{task_id}"` sowie `data-sub`/`data-task`.
  - Statusleiste mit `data-updated-since` (ISO) als Cursor.
  - HTMX: `hx-get` auf `…/matrix/delta`, `hx-trigger="every 3s"`, `hx-swap="outerHTML"` für OOB‑Fragmente; Error‑Handler setzt Warnbanner.
- Fragmente in `main.py`:
  - `teaching_unit_live_matrix_partial` (summary → volle Tabelle als `<tbody>` oder `<table>` je nach Einbettung).
  - `teaching_unit_live_matrix_delta_partial` (delta → Liste `<td hx-swap-oob="true" id="cell-…">✅|—</td>`). Bei 0 Änderungen: `204`.
  - `teaching_unit_live_detail_partial` (Detail‑Pane) lädt `latest` und zeigt Textauszug + Metadaten.

### Refactor & Hardening
- Nach Iteration 3: UI‑Routen rufen Use‑Cases direkt (keine Duplikation der Delta‑/Summary‑Logik).
- Performance: Server baut nur geänderte Zellen um; keine komplette Tabellen‑Re‑Render bei Delta.
- A11y/UX: Tooltips (`title`), Fokus‑Management bei Detail‑Aufklappungen (Folgeiteration), Kontraste für Status.
- Fehlerpfade: 403/404/5xx Bannertexte, Retry‑Strategie (exponentiell begrenzt) für Polls.

### Dokumentation
- `docs/references/teaching_live.md`: Abschnitt „UI (SSR) – Polling und OOB‑Fragmente“, Beispiele für Fragmente, Cursor‑EPS‑Hinweis.
- `docs/CHANGELOG.md`: Eintrag „Live‑Matrix (SSR) – Lehrer“.

### Nicht‑Ziele in dieser Iteration
- Keine Detailansicht mit Feedback‑Rendering (separate Iteration „Detail‑Pane“).
- Keine Client‑seitigen Filter/Sortierung/Heatmaps.
- Kein WebSocket/SSE‑Betrieb (Polling bleibt Standard, SSE ggf. später optional).

## Iteration 5 – Detail‑Pane (Lehrer) für Zellen

Ziel: Beim Klick auf eine Zelle oder den Schülernamen erscheint unterhalb der Matrix eine Detailansicht zur letzten Einreichung des gewählten Schülers für die gewählte Aufgabe. Die Ansicht zeigt Metadaten (Zeitpunkt, Status, Versuche) und — falls vorhanden — den Textkörper (gekürzt) bzw. Links/Vorschau zu Bildern/PDF (ohne Auto‑Download).

### User Story
Als Lehrkraft möchte ich in der Live‑Ansicht aus der Übersicht heraus die letzte Einreichung eines Schülers zu einer Aufgabe einsehen, damit ich schnell Feedback geben und den Lernfortschritt beurteilen kann, ohne die Seite zu verlassen.

### BDD‑Szenarien
- Happy Path
  - Given ich bin Kurs‑Owner und klicke eine Zelle (S, T), When die Detailansicht geladen wird, Then sehe ich Datum/Uhrzeit, Art (Text/Bild/PDF), ggf. Textauszug und einen Link zur vollständigen Ansicht.
- Kein Fund
  - Given es gibt noch keine Einreichung, When ich die Detailansicht öffne, Then sehe ich einen freundlichen Hinweis „Keine Einreichung vorhanden“.
- Fehler/Autorisierung
  - Given ich bin nicht Owner, When ich die Detail‑API aufrufe, Then erhalte ich 403.
  - Given Task/Unit gehören nicht zum Kurs, Then 404.
- Datenschutz
  - Given Bild/PDF‑Einreichungen, Then werden nur Metadaten/Vorschaulinks angezeigt; keine Inhalte im JSON selbst.

### API (Contract‑First)
- `GET /api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest`
  - 200: `{ id, task_id, student_sub, created_at, completed_at, kind, text_body?: string, files?: [ { mime, size, url } ] }`
  - 204: Keine Einreichung gefunden
  - 400: `invalid_uuid` oder `invalid_sub`
  - 403: nicht Owner/Lehrer
  - 404: Kurs/Unit/Task‑Beziehung ungültig
  - Security: Owner‑Only; `Cache-Control: private, no-store`; `Vary: Origin`

OpenAPI‑Snippet (Entwurf):
```
  /api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest:
    get:
      summary: Letzte Einreichung eines Schülers zu einer Aufgabe (Owner)
      tags: [Teaching]
      security: [ { cookieAuth: [] } ]
      parameters:
        - in: path; name: course_id; required: true; schema: { type: string, format: uuid }
        - in: path; name: unit_id;   required: true; schema: { type: string, format: uuid }
        - in: path; name: task_id;   required: true; schema: { type: string, format: uuid }
        - in: path; name: student_sub; required: true; schema: { type: string }
      responses:
        '200': { content: { application/json: { schema: { $ref: '#/components/schemas/TeachingLatestSubmission' } } }, headers: { Cache-Control: { schema: { type: string } }, Vary: { schema: { type: string } } } }
        '204': { description: Keine Einreichung }
        '400': { description: Ungültige Parameter, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '401': { description: Unauthenticated, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '403': { description: Forbidden, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }
        '404': { description: Not found, content: { application/json: { schema: { $ref: '#/components/schemas/Error' } } } }

components:
  schemas:
    TeachingLatestSubmission:
      type: object
      required: [id, task_id, student_sub, created_at, kind]
      properties:
        id: { type: string, format: uuid }
        task_id: { type: string, format: uuid }
        student_sub: { type: string }
        created_at: { type: string, format: date-time }
        completed_at: { type: string, format: date-time, nullable: true }
        kind: { type: string, enum: [text, image, pdf] }
        text_body: { type: string, description: 'Optional; gekürzt auf max 1000 Zeichen' }
        files:
          type: array
          items:
            type: object
            required: [mime, size, url]
            properties:
              mime: { type: string }
              size: { type: integer }
              url: { type: string, format: uri }
```

### Migration (optional)
Keine Schemaänderung notwendig. Optional: SECURITY DEFINER‑Helper `get_latest_submission_for_owner(course_id, task_id, student_sub)` zur Vereinheitlichung; MVP darf fallbacken.

### TDD (pytest)
- `test_teaching_live_detail_api.py`
  - 401/403/404/400 Pfade
  - 204 ohne Einreichung
  - 200 mit Text‑Einreichung → text_body vorhanden
  - 200 mit Bild/PDF → files‑Einträge (simuliert/Mock)
- `test_teaching_live_detail_ssr.py`
  - Detail‑Fragment lädt Karte unter Matrix; Empty‑State bei 204; Fehlerbanner bei 403/404

### UI (SSR)
- Zellen klickbar: `hx-get="…/live/detail?student_sub=…&task_id=…" hx-target="#live-detail" hx-swap="innerHTML"`
- Detail‑Container `<div id="live-detail">` unterhalb der Matrix.
- Karte mit Metadaten und (optional) Textauszug; Bild/PDF als Links/Vorschau (keine Auto‑Einbettung großer Dateien).

## Iteration 6 – Namen (Humanisierung, Konsistenz, Robustheit)

Ziel: In der Live‑Matrix werden ausschließlich echte, human‑lesbare Namen angezeigt – nie SUBs, nie Roh‑E‑Mails, nie technische Präfixe (z. B. `legacy-email:`). Verhalten ist konsistent in API und UI, robust gegen Directory‑Ausfälle und performant.

Aktueller Stand
- Ursache (warum fehlten Namen?): Ein Teil der Kurs‑SUBs stammt aus der Legacy‑Migration (`legacy-email:<adresse>`) oder verweist auf Nutzer, die (noch) nicht im aktuellen Keycloak angelegt sind. Der Directory‑Lookup liefert hier `404`/leer, und aus Datenschutzgründen wurden weder SUB noch Roh‑E‑Mail angezeigt → Fallback „Unbekannt“ in der UI.
- Entscheidung: Für klar erkennbar E‑Mail‑artige Kennungen (inkl. Präfix `legacy-email:`) wird ein sicherer, deterministischer Fallback genutzt: Humanisierung des Localparts (z. B. `legacy-email:max.mustermann@schule.de` → „Max Mustermann“). Roh‑E‑Mails oder SUBs werden weiterhin nie angezeigt.
- Implementiert: Teaching‑API `resolve_student_names` erweitert — wenn Directory keine Auflösung liefert (Wert gleich SUB/leer) und `sid` E‑Mail‑artig ist oder mit `legacy-email:` beginnt, wird `humanize_identifier(sid)` als Anzeigename verwendet; sonst „Unbekannt“.
- Directory‑Adapter bleibt Quelle erster Wahl: `_display_name` bevorzugt `attributes.display_name` > `firstName/lastName` > humanisierte E‑Mail/Username; der neue Fallback greift nur bei Nichtauflösbarkeit.
- Tests ergänzt und grün: Name‑Formatierung, Summary‑Humanisierung sowie Fallback für `legacy-email:`; SSR‑Test prüft sichtbare Namen ohne E‑Mail‑Leckage.

To‑Dos
- SSR‑Absicherung: Zusätzlicher UI‑Test, der sicherstellt, dass Matrix nie `@`, `legacy-email:` oder hexartige SUB‑Muster enthält. (in Teilen umgesetzt; weiter ausbauen)
- Caching (empfohlen): Tabelle `public.identity_display_names(sub, display_name, updated_at)` + Repo‑Funktion `get_display_names(subs)`; Summary nutzt Cache‑Hit, Directory nur bei Miss/Refresh.
- Monitoring: Metrik/Log für Quote der „Unbekannt“-Fälle; Alert, wenn >5%.
- Governance/Ops: In Produktion Confidential Client mit Secret nutzen (Client‑Credentials), Service‑Account‑Rollen `view-users`/`query-users` sicherstellen. `.env`: `KC_ADMIN_CLIENT_ID`, `KC_ADMIN_CLIENT_SECRET`.
- Datenbereinigung: Legacy‑Mitglieder (nicht E‑Mail‑artig) auf echte KC‑Konten heben; bis dahin verbleibt „Unbekannt“ als sicherer Fallback.

Tests (TDD)
- `backend/tests/test_teaching_live_unit_summary_legacy_email_fallback.py`: Für `legacy-email:<adresse>` liefert die Summary humanisierte Namen („Vorname Nachname“), nicht E‑Mail/SUB.
- `backend/tests/test_teaching_live_unit_ui_ssr.py` (angepasst): sichtbarer Name humanisiert; keine E‑Mail im UI‑Text.
- `backend/tests/test_identity_access_directory_name_formatting.py`: vorhanden; deckt Display‑Name‑Regeln/Humanizer ab.

Risiken & Maßnahmen
- Directory‑Latenz/Ausfall → Cache einführen; HTMX‑Fragment initial, kein Re‑Resolve im Delta.
- Fehlkonfiguration KC → „Unbekannt“ statt SUB/E‑Mail; Admin‑Hinweis in Logs/Docs; Confidential‑Client erzwingen in Prod.

Abnahme‑Kriterium (DoD)
- In einer KC‑Testumgebung mit gemischten Mitgliedern (echte KC‑User + `legacy-email:`‑SUBs) zeigt die Matrix für beide Gruppen humanisierte Namen; API‑Antworten enthalten in `rows[].student.name` weder SUBs noch Roh‑E‑Mails/Präfixe. Nicht‑mailartige Placeholders bleiben bewusst „Unbekannt“.

Implementierungsnotizen (Referenzen)
- Fallback‑Logik: `backend/web/routes/teaching.py:1102` — Humanisierung des `sid` bei `legacy-email:`/E‑Mail‑Muster, sonst „Unbekannt“.
- Humanizer: `backend/identity_access/directory.py:100` (`humanize_identifier`).
- Tests: `backend/tests/test_teaching_live_unit_summary_legacy_email_fallback.py`, Anpassungen in `backend/tests/test_teaching_live_unit_ui_ssr.py`.
