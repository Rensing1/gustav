# Logger Implementation Plan für Gustav (v2)

## Problemstellung

Die Gustav-Lernplattform hat folgende Logging-Probleme:
- **Häufige unerklärliche Log-Outs** der Schüler
- **Feedback-Generierungs-Fehler** sind nicht nachvollziehbar
- **351 print()-Statements** über 19 Dateien verteilt (unstrukturiert)
- **Keine zentrale Logging-Konfiguration**
- **Session-Timeouts werden nicht erfasst**
- **Client-seitige Fehler unsichtbar**

## Ziel

Implementierung eines strukturierten, zentralisierten Logging-Systems mit:
- File-basiertem Logging als MVP (später DB)
- JSON-Format für maschinelle Auswertung
- Kontext-Tracking (User, Session, Request)
- Fokus auf Auth-Events und Client-Heartbeat
- Streamlit-kompatible Architektur

## Offene Fragen

### Technische Fragen
1. **Log-Storage:** Wie lange sollen Logs aufbewahrt werden? (DSGVO-konform)
2. **User-Identifikation:** Reicht Session-ID oder brauchen wir User-ID für Analyse?
3. **Performance-Budget:** Wie viel Latenz (ms) ist für Logging akzeptabel?
4. **Supabase-Limits:** Sollen Logs in separate DB oder File-Storage?

### Organisatorische Fragen
1. **Migration:** Alle 351 print() ersetzen oder nur kritische Pfade?
2. **Monitoring:** Wer wertet Logs aus? Automatische Alerts?
3. **Datenschutz:** Welche User-Daten dürfen geloggt werden?
4. **Entwickler-Workflow:** Console-Output beibehalten für Debugging?

## MVP-Ansatz (1 Woche)

### Tag 1-2: Minimaler Logger + Auth-Events

**Datei:** `utils/logger.py`

```python
# Simpler Logger mit:
- JSON-Lines Format (eine Zeile pro Event)
- File-Rotation (täglich, max 7 Dateien)
- Thread-safe für Streamlit
- Kontext: session_id, timestamp, level
- Dual-Output: File + Console (dev-mode)
```

**Sofort-Integration in:**
- `auth.py`: Login/Logout Events
- `utils/session_client.py`: Token-Refresh
- `main.py`: Session-Initialisierung

**Bewusst NICHT:**
- Keine Async-Komplexität
- Keine DB (erstmal)
- Keine 351 print() ersetzen

### Tag 3: Client-Heartbeat

**Einfacher Ansatz:**
```python
# In main.py oder _layout.py:
- Heartbeat alle 30 Sekunden
- Nutzt st.empty() + JavaScript
- Loggt: session_id, timestamp, page
- Erkennt: Inaktivität, Tab-Wechsel
```

### Tag 4-5: Analyse & Iteration

- Log-Files mit grep/jq analysieren
- Muster in Log-Outs erkennen
- Token-Refresh-Probleme identifizieren
- Entscheidung: Lohnt DB-Migration?

## Vollausbau (nach MVP-Erfolg)

### Woche 2: Worker & Feedback Logging

- Worker-Logs vereinheitlichen
- Ollama-Timeouts tracken
- DSPy-Pipeline-Schritte
- Correlation-IDs zwischen App/Worker

### Woche 3: Persistierung & Analyse

**Option A: Datenbank**
```sql
-- Lightweight Schema
CREATE TABLE app_logs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  level VARCHAR(10),
  event VARCHAR(100),
  session_id TEXT,
  context JSONB
);

-- Partitionierung nach Tag
-- Auto-Delete nach 7-30 Tagen
```

**Option B: Object Storage**
- Supabase Storage für Log-Files
- Tägliche Aggregation
- S3-kompatible Analyse-Tools

### Woche 4: Monitoring & Alerts

- Admin-Dashboard (wenn DB)
- Automatische Alert-Rules
- Session-Flow-Visualisierung
- Export für externe Analyse

## Kritische Herausforderungen & Lösungen

### Streamlit-spezifische Probleme

1. **Session-State vs. Logger-State**
   - Problem: Logger in st.session_state = Verlust bei Rerun
   - Lösung: Logger als Singleton außerhalb Session

2. **Rerun-Deduplizierung**
   - Problem: Jeder Rerun triggert duplicate Logs
   - Lösung: Request-ID basierend auf Script-Run

3. **Multi-User-Concurrency**
   - Problem: Parallele Sessions mischen Logs
   - Lösung: Thread-Local Storage für Kontext

### Performance-Risiken

1. **File-I/O Blocking**
   - Risiko: Synchrones Schreiben blockiert UI
   - Lösung: Queue + Background-Thread
   - Trade-off: Möglicher Log-Verlust bei Crash

2. **JSON-Serialisierung**
   - Risiko: Große Objekte (z.B. DataFrames)
   - Lösung: Whitelist für loggbare Typen

### Datenschutz-Compliance

1. **User-Identifikation**
   - Session-ID statt User-ID im MVP
   - Mapping-Tabelle nur für Admins
   - Automatisches Löschen nach 30 Tagen

2. **Sensible Daten**
   - Keine Passwörter, Tokens, Antworten
   - Prompts nur in Länge loggen
   - PII-Scanner vor Log-Write?

## Migration vom print()

### Automatisierungs-Strategie

```python
# migration_script.py
1. AST-Parser findet alle print()
2. Kategorisiert nach Wichtigkeit
3. Generiert Patches für kritische Pfade
4. Schrittweise PR pro Modul
```

### Entwickler-Ergonomie

```python
# Parallelbetrieb ermöglichen:
logger.info("Login successful", console=True)  # Auch auf Console
logger.debug("Details...", console=DEBUG_MODE)  # Nur im Dev
```

## Entscheidungsbaum

```
MVP erfolgreich?
├── JA: Log-Outs erklärt?
│   ├── JA → Minimal weiter, Focus auf Analyse
│   └── NEIN → Client-Tracking verstärken
└── NEIN: Performance-Problem?
    ├── JA → Sampling erhöhen
    └── NEIN → Logging-Logic debuggen
```

## Nächste Schritte

1. **Klärung der offenen Fragen** (siehe oben)
2. **Proof of Concept** (2h): Mini-Logger + 1 Auth-Event
3. **Entscheidung**: File-only oder direkt DB?
4. **Go/No-Go** für MVP-Woche