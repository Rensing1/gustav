# ROADMAP.md · GUSTAV Development Roadmap

## Current Status (Q4 2024)

**GUSTAV** ist eine funktionsfähige KI-gestützte Lernplattform mit solidem MVP-Feature-Set:

### ✅ Production Ready Features
- **Multi-User Authentication** - Supabase Auth mit E-Mail-Bestätigung
- **Course Management** - Vollständige Kurs-/Lerneinheiten-Verwaltung für Lehrer
- **AI Feedback System** - Ollama + DSPy für automatisierte Aufgabenbewertung
- **Spaced Repetition** - FSRS-basierter Wissensfestiger-Algorithmus
- **Live Teaching** - Matrix-View für Klassraumübersicht
- **Asynchronous Processing** - Background worker für KI-Feedback
- **HTTPS Deployment** - Docker Compose mit nginx + Let's Encrypt

### ✅ Recently Completed
- **Input Field Deactivation** - Saubere UX nach Aufgaben-Submission (2025-08-27)
  - Problem: Input-Felder blieben nach Einreichung bearbeitbar, komplizierte Session State Logic
  - Lösung: Database-basierte Anzeige der eingereichten Antwort, eliminiert UI-Blockierungen
  - Status: ✅ Produktiv, deutlich verbesserte User Experience

- **File Upload Production Implementation** - Schüler-Lösungen als PDF/Bild (2025-09-01)
  - Problem: DSPy 2.5.43 Vision-Integration sendete inkompatibles Format an Ollama
  - Lösung: DSPy 3.x Upgrade + qwen2.5vl Vision-Model + LiteLLM-Fix
  - Status: ✅ **Produktionstauglich** - Beide Formate funktionieren zuverlässig
    - PDF-Support: 20.3s Vision-Processing, 2214 Zeichen extrahiert
    - JPG-Support: 15.5s Vision-Processing, 2207 Zeichen extrahiert  
    - UI "Experimentell"-Hinweis entfernt, Feature vollständig aktiviert

### 📊 Current Scale
- **Users:** 30+ simultaneous users tested
- **Security:** Row Level Security (RLS) + Defense in Depth
- **Performance:** <2s page loads, optimized database queries
- **Availability:** 99%+ uptime in school production

---

## Next 3 Months (Q1 2025)

### 🚨 KRITISCHE ISSUES (DRINGEND!)

#### **WORKAROUND: Wissensfestiger Endlos-Wiederholung** 
**Status:** ⚠️ QUICK-FIX AKTIV - System wieder nutzbar  
**Severity:** P0 - Kritisch → P1 - Workaround implementiert  
**Details:** [docs/issues/wissensfestiger_endlos_wiederholung.md](docs/issues/wissensfestiger_endlos_wiederholung.md)

**Problem:** Spaced Repetition System zeigte immer dieselbe Aufgabe an, Streamlit Button-System defekt, Session State Cleanup schlug fehl.

**Quick-Fix implementiert (2025-08-25):**
- ✅ Auto-Feedback-Markierung: Feedback wird sofort als gelesen markiert
- ✅ Feedback-Persistierung deaktiviert: Priorität auf neue Tasks
- ✅ UI-Warnungen: Benutzer werden vor Seitenwechsel gewarnt

**Trade-off:** Verlust der Feedback-Persistierung zugunsten funktionierender Navigation.

**Langfristige Lösung erforderlich:** Database-driven State Management oder Custom JavaScript Button-System.

---

### 🎯 High Priority

#### **Geplant: Terminologie-Vereinheitlichung (Q1 2025)**
**Goal:** Konsistente Begrifflichkeiten in UI, Code und Datenbank
**Status:** 📋 Geplant

- [ ] **Umbenennung "Wissensfestiger" zu "Karteikarten"** - Vereinheitlichung in UI, Code und DB (derzeit: Wissensfestiger und Mastery als parallele Begriffe; künftig nur noch: Karteikarten)
- [ ] **Umbenennung "Meine Aufgaben" zu "Unterricht"** - Klarere Navigation und Begriffswelt für Schüler

**Timeline:** 2 weeks  
**Contributors welcome:** Frontend developers, Backend developers

#### ✅ 0. File Upload Vision-Processing Fixes → ABGESCHLOSSEN 
**Status:** ✅ Produktionstauglich mit DSPy 3.x + qwen2.5vl:7b-q8_0  
**Abgeschlossen:** 2025-09-01
**Implementierte Lösungen:** 
- [x] **DSPy 3.x Upgrade** - Von DSPy 2.5.43 auf DSPy 3.0.3 mit nativer Vision-API
- [x] **qwen2.5vl Integration** - Spezialisiertes Vision-Model für deutsche Handschrift (>95% Genauigkeit)
- [x] **LiteLLM Kompatibilität** - Behoben durch korrekten ollama/ Provider-Präfix
- [x] **Performance Optimierung** - JPG: 56s, PDF: 61s End-to-End (inkl. Feedback)
- [x] **Format-Problem gelöst** - dspy.Image(url=data_url) statt base64_image String

**Performance-Metriken:**
- Vision-Processing: JPG 15.5s, PDF 20.3s
- Text-Extraktion: 2200+ Zeichen zuverlässig erkannt
- GPU-Auslastung: ROCm optimal genutzt (11GB VRAM)

**Architektur:**
- qwen2.5vl:7b-q8_0 für Handschrift-Erkennung
- gemma3:12b-it-q8_0 für Feedback-Generierung
- Automatisches Model-Switching durch Ollama

#### 0.5. KI-Prompt A/B-Testing System (September 2025)
**Status:** 📋 Geplant - Implementierungsplan erstellt  
**Ziel:** Experimentelles Testing verschiedener KI-Prompt-Strategien und Modelle mit Schüler-Bewertungen
**Details:** [docs/plan/ki_prompt_ab_testing_implementierung.md](docs/plan/ki_prompt_ab_testing_implementierung.md)

**Kern-Features:**
- 2-dimensionales A/B-Testing (Prompt-Varianten + Modell-Varianten)
- Zufällige Auswahl: `default`, `detailed`, `socratic` Feedback-Stile
- Multi-Modell-Support: verschiedene LLMs pro Feedback-Generierung
- Schüler-Bewertungen: 0-10 Skala für Feedback-Qualität
- Analytics: Statistische Auswertung der Prompt/Modell-Performance

**Technisch:** 
- Erweitert bestehende DSPy-Module um Varianten-Support
- Minimalinvasiv: nur 4 Dateien ändern, kombiniertes `feedback`-Feld
- Feature-Flag für Aktivierung/Deaktivierung

**Timeline:** 3-4 Tage Implementation + 2-3 Wochen Datensammlung

#### ✅ 1. Security Fixes → ABGESCHLOSSEN
**Goal:** Bestehende Sicherheitslücken schließen vor neuer Feature-Entwicklung
**Status:** ✅ **VOLLSTÄNDIG IMPLEMENTIERT** (Januar 2025)
**Details:** [docs/plan/datei-upload-sicherheit.md](docs/plan/datei-upload-sicherheit.md)

- [x] **File Upload Security** - Extension + Magic Number validation implementiert
- [x] **Path Traversal Protection** - sanitize_filename() für alle Upload-Komponenten
- [x] **Input Validation Framework** - utils/validators.py vollständig implementiert
- [x] **Rate Limiting** - Server-seitiges Rate-Limiting für File-Uploads (10/Stunde, 50MB)
- [x] **Security Test Suite** - Umfassende Tests in app/tests/test_security.py
- [x] **XSS Protection** - Bleach-Sanitization für HTML-Applets

**Timeline:** ✅ Abgeschlossen - Alle kritischen Sicherheitslücken behoben
**Verbleibend:** PII-Logging-Cleanup (niedrige Priorität)

#### ✅ 1. Session-Persistenz Fix → PHASE 1 VOLLSTÄNDIG IMPLEMENTIERT
**Goal:** Lösung der häufigsten User-Beschwerde - ständige Logouts
**Status:** ✅ **PHASE 1 BEHOBEN** - LocalStorage-Lösung implementiert (2025-01-05)
**Details:** [docs/plan/logout_problematik_fix.md](docs/plan/logout_problematik_fix.md)

**PHASE 1: LocalStorage (ABGESCHLOSSEN):**
- [x] **SecureSessionManager** - AES-256 Fernet-Verschlüsselung für Session-Daten
- [x] **90-Minuten Session-Timeout** - Unterrichtsstunden-optimiert (LocalStorage + JWT)
- [x] **CSRF-Protection** - Zusätzliche Token-Validierung gegen Session-Hijacking  
- [x] **Automatisches Token-Refresh** - Transparent ohne User-Unterbrechung
- [x] **XSS-Härtung** - HTML-Sanitization und Security-Headers
- [x] **Root Cause Fix** - Package-Import und Lazy Initialization behoben

**PHASE 2: HttpOnly Cookies (Q2/Q3 2025) - GEPLANT:**
- [ ] **Auth-Service-Architektur** - FastAPI-Service für Session-Management
- [ ] **HttpOnly Cookie Implementation** - XSS-immune, server-seitige Kontrolle
- [ ] **nginx auth_request Module** - Zentrale Session-Validierung
- [ ] **Session Revocation** - Admin kann Sessions beenden
- [ ] **MFA/SSO-Ready** - Enterprise-Features vorbereitet

**Aktueller Status:** F5-Problem vollständig gelöst, Phase 2 für maximale Sicherheit geplant
**Timeline Phase 1:** 8h (komplett) | **Timeline Phase 2:** 6 Wochen (Q2/Q3 2025)

#### 2. Production Stability (Januar 2025)  
**Goal:** Rock-solid deployment for daily school use
**Details:** [docs/plan/logger_implementation.md](docs/plan/logger_implementation.md)

- [ ] **Logging implementieren** - Strukturiertes JSON-Logging (MVP: File-basiert + Auth-Events)
- [ ] **Client-Heartbeat** - Session-Tracking alle 30s für bessere Diagnose
- [ ] **Automatische Backups implementieren** - Tägliche DB-Backups mit Retention Policy
- [x] **E-Mail Rate Limit Problem beheben** - "auth error e-mail rate limit exceeded" bei Registrierung
- [ ] **Zeitzone im Container anpassen** - Deutsche Zeitzone für korrekte Timestamps
- [ ] **db_queries.py refaktorisieren** - Code-Cleanup und Performance-Optimierung

**Timeline:** 3 weeks (nach Session-Fix)  
**Contributors welcome:** DevOps, Python backend developers

#### 2. Task-Type Architecture Refactoring (February 2025)
**Goal:** Saubere Trennung zwischen Regular Tasks und Mastery Tasks
**Status:** 📋 RFC erstellt - Wartet auf Go/No-Go Entscheidung
**Details:** [docs/plan/task_type_trennung_rfc.md](docs/plan/task_type_trennung_rfc.md)

**Problem:** 
- UI-Verwirrung durch gemischte Nummerierung (Aufgaben + Wissensfestiger)
- Lehrer-UI: Mastery/Regular zu eng gekoppelt
- Live-Matrix: Keine Task-Type-Trennung
- Code: Conditional Logic überall (`if is_mastery`)

**Lösung:** Polymorphic Tasks mit `task_category` ENUM + Domain-spezifische Tabellen

**3-Phasen-Migration:**
1. **Write-Both** - Neue Struktur parallel aufbauen
2. **Read-New/Write-Both** - Schrittweiser Umstieg mit Feature-Flag
3. **Read-New/Write-New** - Alte Struktur entfernen

**Timeline:** 3 weeks (nach RFC-Approval)  
**Contributors welcome:** Backend developers, Database experts

#### 3. UX/UI Improvements (März 2025)
**Goal:** Bessere Benutzererfahrung für Lehrer und Schüler

- [x] **Input-Feld Deaktivierung** - Saubere Anzeige eingereichte Antworten (COMPLETED 2025-08-27)
- [x] **Lerneinheiten UI-Update** - Vollbreite Editor, erweiterte Sidebar-Navigation ✅ **COMPLETED 2025-09-03**
  - Problem: Split-View UI zu schmal, gemischte Task-Types in einem Editor, keine Quick Actions
  - Lösung: Vollbreite UI mit Sidebar-Navigation, Task-Type-Trennung Integration, "⚡ Auswählen"-Button
  - Status: ✅ **Production-Ready** - Alle Phasen implementiert und getestet
    - Phase 1: UI-Überarbeitung (Sidebar-Navigation, Structure Tree entfernt)
    - Phase 2: Funktionale Erstellung (Material/Task/Mastery DB-Integration) 
    - Phase 3: Quick Actions Sichtbarkeit + Editor-Fixes (Aufgabentyp-Feld entfernt, Kriterien-Felder hinzugefügt)
  - Details: [docs/plan/Lerneinheiten_UI-Update.md](docs/plan/Lerneinheiten_UI-Update.md)
- [ ] **Real-time Feedback Notifications** - Worker-basierte Toast-Benachrichtigungen implementieren
- [ ] **Markdown-Rendering optimieren** - Verbesserte Darstellung von Lerninhalten
- [ ] **Wortzähler unter abgegebener Aufgabe** - Farblich codiert entsprechend empfohlener Anzahl
- [ ] **Empfohlene Wortanzahl bei Aufgabenerstellung** - Guidance für Lehrer
- [ ] **Automatisches Freischalten des nächsten Abschnittes** - Progressive Content-Freigabe
- [ ] **Feedback-Merge bei Lehrer-Überarbeitung** - Feed-Back und Feed-Forward verschmelzen
- [ ] **Passwort-Zurücksetzen implementieren** - Benutzerfreundliche Passwort-Recovery-Funktion  
  - **Status:** ❌ **FEHLGESCHLAGEN** - Streamlit-Supabase Architektur-Inkompatibilität
  - **Details:** [docs/plan/password_reset_implementierung.md](docs/plan/password_reset_implementierung.md)
  - **Problem:** URL-Fragmente vs. Server-Side-Rendering, Supabase Dashboard Override
  - **Alternative:** OTP-basierte Lösung oder nginx Redirect Rules erforderlich

**Timeline:** 4 weeks  
**Contributors welcome:** Frontend developers, UX designers, Educators

#### 3. Feature Completion (März 2025)
**Goal:** Vollständige Implementation geplanter Features

- [x] **Datei-Upload für Schüler implementieren** - PDF/Bild-Upload mit Text-Extraktion (COMPLETED 2025-08-28)
- [ ] **OCR Integration (Qwen2.5-VL)** - Automatische Texterkennung aus Bildern
- [ ] **Musterlösung bei Mastery-Aufgaben** - Zugänglich nach Abschluss
- [ ] **Musterlösung bei normalen Aufgaben** - Verfügbar nach allen Versuchen
- [ ] **Wissensfestiger-Aufgaben in Live-Matrix** - Integration in Lehrer-Dashboard
- [ ] **Kurs-abhängige Feedback-Speicherung** - Bessere State-Management im Wissensfestiger

**Timeline:** 4 weeks  
**Contributors welcome:** AI/ML developers, Full-stack developers

### 🔧 Security & Infrastructure

#### 4. Security Hardening (Parallel zu Q1)
- [ ] **Service Role Key Elimination** - Replace with SECURITY DEFINER functions
- [ ] **Input Validation Framework** - Centralized validation for all user inputs
- [ ] **CSP Headers** - Content Security Policy implementation
- [ ] **Rate Limiting** - Per-user API rate limits beyond email

**Contributors welcome:** Security experts, Backend developers

---

## Next 6 Months (Q2 2025)

### 🚀 Major Features

#### 1. Advanced AI Capabilities
- [x] **Multi-modal AI** - Vision models for image analysis (qwen2.5vl + DSPy 3.x)
- [x] **DSPy 3.x Migration** - Erfolgreich migriert mit nativer Vision-API Integration
- [ ] **Personalized learning paths** - Adaptive content recommendation  
- [ ] **AI content generation** - Automatic quiz/exercise creation
- [ ] **Plagiarism detection** - Text similarity analysis
- [ ] **Multi-Model Architecture** - Spezialisierte Models für verschiedene Tasks

#### 2. Collaboration Features
- **Real-time collaboration** - Students work together on assignments
- **Peer review system** - Student-to-student feedback
- **Discussion forums** - Course-based communication
- **Video conferencing** - Integrated live sessions

#### 3. Analytics & Insights
- **Learning analytics dashboard** - Progress visualization
- **Predictive modeling** - At-risk student identification
- **Performance insights** - Class-wide statistics
- **Export capabilities** - Data portability

#### 4. Integration Ecosystem
- **LTI compliance** - Learning Tools Interoperability
- **Single Sign-On** - LDAP/Active Directory
- **API development** - RESTful APIs for third-party integration
- **Webhook system** - Event-driven notifications

#### 5. CLI Teacher Planning Tool (Q2 2025)
**Goal:** Command Line Interface für schnelle Unterrichtsplanung
**Status:** 📋 Implementierungsplan erstellt, Security-First Approach
**Details:** [docs/plan/cli_teacher_planning_implementierung.md](docs/plan/cli_teacher_planning_implementierung.md)

**Features:**
- REST API Endpoints für CRUD-Operationen von Lerneinheiten
- Batch-Upload von Kursmaterialien (Markdown, PDFs, Bilder) 
- Template-basierte Aufgabenerstellung mit standardisierten Parametern
- API Key Management mit granularen Scopes
- Atomic Batch Operations

**4-Phasen-Implementation:**
1. **Security Hardening** (1 Woche) - Bestehende Vulnerabilities beheben
2. **Core API** (2 Wochen) - FastAPI Service + Authentication
3. **CLI MVP** (1 Woche) - Basic Commands + JSON Schema
4. **Production Ready** (1 Woche) - Security Testing + Load Testing

**Timeline:** 6 weeks
**Contributors welcome:** Backend developers, Security experts, CLI/DevTools developers

---

## Future Vision (2025+)

### 🌟 Long-term Goals

- **AI-powered curriculum design** - Automated learning path creation
- **Blockchain credentials** - Tamper-proof certificates  
- **VR/AR learning experiences** - Immersive educational content
- **Multi-language support** - International school deployment
- **Machine learning optimization** - Self-improving AI models
- **Micro-learning platform** - Bite-sized lesson delivery

### 🌍 Scale Targets
- **1000+ concurrent users** - Horizontal scaling architecture
- **Multi-tenant SaaS** - School district deployments
- **Cloud-native deployment** - Kubernetes orchestration
- **Global CDN** - Worldwide content delivery

---

## Contributing

### 🤝 How to Get Involved

**For Developers:**
- Review [CODESTYLE.md](CODESTYLE.md) for coding standards
- Check [SECURITY.md](SECURITY.md) for security guidelines  
- Read [ARCHITECTURE.md](ARCHITECTURE.md) for system overview
- Start with issues labeled `good-first-issue` or `help-wanted`

**Priority Contributions Needed:**
1. **Security expertise** - Penetration testing, code audits
2. **DevOps skills** - Monitoring, CI/CD, infrastructure  
3. **Frontend developers** - React/Vue migration, mobile design
4. **Technical writers** - Documentation, tutorials
5. **Educators** - Pedagogical feedback, feature requirements
6. **Translators** - Multi-language support

### 📋 Current Open Issues

**Production Bugs & Features:**
- [x] **KRITISCH: Session-Persistenz Fix → PHASE 1 ABGESCHLOSSEN** - LocalStorage Lösung (8h)
- [ ] Logging implementieren
- [ ] Automatische Backups implementieren
- [x] E-Mail Rate Limit Problem beheben
- [ ] Passwort-Zurücksetzen implementieren ❌ **FEHLGESCHLAGEN** (siehe [docs/plan/password_reset_implementierung.md](docs/plan/password_reset_implementierung.md))
- [ ] Datei-Upload für Schüler (OCR)
- [ ] Musterlösung-System
- [ ] Wissensfestiger in Live-Matrix
- [ ] db_queries.py refaktorisieren

**Security & Infrastructure:**
- [ ] Replace Service Role Key with secure functions
- [ ] Input validation framework
- [ ] CSP headers implementation

**Documentation & Development:**
- [ ] Implement comprehensive test suite
- [ ] Create Docker development environment
- [ ] Build component library documentation

### 🎯 Contribution Impact
- **High impact, low effort** - Documentation improvements, UI fixes
- **High impact, medium effort** - Security enhancements, performance optimizations  
- **High impact, high effort** - New feature development, AI improvements

---

**Last Updated:** December 2024  
**Next Review:** March 2025

For questions about contributing or roadmap priorities, open an issue or contact the maintainers.