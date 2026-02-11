# Ticket: Learning-Auswertung hängt (Ollama-Generate + fehlender echter Timeout + DB-Transaktion) + Feedback-`think`-Inkompatibilität

## Kontext / Impact
- Seit dem Update am **2026-01-14 (mittags)** wurden Einreichungen im Unterricht teils **nicht ausgewertet** (Lehrer-UI zeigt kein OCR/Feedback).
- Symptomatisch: Queue wächst (`learning_submission_jobs.status='queued'`), während `learning-worker` „healthy“ wirkt.
- Betroffen sind sowohl **Bilder** (OCR/Vision) als auch **Text** (Feedback). Das deutet auf einen Worker/Queue-Durchsatz- oder Blockierungsfehler hin (nicht nur OCR).

## Umgebung / Versionen
- Compose-Services: `web`, `learning-worker`, `ollama`, Supabase (externes Netzwerk).
- Ollama (Container): `ollama version is 0.14.0`
- Python Client im Worker-Image: `ollama==0.3.0` (siehe `backend/web/requirements.txt`)
- Modelle in `.env` (prod-local):
  - `AI_VISION_MODEL=qwen3-vl:8b-instruct`
  - `AI_FEEDBACK_MODEL=gpt-oss:120b`

## Timeline (aus Logs/DB rekonstruiert)
- **2026-01-14 15:07Z**: Merge/Update auf `ops/prod-local` (Compose: u. a. Reverse-Proxy/H5P-Healthcheck; keine gezielte Ollama/Netzwerk-Änderung).
- **2026-01-14 20:28:44Z**: Erste klare Blockierung:
  - Postgres `pg_stat_activity` zeigt eine `gustav_app` Session `idle in transaction`, `xact_start=2026-01-14 20:28:44Z`, letztes Query `select set_config('app.current_sub', $1, true)`.
  - Parallel dazu Ollama-Logeintrag: `POST /api/generate` endet `500` nach `2m54s` (Client = learning-worker; docker-intern).
- **2026-01-15 morgens**: Job-Stau sichtbar (queued/pending), Unterricht startet → neue Einreichungen kommen rein, aber Backlog wächst.
- **2026-01-15**: Nach Ollama-Restart ist `/api/generate` wieder responsiv; der Worker verarbeitet kurzfristig wieder Einreichungen (siehe „Erfolge nach Restart“), fällt aber unter Last erneut in Blockierungs-/Retry-Muster.

## Beobachtungen / Belege

### 1) Worker blockiert durch offene DB-Transaktion (RLS-Context + externe Calls)
- Postgres zeigt während der Störung wiederholt:
  - `usename=gustav_app`, `client_addr=(docker-intern)` (learning-worker im Supabase-Netz),
  - `state=idle in transaction`,
  - letztes Query häufig `set_config('app.current_sub', ...)` oder ein `update public.learning_submission_jobs set payload = payload || ...`.
- Das ist kritisch, weil der Worker bei `WORKER_CONCURRENCY=1` Lease + Verarbeitung in **einer** Connection/Transaktion ausführt. Wenn danach ein externer Call (Ollama/Vision/HTTP) hängt, wird die Queue praktisch blockiert.

**Diagnose-Query:**
```sql
select pid, usename, state, client_addr, now()-xact_start as xact_age, left(query,120) as query
  from pg_stat_activity
 where usename='gustav_app'
 order by xact_start nulls last;
```

### 2) Kein wirksamer Timeout für Ollama-Calls (Timeout wird als Model-Option gesendet und ignoriert)
- Ollama-Logs zeigen Warnungen:
  - `msg="invalid option provided" option=timeout`
- Hintergrund:
  - Der Worker sendet `options={"timeout": ...}` (Vision und/oder Feedback).
  - Ollama behandelt `timeout` **nicht** als gültige Modelloption und ignoriert sie.
  - Im verwendeten Python-Client (`ollama==0.3.0`) ist ein echter HTTP-Timeout **Client-Parameter** (`ollama.Client(..., timeout=...)`), Default ist `None` (= unendlich).
- Effekt: Bei einem hängenden `/api/generate` gibt es keinen harten Abbruch → Worker kann beliebig lange hängen bleiben und Transaktionen offen halten.

### 3) Ollama `/api/generate` war zeitweise instabil/hängend
- Vor dem Ollama-Restart war ein einfacher lokaler Smoke-Test instabil (Timeout ohne Response).
- In den Ollama-Logs gab es extrem lang laufende Requests / späte Fehler, inkl. `unexpected EOF`, Disconnects und sehr lange Laufzeiten.
- Nach dem Ollama-Restart:
  - `POST /api/generate` reagiert wieder schnell (z. B. „OK“ in <1s, abhängig vom Prompt).
  - `ollama ps` zeigt zeitweise gleichzeitig `qwen3-vl:8b-instruct` und `gpt-oss:120b` geladen.

### 4) Neues Fehlerbild im Feedback-Teil: `think`-Inkompatibilität
- Worker-Log:
  - `Feedback retry scheduled ... reason=Client.generate() got an unexpected keyword argument 'think'`
- Das führt zu Retries/Backoff und reduziert den Durchsatz weiter (und kann unter Last „stuck“ wirken).
- Annahme: In der Ollama-Client/Server Kombination wird `think` nicht als Parameter unterstützt (oder anders erwartet). Der Adapter sollte nur Parameter senden, die die konkrete Client-Version akzeptiert.

### 5) Erfolge nach Ollama-Restart (belegt, dass der Pipeline-Grundpfad wieder funktioniert)
- Nach Ollama-Restart wurden mindestens diese Einreichungen abgeschlossen:
  - `92776516-...` (Text) `completed_at=2026-01-15 07:08:08Z`
  - `6f7e5e50-...` (Bild) `completed_at=2026-01-15 07:09:37Z`
- Gleichzeitig wuchs die Queue weiter (Unterrichtslast), was auf zu geringen Durchsatz bzw. wiederkehrende Blockierung/Retry hindeutet.

## Root Cause (Zusammenfassung)
1) **Design-Problem im Worker bei `WORKER_CONCURRENCY=1`:** Eine einzelne hängende Verarbeitung hält eine DB-Transaktion offen (`idle in transaction`) und blockiert so effektiv die Queue.
2) **Timeout falsch umgesetzt:** Der konfigurierte Timeout wird als `options.timeout` an Ollama gesendet, aber vom Server ignoriert → kein echter Request-Timeout → Hänger sind nicht begrenzt.
3) **Ollama-Instabilität bei `/api/generate`** (Runner/Unload/Modelzustand) hat den Hänger auslösen können.
4) **Feedback-Regression/Kompatibilitätsproblem (`think` kwarg)** erzeugt zusätzliche Retries und verringert den Durchsatz.

## Sofortmaßnahmen (Ops) – bereits genutzt/validiert
- Ollama neu starten: stellt `POST /api/generate` wieder her, Worker kann wieder abschließen.
- `learning-worker` neu starten: räumt hängende DB-Sessions/Transaktionen auf (Symptom-Reset).
- Fehlgeschlagene Submission/Job manuell resetten (DB), um erneutes Queuing zu erlauben:
  - `learning_submissions`: `analysis_status` zurück auf `pending`, Fehler/Attempts löschen.
  - `learning_submission_jobs`: `status='queued'`, `retry_count=0`, `visible_at=now()` (Lease-Felder nullen).

## Empfehlung: Robustheit (Upstream Fixes)
### A) Echte Timeouts/Circuit Breaker
- Für **alle** Ollama-Calls echte HTTP-Timeouts setzen (`ollama.Client(..., timeout=<sec>)`).
- Keine unbekannten Modelloptionen (wie `options.timeout`) mitsenden.
- Bei Timeout/Disconnect: sauber `TransientError` + Requeue (mit Backoff), aber ohne DB-Transaktion offen zu halten.

### B) DB-Transaktion kurz halten (kritisch für Queue-Fortschritt)
- Worker sollte nicht während externer Calls in einer offenen DB-Transaktion hängen.
  - Option 1: Lease committen, extern arbeiten, Ergebnis in separater kurzer Transaktion persistieren.
  - Option 2: `WORKER_CONCURRENCY>1` mit separaten Connections pro Job (schützt vor Totalblockade durch einen Hänger).
- Zusätzlich als Sicherheitsnetz: DB-seitig `idle_in_transaction_session_timeout` für Worker-Rolle/Connection-User.

### C) `think` nur senden, wenn unterstützt
- Client/Server-Feature-Detection:
  - z. B. Signatur-Check (oder Versionspinning) und `think` nur bei kompatiblen Clients aktivieren.
- Sicherstellen, dass Fallback-Pfade (DSPy → Ollama) ohne inkompatible Parameter funktionieren.

### D) Monitoring / Runbook
- Alarmierung bei:
  - `learning_submission_jobs` Backlog (queued älter als X Minuten) / Wachstum.
  - `pg_stat_activity` `idle in transaction` für `gustav_app` länger als X Minuten.
  - `/api/generate` Smoke-Test (nicht nur `/api/tags`).
- Runbook: “Auswertung hängt” mit klaren Checks und safe recovery steps.

## Akzeptanzkriterien (Suggest)
- Unter Unterrichtslast wächst die Queue nicht dauerhaft; `queued` bleibt bounded und wird abgearbeitet.
- Keine `gustav_app` Sessions `idle in transaction` > 2 Minuten.
- Keine Retries mit `unexpected keyword argument 'think'`.
- `AI_TIMEOUT_*` wirkt tatsächlich (Requests werden nach Budget abgebrochen und requeued).
