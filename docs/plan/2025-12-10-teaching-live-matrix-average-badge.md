# Plan: Durchschnittliche Kriterien-Badge in der Live-Matrix

**Datum:** 2025‑12‑10  

## Ausgangssituation und Problem

In der Lehrkraft‑Ansicht **„Unterricht › Live“** zeigt die Matrix (Schüler × Aufgaben) aktuell nur einen Minimalstatus je Zelle:

- Ein Häkchen `✅`, wenn mindestens eine Einreichung (`Submission`) zu dieser Aufgabe existiert (`has_submission == true`).
- Einen Gedankenstrich `—`, wenn noch keine Einreichung vorliegt.

Technisch basiert diese Ansicht auf:

- **API (JSON, Summary):**  
  `GET /api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary`  
  → liefert `tasks[]` und `rows[]` mit Zellen vom Typ `TeachingUnitTaskCell = { task_id, has_submission }`.
- **API (JSON, Delta):**  
  `GET /api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta`  
  → liefert `cells[]` vom Typ `TeachingUnitDeltaCell = { student_sub, task_id, has_submission, changed_at }`.
- **SSR (Matrix):**  
  `_render_live_matrix(course_id, unit_id, tasks, rows)` in `backend/web/main.py` erzeugt `<td>`‑Zellen mit `✅` bzw. `—`.
- **SSR (Delta‑Fragment):**  
  `teaching_unit_live_matrix_delta_partial` rendert Out‑of‑Band‑Updates (`hx-swap-oob="true"`) und schreibt ebenfalls nur `✅`/`—`.

Die eigentliche Kriterien‑Auswertung (`analysis_json` im Schema `criteria.v2`) steht bereits für die Detailansicht zur Verfügung:

- **Detail‑API:**  
  `GET /api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest`  
  → liefert `TeachingLatestSubmission` inkl. `analysis_json`.
- **Detail‑UI (Lehrkraft):**  
  `/teaching/courses/{course_id}/units/{unit_id}/live/detail?student_sub=…&task_id=…`  
  → nutzt `_render_analysis_criteria_section(analysis_json)`, um Kriterienkarten mit Badges (`badge-success`, `badge-warning`, `badge-error`) anzuzeigen.

**Problem aus Sicht der Lehrkraft:**  
Die Matrix zeigt nur „hat eingereicht / hat nicht eingereicht“. Die Lehrkraft muss für jede Zelle einzeln in die Detailansicht klicken, um zu sehen, *wie gut* eine Einreichung bewertet wurde. Es fehlt ein kompakter, farbcodierter Überblick direkt in der Matrix.

## User Story

> **Als Lehrkraft** möchte ich in der Live‑Matrix (Schüler × Aufgaben) nicht nur sehen, welche Schüler bereits eine Lösung eingereicht haben, sondern zu jeder vorhandenen Einreichung eine farbcodierte Badge mit dem durchschnittlichen Kriterien‑Score sehen, damit ich auf einen Blick erkennen kann, welche Aufgaben gut oder schlecht bearbeitet wurden und gezielt nachfragen kann, ohne jede Detailansicht einzeln öffnen zu müssen.

## BDD‑Szenarien (Given‑When‑Then)

### 1. Happy Path – Einreichung mit vollständiger Kriterien‑Auswertung

- **Given** eine Lerneinheit mit mindestens einer Aufgabe und ein Kurs mit mehreren Schülern,  
  **und** ein Schüler hat zu einer Aufgabe eine Einreichung mit `analysis_json` im Schema `criteria.v2`,  
  **und** `criteria_results[]` enthält mehrere Kriterien mit gültigen `score`‑Werten (0–10),
- **When** die Lehrkraft die Live‑Ansicht für diese Lerneinheit öffnet,  
  **Then** wird in der Matrix‑Zelle für diesen Schüler und diese Aufgabe eine Badge angezeigt,  
  **und** die Badge zeigt den gerundeten Durchschnitt der Kriterien‑Scores (z. B. `7/10`),  
  **und** die Badge‑Farbe folgt dem bestehenden Banding (`badge-error` für niedrige, `badge-warning` für mittlere, `badge-success` für hohe Scores).

### 2. Happy Path – Einreichung ohne abgeschlossene Auswertung (nur Häkchen)

- **Given** ein Schüler hat eine Einreichung zu einer Aufgabe abgegeben,  
  **und** die automatische Auswertung ist noch nicht abgeschlossen (`analysis_json` ist `null` oder enthält keine `criteria_results`),  
  **When** die Lehrkraft die Live‑Matrix betrachtet,  
  **Then** zeigt die Zelle weiterhin nur einen Häkchen‑Status oder ein neutrales Symbol (z. B. `✅`),  
  **und** es wird *keine* Score‑Badge angezeigt,  
  **damit** unvollständige oder noch laufende Auswertungen nicht als „0 Punkte“ missverstanden werden.

### 3. Edge Case – Kriterienscores mit unterschiedlichen Maxima

- **Given** `analysis_json.criteria_results[]` enthält Kriterien mit individuellen `max_score`‑Werten (z. B. 5, 10),  
  **und** ein Kriterium hat `score=4, max_score=5` und ein anderes `score=8, max_score=10`,  
  **When** die Live‑Matrix den Durchschnittswert berechnet,  
  **Then** werden die Einzelwerte zunächst auf eine gemeinsame 0–10‑Skala normalisiert (z. B. 4/5 → 8/10),  
  **und** der Durchschnitt wird aus diesen normalisierten Werten gebildet,  
  **und** die Badge zeigt den gerundeten Durchschnitt auf Basis dieser normierten Skala (z. B. `8/10`).

*(Hinweis: Konkrete Normalisierungsstrategie muss im DB‑/Backend‑Entwurf festgelegt werden; hier wird nur die Erwartung skizziert, dass unterschiedliche Maxima fair aggregiert werden.)*

### 4. Edge Case / Fehlerfall – Keine Kriterien‑Scores oder defekte Analyse

- **Given** `analysis_json` ist zwar gesetzt, aber entweder enthalten die `criteria_results` keine gültigen `score`‑Werte (nur Texte),  
  **oder** das Payload liegt in einem unerwarteten bzw. defekten Format vor (z. B. falsche Typen, fehlende Felder),  
  **When** die Live‑Matrix versucht, einen Durchschnittswert zu berechnen,  
  **Then** wird **kein** numerischer Durchschnitt angezeigt,  
  **und** die Zelle bleibt beim bisherigen Häkchen/Strich‑Status,  
  **und** optional wird eine anonymisierte Log‑Nachricht für die Analysepipeline geschrieben,  
  **damit** rein qualitative oder defekte Auswertungen nicht als „0 Punkte“ fehlinterpretiert werden und die Matrix robust gegen Schema‑Fehler bleibt.

### 5. Edge Case – Mehrere Einreichungen (Versuche) eines Schülers

- **Given** ein Schüler hat mehrere Einreichungen zu derselben Aufgabe,  
  **und** die Detail‑API verwendet die *neueste* Einreichung als Basis (`latest submission`),  
  **When** die Live‑Matrix den Durchschnittswert anzeigt,  
  **Then** basiert der angezeigte Durchschnitt ausschließlich auf der neuesten Einreichung und deren `analysis_json`,  
  **und** ältere Versuche beeinflussen die Badge in der Matrix nicht mehr.

### 6. Fehlerfall – Keine Berechtigung oder fehlende Relation

- **Given** ein angemeldeter Benutzer ohne Lehrerrolle oder ein Lehrer, der nicht Besitzer des Kurses ist, ruft die Summary‑ oder Delta‑Endpunkte auf,  
  **When** die API die Live‑Matrixdaten liefert,  
  **Then** bleiben die bisherigen Sicherheitssemantiken unverändert (401/403/404),  
  **und** es werden in keinem Fall Score‑Informationen an unberechtigte Benutzer ausgeliefert.

### 7. Pagination und Delta‑Updates

- **Given** die Lehrkraft sieht eine Live‑Matrixseite mit paginierter Schülerliste (`limit`/`offset`) und Polling über `/submissions/delta`,  
  **When** neue Einreichungen mit Auswertung hinzukommen oder bestehende Auswertungen sich ändern,  
  **Then** werden die betreffenden Zellen über das Delta‑Fragment aktualisiert,  
  **und** sowohl der Häkchen‑Status als auch die Score‑Badge werden konsistent aktualisiert,  
  **und** der Cursor‑Mechanismus (`changed_at` → `liveCursorUpdated.cursor`) bleibt unverändert robust gegenüber Clock‑Skew.

## Contract‑First: API‑ und Schema‑Entwurf

Ziel: Die Live‑API soll *optional* aggregierte Auswertungsinformationen pro Zelle liefern, ohne bestehende Clients zu brechen und ohne den Datenschutzgrundsatz („nur minimal notwendige Daten“) auszuhebeln.

### 1. Erweiterung `TeachingUnitTaskCell` (Summary‑API)

Aktuell (vereinfacht):

```yaml
TeachingUnitTaskCell:
  type: object
  required: [task_id, has_submission]
  additionalProperties: false
  properties:
    task_id:
      type: string
      format: uuid
    has_submission:
      type: boolean
      description: True if at least one submission exists for this student and task
```

Vorgeschlagene Erweiterung:

- Neues optionales Feld `average_score` als nummerischer 0–10‑Wert pro Zelle.

```yaml
TeachingUnitTaskCell:
  type: object
  required: [task_id, has_submission]
  additionalProperties: false
  properties:
    task_id:
      type: string
      format: uuid
      description: Task identifier within the unit
    has_submission:
      type: boolean
      description: True if at least one submission exists for this student and task
    average_score:
      type: number
      format: float
      minimum: 0
      maximum: 10
      nullable: true
      description: >
        Optional average criteria score for the latest submission (0..10).
        When null or absent, the UI should fall back to a simple submission
        status indicator (e.g. checkmark).
```

### 2. Erweiterung `TeachingUnitDeltaCell` (Delta‑API)

Aktuell (vereinfacht):

```yaml
TeachingUnitDeltaCell:
  type: object
  required: [student_sub, task_id, has_submission, changed_at]
  additionalProperties: false
  properties:
    student_sub: { type: string }
    task_id: { type: string, format: uuid }
    has_submission: { type: boolean }
    changed_at: { type: string, format: date-time }
```

Vorgeschlagene Erweiterung (analog zur Summary‑Zelle):

```yaml
TeachingUnitDeltaCell:
  type: object
  description: Single cell change in the live overview matrix.
  required: [student_sub, task_id, has_submission, changed_at]
  additionalProperties: false
  properties:
    student_sub:
      type: string
      description: Student identifier (OIDC sub).
    task_id:
      type: string
      format: uuid
      description: Task identifier within the unit.
    has_submission:
      type: boolean
      description: True if at least one submission exists after the change; false when none exist.
    average_score:
      type: number
      format: float
      minimum: 0
      maximum: 10
      nullable: true
      description: >
        Optional average criteria score for the latest submission at the time
        of this change. May be null when no completed analysis is available.
    changed_at:
      type: string
      format: date-time
      description: Timestamp (ISO8601 UTC) of the most recent submission status change.
```

### 3. Datenschutz‑ und Sicherheitsaspekte

- Es werden **keine** textuellen Inhalte (`text_body`, `feedback_md`, `explanation_md`) über die Live‑Summary/Delta‑APIs preisgegeben, sondern nur ein aggregierter, dimensionloser Score (0–10).
- RLS‑ und Owner‑Checks bleiben unverändert (`gustav_limited`, `get_unit_latest_submissions_for_owner`), d. h. Scores werden ausschließlich dem Kurs‑Owner angezeigt.
- Die Badge ist damit ein stark verdichteter, aber datensparsamer Indikator, vergleichbar mit einer Note ohne Kommentar.

## DB‑Entwurf (Supabase/PostgreSQL)

Ziel: Den Durchschnittswert effizient berechnen, ohne N+1‑Queries pro Zelle und ohne die bestehende `learning_submissions`‑Tabelle zu duplizieren.

### 1. Quelle der Kriterien‑Scores

- `learning_submissions.analysis_json` speichert die Kriterien‑Auswertung (Schema `criteria.v1`/`criteria.v2`).
- Die Live‑APIs arbeiten bereits mit:
  - `public.get_unit_latest_submissions_for_owner(...)` für Matrix/Delta (IDs und Timestamps).
  - `public.get_latest_submission_for_owner(...)` für die Detailansicht.

### 2. Aggregation im Web‑Adapter (MVP)

Für die erste Iteration bleibt der DB‑Helper `get_unit_latest_submissions_for_owner` unverändert und liefert weiterhin IDs/Timestamps. Die Aggregation der Kriterien‑Scores passiert im Python‑Code des Teaching‑Web‑Adapters:

- Für die im Summary‑Resultat betroffenen `(course_id, unit_id, task_ids[], student_subs[])` wird in einer **gebündelten** Query aus `learning_submissions` das Feld `analysis_json` der jeweils neuesten Submission geladen (unter Beibehaltung von RLS und Ownership‑Checks).  
- Eine kleine, reine Helper‑Funktion `compute_average_score_from_analysis(analysis_json)` normalisiert die einzelnen Kriterien‑Scores auf die 0–10‑Skala (analog zu `_normalise_criterion_score`) und liefert einen gerundeten Durchschnitt oder `None`, wenn keine sinnvolle Berechnung möglich ist.
- Sowohl Summary‑ als auch Delta‑Handler verwenden diesen Helper, um `average_score` für jede Zelle zu setzen, ohne N+1‑Queries zu erzeugen.

### 3. Mögliche spätere Optimierung

Falls sich Performance‑Engpässe zeigen, kann in einer späteren Iteration:

- der SQL‑Helper `get_unit_latest_submissions_for_owner` um ein aggregiertes Score‑Feld erweitert werden, **oder**
- ein zusätzliches SECURITY‑DEFINER‑View/Helper eingeführt werden, das die Aggregation in der DB vornimmt.

Solche Optimierungen sind bewusst **nicht** Teil der ersten Implementierung; sie können bei Bedarf mit separatem Plan und Migration nachgezogen werden.

## Teststrategie (High‑Level)

*Dieser Plan skizziert nur die Tests auf Verhaltensebene; konkrete pytest‑Tests werden in einem separaten Schritt nach TDD‑Schema (RED‑GREEN‑REFACTOR) ausgearbeitet.*

- **API‑Tests Summary (`test_teaching_live_unit_summary_api.py`):**
  - Neuer Happy‑Path‑Test, der sicherstellt, dass bei vorhandener, abgeschlossener `analysis_json.criteria_results` das Feld `average_score` gesetzt ist.
  - Tests für Fälle ohne Analyse bzw. mit defekter Analyse, bei denen `average_score` `null` oder nicht vorhanden ist.
- **API‑Tests Delta (`test_teaching_live_unit_delta_api.py`):**
  - Sicherstellen, dass geänderte Zellen neben `has_submission` auch `average_score` tragen, sobald Auswertung vorhanden ist.
  - Cursor‑Semantik unverändert (200/204, `changed_at` bleibt maßgeblich).
- **Unit‑Tests für Score‑Helper:**
  - Kleine, fokussierte Tests für `compute_average_score_from_analysis`, die unterschiedliche `criteria_results`‑Kombinationen (inkl. fehlender/nicht‑numerischer Scores und Maxima) abdecken.
- **UI‑Tests SSR‑Matrix (`backend/web/main.py`):**
  - Tests für `_render_live_matrix`, die prüfen:
    - Zelle ohne `average_score` → Häkchen/Strich wie bisher.
    - Zelle mit `average_score` → Badge mit Score (`x/10`) und korrekter CSS‑Klasse (`badge-error`/`badge-warning`/`badge-success`).
  - Delta‑Fragment‑Tests: `teaching_unit_live_matrix_delta_partial` rendert OOB‑`<td>` mit entsprechendem Badge‑HTML.

## Nächste Schritte (Implementierungsfahrplan)

1. **Contract‑Anpassung:**  
   OpenAPI‑Schemas `TeachingUnitTaskCell` und `TeachingUnitDeltaCell` gemäß obigem Entwurf um das optionale Feld `average_score` erweitern; Referenzdokument `docs/references/teaching_live.md` aktualisieren, um die Semantik des Durchschnitts‑Scores zu beschreiben.

2. **Tests (RED):**  
   Neue pytest‑Tests für Summary/Delta‑APIs und SSR‑Rendering der Matrix schreiben, die das neue Badge‑Verhalten erwarten (Durchschnitt, Farbbanding, Fallbacks).

3. **Backend‑Implementierung (GREEN, minimal):**  
   - Aggregation der Scores im Python‑Code des Teaching‑Web‑Adapters implementieren (`compute_average_score_from_analysis`).  
   - Summary‑ und Delta‑Handler in `backend/web/routes/teaching.py` erweitern, um `average_score` pro Zelle zu setzen.  
   - `_render_live_matrix` und `teaching_unit_live_matrix_delta_partial` anpassen, um bei vorhandenem Score eine Badge statt eines reinen Häkchens zu rendern.

4. **Refaktor & Robustheit (REFACTOR):**  
   - Code auf KISS, Clean Architecture und Performance (kein N+1) prüfen.  
   - Auslagerung der Score‑Aggregation und des Zell‑Renderings in kleine, gut testbare Helper‑Funktionen (z. B. `compute_average_score_from_analysis(analysis_json)` und `_render_live_cell(...)`), analog zu `_normalise_criterion_score`, um Duplikate zwischen initialer Matrix und Delta‑Fragment zu vermeiden.

5. **Dokumentation:**  
   - `docs/references/teaching_live.md` um den neuen Badge‑Score in der Matrix ergänzen.  
   - Kurze Beschreibung der Semantik („Durchschnitt der Kriterien‑Scores“, 0–10‑Skala, Farbbanding) für Lehrkräfte.

## Bekannter Bug: Häkchen nach Delta nicht mehr klickbar

### Beobachtung

In der aktuellen Implementierung wird die Live‑Matrix initial vollständig per SSR gerendert. Jede Zelle enthält dabei:

- einen `id`‑Attributwert der Form `cell-{student_sub}-{task_id}`,  
- `data-sub`/`data-task`,  
- und vor allem die HTMX‑Attribute `hx-get`, `hx-target="#live-detail"`, `hx-swap="innerHTML"`,  
  sodass ein Klick auf die Zelle das Detail‑Panel unter der Matrix lädt.

Bei späteren Updates über das Delta‑Fragment (`/teaching/courses/{course_id}/units/{unit_id}/live/matrix/delta`) werden die betroffenen `<td>`‑Elemente per `hx-swap-oob="true"` ersetzt. Die aktuell gerenderte HTML‑Form:

- `<td id="cell-…-…" hx-swap-oob="true">✅</td>`

ersetzt das bestehende `<td>` vollständig und **enthält keine** `hx-get`/`hx-target`‑Attribute mehr. Ergebnis:

- Der neu erscheinende Haken ist eine „nackte“ Zelle ohne HTMX‑Verhalten.  
- Erst ein vollständiger Reload der Seite (erneutes SSR der Matrix) stellt die Klickbarkeit wieder her.

### Minimalinvasive Lösung (geplanter Fix)

Statt im Delta‑Fragment nackte `<td>`‑Elemente ohne HTMX‑Attribute zu rendern, soll das Delta dieselbe Struktur verwenden wie die initiale Matrix:

- Für jede geänderte Zelle werden die Attribute aus `_render_live_matrix` nachgebildet:
  - `id="cell-{student_sub}-{task_id}"`  
  - `data-sub="{student_sub}"` und `data-task="{task_id}"`  
  - `hx-get="/teaching/courses/{course_id}/units/{unit_id}/live/detail?student_sub=…&task_id=…"`  
  - `hx-target="#live-detail"`  
  - `hx-swap="innerHTML"`  
  - zusätzlich `hx-swap-oob="true"` für die Out‑of‑Band‑Ersetzung.

Auf diese Weise ersetzt das Delta‑Fragment das `<td>`‑Element komplett, aber der neu eingesetzte Knoten besitzt von Anfang an wieder die benötigten HTMX‑Attribute für zukünftige Klicks.

**Konkreter Implementierungsschritt (in einer späteren Iteration):**

- In `teaching_unit_live_matrix_delta_partial` (SSR‑Delta‑Route in `backend/web/main.py`) wird im Loop über `cells[]` statt
  - `'<td id="{cell_id}" hx-swap-oob="true">{content}</td>'`
  eine Variante verwendet, die die oben genannten Attribute mitsamt Link auf die Detail‑Route setzt.  
- Optional kann die Logik zum Bauen einer Zelle in einen kleinen Helper ausgelagert werden (z. B. `_render_live_cell(course_id, unit_id, student_sub, task_id, content, *, oob=False)`), um die HTML‑Struktur zwischen Initial‑Matrix und Delta‑Fragment synchron zu halten.

Die Änderung ist bewusst minimalinvasiv:

- Keine API‑ oder Schemaänderung notwendig.  
- Nur das SSR‑Delta‑Fragment wird angepasst, um OOB‑Updates „vollwertige“ klickbare Zellen zu machen.

## Konsistentes Markdown‑Rendering für Schüler‑ und Lehreransicht

### Ausgangssituation

- In der **Schüleransicht** (Submission‑History im Learning‑Bereich) wird der Antworttext (`text_body`) über  
  `render_markdown_safe(text_src)` in HTML gerendert (`backend/web/main.py:688`).  
  → Markdown‑Syntax (Überschriften, Listen, Hervorhebungen) erscheint formatiert.
- In der **Lehreransicht** der Live‑Detailansicht (`/teaching/…/live/detail`) wird derselbe `text_body` aktuell so verarbeitet:
  - `body_raw = str(data.get("text_body") or "")`  
  - `body = Component.escape(body_raw)`  
  - Rendering im Text‑Tab via  
    `<pre class="submission-body">{body}</pre>` (`backend/web/main.py:3523`).  
  → Ergebnis: Lehrer sehen einen reinen, escapten Textblock mit sichtbarer Markdown‑Syntax, nicht formatiert.
- Für **Materialien** (`body_md`) und **Aufgaben‑Anweisungen** (`instruction_md`) wird bereits dieselbe Funktion `render_markdown_safe` verwendet (`backend/web/main.py:1350`, `1405`).

### Geplante Vereinheitlichung

Ziel: Schüler‑ und Lehreransicht sollen denselben, sicheren Markdown‑Parser nutzen, damit Einreichungen in beiden Rollen optisch konsistent erscheinen.

- Im Text‑Tab der Live‑Detailansicht wird zukünftig:
  - `text_body` (bzw. ein analoger Fallback wie in der Schüleransicht) über `render_markdown_safe` gerendert,  
  - das `<pre>`‑Element durch einen normalen Container (z. B. `<div class="analysis-text">…</div>`) ersetzt, der denselben Stil wie die Schüler‑History verwendet.
- Der Parser bleibt identisch:
  - Implementierung in `backend/web/components/markdown.py: render_markdown_safe`,  
  - bereits im Einsatz für Material‑Markdown, Aufgaben‑Instruktionen und Schüler‑Antworten.

### Einordnung in den Fahrplan

Diese Änderung ist logisch mit der Live‑Detailansicht verknüpft, aber unabhängig vom Matrix‑Badge‑Feature:

- Sie erfordert keine API‑ oder DB‑Änderung, sondern nur Anpassungen im SSR‑Code der Detail‑Route.  
- Sie kann nach Umsetzung der Badge‑Logik als eigener, kleiner TDD‑Slice umgesetzt werden:
  1. RED: Neuer SSR‑Test, der sicherstellt, dass Markdown in der Lehrer‑Detailansicht formatiert (nicht als Raw‑Text) erscheint.  
  2. GREEN: Umstellung auf `render_markdown_safe` und Austausch des `<pre>`‑Containers.  
  3. REFACTOR: Optionales Zusammenführen der Rendering‑Hilfen für Schüler‑ und Lehreransicht, um Dopplungen zu vermeiden.
