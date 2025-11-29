## Ticket: Hohe Rate an 0/10-Kriterien-Scores bei KI-Auswertung (28.11.2025)

**Status:** offen  
**Betroffene Umgebung:** Produktion (`gustav-lernplattform.de`)  
**Datum der Beobachtung:** 2025-11-28 (Analyse bis 2025-11-29)  
**Komponenten:** Learning-Worker, DSPy-Feedbackpipeline, `criteria.v2`-Auswertung, Frontend-History-Ansicht

### Kurzbeschreibung

Lehrkräfte und Schüler:innen berichten, dass bei KI-bewerteten Abgaben häufig alle Kriterien mit `0/10` Punkten angezeigt werden, obwohl die Texte inhaltlich passend sind und die Ollama-Logs auf differenzierte Modellbewertungen hindeuten.

Die Analyse der Datenbankeinträge am **28.11.2025** zeigt:

- Alle Submissions wurden technisch als `completed` mit `schema="criteria.v2"` gespeichert.
- Ein Großteil der Abgaben hat **für alle Kriterien `score=0`** und eine Standard-Begründung („Kein Beleg im Schülertext gefunden.“), obwohl der Schülertext objektiv mehr hergeben würde.
- Die Zero-Scores stammen nicht aus einem UI-Fehler, sondern aus der im Backend erzeugten `analysis_json`-Struktur.

### Datenlage (DB-Auswertung 2025-11-28)

Abfragen auf `public.learning_submissions` (Prod-DB, Container `supabase_db_gustav-alpha2`, DB `postgres`, User `postgres`):

1. Anzahl Submissions an diesem Tag:

```sql
SELECT created_at::date AS tag, count(*) AS submissions
FROM public.learning_submissions
WHERE created_at::date = '2025-11-28'
GROUP BY tag;
-- Ergebnis: tag=2025-11-28, submissions=13
```

2. Alle 13 Submissions wurden mit `criteria.v2` und Kriterienliste gespeichert:

```sql
SELECT count(*) AS completed_with_criteria
FROM public.learning_submissions
WHERE created_at::date = '2025-11-28'
  AND analysis_status = 'completed'
  AND analysis_json->>'schema' = 'criteria.v2'
  AND jsonb_array_length(analysis_json->'criteria_results') > 0;
-- Ergebnis: completed_with_criteria = 13
```

3. Verteilung „alle Kriterien 0“ vs. „mindestens ein Kriterium >0“:

```sql
WITH s AS (
  SELECT id, analysis_json
  FROM public.learning_submissions
  WHERE created_at::date = '2025-11-28'
    AND analysis_status = 'completed'
    AND analysis_json->>'schema' = 'criteria.v2'
    AND jsonb_array_length(analysis_json->'criteria_results') > 0
)
SELECT count(*) AS all_zero
FROM s
WHERE NOT EXISTS (
  SELECT 1
  FROM jsonb_array_elements(analysis_json->'criteria_results') AS c
  WHERE (c->>'score')::int <> 0
);
-- Ergebnis: all_zero = 10

WITH s AS (
  SELECT id, analysis_json
  FROM public.learning_submissions
  WHERE created_at::date = '2025-11-28'
    AND analysis_status = 'completed'
    AND analysis_json->>'schema' = 'criteria.v2'
    AND jsonb_array_length(analysis_json->'criteria_results') > 0
)
SELECT count(*) AS any_nonzero
FROM s
WHERE EXISTS (
  SELECT 1
  FROM jsonb_array_elements(analysis_json->'criteria_results') AS c
  WHERE (c->>'score')::int <> 0
);
-- Ergebnis: any_nonzero = 3
```

4. Auf Task-Ebene (nur drei Aufgaben betroffen):

```sql
WITH s AS (
  SELECT id, course_id, task_id, analysis_json
  FROM public.learning_submissions
  WHERE created_at::date = '2025-11-28'
    AND analysis_status = 'completed'
    AND analysis_json->>'schema' = 'criteria.v2'
    AND jsonb_array_length(analysis_json->'criteria_results') > 0
),
flags AS (
  SELECT
    id,
    course_id,
    task_id,
    NOT EXISTS (
      SELECT 1
      FROM jsonb_array_elements(analysis_json->'criteria_results') AS c
      WHERE (c->>'score')::int <> 0
    ) AS all_zero
  FROM s
)
SELECT task_id, count(*) AS total, sum(CASE WHEN all_zero THEN 1 ELSE 0 END) AS zero_cases
FROM flags
GROUP BY task_id
ORDER BY task_id;
-- Ergebnis:
-- task_id=0093383d-... | total=8 | zero_cases=7
-- task_id=ab1fe216-... | total=2 | zero_cases=2
-- task_id=e894c71d-... | total=3 | zero_cases=1
```

5. Übersicht aller 13 Submissions (gekürzt) am 28.11.:

```sql
SELECT id,
       course_id,
       task_id,
       analysis_json->>'score' AS overall,
       jsonb_array_length(analysis_json->'criteria_results') AS crit_count
FROM public.learning_submissions
WHERE created_at::date = '2025-11-28'
  AND analysis_status = 'completed'
ORDER BY created_at;
```

Beispielhafte Ausgabe (vereinfacht, IDs vollständig in DB):

- `b28cf9cd-...` (Task `ab1fe216-...`): overall=0, crit_count=8  
- `7df33172-...` (Task `ab1fe216-...`): overall=0, crit_count=8  
- `b3d2ea87-...` (Task `0093383d-...`): overall=0, crit_count=9  
- `e52d7288-...` (Task `0093383d-...`): overall=0, crit_count=9  
- `8bed75d5-...` (Task `e894c71d-...`): overall=0, crit_count=10  
- `d3aa3601-...` (Task `0093383d-...`): overall=0, crit_count=9  
- `8b3f135d-...` (Task `0093383d-...`): overall=5, crit_count=9  
- `509350f9-...` (Task `e894c71d-...`): overall=4, crit_count=10  
- `69ac5f2c-...` (Task `0093383d-...`): overall=0, crit_count=9  
- `8614d2ab-...` (Task `e894c71d-...`): overall=0, crit_count=10  
- `28dbd85e-...` (Task `0093383d-...`): overall=0, crit_count=9  
- `958d88cf-...` (Task `0093383d-...`): overall=0, crit_count=9  
- `49f5fbee-...` (Task `0093383d-...`): overall=3, crit_count=9

Interpretation:

- Am 28.11. wurden 13 Abgaben mit KI-Kriterienanalyse abgeschlossen.
- Bei **10/13** Submissions haben **alle Kriterien `score=0`**, obwohl das Modell in anderen Fällen offenbar differenziert (Scores 3–7) bewertet.
- Das betrifft vor allem eine konkrete Aufgabe (`0093383d-...`, Pressefreiheit Russland/Deutschland), aber auch zwei weitere Tasks.

### Inhaltliche Stichprobe

Beispiel-Submission mit komplett 0-bewerteten Kriterien:

- `id = 958d88cf-d12f-5182-885e-4b17daedf781`  
- `Task = 0093383d-c176-41e4-b3f6-0f81cda32b22` (Pressefreiheit in Russland/Deutschland)  
- `overall_score = 0`  
- `criteria_results = 9` Einträge, alle `score = 0`, alle `max_score = 10`, alle `explanation_md = "Kein Beleg im Schülertext gefunden."`

Text-Snippet (Prod-DB, gekürzt):

```sql
SELECT id, LEFT(text_body, 400) AS snippet
FROM public.learning_submissions
WHERE id = '958d88cf-d12f-5182-885e-4b17daedf781';
```

Der Text beschreibt u.a. konkrete Einschränkungen der Pressefreiheit in Russland (Drangsalierung von Journalisten, Druck auf unabhängige Medien, Informationszugang), ist also aus Lehrkraftsicht nicht „leer“.

### Logs / Runtime-Kontext

**Learning-Worker (Container `gustav-learning-worker`):**

- Beim Start:
  - `learning.adapters.selected backend=local vision=backend.learning.adapters.local_vision feedback=backend.learning.adapters.local_feedback`
  - `learning.feedback.dspy_configured model=gpt-oss:120b adapter=default` (bzw. `adapter=default` bei deaktiviertem JSONAdapter)
- Während der Auswertung im relevanten Zeitfenster:
  - Wiederholt:  
    - `learning.feedback.dspy_pipeline_completed feedback_source=feedback parse_status=parsed_structured criteria_count=9/10`  
    - `learning.feedback.completed feedback_backend=dspy criteria_count=9/10 parse_status=parsed_structured`
- Keine offensichtlichen `FeedbackTransientError` oder `feedback_failed`-Logs im analysierten Ausschnitt, d.h. aus Sicht des Workers laufen die Jobs „erfolgreich“ durch und werden als `completed` markiert.

**Ollama (Container `gustav-ollama`):**

- Logs zeigen:
  - Normale Aktivität: `POST /api/generate`, `POST /api/chat`, `GET /api/tags`, gelegentliche `500` und lange Laufzeiten.
  - Für den **28.11.** sind 500er und Runtime-Warnungen dokumentiert (siehe `docs/runbooks/ops_report_2025-11-27.md`), aber für die hier betrachteten 13 Submissions liegen in den Auszügen keine klar zuordenbaren Fehler exakt bei deren Zeitstempeln vor.
- Wichtiger Punkt: Die Zero-Fälle sind `completed` und haben voll ausgefüllte `criteria.v2`-JSONs – das deutet eher auf ein Problem bei Interpretation/Normalisierung der Modellantwort hin, nicht auf einen harten Timeout/Abbruch.

### Relevante Codepfade (stark vereinfacht)

**Worker:**  
`backend/learning/workers/process_learning_submission_jobs.py`

- `_process_job` ruft:
  - `vision_adapter.extract(...)` → `VisionResult`
  - `feedback_adapter.analyze(text_md=..., criteria=..., instruction_md=..., hints_md=...)` → `FeedbackResult`
- Erfolgreicher Pfad:

```python
_update_submission_completed(
    conn=conn,
    submission_id=job.submission_id,
    text_md=vision_result.text_md,
    analysis_json=feedback_result.analysis_json,
    feedback_md=feedback_result.feedback_md,
)
```

**Feedback-Adapter (local/Ollama + DSPy):**  
`backend/learning/adapters/local_feedback.py`

- Bei vorhandener DSPy-Umgebung:
  - lädt `backend.learning.adapters.dspy.feedback_program` als `dspy_program`.
  - ruft `dspy_program.analyze_feedback(...)`.
  - wandelt Ergebnis in `FeedbackResult` um.
- Der Logger schreibt z.B.:
  - `learning.feedback.completed feedback_backend=dspy criteria_count=... parse_status=parsed_structured`

**DSPy-Feedbackprogramm:**  
`backend/learning/adapters/dspy/feedback_program.py`

Wesentliche Punkte:

- `analyze_feedback(...)` orchestriert:
  - `dspy_programs.run_structured_analysis(...)` → `CriteriaAnalysis`
  - Konvertierung zu `analysis_json` (`criteria.v2`-Schema) via `_parse_to_v2`.
  - `dspy_programs.run_structured_feedback(...)` basierend auf `analysis_json`.
- Die zentrale Fallback-Funktion:

```python
def _build_default_analysis(criteria: Sequence[str]) -> Dict[str, Any]:
    crit_items = [
        {
            "criterion": str(name),
            "max_score": 10,
            "score": 0,  # Start ohne Beleg
            "explanation_md": "Kein Beleg im Schülertext gefunden.",
        }
        for name in criteria
    ]
    return {"schema": "criteria.v2", "score": 0, "criteria_results": crit_items}
```

- `_parse_to_v2` kümmert sich darum, eine JSON-Antwort (oder ein `CriteriaAnalysis`-Objekt) in das flache `criteria.v2`-Schema zu überführen:
  - flexible Feldnamen (`criteria` vs. `criteria_results`, `name` vs. `criterion`, `max` vs. `max_score`, `explanation` vs. `explanation_md`),
  - Clamping von Scores,
  - Nachziehen fehlender Kriterien.
- Wenn `_parse_to_v2` die Modellantwort **nicht sinnvoll interpretieren kann**, wird `analysis_json` auf `_build_default_analysis(criteria)` gesetzt:
  - `score=0` für alle Kriterien,
  - `overall_score=0`,
  - `explanation_md="Kein Beleg im Schülertext gefunden."`.

**Wichtig:** Dieser Fallback wird verwendet, ohne die Submission als `failed` zu markieren. Für das UI sind solche Fälle nicht von einer „echten“ (aber sehr strengen) Null-Bewertung zu unterscheiden.

### Hypothese zur Ursache (28.11.2025)

Die Daten für den 28.11. und die Logs sprechen eher für ein **Bewertungs-/Parsingproblem** als für einen reinen technischen Ausfall:

1. **Pipeline läuft formal erfolgreich:**  
   - `analysis_status='completed'`, `schema='criteria.v2'`, volle Kriterienliste.
   - Worker-Logs: `dspy_pipeline_completed parse_status=parsed_structured`.

2. **Hohe Zero-Score-Rate bei bestimmten Tasks:**  
   - Task `0093383d-...`: 7 von 8 Submissions mit nur 0-Punkten.  
   - Task `ab1fe216-...`: 2 von 2 Submissions komplett 0.  
   - Task `e894c71d-...`: 1 von 3 Submissions komplett 0.

3. **Fallback-Muster im JSON:**  
   - In den Zero-Fällen sehen die `criteria_results` exakt wie der Code-Fallback aus:
     - alle `score=0`,
     - Standardtext „Kein Beleg im Schülertext gefunden“,
     - `max_score=10`, `schema='criteria.v2'`.

4. **Strenge „evidence-only“-Logik der Signature:**  
   - Die `FeedbackAnalysisSignature` zwingt das Modell:
     - nur explizite Belege im Schülertext zu berücksichtigen,
     - bei fehlenden Belegen `score=0` zu setzen und explizit zu notieren, dass kein Beleg gefunden wurde.
   - In Kombination mit `_parse_to_v2` (das bei fehlenden/inkonsistenten Feldern ebenfalls 0 + „Kein Beleg...“ setzt) entsteht eine sehr konservative Pipeline:
     - Modellantwort + Parser führen bei leichten Abweichungen oder uneindeutigen Textpassagen dazu, dass ganze Kriterienblöcke (oder im Extremfall alle Kriterien) auf 0 fallen.

5. **Timeouts / Thinking-Tokens als Hauptursache unwahrscheinlich:**  
   - Timeouts/500er sind in den Runbooks dokumentiert, aber:
     - sie würden eher zu `analysis_status='failed'` oder Retries führen,
     - nicht zu formal vollständigen `criteria.v2`-Analysen mit 0-Scores.
   - Die Zero-Fälle am 28.11. sind `completed` und haben saubere JSON-Strukturen → spricht gegen eine unmittelbare Timeout-Ursache.

### Auswirkungen

- Für Lehrkräfte und Schüler:innen wirken die Bewertungen unfair:
  - inhaltlich solide Antworten werden mit `0/10` in allen Kriterien angezeigt,
  - das UI hat keine Möglichkeit, zwischen „wirklich keine Belege“ und „Fallback der Bewertungslogik“ zu unterscheiden.
- Pädagogisch problematisch:
  - Demotivierende Wirkung bei eigentlich brauchbaren Leistungen,
  - Vertrauen in KI-Feedback wird untergraben.
- Operativ:
  - Support-Aufwand („Warum 0/10, obwohl ich alles richtig habe?“),
  - Lehrkräfte müssen häufig manuell nachsteuern.

### Vorschläge für das Dev-Team

1. **Instrumentierung / Observability nachschärfen**

- In `feedback_program.py`:
  - explizite Logs, wenn `_build_default_analysis(criteria)` verwendet wird, z.B.:
    - `event=default_analysis`, `reason=parsing_failed|legacy_fallback`, `criteria_count`, optional: Submission-/Task-spezifischer Hash (ohne PII).
  - Logs bei `_parse_to_v2`, wenn:
    - `analysis_json is None` (JSON nicht interpretierbar),
    - `criteria_results` leer sind, obwohl Kriterien vorhanden sind.
- Ziel: Auf Applikationsebene sichtbar machen, **wann** und **wie oft** die Pipeline in den 0-Fallback geht.

2. **Fallback-Strategie überarbeiten**

- Statt sofort auf „alle Kriterien 0, Kein Beleg im Schülertext gefunden“ zu gehen:
  - Zwischenfälle markieren:
    - `parse_status="analysis_fallback"` oder ähnlich,
    - optional zusätzliche Felder wie `fallback_reason`.
  - UI und/oder Datenmodell so erweitern, dass Lehrkräfte erkennen:
    - „Dieses Ergebnis ist ein technischer Fallback, keine echte inhaltliche Bewertung.“
- Minimaler technischer Schritt:
  - `_build_default_analysis(criteria)` mit einer neutraleren `explanation_md` versehen, z.B. „Automatisierte Auswertung nicht möglich – bitte manuell prüfen.“ und **nicht** zwingend alle Scores auf 0 setzen (z.B. Scores auf `null` lassen).

3. **Parser-Toleranz und Signature-Text überprüfen**

- Prüfen, ob die Kombination aus:
  - sehr strenger Signature (evidence-only) und
  - parsingsensitiver `_parse_to_v2`-Logik
  für bestimmte Aufgaben zu häufigen Zero-Fällen führt.
- Konkrete Schritte:
  - Stichproben vom 28.11. (z.B. `958d88cf-...`, `69ac5f2c-...`, `28dbd85e-...`) in einer Staging-Umgebung durch `analyze_feedback(...)` laufen lassen:
    - Rohes `CriteriaAnalysis` aus `run_structured_analysis` loggen (ohne Schülertext),
    - daraus erzeugtes `analysis_json` vor/nach `_parse_to_v2` vergleichen.
  - Ziel: Herausfinden, ob das Modell selbst „real“ 0 vergibt, oder ob Scores beim Parsing verloren gehen.

4. **UI-Hinweis bei Fallback-Fällen**

- Wenn `parse_status` auf einen Fallback hinweist (z.B. `analysis_fallback`, `analysis_feedback_fallback`):
  - im SSR (`backend/web/main.py`) zusätzlich einen Hinweis für Lehrkräfte einblenden:
    - „Hinweis: Die automatische Analyse konnte nicht zuverlässig durchgeführt werden. Bitte manuell prüfen.“
  - So wird transparent, dass die 0-Scores ggf. aus einem technischen Fallback stammen.

5. **Langfristig: Kennzahl und Alerting**

- Metriken in der DB oder in einem Monitoring:
  - z.B. „Anteil der Submissions je Tag, bei denen `analysis_json.score=0` und alle `criteria_results[*].score=0`“.
- Alert:
  - bei Überschreiten eines Schwellwerts (z.B. >50 % Zero-Fälle an einem Tag) einen Alarm auslösen, um frühzeitig Probleme in der Bewertungslogik zu erkennen.

### Definition of Done (Vorschlag)

- Für die betroffenen Aufgaben (mindestens Task `0093383d-...`, `ab1fe216-...`, `e894c71d-...`) ist nachvollziehbar dokumentiert:
  - ob die Zero-Scores primär auf Modellverhalten oder auf Parser-Fallbacks zurückgehen.
- Im Code existiert klarer Logging-Support, der Fallback-Fälle von „echten“ 0-Bewertungen unterscheidbar macht.
- Die Zero-Fallback-Strategie ist so angepasst, dass:
  - Lehrkräfte im UI erkennen können, wenn eine Bewertung nicht zuverlässig war,
  - und nicht pauschal alle Kriterien mit 0/10 dargestellt werden, nur weil der Parser/Adapter unsicher war.
- Optional (Nacharbeit): Zero-Fälle aus dem Zeitraum 2025-11-27/28 werden nach einem Fix in einer Staging-Umgebung neu bewertet, um das neue Verhalten zu validieren, bevor eine eventuelle Reanalyse in Prod diskutiert wird.

