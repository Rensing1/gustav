# Upload and LLM Data Boundaries

Status: Implemented in working tree
Owner: Produktverantwortlicher
Local checks: `.venv/bin/pytest -q backend/tests/test_makefile_targets.py`, `make test-upload-llm-boundaries`
CI status: Keine anbietergebundene CI erforderlich; Upload-/LLM-Boundaries bleiben zunächst ein lokaler Hard-Gate-Baustein.
Related plans: `docs/plan/2026-05-02-harness-engineering-refactor-plan.md`
Review cadence: nach Abschluss von PR 4

## Zweck
PR 4 macht Upload-Sicherheitsgrenzen und LLM-Datengrenzen als eigenes Gate sichtbar. Das Gate schützt technische Grenzen wie Größe, MIME/Extension, Content-Signaturen, Storage-Keys, Proxy-Pfade und Privacy-Logging. Es führt keine inhaltliche Prüfung von Schüler-Submissions ein.

## Produktentscheidung
Schüler-Submissions werden vor dem LLM nicht inhaltlich geprüft, nicht gefiltert, nicht korrigiert, nicht normalisiert, nicht moderiert und nicht umgeschrieben. Das LLM erhält den originalen Schülerinhalt. Technische Verpackung ist erlaubt, zum Beispiel PDF-Rendering für ein Vision-Modell, Bildkodierung für den Transport oder Metadaten für MIME, Größe und Storage-Key. Das gespeicherte Original bleibt unverändert.

## User Story
Als Produktverantwortlicher will ich, dass Uploads technisch sicher begrenzt sind und LLM-Flows die Einreichungen der Lernenden original verwenden, damit GUSTAV keine versteckte Vorbewertung oder Veränderung von Schülerleistungen vornimmt.

## BDD-Szenarien
- Given ein Schüler fordert einen Upload-Intent an, when Größe, MIME-Typ oder Dateiformat nicht erlaubt sind, then wird der Upload technisch abgewiesen.
- Given ein Upload verwendet gefährliche Pfade oder fremde Hosts, when Proxy oder Storage-Verifikation laufen, then wird der Zugriff fail-closed abgewiesen.
- Given eine Datei deklariert einen MIME-Typ, when die Content-Signatur nicht dazu passt, then wird die Submission-Erstellung verhindert.
- Given eine gültige Text-, Bild- oder PDF-Submission wird für Feedback verarbeitet, when technische Verpackung nötig ist, then bleibt der Schülerinhalt semantisch unverändert.
- Given untrusted student text enthält Prompt-Injection-artige Anweisungen, when das LLM aufgerufen wird, then darf GUSTAV diese Submission nicht vorab inhaltlich verändern oder still moderieren; Grenzen werden durch Prompt-Kontext, Logging-Redaktion und Modellverhalten behandelt.

## Teststrategie
- Rot: `backend/tests/test_makefile_targets.py` fordert ein eigenes `test-upload-llm-boundaries`-Profil und die fokussierten Upload-/LLM-Dateien.
- Rot: Ein Harness-Contract fordert die dokumentierte LLM-Produktentscheidung.
- Grün: `Makefile` ergänzt das Profil mit vorhandenen servicefreien Tests für Upload-Intent, Proxy, Storage-Key, Content-Signatur, Submission-Kind, Feedback-Fehlerabbildung und DSPy/Privacy-Verträge.
- Refactor: Security-, Quality-Gate-, Meilenstein- und Masterplan-Dokumente markieren PR 4 als im Arbeitsbaum umgesetzt.

## Evidenz
- Rot: `.venv/bin/pytest -q backend/tests/test_makefile_targets.py backend/tests/test_upload_llm_boundaries_contract.py` schlug fehl, weil `test-upload-llm-boundaries` und die Security-Baseline-Regel noch fehlten.
- Grün: `.venv/bin/pytest -q backend/tests/test_makefile_targets.py backend/tests/test_upload_llm_boundaries_contract.py` → 7 passed.
- Gate: `make test-upload-llm-boundaries` → 81 passed.

## Restrisiko
Echte Supabase-Storage-, OpenAI-/Ollama- und H5P-E2E-Flows bleiben opt-in. PR 4 schafft ein schnelles hartes Boundary-Gate, ersetzt aber keine spätere produktionsnahe Storage- oder E2E-Verifikation.

Learning-Upload-Intent-Happy-Path-Tests bleiben außerhalb dieses schnellen Profils, weil sie aktuell unter API-/Autorisierungsbedingungen `authorization_unavailable` statt der erwarteten Upload-Antworten liefern können. Das ist als offene Upload-Intent-API-Härtung sichtbar; die servicefreien Boundary-Tests decken bis dahin Pfade, Hosts, Header, Storage-Keys, Content-Signaturen, MIME/Kind und LLM-/Privacy-Verträge ab.
