# Teaching — Live-Ansicht (Einheit)

Ziel: Lehrkräfte sehen in der Seite „Unterricht › Live“ für eine Lerneinheit die Aktivität ihrer Kursteilnehmer. Die Live-Ansicht setzt auf Polling (Delta) statt SSE und überträgt nur geänderte Zellen.

Begriffe: Abschnitt = Section, Aufgabe = Task, Einreichung = Submission.

## Endpunkte (API)

- GET `/api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary`
  - Liefert die Aufgaben der Einheit (`tasks[]`) und optional die Schülerzeilen (`rows[]`) mit Minimalstatus je Zelle: `{ task_id, has_submission }`.
  - Query:
    - `include_students` (bool, default true): Wenn `false`, werden nur `tasks[]` geliefert (Startoptimierung in der UI).
    - `limit`/`offset`: Paginierung der Schülerliste.
  - Sicherheit: Nur Owner (Lehrer) des Kurses; Einheit muss zum Kurs gehören. `Cache-Control: private, no-store`, `Vary: Origin`.

- GET `/api/teaching/courses/{course_id}/units/{unit_id}/submissions/delta`
  - Liefert nur geänderte Zellen seit `updated_since`.
  - Query:
    - `updated_since` (ISO‑Zeitstempel, required): Cursor; nur Änderungen NACH diesem Zeitpunkt.
    - `limit`/`offset`: Paginierung der Änderungen.
  - Antwort:
    - 200 `{ cells: [{ student_sub, task_id, has_submission, changed_at }] }`
    - 204 No Content (keine Änderungen seit Cursor)
  - Sicherheit: Owner‑Only; `private, no-store`, `Vary: Origin`. Es werden keine Inhalte (Text/Bilder) übertragen.

- PATCH `/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility`
  - Schaltet die Sichtbarkeit eines Abschnitts für den Kurs um (`visible=true|false`).
  - Sicherheit: Browser‑Anfragen MÜSSEN `Origin` oder `Referer` enthalten und same‑origin sein, sonst `403` mit `detail=csrf_violation`.
    Der SSR‑Helper leitet einen passenden `Origin`‑Header weiter.

OpenAPI: siehe `api/openapi.yml` (Schemas `TeachingUnitLiveRow`, `TeachingUnitTaskCell`, `TeachingUnitDeltaCell`, `TeachingLatestSubmission`).

## Zeit/Cursor‑Semantik (Clock‑Skew‑robust)

- Server verarbeitet Cursor als exklusiven Zeitpunkt. Eine Änderung wird nur geliefert, wenn sie effektiv „nach“ dem Cursor liegt.
- Zur Robustheit gegen kleine Zeitabweichungen (Host ↔ DB) verwendet der Server ein EPS‑Fenster (1 s):
  - Inklusion: `changed_dt > (cursor - EPS)`
  - Ausgegebenes `changed_at`:
    - Normalfall (`changed_dt > cursor`): `changed_at = changed_dt` (UTC, Mikrosekunden)
    - Skew‑Fall (`changed_dt <= cursor`): `changed_at = cursor + EPS` (monoton steigend)
- Folge‑Poll mit dem zuletzt empfangenen `changed_at` als Cursor liefert deterministisch keine Duplikate (204), solange keine weiteren Änderungen passiert sind.

## Client‑Polling (Empfehlung)

1) Initial: `GET …/summary?include_students=false`
2) Erste Matrix: `GET …/summary` (optional paginiert)
3) Cursor setzen: `cursor = now()` (ISO)
4) Polling (alle 3–5 s): `GET …/delta?updated_since=cursor`
   - Bei `200`: Zellen in UI anwenden, `cursor = max(cells[].changed_at)`
   - Bei `204`: UI unverändert lassen

Hinweis: Namen werden für Lehrkräfte angezeigt; Inhalte (Text/Bilder) müssen separat über dedizierte Endpunkte geladen werden.

## Detailansicht: letzte Abgabe (Owner)

- Endpoint: `GET /api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest`
- Antworten: `200` (Schema `TeachingLatestSubmission`), `204` (keine Abgabe), `404` (Relation ungültig), `403/401` (Auth).
- Sicherheit: Kurs‑Ownership erforderlich; die Einheit muss am Kurs hängen; die Aufgabe muss zur Einheit gehören. `Cache-Control: private, no-store`, `Vary: Origin`.
- UI (Detail-Tab unter der Matrix):
  - Tabs für „Text“ (Auszug aus `text_body`) und bei Datei-Abgaben zusätzlich „Datei“ mit Inline-Vorschau.
  - Wenn Analyse/Feedback vorliegen, erscheinen zusätzliche Tabs „Auswertung“ (Kriterienkarten aus `analysis_json`) und „Rückmeldung“ (Markdown aus `feedback_md`), in dieser Reihenfolge.
- Semantik:
  - `text_body`: Best‑Effort‑Textrepräsentation der Abgabe, unabhängig vom `kind` (Text/PDF/Bild/Datei). Aus Gründen der Bandbreite kann der Text serverseitig gekürzt werden (aktuell ca. 1000 Zeichen).
  - `feedback_md`: Formatives Feedback („Rückmeldung“) in Markdown; wird angezeigt im Tab „Rückmeldung“.
  - `analysis_json`: Strukturierte Kriterien‑Auswertung („Auswertung“) im Schema `AnalysisJsonCriteriaV1|V2` (insb. `criteria.v2` mit `criteria_results`).
  - `files[]`: Enthält Original‑Upload(s) mit signierten URLs. Jedes Element besitzt eine ganzzahlige `size` in Bytes; wenn die Größe nicht zuverlässig ermittelt werden kann, wird die Datei nicht in `files[]` aufgenommen.
  - Fallback: Bei Infrastrukturproblemen (Storage/Helper) wird nach Möglichkeit weiterhin ein vollständiges Domain‑Objekt (`text_body`, `feedback_md`, `analysis_json`) geliefert; nur `files[]` kann temporär leer sein.

## DB & RLS

- Der Teaching‑Adapter verwendet SECURITY‑DEFINER‑Helper:
  - `get_unit_latest_submissions_for_owner(…)` (Matrix/Delta)
  - `get_latest_submission_for_owner(p_owner_sub, p_course_id, p_unit_id, p_task_id, p_student_sub)` (Detail)
- RLS bleibt aktiv; die Helper prüfen Ownership und Kurs/Unit/Task‑Relationen.
- Defensiver Fallback:
  - Primär wird immer über die Helper gearbeitet.
  - Falls der Helper vorübergehend nicht verfügbar ist (z.B. während einer Migration), fällt der Teaching‑Detail‑Endpunkt auf eine stark eingegrenzte Abfrage gegen `public.learning_submissions` zurück. Vor dem Fallback-SELECT wird derselbe Relation‑Check (`task ∈ unit ∈ course`) wie im Primärpfad erneut durchgeführt; bei einer ungültigen Kombination liefert der Endpunkt weiterhin `404`.
  - Dabei bleiben Ownership/Relationen und `app.current_sub` erhalten; das Domain‑Objekt (`text_body`, `feedback_md`, normalisiertes `analysis_json`) bleibt vollständig, nur `files[]` kann entfallen (oder als leere Liste erscheinen, wenn keine Dateien aufgelöst werden konnten).
  - Ältere Analyseformate (z.B. `summary`/`criteria` ohne `schema`) werden intern in ein criteria.v1/v2‑Objekt überführt; nach außen sehen Clients immer ein `analysis_json` mit `schema` und optionalen `criteria_results`. Für Analyse‑Payloads mit einem nicht abbildbaren Shape schreibt der Endpoint einen anonymisierten Log‑Eintrag (`analysis_json_unhandled_shape`), ohne PII oder Inhalte zu protokollieren.

## Tests (pytest)

- `backend/tests/test_teaching_live_unit_summary_api.py`: Vertrag/Fehlerfälle/`include_students`.
- `backend/tests/test_teaching_live_unit_delta_api.py`: 401/403/404/400 sowie Happy‑Path „200 dann 204“ mit neuem Cursor.
- `backend/tests/test_teaching_live_detail_api.py`: Detail‑Contract für `TeachingLatestSubmission` inkl. Feedback/Analysis/Fallback‑Verhalten.

## Weiterführende Pläne

- `docs/plan/2025-12-04-PR-fix.md`: Ursprüngliche Contract‑Fix‑Entscheidung für `analysis_json` und `files[].size`.
- `docs/plan/2025-12-04-PR-fix2.md`: Ergänzende Review‑Notizen zu Fallback‑Verhalten, UI‑Konsistenz und weiteren Feinjustierungen des Teaching‑Detail‑PR.
