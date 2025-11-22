# Ticket: Learning-Worker parallelisieren und OCR/Feedback trennen

## Problem
- Der Learning-Worker arbeitet strikt seriell: pro Durchlauf wird nur ein Job geleast und voll abgearbeitet. Damit bleibt die in Compose aktivierte Ollama-Parallelität ungenutzt, und der Durchsatz bricht bei Lastspitzen ein.
- Feedback-Retries wiederholen die komplette Pipeline (inklusive OCR), obwohl das Vision-Ergebnis bereits vorlag. Das kostet Zeit, vor allem bei PDFs.

## Ziel
- Mehrere Jobs gleichzeitig verarbeiten, um Warte- und Laufzeiten zu senken.
- OCR-Ergebnisse zwischenspeichern und Feedback separat fortsetzen, sodass Retries nur den teuren Schritt wiederholen, der tatsächlich fehlgeschlagen ist.

## Vorschlag (Kombi aus Option 2 + 3)
1) **In-Process-Concurrency einführen**
   - Neuer Schalter `WORKER_CONCURRENCY` (Default 1). Ab `>1` leased der Worker pro Tick bis zu N Jobs (FOR UPDATE SKIP LOCKED) und arbeitet sie parallel ab (z. B. ThreadPool, begrenzt auf 2–4).
   - Pro Job eigene DB-Connection/Transaktion, damit `set_config('app.current_sub')` sauber isoliert bleibt.
   - Telemetrie: `analysis_jobs_inflight` bei Lease/Commit anpassen; Fehler/Retry-Handling wie bisher.
   - Rollout: Start mit 2, Logs/Metriken beobachten (`ai_worker_*`, Queue-Lag, Ollama-Logs auf parallele `/api/generate`), bei Bedarf hoch/runter skalieren.

2) **Pipeline in zwei Etappen teilen**
   - Etappe 1: Vision/OCR, Ergebnis (`text_md`) speichern, Status auf `extracted` setzen (gibt es schon), Job in die Feedback-Etappe überführen.
   - Etappe 2: Feedback aus gespeicherten OCR-Daten erzeugen; Retries in dieser Phase wiederholen nur den Feedback-Schritt.
   - Umsetzung: Entweder zwei Queue-Typen (vision→feedback) oder ein Flag im Payload, das nach OCR den nächsten Durchlauf direkt in die Feedback-Phase schickt. Status-/Error-Codes beibehalten (`vision_*`, `feedback_*`).
   - Cache nutzen: vorhandene PDF-Derivate (`derived/…/stitched.png`, `page_keys`) weiterverwenden, um OCR nicht erneut zu rechnen.

3) **Schutzgeländer**
   - Defaults konservativ (Concurrency=1), schnelle Rückfallebene.
   - Healthcheck unverändert halten; bei Degradation Concurrency wieder auf 1 stellen.
   - Tests für: (a) paralleles Leasing, (b) Feedback-Retry ohne erneutes OCR, (c) Status-Transitions `pending → extracted → completed/failed`.

## Erwarteter Effekt
- Kürzere Latenzen unter Last, bessere Auslastung der bereits konfigurierten Ollama-Parallelität.
- Weniger doppelte Modellaufrufe bei Retries, insbesondere bei PDFs oder instabilen Feedback-Läufen.

## Risiko / Aufwand
- Aufwand: mittel (begrenzte Code-Anpassungen am Worker-Loop und an der Job-Transition).
- Risiken: Zu hohe Parallelität könnte DB oder Ollama kurzfristig stressen; deshalb Soft-Schalter + vorsichtiger Rollout.
