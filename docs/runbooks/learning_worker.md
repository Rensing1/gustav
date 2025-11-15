# Learning Worker — Runbook

Purpose: Operate and troubleshoot the asynchronous learning worker (vision + feedback).

## Credentials & DSN
- Production: create a dedicated DB role `gustav_worker` without committing passwords to VCS.
  - SQL (run in admin context): `create role gustav_worker login; alter role gustav_worker inherit;` then `grant gustav_limited to gustav_worker;`
  - Set the password out-of-band via secret store; never in migrations.
  - Configure the worker with `LEARNING_DATABASE_URL=postgresql://gustav_worker:<SECRET>@<host>:<port>/postgres`.
- Development: default to the application login DSN (IN ROLE `gustav_limited`) via environment.
- Web/API uses `DATABASE_URL` (app login). Avoid service-role DSNs except for session store internals.

## Health Probe
- Endpoint: `GET /internal/health/learning-worker` (teacher/operator only).
- Response: `200 { status: "healthy", currentRole, checks: [...] }` or `503` when degraded.
- Cache headers: `Cache-Control: private, no-store`, `Vary: Origin`.
- DB function: `public.learning_worker_health_probe()` (SECURITY DEFINER) checks role presence and queue visibility.

## Queue & Leasing
- Table: `public.learning_submission_jobs`.
- Status: `queued|leased|failed`; leased rows include `lease_key` and `leased_until`.
- Index: `(status, visible_at)`; worker uses `FOR UPDATE SKIP LOCKED` to lease.

## Retries & Failures
- Transient adapter errors → `_nack_retry` with exponential backoff; submission stays `pending` and `error_code` is `vision_retrying|feedback_retrying`.
- Permanent errors → submission `failed` via `public.learning_worker_update_failed(...)` and job `status=failed`.
- Completed → `public.learning_worker_update_completed(...)` sets `text_body`, `feedback_md`, and `analysis_json` (schema `criteria.v1` oder `criteria.v2`, abhängig vom Adapter).

## Observability
- Gauges/Counters: `analysis_jobs_inflight`, `ai_worker_retry_total{phase}`, `ai_worker_failed_total{error_code}`.
- Logs should not contain PII; error messages are truncated to 1024 chars.

## Common Issues
- 503 on health probe with `db_role failed`: ensure role `gustav_worker` exists (or worker DSN points to app login) and function grants include `gustav_limited`.
- Jobs not picked up: confirm `(status='queued' and visible_at <= now())` and no long-lived leases.
- RLS blocks submission updates: ensure helpers are installed and `gustav_worker` has EXECUTE on them.

## Commands
- Start: `docker compose up -d --build` (worker auto-starts).
- Migrations: `supabase migration up`.
- Tests: `.venv/bin/pytest -q`.

## Preflight Checklist (Local = Prod)

Ziel: In wenigen Schritten verifizieren, dass der Learning‑Worker korrekt
konfiguriert ist, DSPy/Ollama erreicht und sinnvolle Ergebnisse persistiert.

1) Container starten/neu erstellen

- `docker compose up -d --build`

2) Runtime‑ENV im Worker prüfen (DI/Ollama/DSPy)

- `docker compose exec -T learning-worker sh -lc 'printf "AI_BACKEND=%s\nLEARNING_DSPY_JSON_ADAPTER=%s\nOLLAMA_BASE_URL=%s\nAI_FEEDBACK_MODEL=%s\n" "$AI_BACKEND" "$LEARNING_DSPY_JSON_ADAPTER" "$OLLAMA_BASE_URL" "$AI_FEEDBACK_MODEL"'`
- Erwartet:
  - `AI_BACKEND=local`
  - `LEARNING_DSPY_JSON_ADAPTER=default` Use Case: lokal ggf. `false`
  - `OLLAMA_BASE_URL=http://ollama:11434`
  - `AI_FEEDBACK_MODEL=<dein modell>`

3) Worker‑Logs auf Adapter/DSPy‑Signal prüfen

- `docker compose logs -n 200 learning-worker | rg "learning.adapters.selected|learning.feedback.dspy_configured|learning.feedback.dspy_pipeline_completed|feedback_backend="`
- Erwartet:
  - `learning.adapters.selected backend=local … feedback=backend.learning.adapters.local_feedback`
  - `learning.feedback.dspy_configured model=… adapter=JSONAdapter` oder `adapter=default` (falls JSONAdapter deaktiviert)
  - Bei Einreichung: `learning.feedback.dspy_pipeline_completed … parse_status=parsed_structured|parsed`

4) Ollama‑Logs auf Model‑Load/Generate prüfen

- `docker compose logs -n 200 ollama | rg -i "/api/generate|loading model|started|invalid option|currentDate"`
- Erwartet:
  - `/api/generate` mit `200`
  - „loading model“, „runner started“ (beim ersten Aufruf)
  - Keine `invalid option provided option=timeout` und kein `function "currentDate" not defined`

5) DB‑Persistenz (eine Test‑Einreichung vorausgesetzt)

- `psql 'postgresql://gustav_app:CHANGE_ME_DEV@127.0.0.1:54322/postgres' -c "select analysis_status, left(feedback_md,120) as feedback, analysis_json->>'schema' as schema, created_at from public.learning_submissions order by created_at desc limit 5;"`
- Erwartet:
  - `analysis_status = completed`
  - `schema = criteria.v2`
  - `feedback` ist nicht leer/"None"

Troubleshooting‑Hinweise:
- Leere/semantisch schwache structured Outputs: JSONAdapter lokal deaktivieren (`.env: LEARNING_DSPY_JSON_ADAPTER=false`, dann `docker compose up -d --force-recreate learning-worker`).
- Template/500‑Fehler: Client mit `options={raw: true, template: "{{ .Prompt }}"}` aufrufen (im Code bereits so implementiert).
- Netz/Host: `OLLAMA_BASE_URL` muss im Container erreichbar sein (Compose‑Service‑Name `ollama`).

## Lokale KI (Ollama/DSPy)

Ziel: Lokale Inferenz ohne Cloud‑Egress. Standard ist `AI_BACKEND=stub`.
Nur mit `AI_BACKEND=local` plus gesetzten `AI_FEEDBACK_MODEL` und
`OLLAMA_BASE_URL` erzeugt der Worker echte Feedbacks via DSPy/Ollama; der
Stub-Pfad bleibt absichtlich deterministisch für CI.

- Compose bringt den Service `ollama` mit (interner Port `11434`).
- Modelle bereitstellen (dev/staging):
  - `docker compose exec ollama ollama pull ${AI_VISION_MODEL}`
  - `docker compose exec ollama ollama pull ${AI_FEEDBACK_MODEL}`
- Umschalten auf lokale Adapter:
  - In `.env`: `AI_BACKEND=local`
  - Neustarten: `docker compose up -d --build`
- DSPy ist im Worker-Image vorinstalliert und nutzt exakt die oben genannten Variablen
  (`AI_FEEDBACK_MODEL`, `OLLAMA_BASE_URL`, Timeouts). Es existiert kein separates
  Feature-Flag. Schlägt der DSPy-Aufruf fehl (Timeout, Parsing, Konfig), loggt der
  Worker eine WARN-Meldung. Strukturierte Ausgaben können über den JSONAdapter
  erzwungen werden (siehe unten).
- Security/Compliance:
  - Deployment-Verantwortliche wählen das Modell bewusst über `.env`. Der Worker prüft
    lediglich, ob die Variablen gesetzt sind und behandelt Laufzeitfehler als Fallback.
  - Keine Rohtexte in Logs hinterlassen; nur IDs/Fehlercodes protokollieren.
- Health/Verifikation:
  - Worker‑Logs prüfen (keine PII, nur IDs/Fehlercodes/Timings)
  - Interner Check auf `ollama list` (Container‑Healthcheck)
- Neustart Ollama (z. B. nach Modell‑Updates):
  - `docker compose restart ollama`

### DSPy JSONAdapter (strukturierte Ausgaben)

- Zweck: Der JSONAdapter erzwingt strikt typisierte Felder für die DSPy‑Signaturen
  (Analysis/Synthesis). Manche lokalen Modelle liefern formal JSON, aber befüllen
  die typisierten Felder nicht sinnvoll. Ergebnis: Logs zeigen `parsed_structured`,
  aber inhaltlich leere Kriterien/Feedback.

- Steuerung (Compose‑ENV):
  - `.env` im Projektwurzelverzeichnis setzen:
    - `LEARNING_DSPY_JSON_ADAPTER=false` (deaktiviert) oder `true` (Standard)
  - Compose propagiert diese Variable in den Container (siehe `docker-compose.yml:110`).
  - Neustarten: `docker compose up -d --force-recreate learning-worker`

- Verifikation:
  - Worker‑Logs beim Start: `learning.feedback.dspy_configured model=… adapter=JSONAdapter` (aktiv)
    oder `adapter=default` (deaktiviert).
  - Laufzeitprüfung: `docker compose exec -T learning-worker sh -lc 'echo LEARNING_DSPY_JSON_ADAPTER=$LEARNING_DSPY_JSON_ADAPTER'`

- Troubleshooting‑Pattern:
  - Symptom: `dspy_pipeline_completed parse_status=parsed_structured`, aber `criteria_results=[]`
    bzw. Scores fast ausschließlich 0; Feedback leer/„None“.
  - Maßnahme: JSONAdapter testweise deaktivieren (`LEARNING_DSPY_JSON_ADAPTER=false`) und
    Worker neu starten. Parser/Normalisierung akzeptieren dann tolerant Feldvarianten und
    ordnen nach Reihenfolge.
  - Hinweis: In Prod nur mit Modell‑Allowlist aktivieren/deaktivieren. Immer Log‑Signal prüfen.

### ROCm (AMD‑GPU)
- Das Compose nutzt `ollama/ollama:rocm` mit Gerätemappings `/dev/kfd`, `/dev/dri` und Gruppen `video`, `render`.
- Optionale Umgebungsvariablen:
  - `HIP_VISIBLE_DEVICES` (Default `all`) zur Auswahl der GPU
  - `HSA_OVERRIDE_GFX_VERSION` nur bei Bedarf setzen (Hardware/Stack‑abhängig)
- Bei GPU‑Zugriffsproblemen Host‑Kernel‑Module und Gruppenrechte prüfen; Logs des Containers (`docker compose logs -f ollama`).
