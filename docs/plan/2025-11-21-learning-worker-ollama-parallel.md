# Plan: Learning-Worker Parallelisierung mit Ollama

Status: In Arbeit (Ticket „Learning-Worker parallelisieren und OCR/Feedback trennen“)

## Ziel (minimalinvasiv, ENV-gesteuert)
- Latenz und Durchsatz der KI-Pipeline senken, ohne Dev-Hardware zu überlasten. Dev bleibt bei 1, Prod kann parallelisieren.
- Steuerung ausschließlich per `.env`: Defaults bewahren aktuelles Verhalten (Single-Job, seriell).

## Ist-Stand (Code)
- Worker (`backend/learning/workers/process_learning_submission_jobs.py`) verarbeitet genau einen Job seriell: Lease → Vision → Feedback → Update → delete Job.
- Adapters: Vision/Feedback synchron (`local_vision.extract`, `local_feedback.analyze`), kein Streaming/Pipelining, kein Job-Batching.
- Retries wiederholen immer Vision + Feedback (auch wenn OCR schon vorliegt). Status `pending|extracted` wird akzeptiert, aber die Pipeline startet immer vollständig.

## Geplante Änderungen (priorisiert, kleinster Eingriff zuerst)
1) ENV-gesteuerte In-Process-Concurrency
   - Neue Env `WORKER_CONCURRENCY` (Default 1 → identisch zum Ist). Bei >1 werden pro Tick bis zu N Jobs geleast (SKIP LOCKED) und in kleinem ThreadPool (2–4) abgearbeitet.
   - Pro Job eigene DB-Connection/Transaktion + eigenes `set_config('app.current_sub', ...)`; keine Connection-Sharing zwischen Threads.
   - Telemetrie `analysis_jobs_inflight` beibehalten; Backoff/Retry-Logik unverändert.
   - Dev kann bei 1 bleiben, Prod stellt 2–4 ein.

2) OCR-Ergebnisse wiederverwenden (Feedback-Retries ohne erneutes Vision)
   - Wenn Submission bereits `analysis_status='extracted'`, Feedback direkt aus gespeichertem OCR-Resultat erzeugen, ohne Vision erneut anzustoßen.
   - Spart Zeit bei Feedback-Retries und senkt Last ohne Parallelität zu erzwingen. Default-Verhalten bleibt für `pending`.

3) Ops-Option (ohne Code): Mehrere Worker-Instanzen
   - Compose-Scale >1 nutzt bestehendes SKIP LOCKED. Für Dev 1 Instanz, für Prod 2–4 je nach Kapazität. Overhead: zusätzliche Prozesse/Container.

4) Optionales Adapter-/Ollama-Tuning (nur Prod)
   - Env: `OLLAMA_NUM_PARALLEL=2-4`, `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_KEEP_ALIVE=5m`, `OLLAMA_KV_CACHE_TYPE=q8_0/q4_0`, `OLLAMA_FLASH_ATTENTION=1`, evtl. `OLLAMA_MAX_QUEUE` für Backpressure.
   - Modelle quantisiert (Q4/Q5); Adapter-Options `num_batch/num_thread` durchreichen, falls unterstützt.

## Messplan
- Metriken: End-to-End-Latenz pro Submission, Tokens/s pro Modell, RAM/VRAM (`ollama ps`), Fehlerrate/Retry, Queue-Lag.
- Baseline: Ist-Zustand (Concurrency=1, 1 Worker-Instanz).
- Variation A: Nur Concurrency >1 (gleiche Instanzzahl).
- Variation B: Mehrere Worker-Instanzen (Concurrency=1 oder klein).
- Variation C (nach Bedarf): Concurrency >1 + mehrere Instanzen.

## Risiken/Guardrails
- Parallelität erhöht KV-Cache- und RAM-Bedarf bei Ollama (Kontext * Parallel-Faktor) → Quantisierung Pflicht.
- psycopg-Connections strikt nicht zwischen Threads teilen.
- Dev-Hardware schwach: Defaults bleiben 1, damit kein Overhead. Prod stellt explizit höhere Werte ein.

## Scope-Update (heute)
- Wir setzen nur zwei Punkte um: (a) In-Process-Concurrency per ENV, (b) OCR-Ergebnisse beim Feedback-Retry wiederverwenden.
- Keine API- oder Schema-Änderungen geplant.

## BDD-Szenarien (Given-When-Then)
- Concurrency Happy Path  
  Given 3 queued Jobs und `WORKER_CONCURRENCY=2`, When der Worker einen Tick ausführt, Then werden 2 Jobs mit `skip locked` geleast, parallel verarbeitet und am Ende ist `analysis_jobs_inflight` wieder 0.
- Concurrency Edge/Fehler  
  Given ein Job wirft Vision-Transient, When zwei Jobs parallel laufen, Then der Backoff betrifft nur den betroffenen Job und die andere Verarbeitung committet trotzdem.
- OCR-Reuse Happy Path  
  Given Submission `analysis_status='extracted'` und Job-Payload enthält `cached_text_md`, When Feedback erneut läuft, Then Vision wird nicht aufgerufen und Feedback nutzt den Cache-Text.
- OCR-Reuse Fallback  
  Given Submission `analysis_status='extracted'` ohne Cache, When Job verarbeitet wird, Then Worker ruft Vision normal auf und persistert danach den Cache für spätere Retries.

## Konfiguration (Dev vs. Prod)
- Defaults bleiben Dev-freundlich (`WORKER_CONCURRENCY=1`). Prod kann auf 2–3 erhöhen.
- OCR-Reuse liegt im Job-Payload, keine Migration nötig. Feedback-Retries nutzen den Cache automatisch.
