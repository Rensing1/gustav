# Lernraum: Spamschutz für doppelte Rückmeldungsanfragen

## Reparaturplan – 2026-04-09 08:41

- Problem: `Rückmeldung einholen` setzt im Lernraum pro Klick einen neuen `Idempotency-Key`. Der Backend-Flow dedupliziert nur gleiche Schlüssel, daher können versehentliche Doppelklicks heute zwei Feedback-Submissions und zwei Worker-Läufe starten.
- Zielbild:
  - Nur identische `intent=feedback`-Anfragen werden dedupliziert.
  - Deduplizierung greift nur für bereits laufende passende Rückmeldungen.
  - Nach abgeschlossener oder terminal fehlgeschlagener Rückmeldung darf dieselbe unveränderte Lösung bewusst erneut ausgewertet werden.
  - Der Server antwortet bei Wiederverwendung normal erfolgreich mit der bestehenden Submission.
- Technischer Ansatz:
  - Kein UI-only-Fix. Die harte Garantie kommt in den Learning-Repo-Pfad.
  - Keine Migration. Die bestehende Advisory-Lock-Serialisierung über `next_attempt_nr(...)` und die vorhandene Unique-Constraint für `idempotency_key` reichen aus.
  - Gleichheit:
    - Text: gleiches normalisiertes `text_body`
    - Upload: gleiches `kind`, `sha256`, `mime_type`, `size_bytes`
  - In-flight:
    - `analysis_status in ('pending', 'extracted')`
    - plus Retry-Marker `vision_retrying|feedback_retrying`
- Geplante Red-Tests:
  - identische Text-Rückmeldung mit zwei verschiedenen Idempotency-Keys wird wiederverwendet
  - identische Upload-Rückmeldung mit zwei verschiedenen Idempotency-Keys wird wiederverwendet
  - nach `completed` erzeugt dieselbe Lösung bewusst eine neue Rückmeldung
  - Queue-Job-Anzahl bleibt bei deduplizierten Fällen `1`

## Umsetzungsstand – 2026-04-09 08:51

- Geschlossen:
  - `intent=feedback` dedupliziert jetzt identische laufende Text- und Upload-Anfragen serverseitig, auch wenn neue Idempotency-Keys ankommen.
  - Die Deduplizierung greift nur für in-flight Zustände (`pending`, `extracted`, Retry-Marker) und blockiert keine bewusste Neuauswertung nach `completed`.
  - Die OpenAPI-Beschreibung dokumentiert die neue Feedback-Deduplizierung.
- Offen:
  - Kein weiterer UI-spezifischer Cooldown. Der weiche Frontend-Schutz bleibt unverändert, die harte Garantie kommt aus dem Backend.
- Tests:
  - `.venv/bin/pytest -q backend/tests/test_openapi_learning_submissions_intent_contract.py`
  - `.venv/bin/pytest -q backend/tests/test_learning_api_contract.py -k "feedback_request_reuses_matching_inflight or feedback_request_creates_new_submission_again_after_previous_feedback_completed"`
  - `.venv/bin/pytest -q backend/tests/test_learning_api_contract.py backend/tests/test_learning_submissions_idempotency_header.py backend/tests/test_openapi_learning_submissions_intent_contract.py`
  - `make verify`
- Restrisiko:
  - Doppelte Upload-Objekte im Storage werden durch diesen Fix nicht verhindert. Geschlossen ist bewusst nur der doppelte Analyse-/Worker-Lauf.
