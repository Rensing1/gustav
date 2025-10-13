# CLI Teacher Planning Tool - Implementierungsplan

## 2025-08-26T14:30:00+01:00
**Update:** 2025-08-26T15:45:00+01:00 - Security-Optimierungen nach Codebase-Audit hinzugefügt

**Ziel:** Command Line Interface für Lehrer zur schnellen Erstellung und Bearbeitung von Wissensfestiger-Aufgaben und Lerneinheiten über REST API

**Annahmen:**
- Fokus auf Wissensfestiger-Aufgaben (häufigster Use Case)
- API-Key basierte Authentifizierung
- JSON + Markdown Input-Format  
- Online-only (keine Offline-Fähigkeit)
- Bestehende GUSTAV Database/Auth-System nutzen

**Offene Punkte:**
- API Key Management & Security-Scope
- Batch-Upload Workflow für mehrere Aufgaben
- CLI Installation & Distribution

**Kritische Security-Findings (2025-08-26):**
- PII Logging: Bestehende `db_queries.py` loggt User-IDs in Klartext (15+ Stellen)
- File Upload: Path Traversal Vulnerabilities in aktueller Implementation
- JWT Validation: Keine bestehende JWT-Validierung für API Endpoints
- Transaction Management: Fehlende Atomic Operations für Batch-Uploads

**Status:** Diese Vulnerabilities existieren JETZT und müssen vor CLI API behoben werden.

---

## Mini-RFC: CLI Teacher Planning Tool

### Problem
Lehrer müssen aktuell alle Wissensfestiger-Aufgaben und Lerneinheiten über die Streamlit Web-UI erstellen. Für wiederkehrende Unterrichtsplanung ist dies zeitaufwendig und unterbricht den Workflow.

### Constraints (Daten, Rollen/RLS, Latenz, Deploy)
- **Daten:** Bestehende PostgreSQL/Supabase Schema (`task`, `learning_unit`, `unit_section`)
- **Rollen/RLS:** Lehrer-Berechtigung via `profiles.role = 'teacher'`, bestehende RLS Policies
- **Latenz:** Akzeptabel für CLI (< 2s pro Operation)
- **Deploy:** Separate CLI-Binary + REST API Service parallel zu Streamlit

### Vorschlag (kleinster Schritt, ggf. Feature-Flag)
**Phase 1 - MVP:**
1. **REST API Module** (`app/api/`) mit FastAPI für Wissensfestiger-CRUD
2. **API Key System** via neue Tabelle `teacher_api_keys`
3. **CLI Tool** (`gustav-cli`) in Python mit Click/Typer
4. **JSON Schema** für Wissensfestiger-Aufgaben

**Feature-Flag:** `ENABLE_CLI_API` in Environment

### Security/Privacy (Angriffsfläche, PII, Secrets)
- **API Keys:** Granulare scoped permissions (mastery:own:read/write, mastery:course:read/write)
- **Rate Limiting:** Per-Teacher API limits (100 requests/hour) via Redis
- **Input Validation:** Centralized validation framework + JSON Schema + File type whitelist
- **PII:** Security Logging mit gehashten User-IDs (hash_id() utility)
- **JWT Security:** Middleware für Token-Validierung + Teacher-Role-Check
- **File Security:** Sanitized filenames, MIME validation, size limits (50MB total)
- **RLS Compliance:** API nutzt User-Context (nie Service Role für User-Operations)

### Beobachtbarkeit/Monitoring (Logs, Metrics, Alerts)
- **Logs:** Structured logging für API requests (ohne sensitive data)
- **Metrics:** CLI operation counts, success rates, response times
- **Alerts:** Unusual API activity, failed authentication attempts

### Risiken & Alternativen
**Risiken:**
- Komplexität durch zweite API neben Streamlit
- CLI Distribution & Updates
- **Security:** Path Traversal in File Uploads (bestehende Vulnerability)
- **Concurrency:** Race Conditions bei gleichzeitiger Web-UI + CLI Nutzung
- **Resource:** Memory Exhaustion bei großen Batch-Uploads (1000+ Tasks)

**Alternativen:**
- **A:** Streamlit REST endpoints erweitern (weniger sauber, gleiche Security Issues)
- **B:** GraphQL statt REST (Overengineering für MVP)
- **C:** gRPC für Performance (Overengineering, schlechtere CLI Integration)

**Trade-offs:** API-First Design vs. schnelle Integration vs. Security Hardening Time

### Migration/Testing (Happy + 1 Negativfall), Rollback
**Testing:**
- Happy: Wissensfestiger-Aufgabe via CLI erstellen → in GUSTAV sichtbar
- Negativfall: Invalid JSON Input → klare Fehlermeldung, keine DB-Corruption

**Migration:** 
- Keine DB-Migration nötig (neue API nutzt bestehende Tabellen)
- CLI als optionales Tool (Web-UI weiterhin primär)

**Rollback:** Feature Flag deaktivieren, CLI-Service stoppen

---

## Technische Implementierung

### Architektur-Übersicht

```
[gustav-cli] --HTTP--> [FastAPI Service] --SQL--> [Supabase PostgreSQL]
                              |
                       [Streamlit App] (bestehend)
```

### Komponenten-Details

#### 1. REST API Service (`app/api/`)

**Tech Stack:**
- FastAPI (async, OpenAPI docs)
- Bestehende `db_queries.py` Funktionen als Backend
- Pydantic Models für Request/Response Validation

**Key Endpoints:**
```python
# Authentication
POST /api/v1/auth/token  # API Key → JWT Token

# Courses & Units  
GET /api/v1/courses
GET /api/v1/courses/{course_id}/units
POST /api/v1/courses/{course_id}/units

# Wissensfestiger Tasks
GET /api/v1/courses/{course_id}/mastery/tasks
POST /api/v1/courses/{course_id}/mastery/tasks  # Neue Aufgabe
PUT /api/v1/mastery/tasks/{task_id}             # Aufgabe bearbeiten
DELETE /api/v1/mastery/tasks/{task_id}

# Bulk Operations
POST /api/v1/courses/{course_id}/mastery/tasks/batch
```

#### 2. CLI Tool (`gustav-cli`)

**Tech Stack:**
- Python Click/Typer für Command Interface
- Requests für HTTP Calls
- Rich für schöne Terminal Output
- JSON Schema validation

**Command Structure:**
```bash
gustav-cli auth login --api-key <key>
gustav-cli course list
gustav-cli mastery create --course <id> --file task.json
gustav-cli mastery edit <task-id> --file updated_task.json
gustav-cli mastery batch --course <id> --directory ./tasks/
```

#### 3. Data Models & JSON Schema

**Wissensfestiger Task JSON:**
```json
{
  "title": "Deutsche Grammatik: Akkusativ vs. Dativ",
  "instruction": "Erkläre den Unterschied zwischen Akkusativ und Dativ mit Beispielen.",
  "learning_material": {
    "content": "# Grammatik Grundlagen\n\n...",
    "images": ["./grammar_chart.png"],
    "external_links": ["https://example.com/grammar"]
  },
  "assessment_criteria": [
    "Korrekte Definition beider Fälle",
    "Mindestens 2 Beispiele pro Fall", 
    "Klarheit der Erklärung"
  ],
  "assessment_hints": [
    "Achte auf die Verwendung der Fragewörter 'Wen/Was?' vs 'Wem?'",
    "Beispiele sollten aus verschiedenen Kontexten stammen"
  ],
  "metadata": {
    "difficulty": "medium",
    "estimated_time": "5-10 Minuten",
    "tags": ["grammatik", "deutsch", "kasus"]
  }
}
```

#### 4. API Key Management System

**Neue Tabelle:**
```sql
CREATE TABLE teacher_api_keys (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id uuid REFERENCES profiles(id),
    name TEXT NOT NULL, -- "CLI Access", "VS Code Extension"
    key_hash TEXT NOT NULL,
    scopes TEXT[] DEFAULT ARRAY['mastery:own:read', 'mastery:own:write'],
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Management Commands:**
```bash
gustav-cli auth create-key --name "My Laptop"
gustav-cli auth list-keys
gustav-cli auth revoke-key <key-id>
```

### Implementation Phases

#### Phase 0 - Security Hardening (1 Woche - KRITISCH!)
- [ ] **PII Logging Fix** - hash_id() utility und security_log() für alle User-IDs
- [ ] **File Upload Validation** - Path sanitization, MIME validation, type whitelist
- [ ] **Input Validation Framework** - Centralized validators (validate_course_name, etc.)
- [ ] **JWT Middleware** - Token verification + teacher role validation
- [ ] **Rate Limiting Setup** - Redis-basiert, per API Key

#### Phase 1 - Core API (2 Wochen)
- [ ] FastAPI Service Setup (`app/api/main.py`) with security middleware
- [ ] **Transaction Wrapper** - Atomic operations für Batch-Uploads
- [ ] **Connection Pooling** - Supabase client reuse
- [ ] Wissensfestiger CRUD Endpoints mit granularen Scopes
- [ ] OpenAPI Documentation mit Security Schema
- [ ] **Optimistic Locking** - Concurrent modification protection

#### Phase 2 - CLI MVP (1 Woche)  
- [ ] CLI Package Setup (`gustav-cli/`) mit Rich error messages
- [ ] Authentication Commands mit secure storage
- [ ] Basic CRUD Commands für Wissensfestiger
- [ ] **Local JSON Schema Validation** - Immediate feedback vor API calls
- [ ] Configuration Management mit encrypted API key storage
- [ ] **Error UX** - Structured error messages mit line numbers

#### Phase 3 - Advanced Features (1 Woche)
- [ ] **Atomic Batch Operations** - All-or-nothing für multiple Tasks
- [ ] **Secure File Upload** - Client-side compression, streaming upload
- [ ] **Request Size Limits** - 50MB total, einzelne Files max 20MB
- [ ] Template System für häufige Task-Strukturen
- [ ] **Parallel Upload** - Concurrent API calls mit --parallel flag
- [ ] Enhanced Error Messages mit suggested fixes

#### Phase 4 - Production Ready (1 Woche)
- [ ] **Security Testing** - Path traversal, JWT bypass, rate limit tests
- [ ] **Concurrency Testing** - Race condition detection
- [ ] **Load Testing** - Batch upload stress tests (100+ Tasks)
- [ ] Monitoring & Security Logging Integration
- [ ] Documentation mit Security Best Practices
- [ ] **Penetration Test** - External security audit

---

## Nächste Schritte

### Sofort (diese Woche) - SECURITY FIRST
1. **Security Audit** der bestehenden File Upload Vulnerabilities
2. **PII Logging Fix** - hash_id() utility implementieren  
3. **Input Validation Framework** - Centralized validators setup

### Iteration 1 (Woche 2)
1. **FastAPI Service Grundstruktur** mit Security Middleware
2. **API Key System** mit granularen Scopes
3. **JWT Validation** + Rate Limiting Setup

### Iteration 2 (Woche 3)
1. **CLI Package Setup** mit secure credential storage
2. **Atomic Transaction Wrapper** für Batch-Operations
3. **Wissensfestiger CRUD** mit Optimistic Locking

### Validierung
- [ ] **Security:** Path Traversal Tests bestanden, keine PII in Logs
- [ ] **Functionality:** CLI kann Wissensfestiger-Aufgaben erstellen/bearbeiten
- [ ] **Integration:** Tasks in GUSTAV Web-UI sichtbar und funktionsfähig
- [ ] **Performance:** Batch-Upload von 50 Tasks in <30s
- [ ] **Concurrency:** Keine Race Conditions bei paralleler Web-UI Nutzung
- [ ] **Authentication:** API Key Scopes verhindern unauthorized access

### Kritische Erfolgskriterien
- ✅ **Keine Security Regressions** - Bestehende Vulnerabilities behoben
- ✅ **Atomic Batch Operations** - All-or-nothing bei Fehlern
- ✅ **Teacher Scope Enforcement** - Zugriff nur auf eigene Kurse/Tasks

---

**Beschluss:** Genehmigung für **Phase 0 (Security Hardening)** erforderlich vor Feature-Development

**Nächster Schritt:** Security Audit + PII Logging Fix implementieren

**Geschätzte Gesamtzeit:** 6 Wochen (statt 5) - Security First Approach