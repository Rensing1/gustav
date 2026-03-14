# 2026-03-11 - Teaching Live: Schueler-Gesamtansicht ueber mehrere Lerneinheiten

Status: umgesetzt (2026-03-14, inklusive Review-Fixes)
Datum: 2026-03-11

## Abschluss 2026-03-14

- Die Branch-Review-Nacharbeiten sind umgesetzt:
  - kanonische `unit_ids`-Normalisierung
  - explizite SSR-Fehlerzustaende fuer `400`, `403`, `404`
  - Query-/Render-Hardening fuer die Multi-Unit-Uebersicht
- Die UX-Nacharbeit aus
  `docs/plan/2026-03-14-teaching-live-student-overview-ux.md` wurde im selben
  Batch mit umgesetzt.
- Verifiziert mit:
  - `backend/tests/test_teaching_live_student_overview_api.py`
  - `backend/tests/test_teaching_live_student_overview_ssr.py`
  - `backend/tests/test_teaching_live_detail_ssr.py`

Ziel: Die bestehende Lehrer-Live-Ansicht zeigt heute Abgaben fuer genau eine `Kurs x Lerneinheit`-Kombination. Es soll eine zweite Sicht entstehen, in der eine Lehrkraft aus der bestehenden Unit-Live-Seite heraus einen Schueler oeffnen und danach dessen Abgaben ueber alle oder eine ausgewaehlte Menge der Lerneinheiten dieses Kurses sehen kann.

Das Dokument haelt bewusst nicht nur den Zielzustand fest, sondern auch den relevanten Repo-Kontext, damit spaetere Implementierungen nicht erneut die bestehende Live-Architektur recherchieren muessen.

## Fixierte Produktentscheidungen

- Einstieg: aus der bestehenden Unit-Live-Seite, nicht von `/teaching/live` oder der Mitgliederseite.
- Darstellung: eigene Seite, nicht Drawer und nicht Detailpanel unter der Matrix.
- Default-Scope: alle dem Kurs zugeordneten Lerneinheiten sind vorausgewaehlt.
- Sichtbarkeit: alle Aufgaben bleiben sichtbar, auch wenn keine Abgabe vorliegt.
- Detailtiefe: Uebersicht plus Klick-Detail; keine Inline-Vollansicht jeder Abgabe.
- Aktualisierung: v1 ist ein serverseitiger Snapshot ohne Polling/Delta.
- Zusatzanforderung: In bestehender und neuer Ansicht muss die Aufgabenstellung angezeigt werden, wenn eine Lehrkraft auf eine Abgabe klickt.
- Leere Filterauswahl: Wenn der Lehrer alle Checkboxen abwaehlt, zeigt die Seite bewusst keine Lerneinheiten und einen klaren Empty State. Es erfolgt kein stiller Fallback auf "alle".
- `unit_ids`-Normalisierung: Doppelte Werte werden dedupliziert; die API akzeptiert hoechstens 50 `unit_ids` pro Request.
- Skalierung der SSR-Seite: Lerneinheiten werden als einzeln kollabierbare Cards gerendert; in v1 sind sie initial aufgeklappt.
- Logging/PII: Keine Klartext-Logs fuer `student_sub`, `instruction_md`, Submission-Inhalte oder komplette Filterlisten.

## Stand 2026-03-13 nach Branch-Review

### Bereits umgesetzt auf `feature/teaching-live-student-overview`

- neuer API-Pfad `GET /api/teaching/courses/{course_id}/students/{student_sub}/submissions/overview`
- neue SSR-Seite `GET /teaching/courses/{course_id}/students/{student_sub}/live`
- Verlinkung aus der bestehenden Unit-Live-Matrix auf die neue Schueleransicht
- Erweiterung des bestehenden Detailpfads um die Aufgabenstellung (`instruction_md`)
- schlanke Orchestrierung in `backend/teaching/services/live_student_overview.py`

### Im Review identifizierte Nacharbeiten

- Die SSR-Seite behandelt `400` und `403` der Overview-API nicht explizit.
  - Folge: Die Seite kann einen irrefuehrenden Leerzustand mit `200` rendern, obwohl ein echter Fehler vorliegt.
- Die `unit_ids`-Normalisierung ist nicht kanonisch.
  - Folge: Gueltige UUIDs in anderer Schreibweise, z. B. in Grossbuchstaben, koennen faelschlich als `unit_not_in_course` enden.
- Die SSR-Seite und der Service enthalten vermeidbare N+1-Query-Pfade.
  - Folge: Die neue Mehrfach-Unit-Sicht skaliert schlechter als noetig.
- Die Testabdeckung fehlt noch fuer genau diese Nacharbeiten.
  - Es gibt noch keine roten Tests fuer SSR-Fehlerdarstellung, `too_many_unit_ids` im SSR-Fluss oder kanonische UUID-Normalisierung.

### Naechste Schritte fuer die Branch-Pflege

1. Plandokument auf den Ist-Stand bringen und die Nacharbeiten explizit festhalten.
2. Rote Tests fuer die Review-Findings schreiben:
   - Service/API: kanonische UUID-Normalisierung fuer `unit_ids`
   - SSR: klare Darstellung fuer `400 too_many_unit_ids`
   - SSR: klare Darstellung fuer `403/404`, statt still in einen Leerzustand zu kippen
   - falls praktikabel: ein Refactor-Test fuer einen gebuendelten Query-Pfad ohne verhaltensaendernde Regression
3. Minimal implementieren:
   - UUIDs kanonisch normalisieren
   - SSR-Fehlerzustaende explizit rendern
   - API/SSR-Hilfsfunktionen so zuschneiden, dass keine vermeidbaren Mehrfach-Requests pro Unit mehr entstehen
4. Tests gruen ziehen, Referenzdoku bei Bedarf knapp nachziehen, dann committen.

### Leitplanke fuer die Nacharbeit

- Die Pflege bleibt bewusst innerhalb des bestehenden Contracts.
- Keine neuen Endpunkte und keine neue Migration, solange die Review-Findings sauber im vorhandenen API-/Repo-Schnitt behoben werden koennen.
- TDD bleibt auch fuer die Branch-Pflege verbindlich: erst fehlende Regressionstests, dann minimale Implementierung, dann kleiner Refactor.

## Relevanter Ist-Stand im Repo

### Lehrer-Live-Architektur heute

- Referenzdokument: `docs/references/teaching_live.md`
  - beschreibt die bestehende Architektur fuer Summary-/Delta-API und die Detailansicht der letzten Abgabe.
- Einstieg fuer Lehrkraefte:
  - SSR-Startseite: `GET /teaching/live`
  - Unit-Redirect: `GET /teaching/live/open`
  - Zielseite: `GET /teaching/courses/{course_id}/units/{unit_id}/live`
- JSON-API fuer die bestehende Live-Matrix:
  - `GET /api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary`
  - `GET /api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta`
- Detail-API fuer die letzte Abgabe:
  - `GET /api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest`
- SSR-Detailpartial:
  - `GET /teaching/courses/{course_id}/units/{unit_id}/live/detail`

### Wichtige Code-Stellen

- `backend/web/main.py`
  - `teaching_unit_live_page(...)`
  - `_render_live_matrix(...)`
  - `teaching_unit_live_detail_partial(...)`
- `backend/web/routes/teaching.py`
  - `get_unit_live_summary(...)`
  - `get_unit_live_delta(...)`
  - `get_latest_submission_detail(...)`
- `api/openapi.yml`
  - bestehende Live-Schemas `TeachingUnitLiveRow`, `TeachingUnitTaskCell`, `TeachingUnitDeltaCell`, `TeachingLatestSubmission`

### Was heute bereits vorhanden ist

- Owner-only Guards fuer Lehrkraefte inklusive `Cache-Control: private, no-store` und `Vary: Origin`.
- Ein bestehender roster-faehiger API-Pfad:
  - `GET /api/teaching/courses/{course_id}/members`
- Ein bestehender SSR-Mechanismus zum Laden aller Kursmitglieder:
  - `_fetch_all_course_members_for_ssr(...)` in `backend/web/main.py`
- Bestehende Detaildarstellung fuer Text/Datei/H5P/Auswertung/Rueckmeldung.

### Was heute noch fehlt

- Keine bestehende Ansicht `Kurs x Schueler x mehrere Lerneinheiten`.
- Keine API, die fuer genau einen Schueler die Aufgaben-/Abgabesicht ueber mehrere Lerneinheiten eines Kurses liefert.
- `TeachingLatestSubmission` enthaelt aktuell keine `instruction_md`; die Aufgabenstellung wird also im Klick-Detail heute nicht mitgeliefert.
- In `_render_live_matrix(...)` sind Schuelernamen derzeit reine Tabellenzellen, keine Links in eine Schueleransicht.

### Relevante bestehende Tests

- `backend/tests/test_teaching_live_nav_ssr.py`
- `backend/tests/test_teaching_live_unit_summary_api.py`
- `backend/tests/test_teaching_live_unit_delta_api.py`
- `backend/tests/test_teaching_live_unit_ui_ssr.py`
- `backend/tests/test_teaching_live_detail_api.py`
- `backend/tests/test_teaching_live_detail_ssr.py`
- `backend/tests/test_openapi_teaching_live_unit_contract.py`
- `backend/tests/test_openapi_teaching_live_detail_contract.py`
- DB-Hardening der bestehenden Helper:
  - `backend/tests/migration/test_teaching_live_unit_summary_helper_hardening.py`
  - `backend/tests/migration/test_teaching_latest_submission_owner_helper_hardening.py`

### Relevante DB-Helfer heute

- Bestehender Summary-Helper:
  - `public.get_unit_latest_submissions_for_owner(...)`
  - Migration: `supabase/migrations/20251102095715_teaching_live_unit_summary.sql`
- Bestehender Detail-Helper:
  - `public.get_latest_submission_for_owner(...)`
  - gehardete Signatur in `supabase/migrations/20260111130000_teaching_latest_submission_owner_helper_hardening.sql`

## Clean-Architecture- und DDD-Leitplanken fuer dieses Feature

### Bounded-Context-Zuordnung

- `teaching` bleibt der fuehrende Kontext fuer:
  - Kurs
  - Lerneinheit
  - Abschnitt
  - Aufgabe
  - Kursmodul-Reihenfolge
  - Lehrer-Sicht im Unterricht
- `learning` bleibt der fuehrende Kontext fuer:
  - Abgabe
  - Analyse
  - Rueckmeldung
  - neuester Abgabestatus pro Aufgabe
- Die neue Schueler-Gesamtansicht ist fachlich eine diagnostische Lehrer-Sicht, lebt fuer alpha-2 aber weiterhin im Kontext `teaching`, weil sie Unterrichtsstruktur aus `teaching` mit Abgabe-Aggregaten aus `learning` kombiniert.

### Fachliche Regel fuer den Datenschnitt

- Die neue Overview-API darf keine Roh-Submission-Liste aus `learning` als eigenes Modell nach aussen durchreichen.
- Stattdessen liefert sie ein `teaching`-faehiges Read-Model:
  - Schueler-Referenz
  - geordnete Lerneinheiten
  - geordnete Aufgaben
  - pro Aufgabe nur die minimalen Learning-Aggregate:
    - `has_submission`
    - `average_score`
    - `h5p_completed`
- Das verhindert, dass die Lehreransicht implizit zu einer zweiten Learning-API mit anderer Semantik wird.

### Gewuenschte Schichtgrenzen fuer die Umsetzung

- Web-Adapter:
  - nimmt HTTP entgegen
  - validiert Query-/Pfadparameter
  - ruft einen Use Case bzw. eine kleine Application-Funktion auf
  - rendert SSR/JSON
- Application / Use Case:
  - orchestriert Teaching-Struktur plus Learning-Aggregate
  - kennt keine FastAPI-, HTMX- oder HTML-Details
  - enthaelt die fachliche Regel "alle Aufgaben sichtbar, auch ohne Abgabe"
- Infrastruktur / Adapter:
  - bestehende Repos und SQL-Helper
  - optionale neue Query-Funktion fuer Snapshot-Statusdaten

### Minimalziel fuer v1

- Auch wenn noch nicht das volle Domain/Application-Layer aus `docs/ARCHITECTURE.md` umgesetzt ist, soll dieses Feature nicht noch mehr Fachlogik direkt in SSR-Renderingfunktionen vergraben.
- Deshalb soll fuer die neue Schueleransicht mindestens eine kleine, explizit benannte Orchestrierungsfunktion oder ein schlanker Use Case entstehen, statt die komplette Zusammenfuehrung in `backend/web/main.py` zu verteilen.
- Der Plan bleibt trotzdem minimalinvasiv:
  - kein grosser Package-Umbau
  - keine vollstaendige Extraktion aller bestehenden Live-Routen
  - aber neue Logik moeglichst nicht direkt an die Renderfunktionen kleben

## User Story

Als Lehrkraft moechte ich aus der bestehenden Live-Ansicht eines Kurses einen Schueler oeffnen und danach dessen Abgaben ueber alle oder ausgewaehlte Lerneinheiten dieses Kurses sehen, damit ich Unterrichtsleistungen und Luecken auf einen Blick beurteilen kann.

## BDD-Szenarien

### 1) Einstieg aus der bestehenden Live-Matrix

- Given ich bin Kurs-Owner auf `/teaching/courses/{course_id}/units/{unit_id}/live`
- When ich auf den Namen eines Schuelers klicke
- Then oeffnet sich `/teaching/courses/{course_id}/students/{student_sub}/live`
- And die Seite ist auf denselben Kurs bezogen

### 2) Default-Scope = alle Lerneinheiten des Kurses

- Given ich oeffne die neue Schueleransicht ohne `unit_ids`
- When die Seite serverseitig gerendert wird
- Then werden alle dem Kurs zugeordneten Lerneinheiten angezeigt
- And die Reihenfolge folgt der Kursmodul-Reihenfolge

### 3) Filter auf eine Teilmenge von Lerneinheiten

- Given ich oeffne die Schueleransicht mit einer Teilmenge `unit_ids`
- When alle angefragten `unit_ids` zum Kurs gehoeren
- Then werden nur diese Lerneinheiten angezeigt
- And alle anderen Lerneinheiten bleiben ausgeblendet

### 3a) Leere Auswahl ist ein bewusster Leerzustand

- Given ich rufe die Schueleransicht ohne angehakten Filter auf
- When der Request verarbeitet wird
- Then wird keine Lerneinheit geladen
- And die Seite zeigt einen klaren Hinweis, dass keine Lerneinheiten ausgewaehlt sind

### 3b) Doppelte Filterwerte werden robust normalisiert

- Given der Query-String enthaelt dieselbe `unit_id` mehrfach
- When der Request validiert wird
- Then behandelt die API diese Werte wie eine deduplizierte Menge
- And jede Lerneinheit erscheint hoechstens einmal in der Antwort

### 4) Fehlerfall: fremde oder ungueltige Lerneinheit

- Given ich rufe die Overview-API mit einer `unit_id` auf, die nicht zum Kurs gehoert
- When der Request validiert wird
- Then antwortet der Endpunkt mit `404`
- And es erfolgt kein stilles Ignorieren der fehlerhaften Filter-ID

### 5) Fehlerfall: Schueler ist nicht Mitglied des Kurses

- Given ich bin Lehrer und Owner des Kurses
- When ich die Schueleransicht fuer einen `student_sub` aufrufe, der nicht Mitglied des Kurses ist
- Then erhalte ich `404`

### 6) Alle Aufgaben bleiben sichtbar

- Given ein ausgewaehlter Schueler hat nur zu einem Teil der Aufgaben Abgaben erstellt
- When die Overview-API geladen wird
- Then liefert sie alle Aufgaben der ausgewaehlten Lerneinheiten
- And Aufgaben ohne Abgabe bleiben mit `has_submission=false` sichtbar

### 7) Klick-Detail mit Aufgabenstellung

- Given in bestehender oder neuer Ansicht wird eine vorhandene Abgabe angeklickt
- When das Detail geladen wird
- Then erscheint oberhalb der eigentlichen Abgabedetails die Aufgabenstellung aus `instruction_md`
- And darunter bleiben Text/Datei/Auswertung/Rueckmeldung wie bisher erhalten

## API- und SSR-Entwurf

### Neuer SSR-Route

- `GET /teaching/courses/{course_id}/students/{student_sub}/live`

Verhalten:

- teacher-only wie die bestehende Live-Seite
- laedt Kurs-Titel, Schueler-Name und die neue Overview-API ueber den internen API-Client
- rendert ein GET-Filterformular mit einer Checkbox pro Lerneinheit des Kurses
- alle Checkboxen sind standardmaessig gesetzt, wenn keine `unit_ids` im Query-String vorhanden sind
- rendert eine gruppierte Uebersicht:
  - pro Lerneinheit eine Section/Card
  - darin alle Aufgaben in bestehender Positionslogik
  - pro Aufgabe eine kompakte Beschriftung aus `instruction_md`
  - daneben Statusdarstellung analog zur bisherigen Live-Matrix:
    - H5P: `--`, `bearbeitet`, `abgeschlossen`
    - andere Aufgaben: Badge oder Praesenzmarker
- rendert ein leeres Detailpanel, das bei Klick auf eine Aufgabe per bestehendem SSR-Detailpfad gefuellt wird

### Neuer API-Route

- `GET /api/teaching/courses/{course_id}/students/{student_sub}/submissions/overview`

Fachlicher Status:

- Der Endpunkt gehoert zum Teaching-API-Surface, weil er eine Lehrer-Read-Projection fuer den Unterricht liefert.
- Intern konsumiert er Learning-Aggregate, exponiert aber kein Learning-spezifisches Submission-Modell.

Query:

- `unit_ids` wiederholbar, optional
- fehlt `unit_ids`, werden alle Kurs-Lerneinheiten verwendet
- `unit_ids` werden vor der Verarbeitung dedupliziert
- maximal 50 `unit_ids`; darueber `400 bad_request`
- wenn `unit_ids` explizit praesent, aber nach Normalisierung leer sind, wird eine leere `units`-Liste geliefert

Antwort `200`:

```json
{
  "student": {
    "sub": "student-123",
    "name": "Anna Beispiel"
  },
  "units": [
    {
      "id": "unit-uuid",
      "title": "Lineare Funktionen",
      "tasks": [
        {
          "id": "task-uuid",
          "instruction_md": "### Aufgabe 1",
          "position": 1,
          "kind": "native",
          "has_submission": true,
          "average_score": 8.5,
          "h5p_completed": null
        }
      ]
    }
  ]
}
```

Semantik:

- `401` unauthenticated
- `403` nicht Lehrer / nicht Owner
- `404` Schueler nicht im Kurs oder mindestens eine angefragte `unit_id` gehoert nicht zum Kurs
- `400` bei ungueltigen UUIDs oder mehr als 50 `unit_ids`
- `Cache-Control: private, no-store`
- `Vary: Origin`
- Rueckgabe-Reihenfolge:
  - `units` nach Kursmodul-Position
  - `tasks` innerhalb der Unit nach bestehender Positionslogik

### Erweiterung des bestehenden Detail-Vertrags

- Schema `TeachingLatestSubmission` in `api/openapi.yml` um `instruction_md` erweitern
- `instruction_md` soll fuer `200`-Antworten verpflichtend mitgeliefert werden
- Kann die Route trotz gueltiger `course x unit x task`-Relation die Aufgabenstellung nicht aufloesen, antwortet sie fail-closed mit Fehler statt mit einem stillen `null`
- die bestehende Detail-API bleibt auf demselben Pfad; nur der Response-Body wird erweitert

## Migrations- / SQL-Entwurf

### Neue Migration nur falls wirklich noetig

Vorgeschlagene Datei:

- `supabase/migrations/<timestamp>_teaching_course_student_live_overview.sql`

Ziel:

- neue SECURITY-DEFINER-Funktion fuer den schnellen Lookup der neuesten Abgaben eines einzelnen Schuelers ueber mehrere Lerneinheiten eines Kurses

Wichtige Vorentscheidung:

- Vor dem Schreiben einer Migration wird zuerst ein roter API-Test gegen eine Implementierung ohne neuen DB-Helper entworfen.
- Wenn die Snapshot-API fuer genau einen Schueler mit bestehenden Repo-/SQL-Pfaden klar, lesbar und performant genug umgesetzt werden kann, entfällt die neue DB-Funktion komplett.
- Die unten skizzierte Funktion ist also ein Fallback-Design fuer den Fall, dass die API-Schicht sonst unnoetig viele Einzelqueries oder komplizierte RLS-Workarounds benoetigt.
- Wenn ein neuer SQL-Helper eingefuehrt wird, soll er als Infrastrukturdetail hinter einem klar benannten Port bzw. einer kleinen Repo-Methode verschwinden und nicht direkt von mehreren Web-Routen aus aufgerufen werden.

Vorgeschlagene Signatur:

```sql
create or replace function public.get_course_student_latest_submissions_for_owner(
  p_owner_sub text,
  p_course_id uuid,
  p_student_sub text,
  p_unit_ids uuid[] default null
)
returns table (
  unit_id uuid,
  task_id uuid,
  submission_id uuid,
  h5p_completed boolean
)
```

Design-Entscheidungen:

- keine Tabellen- oder Spaltenaenderung
- keine Aenderung an `get_latest_submission_for_owner(...)`
- `instruction_md` fuer das Klick-Detail wird nicht aus dem bestehenden Detail-Helper herausgezogen, sondern in der Route separat ueber die bereits gepruefte `course x unit x task`-Relation geladen
- `search_path` hart auf `pg_catalog, public`
- `EXECUTE` nur fuer `gustav_limited`
- Owner-Bindung ueber `current_setting('app.current_sub', true)` statt ueber einen untrusted Parameter

Begruendung:

- das ist minimalinvasiver als die bestehende Detail-Helper-Signatur erneut zu veraendern
- die neue Funktion liefert nur Statusdaten, keine Inhalte
- die Detail-API kann dadurch gezielt um `instruction_md` erweitert werden, ohne ihre bestehende Sicherheits- und Fallback-Logik strukturell umzubauen
- zugleich gilt: kein neuer SECURITY-DEFINER-Helper ohne nachgewiesenen Bedarf im roten Test und in der API-Implementierungsskizze

## TDD-Plan (Red-Green-Refactor)

### 1) OpenAPI zuerst

Neue oder erweiterte Contract-Tests:

- neuer Contract-Test fuer `/api/teaching/courses/{course_id}/students/{student_sub}/submissions/overview`
- bestehender Contract-Test fuer `TeachingLatestSubmission` wird um `instruction_md` erweitert

### 2) API-Tests rot schreiben

Neue Datei:

- `backend/tests/test_teaching_live_student_overview_api.py`

Abdecken:

- `401` / `403`
- `400` bei mehr als 50 `unit_ids`
- `404` bei Nicht-Mitglied
- `404` bei fremder `unit_id`
- Default ohne `unit_ids` = alle Kurs-Lerneinheiten
- Teilmengenfilter mit `unit_ids`
- explizit leere Auswahl liefert leere `units`-Liste
- doppelte `unit_ids` werden dedupliziert
- Aufgaben ohne Abgabe bleiben enthalten
- H5P-/Score-Felder werden korrekt gesetzt

Zusatz fuer Schichtenkonsistenz:

- ein kleiner Unit-Test fuer die reine Orchestrierungsfunktion / den Use Case, sobald diese Extraktion entsteht
- dort keine HTTP- oder HTML-Assertions, sondern nur:
  - Reihenfolge der Lerneinheiten
  - Sichtbarkeit aller Aufgaben
  - Overlay der Learning-Aggregate

### 3) SSR-Tests rot schreiben

Neue oder erweiterte Tests:

- in `backend/tests/test_teaching_live_unit_ui_ssr.py`
  - Schuelernamen in `_render_live_matrix(...)` sind Links auf die neue Schuelerseite
- neue Datei:
  - `backend/tests/test_teaching_live_student_overview_ssr.py`

Abdecken:

- Lehrer kann die neue Seite oeffnen
- alle Units sind initial vorausgewaehlt
- Checkbox-Filter reduziert die sichtbaren Lerneinheiten
- komplett abgewaehlte Filterung zeigt einen klaren Empty State
- Aufgaben bleiben auch ohne Abgabe sichtbar
- Klick auf eine Aufgabe zeigt das bestehende Detailpanel
- Schuelerlinks und Aufgabenlinks bleiben per Tastatur erreichbar und haben verstaendliche Linktexte

### 4) Detail-API/SSR rot erweitern

Bestehende Tests erweitern:

- `backend/tests/test_teaching_live_detail_api.py`
- `backend/tests/test_teaching_live_detail_ssr.py`

Neue Erwartungen:

- `instruction_md` ist im JSON der Detail-API enthalten
- die SSR-Detailansicht rendert einen Abschnitt "Aufgabenstellung" oberhalb der Abgabe

### 5) Minimale Implementierung

Reihenfolge:

1. OpenAPI aendern
2. kleine Application-Orchestrierung fuer "Schueler-Live-Uebersicht" einfuehren
3. neue API fuer die Uebersicht implementieren
4. neue SSR-Seite implementieren
5. bestehende Live-Matrix-Namen verlinken
6. bestehende Detail-API und SSR um `instruction_md` erweitern
7. Referenzdoku `docs/references/teaching_live.md` aktualisieren

### 6) Refactor

- gemeinsame kleine Hilfsfunktionen fuer:
  - Validierung der ausgewaehlten `unit_ids`
  - Laden des Kurs-Schuelers
  - Gruppierung der Aufgaben nach Lerneinheit
- keine grosse Architekturverschiebung in v1
- Clean-Architecture-Luecken der bestehenden Live-Routen nur markieren, nicht in diesem Schritt gross umbauen
- Falls die Orchestrierung anfangs als lokale Funktion entsteht, im Refactor in einen klar benannten, framework-freien Ort verschieben, z. B. in den Teaching-Kontext statt in SSR-Code.

## Konkrete Implementierungshinweise

### Fuer die neue Overview-API

- Owner- und Kurs-Guard genauso fail-closed wie in der bestehenden Live-API
- Kursmodule einmal laden und daraus die erlaubte Menge von `unit_ids` ableiten
- Kursmitgliedschaft des `student_sub` explizit pruefen
- Query-Parameter vor jeder DB-Arbeit normalisieren:
  - UUID-Validierung
  - Deduplizierung
  - Limit `<= 50`
- Aufgabenlisten nicht aus Submission-Daten rekonstruieren, sondern aus der Teaching-Struktur:
  - Kursmodule -> Unit -> Sections -> Tasks
- Statusdaten aus dem neuen DB-Helper auf die strukturierte Aufgabenliste ueberlagern
- Falls ohne neuen DB-Helper implementiert wird, den Query-Pfad so waehlen, dass keine N+1-Schleifen pro Aufgabe entstehen
- Die API darf intern eine Anti-Corruption-Schicht zwischen `learning`-Rohdaten und dem Teaching-Read-Model haben:
  - keine Weitergabe von `learning_submissions`-Zeilen direkt an JSON/SSR
  - stattdessen explizite Mapping-Funktion von Learning-Aggregat -> Teaching-Task-Status

### Fuer die neue SSR-Seite

- kein neues Frontend-JS in v1
- Filter als normales GET-Formular
- pro Lerneinheit eine kollabierbare Card mit kurzer Summary-Zeile:
  - Unit-Titel
  - Anzahl Aufgaben
  - Anzahl Aufgaben mit Abgabe
- Detailpanel ueber den bestehenden SSR-Detailpfad laden:
  - `/teaching/courses/{course_id}/units/{unit_id}/live/detail?student_sub=...&task_id=...`
- Empty-State-Faelle explizit rendern:
  - keine Lerneinheiten ausgewaehlt
  - gewaehlte Lerneinheiten enthalten keine Aufgaben
- SSR soll nur praesentieren:
  - keine Query- oder Join-Logik in der Renderfunktion
  - vorbereitete View-Model-Daten aus der API/Application-Schicht rendern

### Fuer das bestehende Klick-Detail

- `get_latest_submission_detail(...)` laedt `instruction_md` zusaetzlich zur Submission
- `teaching_unit_live_detail_partial(...)` rendert die Aufgabenstellung oberhalb des bestehenden Inhalts
- dieselbe SSR-Detaildarstellung wird von alter und neuer Ansicht wiederverwendet
- Markdown der Aufgabenstellung wird ueber denselben sicheren Renderer wie bestehende Aufgaben-/Materialtexte ausgegeben
- Die Detailroute bleibt fachlich eine Teaching-Read-Projection ueber genau eine Aufgabe und eine Abgabe, nicht eine allgemeine Learning-Detail-API

### Fuer Logging und Datenschutz

- Nur strukturierte, minimierte Logeintraege:
  - keine Klartext-Schuelernamen
  - kein `student_sub` im Klartext
  - keine `instruction_md`- oder Submission-Inhalte
- Bei Diagnosefeldern hoechstens gehashte oder gekuerzte IDs verwenden, analog zu bestehenden Live-Routen
- Die neue Seite bleibt owner-only; keine zusaetzlichen Cache-Ausnahmen oder oeffentlichen Links

## Nicht-Ziele fuer v1

- kein Polling/Delta fuer die neue Schueleransicht
- kein zusaetzlicher Student-Switcher auf der neuen Seite
- keine neue Analytics-Aggregation ueber den hier benoetigten Live-Status hinaus
- kein grosser Umbau der bestehenden Live-Routen in separate Use-Case-Klassen
- keine gesamte Submission-Historie pro Aufgabe; sichtbar bleibt der neueste Status wie in der bestehenden Live-Semantik
- kein neues, kontextuebergreifendes "Super-DTO", das Teaching- und Learning-Begriffe ungeordnet vermischt

## Risiken und offene technische Punkte

- Die bestehende Live-Implementierung liegt teilweise direkt in `backend/web/routes/teaching.py` und `backend/web/main.py`; fuer diesen Schritt ist das akzeptiert, aber nicht das langfristige Zielbild.
- Der neue DB-Helper muss dieselben Hardening-Standards wie die bestehenden SECURITY-DEFINER-Funktionen einhalten.
- Weil `instruction_md` bislang nicht Teil von `TeachingLatestSubmission` ist, muessen OpenAPI, API-Tests und SSR-Tests synchron aktualisiert werden, sonst driftet der Vertrag.
- Die neue Uebersicht soll bewusst keine gesamte Submission-Historie zeigen; dargestellt wird weiterhin der neueste Status pro Aufgabe, das passt zur bestehenden Live-Semantik.
- Das groesste Komplexitaetsrisiko ist ein vorschnell eingefuehrter neuer DB-Helper. Deshalb erst API-Design und Test rot festziehen, dann ueber SQL entscheiden.
- Das groesste Bedienbarkeitsrisiko ist eine zu lange Seite bei vielen Lerneinheiten; deshalb kollabierbare Cards und Empty States von Anfang an einplanen.

## Repo- und Docs-Konsistenz

- Nach der Implementierung `docs/references/teaching_live.md` erweitern:
  - neue Schueler-Overview-API
  - neue SSR-Seite
  - erweiterte Detailansicht mit Aufgabenstellung
- Falls ein neuer DB-Helper entsteht, seine Sicherheitsannahmen auch ueber einen passenden Migrationstest absichern.
- Das Wording soll an `docs/glossary.md` anschliessen:
  - `Kurs`, `Lerneinheit`, `Aufgabe`, `Abgabe`, `Rueckmeldung`, `Analyse`
- In der Dokumentation klar benennen, dass die neue Sicht im Kontext `teaching` implementiert ist, aber Learning-Aggregate konsumiert.
- Falls eine neue Orchestrierungsfunktion oder ein neuer Use Case entsteht, diese Benennung auch in Plan, Tests und Referenzdoku konsistent durchziehen.

## Kurzfassung fuer den naechsten Assistenten

Wenn du dieses Feature umsetzt, beginne nicht mit der UI. Beginne mit:

1. OpenAPI fuer den neuen Overview-Endpunkt und `TeachingLatestSubmission.instruction_md`
2. einem roten API-Test fuer `course x student x unit_ids`
3. einem roten API-/SSR-Test fuer die neue Aufgabenstellung im Klick-Detail
4. ziehe die neue Fachlogik zuerst in eine kleine, framework-freie Orchestrierung statt direkt in SSR-Code
5. pruefe dann bewusst, ob die API ohne neuen DB-Helper klar umsetzbar ist

Danach erst die minimale Implementierung in API, SSR-Seite, Detailrenderer und Referenzdoku.
