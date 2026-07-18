# Teaching — Live-Ansicht (Einheit)

Ziel: Lehrkräfte sehen in der Seite „Unterricht › Live“ für eine Lerneinheit die Aktivität ihrer Kursteilnehmer. Die Live-Ansicht setzt auf Polling (Delta) statt SSE und überträgt nur geänderte Zellen.

Begriffe: Abschnitt = Section, Aufgabe = Task, Einreichung = Submission.

## Endpunkte (API)

- GET `/api/teaching/courses/{course_id}/units/{unit_id}/submissions/summary`
  - Liefert einen initialen Polling-Cursor (`cursor`) auf Basis der Datenbank-Uhr als robusten Seed für den nächsten Delta-Poll, die Aufgaben der Einheit (`tasks[]`) und optional die Schülerzeilen (`rows[]`) mit Minimalstatus je Zelle:
    `{ task_id, has_submission, average_score, created_at }`.
  - Kann der DB-basierte Cursor-Seed nicht bestimmt werden, antwortet der Endpunkt fail-closed mit `503 service_unavailable` und `detail=summary_cursor_unavailable`, statt still auf die Host-Uhr zurückzufallen.
  - `average_score` ist ein optionaler Float (0..10) für den Durchschnitt der Kriterien-Scores der
    neuesten Einreichung; `null` wenn keine abgeschlossene Auswertung vorliegt.
  - `created_at` ist der UTC-Zeitstempel der neuesten Abgabe in dieser Zelle; `null`, wenn noch keine Abgabe existiert.
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
    - 200 `{ cells: [{ student_sub, task_id, has_submission, average_score, changed_at }] }`
    - 204 No Content (keine Änderungen seit Cursor)
  - Sicherheit: Owner‑Only; `private, no-store`, `Vary: Origin`. Es werden keine Inhalte (Text/Bilder) übertragen,
    nur ein optionaler, aggregierter Score.

- PATCH `/api/teaching/courses/{course_id}/modules/{module_id}/sections/{section_id}/visibility`
  - Schaltet die Sichtbarkeit eines Abschnitts für den Kurs um (`visible=true|false`).
  - Sicherheit: Browser‑Anfragen MÜSSEN `Origin` oder `Referer` enthalten und same‑origin sein, sonst `403` mit `detail=csrf_violation`.
    Der SSR‑Helper leitet einen passenden `Origin`‑Header weiter.

OpenAPI: siehe `api/openapi.yml` (Schemas `TeachingUnitLiveRow`, `TeachingUnitTaskCell`, `TeachingUnitDeltaCell`, `TeachingLatestSubmission`).

- GET `/api/teaching/courses/{course_id}/students/{student_sub}/submissions/overview`
  - Liefert eine teacher-facing Read-Projection fuer genau einen Schueler ueber alle oder gefilterte Lerneinheiten des Kurses:
    `{ student, units: [{ id, title, tasks: [{ id, instruction_md, position, kind, has_submission, average_score, h5p_completed }] }] }`.
  - Query:
    - `unit_ids` (0..50 Wiederholungen): optionaler Filter; ohne Query-Key werden alle Kurs-Lerneinheiten geladen.
    - `unit_ids=` ohne Werte bedeutet explizit: keine Lerneinheiten ausgewaehlt.
  - Sicherheit: Nur Owner (Lehrer) des Kurses; Schueler muss Kursmitglied sein; jede angefragte Unit muss zum Kurs gehoeren. `Cache-Control: private, no-store`, `Vary: Origin`.

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
3) Cursor setzen: `cursor = summary.cursor`
4) Polling (alle 3–5 s): `GET …/delta?updated_since=cursor`
   - Bei `200`: Zellen in UI anwenden, `cursor = max(cells[].changed_at)`; ein anschließender Summary-Reload aktualisiert nur das UI-Read-Model, aber überschreibt diesen Delta-Cursor nicht
   - Bei `204`: UI unverändert lassen

Hinweis fuer das kanonische `/live`-Dashboard:

- Die SvelteKit-Seite bootstrapt initial per SSR das Dashboard-Read-Model.
- Danach pollt sie denselben Delta-Endpunkt in-place weiter und lädt bei
  echten Änderungen das aktuelle Dashboard mit derselben `student_sub` /
  `task_id`-Auswahl nach.
- Klicks auf Schüler und Aufgaben bleiben innerhalb desselben Workspace und
  synchronisieren nur die URL, nicht die ganze Seite.
- Die Tabellenanzeige priorisiert `Vorname Nachname`; nur ohne Personenname
  fällt `/live` auf den Mail-Localpart zurück.

Hinweis: Namen werden für Lehrkräfte angezeigt; Inhalte (Text/Bilder) müssen separat über dedizierte Endpunkte geladen werden.

## Detailansicht: letzte Abgabe (Owner)

- Endpoint: `GET /api/teaching/courses/{course_id}/units/{unit_id}/tasks/{task_id}/students/{student_sub}/submissions/latest`
- Antworten: `200` (Schema `TeachingLatestSubmission`), `204` (keine Abgabe), `404` (Relation ungültig), `403/401` (Auth), `503` (erforderliche Teaching-Infrastruktur nicht verfügbar) und `500` (unerwarteter interner Fehler).
- Sicherheit: Kurs‑Ownership erforderlich; die Einheit muss am Kurs hängen; die Aufgabe muss zur Einheit gehören. `Cache-Control: private, no-store`, `Vary: Origin`.
- H5P-Review: `h5p.review_token` ist ein kurzlebiges AES-GCM-verschlüsseltes Credential mit minimalen Claims. Der Browser übermittelt es nur als `Authorization: Bearer` an `/h5p/player/review`; danach hält ein auf `/h5p` begrenztes `HttpOnly; Secure; SameSite=Strict`-Cookie pro Review den read-only User-State-Zugriff aufrecht. Die User-State-URL führt lediglich eine opake `review_id`, die aus dem zufälligen AES-GCM-Nonce abgeleitet wird und den passenden Cookie auswählt. Dadurch überschreiben sich parallele Reviews nicht. Credential und Personenkennungen werden nie in H5P-URLs geschrieben; fehlende, ungültige oder nicht zum Cookie passende Handles liefern fail-closed `403`. Review-Antworten setzen zusätzlich `Referrer-Policy: no-referrer`.
- UI (Detail-Tab unter der Matrix):
  - Oberhalb der Einreichung wird immer die Aufgabenstellung (`instruction_md`) angezeigt.
  - Tabs für „Text“ (Auszug aus `text_body`) und bei Datei-Abgaben zusätzlich „Datei“ mit Inline-Vorschau.
  - Wenn Analyse/Feedback vorliegen, erscheinen zusätzliche Tabs „Auswertung“ (Kriterienkarten aus `analysis_json`) und „Rückmeldung“ (Markdown aus `feedback_md`), in dieser Reihenfolge.
- Semantik:
  - `text_body`: Best‑Effort‑Textrepräsentation der Abgabe, wenn der jeweilige Submission-Pfad eine Textrepräsentation erzeugt. Text- und OCR-basierte Abgaben liefern hier denselben Text wie im Learning-Bereich; visuell direkt ausgewertete Datei-Abgaben können das Feld auch im Status `completed` leer lassen. Die Länge ist nur durch das globale `text_body`‑Limit (aktuell 65.536 Zeichen ≙ 64k) begrenzt.
  - `instruction_md`: Aufgabenstellung der Aufgabe; wird im API-Contract des Detailobjekts mitgeliefert und in SSR oberhalb der Einreichung gerendert.
  - `feedback_md`: Formatives Feedback („Rückmeldung“) in Markdown; wird angezeigt im Tab „Rückmeldung“.
  - `analysis_json`: Strukturierte Kriterien‑Auswertung („Auswertung“) im Schema `AnalysisJsonCriteriaV1|V2` (insb. `criteria.v2` mit `criteria_results`).
  - `files[]`: Enthält Original‑Upload(s) mit signierten URLs. Jedes Element besitzt eine ganzzahlige `size` in Bytes; wenn die Größe nicht zuverlässig ermittelt werden kann, wird die Datei nicht in `files[]` aufgenommen.
  - Storage-Verhalten: Ist ausschließlich die Dateiablage vorübergehend nicht verfügbar, kann das Domain-Objekt (`text_body`, `feedback_md`, `analysis_json`) weiterhin geliefert werden; nur `files[]` kann temporär leer sein. Ein fehlender Datenbank-Helper ist dagegen ein nicht erfüllter Schema-Vertrag und führt fail-closed zu `503`.

## DB & RLS

- Der Teaching‑Adapter verwendet SECURITY‑DEFINER‑Helper:
  - `get_unit_latest_submissions_for_owner(…)` (Matrix/Delta)
  - `get_latest_submission_for_owner(p_owner_sub, p_course_id, p_unit_id, p_task_id, p_student_sub)` (Detail)
- RLS bleibt aktiv; die Helper prüfen Ownership und Kurs/Unit/Task‑Relationen.
- Fail-closed-Verhalten:
  - Der Detail- und der Datei-Endpunkt lesen die neueste Abgabe ausschließlich über `get_latest_submission_for_owner(…)`. Es gibt keinen direkten Fallback-SELECT gegen `public.learning_submissions`, weil dessen Sichtbarkeit von der aktiven Datenbankrolle abhängen würde.
  - Fehlt der Helper, ist die erforderliche Migration nicht vollständig angewendet. Der Repository-Adapter meldet dann `TeachingRepositoryUnavailable`; der zentrale Teaching-Handler antwortet mit einer privaten `503`-Antwort.
  - Andere unerwartete Fehler werden nicht als „keine Abgabe“ oder „nicht gefunden“ verschleiert, sondern als private `500 internal_error`-Antwort sichtbar gemacht. Logs enthalten dabei nur Fehlerklasse und technische IDs, keine Abgabeinhalte oder Schülerkennung.
  - Ältere Analyseformate (z.B. `summary`/`criteria` ohne `schema`) werden intern in ein criteria.v1/v2‑Objekt überführt; nach außen sehen Clients immer ein `analysis_json` mit `schema` und optionalen `criteria_results`. Für Analyse‑Payloads mit einem nicht abbildbaren Shape schreibt der Endpoint einen anonymisierten Log‑Eintrag (`analysis_json_unhandled_shape`), ohne PII oder Inhalte zu protokollieren.

## Tests (pytest)

- `backend/tests/test_teaching_live_unit_summary_api.py`: Vertrag/Fehlerfälle/`include_students`.
- `backend/tests/test_teaching_live_unit_delta_api.py`: 401/403/404/400 sowie Happy‑Path „200 dann 204“ mit neuem Cursor.
- `backend/tests/test_teaching_live_detail_api.py`: Detail-Contract für `TeachingLatestSubmission` inklusive Feedback/Analysis, Relationsprüfung und fail-closed Helper-Verhalten.
- `backend/tests/test_teaching_live_student_overview_api.py`: neuer Schueler-Ueberblick ueber Kurs-Lerneinheiten.
- `backend/tests/test_teaching_live_student_overview_ssr.py`: SSR-Seite fuer die neue Schueleransicht.

## Weiterführende Pläne

- `docs/plan/2025-12-04-PR-fix.md`: Ursprüngliche Contract‑Fix‑Entscheidung für `analysis_json` und `files[].size`.
- `docs/plan/2025-12-04-PR-fix2.md`: Ergänzende Review‑Notizen zu Fallback‑Verhalten, UI‑Konsistenz und weiteren Feinjustierungen des Teaching‑Detail‑PR.
