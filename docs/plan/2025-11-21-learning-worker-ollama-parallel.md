# Plan: Learning-Worker Parallelisierung mit Ollama

## Ziel
- Latenz und Durchsatz der KI-Pipeline senken, indem Vision- und Feedback-Aufrufe parallelisiert werden und der Ollama-Server mehrere gleichzeitige Requests abarbeitet.
- Hardware: AMD Strix Halo (Ryzen AI Max 395, Radeon 8060S iGPU), 128 GB unified RAM. GPU-VRAM knapp, deshalb CPU-first und ggfs. HIP/ROCm-Offload messen.

## Ist-Stand (Code)
- Worker (`backend/learning/workers/process_learning_submission_jobs.py`) verarbeitet genau ein Job pro Prozess: Vision → Feedback → DB-Update, alles blocking.
- Adapter:
  - Vision (`backend/learning/adapters/local_vision.py`): ein synchroner Ollama-`generate`-Call, default Modell `AI_VISION_MODEL` (aktuell qwen2.5vl:3b).
  - Feedback (`backend/learning/adapters/local_feedback.py`): DSPy, sonst synchroner Ollama-`generate`, default `AI_FEEDBACK_MODEL` (gpt-oss:latest).
- Keine Nutzung von Streaming, kein Request-Pipelining, kein Job-Batching.

## Ansatz 1: Mehrere Worker-Instanzen (keine Code-Änderung)
- Docker Compose: mehrere Worker-Container starten (`run_forever` + SKIP LOCKED verhindert doppelte Jobs).
- Ollama-Server-Tuning:
  - `OLLAMA_NUM_PARALLEL=2-4`
  - `OLLAMA_MAX_LOADED_MODELS=2`
  - `OLLAMA_KEEP_ALIVE=5m`
  - `OLLAMA_KV_CACHE_TYPE=q8_0` oder `q4_0`, `OLLAMA_FLASH_ATTENTION=1`
  - `OLLAMA_MAX_QUEUE` niedriger setzen, falls Backpressure gewünscht.
- Modelle quantisiert wählen (Q4/Q5), damit Vision+Feedback parallel im RAM bleiben.

## Ansatz 2: Parallele Job-Abarbeitung innerhalb eines Workers (Code-Änderung)
- `run_forever` erweitern: mehrere Jobs leasen und parallel in Thread-/Process-Pool ausführen.
- Pro Job eigene DB-Connection + eigenes `set_config('app.current_sub', ...)` (nicht teilen).
- Konfigurierbare Pool-Größe (z. B. `WORKER_CONCURRENCY=2-4`) und Backoff beibehalten.
- Optionale `num_batch`/`num_thread` per Env in die Adapter-Options übernehmen.

## Ansatz 3: Vision→Feedback Pipelining (Code-Änderung, optional)
- Vision-Adapter um Streaming/Chunking ergänzen (OCR liefert Tokens/Absätze fortlaufend).
- Worker baut eine kleine interne Queue: GPT-OSS startet, sobald erste Vision-Chunks kommen.
- Backpressure und Timeouts definieren; nur sinnvoll, wenn Vision signifikant langsamer als Feedback ist.

## Messplan
- Metriken: End-to-End-Latenz pro Submission, Tokens/s pro Modell, RAM/VRAM-Auslastung (`ollama ps`), Fehlerrate/Retry.
- Baseline: aktueller Zustand mit 1 Worker, Standard-Ollama-Settings.
- Variation A (ohne Code): 2–4 Worker-Instanzen + Ollama Parallel-Settings.
- Variation B (mit Code): Worker-Concurrency=2–4; messen Impact auf DB/CPU.
- Variation C (optional): Pipelining-Prototyp mit Streaming Vision.

## Risiken/Guardrails
- Parallelität erhöht Kontext-Speicher in Ollama (Kontext * Parallel-Faktor) → KV-Quantisierung Pflicht.
- psycopg-Connections strikt nicht zwischen Threads teilen.
- GPU-VRAM schnell voll: bei ROCm/HIP-Offload sorgfältig messen, sonst CPU-only bleiben.
