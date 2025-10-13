# Mini-RFC: Asynchrone KI-Feedback-Generierung mit Retry-Mechanismus

**Problem:**
Ollama kann nur eine KI-Generation gleichzeitig verarbeiten (sequenzielle interne Queue). Bei bis zu 50 gleichzeitigen Nutzern führt dies zu langen Wartezeiten und Client-Timeouts. Die aktuelle synchrone Implementierung blockiert die UI und bietet keine Fehlertoleranz.

**Context & Constraints:**
- Maximal 50 gleichzeitige Nutzer erwartet
- Hardware unterstützt nur ein LLM gleichzeitig (keine horizontale Skalierung möglich)
- Garantiertes Feedback ist wichtiger als Geschwindigkeit
- Fehlgeschlagene KI-Aufrufe sollen automatisch wiederholt werden
- Lösung muss minimalistisch bleiben (keine komplexe Message-Queue-Infrastruktur)
- Datenfluss von Schülerlösungen (PII) zur KI muss abgesichert bleiben
- Lösung muss persistent sein (kein Datenverlust bei System-Neustart)

**Proposed Change:**
Entkopplung der Einreichung von der KI-Analyse durch eine datenbankgestützte Warteschlange mit intelligentem Retry-Mechanismus.

1. **Datenbank-Erweiterung:**
   - `submission.feedback_status`: TEXT mit Werten 'pending', 'processing', 'completed', 'failed', 'retry' (Default: 'pending')
   - `submission.retry_count`: INTEGER (Default: 0)
   - `submission.last_retry_at`: TIMESTAMP (Default: NULL)
   - `submission.processing_started_at`: TIMESTAMP (Default: NULL)
   - `submission.queue_position`: INTEGER (virtuell berechnet für UI)

2. **Anpassung der Einreichung:**
   - In `app/pages/3_Meine_Aufgaben.py`: Direkter Aufruf von `generate_ai_insights_for_submission` wird entfernt
   - UI zeigt stattdessen Queue-Position und geschätzte Wartezeit
   - Polling-Mechanismus bleibt für Status-Updates erhalten

3. **Worker-Prozess (`app/ai/feedback_worker.py`):**
   - Läuft als separater Container in docker-compose
   - Polling-Intervall: 5 Sekunden
   - Verarbeitungslogik:
     ```
     1. Hole älteste Submission mit status IN ('pending', 'retry')
        WHERE retry_count < 3 
        AND (last_retry_at IS NULL OR last_retry_at < NOW() - INTERVAL retry_count * 5 MINUTES)
     2. Setze status = 'processing', processing_started_at = NOW()
     3. Rufe generate_ai_insights_for_submission() mit Timeout (120s) auf
     4. Bei Erfolg: status = 'completed'
     5. Bei Fehler: 
        - retry_count < 3: status = 'retry', retry_count++, last_retry_at = NOW()
        - retry_count >= 3: status = 'failed'
     ```

4. **Timeout-Implementierung:**
   - HTTP-Timeout für Ollama-Requests: 120 Sekunden
   - Worker-Health-Check: Wenn processing_started_at > 5 Minuten alt → Status zurück auf 'retry'

**Data Model / API Impact:**
```sql
ALTER TABLE submission 
ADD COLUMN feedback_status TEXT DEFAULT 'pending',
ADD COLUMN retry_count INTEGER DEFAULT 0,
ADD COLUMN last_retry_at TIMESTAMP,
ADD COLUMN processing_started_at TIMESTAMP;

CREATE INDEX idx_submission_feedback_queue 
ON submission(feedback_status, retry_count, created_at) 
WHERE feedback_status IN ('pending', 'retry');
```

**Security & Privacy:**
- Worker nutzt gleiche DB-Credentials aus .env (kein Service-Role-Key)
- Keine zusätzlichen PII-Risiken
- RLS-Policies bleiben unverändert
- Logging ohne PII bei Fehlern

**Testing:**
- **Load-Test:** 50 gleichzeitige Submissions → Alle werden sequenziell verarbeitet
- **Fehlertoleranz:** Ollama-Ausfall während Verarbeitung → Automatic retry nach Backoff
- **Worker-Restart:** Queue-Verarbeitung wird fortgesetzt, "stuck" Jobs werden erkannt
- **Timeout-Test:** Lange KI-Generation → Timeout nach 120s, Retry

**Rollback:**
1. Feature-Flag `ENABLE_ASYNC_FEEDBACK=false` in .env setzen
2. Worker-Container stoppen
3. DB-Migration rückgängig machen (Down-Migration bereitstellen)

**Mögliche Fallstricke bei der Implementierung:**

1. **Race Conditions:**
   - Problem: Zwei Worker könnten gleichzeitig dieselbe Submission holen
   - Lösung: SELECT ... FOR UPDATE SKIP LOCKED in der Queue-Abfrage

2. **Zombie-Prozesse:**
   - Problem: Worker stürzt während 'processing' ab → Submission bleibt ewig in processing
   - Lösung: Health-Check-Query für "stuck" Jobs (processing_started_at > 5 min)

3. **Memory Leaks im Worker:**
   - Problem: Lang laufender Python-Prozess könnte Memory leaken
   - Lösung: Worker periodisch neustarten (z.B. nach 1000 verarbeiteten Jobs)

4. **Ollama Container-Restart:**
   - Problem: Ollama-Neustart während KI-Generation → Verbindungsabbruch
   - Lösung: Robuste Exception-Behandlung, automatischer Retry

5. **Datenbank-Connection-Pool:**
   - Problem: Worker hält DB-Connection dauerhaft offen
   - Lösung: Connection-Recycling alle 30 Minuten

6. **Exponential Backoff Berechnung:**
   - Problem: Zu aggressive Retries überlasten Ollama
   - Lösung: Mindest-Wartezeit zwischen Retries: retry_count * 5 Minuten

7. **Queue-Position-Berechnung:**
   - Problem: Genaue Position schwer zu berechnen mit retry-Jobs
   - Lösung: Vereinfachte Schätzung basierend auf created_at

8. **Docker-Networking:**
   - Problem: Worker kann Ollama nicht erreichen
   - Lösung: Sicherstellen dass beide im gleichen Docker-Network sind

9. **Logging-Volumen:**
   - Problem: Worker generiert zu viele Logs
   - Lösung: Log-Rotation, strukturiertes Logging mit Levels

10. **Zeitstempel-Synchronisation:**
    - Problem: Docker-Container haben unterschiedliche Systemzeiten
    - Lösung: Alle Zeitstempel von DB generieren lassen (NOW())

**Alternativen (und warum verworfen):**
- **In-Memory Queue:** Nicht persistent, Datenverlust bei Neustart
- **Celery/Redis:** Zusätzliche Infrastruktur-Komplexität nicht gerechtfertigt
- **Mehrere Ollama-Instanzen:** Hardware-Limitation (nur ein Modell gleichzeitig)
- **Batch-Processing:** Schlechtere UX, Schüler warten länger auf Feedback
