# GUSTAV - Roadmap

**Gustav unterstützt Schüler tadellos als Vertretungslehrer**

*(Status: Prototyp in Entwicklung)*

## 1. Konzept & Vision

GUSTAV ist eine KI-gestützte Lernplattform, die entwickelt wird, um Lehrkräfte im Schulalltag zu entlasten und Schülern eine individualisierte Lernerfahrung zu ermöglichen.

**Kernidee:**
Die Plattform soll Schülern automatisiertes, KI-generiertes Feedback zu ihren eingereichten Aufgabenlösungen geben und Vorschläge für Bewertungen erstellen. Dies reduziert den Korrekturaufwand für Lehrer erheblich, insbesondere in Vertretungssituationen oder bei Standardaufgaben. Gleichzeitig erhalten Schüler zeitnahes, spezifisches Feedback, das den Lernprozess unterstützt.

**Funktionsweise (Prototyp):**
*   **Nutzerrollen:** Es gibt Schüler und Lehrer mit eigenen Accounts.
*   **Content-Erstellung (Lehrer):** Lehrer erstellen Lerneinheiten, die sie in logische Abschnitte unterteilen. Zu jedem Abschnitt können sie Lernmaterialien (Markdown, Links) und Aufgaben (Typ 'text' mit **optionalen Bewertungskriterien**) hinzufügen.
*   **Kursmanagement (Lehrer):** Lehrer erstellen Kurse und weisen Schüler und Lerneinheiten diesen Kursen zu.
*   **Freigabe (Lehrer):** Lehrer geben gezielt einzelne Abschnitte einer Lerneinheit für bestimmte Kurse frei.
*   **Lernansicht (Schüler):** Schüler sehen die für ihre Kurse freigegebenen Abschnitte, Materialien (in Expandern) und Aufgaben linear.
*   **Aufgabenbearbeitung (Schüler):** Schüler reichen ihre Lösungen zu Textaufgaben ein (**Mehrfacheinreichung geplant aber noch nicht implementiert**). Die eigene Lösung wird angezeigt.
*   **KI-Feedback (Automatisiert):** Nach der Einreichung analysiert eine lokal gehostete generative KI (via Ollama, gesteuert durch DSPy) die Lösung anhand der Lehrer-Kriterien und generiert Feedback sowie eine Kriterienanalyse.
*   **Ergebniseinsicht:** Schüler sehen ihr Feedback direkt in der Aufgabenansicht. Lehrer können in der Live-Unterricht Ansicht das KI-Feedback direkt bearbeiten. Bearbeitetes Feedback wird Schülern mit einem entsprechenden Hinweis angezeigt.

**Zielgruppe:** Schüler und Lehrer (Sekundarstufe I/II), insbesondere zur Unterstützung bei Vertretungsstunden, für Hausaufgaben oder für Phasen des selbstorganisierten Lernens.

**Problem:** Hohe Arbeitsbelastung von Lehrkräften durch Korrekturen, Bedarf an zeitnahem und individuellem Feedback für Schüler, Sicherstellung von Lernfortschritt bei Abwesenheit der Lehrkraft.

**Langfristige Vision:** Entwicklung zu einer umfassenden Lernplattform mit adaptiven Lernpfaden, die sich an den individuellen Fortschritt anpassen, vielfältigen interaktiven Aufgabentypen, detaillierten Lernanalysen, einer Mobile App und erweiterten KI-Funktionen zur Inhaltserstellung und Lernunterstützung.

## 2. Technologie-Stack

*   **Deployment:** Docker Compose
*   **Web Framework/UI:** Streamlit
*   **KI-Modell-Hosting:** Ollama (Lokal)
*   **KI-Modell-Steuerung:** DSPy
*   **Datenbank:** Supabase (PostgreSQL) (Lokal via Supabase CLI verwaltet)
*   **Authentifizierung:** Supabase Auth
*   **Dateispeicherung:** Supabase Storage

*Begründung:* Fokus auf Open Source, lokale Ausführbarkeit/Kontrolle, Python-Ökosystem.

## 3. Architekturüberblick (Vereinfacht)

```
+-----------------+      +-------------------------+      +---------------------+
| Streamlit App   | ---- | Supabase Backend (CLI)  | ---- | PostgreSQL Database |
| (UI, Logik)     |      | (Auth, API, Storage)    |      | (Schema, RLS)       |
| (Docker Compose)|      | (Docker via CLI)        |      | (Docker via CLI)    |
+-----------------+      +-------------------------+      +---------------------+
       |                        | (via localhost:API_PORT / host.docker.internal)
       | (host.docker.internal) |
       |                        |
       +------------------------+
       |
       | (HTTP Request)         +---------------------+
       +----------------------->| Ollama (KI Modelle) |
       | (DSPy)                 | (Docker Compose)    |
       |                        +---------------------+
+-----------------+
| Mailpit         |<-+
| (Docker via CLI)|  | (SMTP)
+-----------------+  |
                     |
+--------------------+
| Supabase Auth (GoTrue) |
| (Docker via CLI)       |
+------------------------+
```
*   Supabase Backend (DB, Auth, Storage, API Gateway etc.) läuft in Docker-Containern, die von der Supabase CLI verwaltet werden. Die API ist auf `localhost:<API_PORT>` erreichbar.
*   Die Streamlit App und Ollama laufen in separaten Docker-Containern, die über eine eigene `docker-compose.yml` verwaltet werden.
*   Die Streamlit App kommuniziert mit dem Supabase Backend über `http://host.docker.internal:<API_PORT>` (wenn App im Docker läuft) oder `http://localhost:<API_PORT>` (wenn lokal gestartet).
*   Die Streamlit App kommuniziert mit Ollama über dessen Service-Namen (`http://ollama:11434` im Docker-Netzwerk).
*   Supabase Auth sendet lokale E-Mails an Mailpit.

## 4. Datenbankstruktur (Schema v2.1 - mit Abschnitten)

*   ENUM `user_role`: ('student', 'teacher')
*   `profiles`: Verknüpft `auth.users` mit `role`, `full_name`, `email`. Trigger füllt automatisch.
*   `course`: Kurse (id, name, ~~description~~, creator_id). **(description entfernt in Phase 8)**
*   `course_teacher`, `course_student`: M:N Verknüpfungen.
*   `learning_unit`: Lerneinheiten (id, title, ~~description~~, creator_id). **(description entfernt in Phase 8)**
*   `unit_section`: Abschnitte (id, unit_id, title, order_in_unit, `materials` JSONB).
    *   `materials`: Liste von Objekten (Typ 'markdown' oder 'link').
*   `task`: Aufgaben (id, section_id, ~~title~~, instruction, task_type (`'text'`), order_in_section, **`assessment_criteria` JSONB**, **`solution_hints` TEXT**, **`is_mastery` BOOLEAN**, **`max_attempts` INTEGER**). **(title entfernt in Phase 8, criteria→assessment_criteria als JSONB Array, solution_hints hinzugefügt in Phase 9, is_mastery für Wissensfestiger in Phase 9, max_attempts in Phase 9)**
*   `course_learning_unit_assignment`: M:N Zuweisung Einheit <-> Kurs.
*   `course_unit_section_status`: Freigabestatus (`is_published`) pro Kurs/Abschnitt.
*   `submission`: Einreichungen (id, student_id, task_id, `solution_data` JSONB, **`attempt_number` INTEGER**, **`ai_criteria_analysis` TEXT**, `ai_feedback` TEXT, `ai_grade` TEXT, **`feed_back_text` TEXT**, **`feed_forward_text` TEXT**, overrides). `UNIQUE(student_id, task_id)` wurde ersetzt durch `UNIQUE(student_id, task_id, attempt_number)`. **(Struktur für Mehrfacheinreichung in Phase 9 angepasst)**
*   **`student_mastery_progress`**: Lernfortschritt für Wissensfestiger (student_id, task_id, current_interval, next_due_date, ease_factor, repetition_count, status, learning_step_index, relearning_step_index, last_attempt_date, last_score, total_attempts). **(Neue Tabelle für Spaced Repetition in Phase 9)**

*(Detaillierte `CREATE TABLE`-Statements befinden sich in den SQL-Migrationsdateien).*

## 5. Sicherheitskonzept (RLS & Temporäre Fixes)

*   Authentifizierung: Supabase Auth (E-Mail/Passwort mit Bestätigung via Mailpit lokal).
*   Autorisierung: Row-Level Security (RLS) in PostgreSQL.
*   **RLS-Prinzipien (Implementiert):**
    *   Nutzer können nur eigene `profiles`-Daten sehen/ändern (Lehrer dürfen andere zum Auswählen sehen).
    *   Schüler sehen nur Kurse/Einheiten/Abschnitte/Aufgaben, die für sie freigegeben sind (über diverse RLS-Policies und Joins geprüft).
    *   Schüler können nur eigene `submission` erstellen/sehen.
    *   Lehrer können Einheiten/Abschnitte/Aufgaben für Einheiten sehen/verwalten, deren `creator_id` sie sind.
*   **Temporäre Fixes / TODOs für Produktion:**
    *   Lehrer-RLS Verfeinerung (Zugriff auf Kurse/Einreichungen anderer Lehrer einschränken).
    *   Storage Upload Policy (aktuell unsicher, Funktion auskommentiert).
    *   Storage Bucket (aktuell öffentlich).

## 6. Datei- & Ordnerstruktur

```
gustav/
├── .env.example
├── .env
├── .gitignore
├── docker-compose.yml
├── README.md
│
├── app/
│   ├── Dockerfile
│   ├── requirements.txt    # (enthält jetzt dspy-ai)
│   ├── main.py
│   ├── supabase_client.py
│   ├── auth.py
│   ├── config.py
│   ├── __init__.py
│   ├── pages/
│   │   ├── 0_Dashboard.py
│   │   ├── 1_Kurse_verwalten.py
│   │   ├── 2_Lerneinheiten_verwalten.py # (assessment_criteria & solution_hints für KI)
│   │   ├── 3_Meine_Aufgaben.py          # (Vollständig mit Feed-Back/Feed-Forward-Anzeige)
│   │   ├── 4_Meine_Ergebnisse.py        # (Leer - Feedback in Aufgabenansicht)
│   │   ├── 5_Schueleruebersicht.py      # (Verweis auf Live-Unterricht)
│   │   ├── 6_Live_Unterricht.py         # (Matrix-View & Feedback-Bearbeitung)
│   │   └── 7_Wissensfestiger.py         # (Spaced Repetition Modul für Schüler)
│   ├── assets/
│   ├── config/
│   │   └── mastery_config.py      # (Spaced Repetition Parameter & Lernstufen-Labels)
│   └── utils/
│       ├── db_queries.py          # (Erweitert mit Live-Übersicht, Teacher-Override & 7 Mastery-Funktionen)
│       ├── mastery_algorithm.py   # (SM-2 Spaced Repetition Algorithmus)
│       └── __init__.py
│
│   ├── ai/
│   │   ├── config.py              # (Ehemals dspy_setup.py - Ollama/DSPy Konfiguration)
│   │   ├── feedback.py            # (Konsolidiert: Signaturen + Module + Service)
│   │   ├── mastery.py             # (Score-Generierung für Spaced Repetition)
│   │   ├── deprecated/            # (Archivierte alte Module)
│   │   └── __init__.py
│
└── supabase/
    ├── config.toml
    ├── migrations/         # (Enthält 20250801123332 für assessment_criteria/solution_hints)
    │   ├── 20250802135638_add_mastery_flag_to_tasks.sql
    │   ├── 20250802135702_create_student_mastery_progress.sql
    │   └── ...
    ├── functions/
    └── seed.sql
```

---

## 7. Entwicklungs-Roadmap (Phasen)

1.  **Phase 0: Projekt-Setup & Lokale Umgebung** `[DONE]`
2.  **Phase 1: Supabase Schema & RLS** `[DONE]`
3.  **Phase 2: Basis-Authentifizierung & Nutzerrollen (Streamlit)** `[DONE]`
4.  **Phase 3: Content Management - Lehrer-Flow** `[DONE (Core Features)]`
5.  **Phase 4: Lernansicht & Einreichung - Schüler-Flow** `[DONE]`
6.  **Phase 5: KI-Integration (Ollama & DSPy)** `[DONE]`
7.  **Phase 6: Anzeige von Feedback & Ergebnissen** `[DONE]`
8.  **Phase 7: Live-Unterrichts-Ansicht (Lehrer-Cockpit)** `[DONE]`

9.  **Phase 8: Refactoring & Vereinfachung** `[DONE]`
    *   **Ziel:** Die Benutzeroberfläche und die Datenstrukturen vereinfachen, um die Kernfunktionalität zu schärfen und die Wartbarkeit zu erhöhen.
    *   **Ergebnisse:**
        *   **Kurs-Beschreibungen entfernt:** Die Spalte `description` wurde aus der `course`-Tabelle entfernt. Die UI in "Kurse verwalten" wurde entsprechend angepasst, um die Eingabe und Anzeige von Beschreibungen zu entfernen.
        *   **Lerneinheit-Beschreibungen entfernt:** Die Spalte `description` wurde aus der `learning_unit`-Tabelle entfernt. Die UI in "Lerneinheiten verwalten" wurde ebenfalls angepasst.
        *   **Aufgaben vereinfacht:**
            *   Die Spalte `title` wurde aus der `task`-Tabelle entfernt.
            *   Die Reihenfolge der Aufgaben (`order_in_section`) wird nun automatisch als "nächstes in der Warteschlange" festgelegt, wodurch die manuelle Eingabe bei der Erstellung entfällt.
            *   Die UI wurde entsprechend angepasst, um Titel und Reihenfolgen-Eingabe zu entfernen. Die Möglichkeit zur späteren Re-Implementierung einer manuellen Sortierung wurde im Code berücksichtigt.

10. **Phase 9: Multi-User Skalierung & Asynchrone Verarbeitung** `[DONE]`
    *   **Ziel:** Skalierung auf 50+ gleichzeitige Nutzer durch asynchrone Feedback-Verarbeitung und robuste Queue-Architektur.
    *   **Ergebnisse:**
        *   **Asynchrone Feedback-Pipeline:** Vollständige Umstellung von synchroner zu queue-basierter Verarbeitung mit separatem Worker-Prozess
        *   **PostgreSQL-Queue-System:** Atomare Queue-Operationen mit `feedback_status`, Retry-Mechanismen, und Stuck-Job-Recovery
        *   **Service-Role/RLS-Trennung:** Worker umgeht RLS für Queue-Management, App respektiert weiterhin Student-Policies
        *   **Real-time UX:** Live-Queue-Status, Warteschlangen-Position, intelligente Auto-Refresh ohne Textverlust
        *   **Robuste Fehlerbehandlung:** Exponential backoff, Timeouts, Health-checks, graceful degradation
        *   **Production-Ready:** Docker-orchestriert, horizontale Worker-Skalierung möglich

11. **Phase 10: Performance & Multi-User-Skalierung** `[DONE]` (2025-08-19)
    *   **Session-Isolation für Multi-User-Betrieb:** `[DONE]`
        *   ✅ **Kritischer Bug behoben:** Session-Vermischung bei >10 gleichzeitigen Nutzern
        *   ✅ **Session-Client-Architektur:** Jeder User erhält eigenen Supabase-Client in `st.session_state`
        *   ✅ **DB-Query-Migration:** Alle 60+ Queries zu session-spezifischen Clients migriert
        *   ✅ **Token-Management:** Automatisches Token-Refresh und proper Session-Cleanup
        *   ✅ **Anonyme Clients:** Login/Registrierung getrennt von User-Sessions
    *   **Query-Performance-Optimierung:** `[DONE]`
        *   ✅ **N+1 Query Problem behoben:** `get_submission_status_matrix` von 200+ auf 4 Queries reduziert
        *   ✅ **Batch-Loading implementiert:** Live-Unterricht Matrix-View lädt alle Tasks in einem Query
        *   ✅ **Result-Caching:** 60-Sekunden Cache für Matrix-Daten mit intelligenter Invalidierung
        *   ✅ **Smart Navigation Caching:** Kurse (90min TTL) und Einheiten (10min TTL) cached
        *   ✅ **User Selection Persistence:** Kurs/Einheit-Auswahl bleibt 90min erhalten
    *   **Material-System Bugfixes:** `[DONE]` ✅
        *   ✅ **Session-Client Integration:** Material-Upload/Download auf Session-Clients umgestellt
        *   ✅ **Storage Auth-Problem gelöst:** Public Storage für `section_materials` mit App-Level Security implementiert
        *   ✅ **Sicherheitsmodell:** Defense-in-Depth - RLS verhindert path discovery, UUID-Schutz (128-bit), App-Autorisierung
        *   ✅ **Migration:** 20250819173931_implement_public_storage_with_app_security.sql angewendet
    *   **Datei-Upload-Funktionalität für Schüler:** `[TODO]`
        *   Schüler können Lösungen als PDF/JPG/PNG hochladen
        *   Vision Model (Qwen2.5-VL) extrahiert Text aus Bildern
        *   Extrahierter Text wird wie normale Texteinreichung behandelt
        *   Detailplan in `Implementierung_Datei-Upload.md`
    *   **Ziel:** Stabile Performance bei 30+ gleichzeitigen Nutzern und verbesserte User Experience.
    *   **Detaillierte Schritte:**
        *   **UI-Workflow-Optimierung:** `[DONE]`
            *   ✅ **Styleguide:** Umfassendes Design-System erstellt (styleguide.md v1.3.0)
                *   ✅ Einheitliche Sidebar-Komponente für 8/10 Seiten implementiert
                *   ✅ Konsistente st.set_page_config() auf allen 10 Seiten
                *   ✅ Zentrale UI-Komponenten-Bibliothek (ui_components.py)
                *   ✅ Standardisierte Layouts und Interaktions-Patterns
                *   ✅ iPad-optimiertes, minimalistisches Design
                *   ✅ Logo als Favicon integriert
            *   ✅ **Kurse:** Seite modernisiert mit neuer Sidebar und Tab-Struktur
            *   ✅ **Lerneinheiten:** Seite mit Sidebar für Kurs- und Einheitenauswahl
            *   ✅ **Schüler:** Neue Implementierung mit Kursfilter und Schülerliste
            *   ✅ **Meine Ergebnisse:** Grundstruktur mit Sidebar und Vorschau-Layout
            *   ✅ **Dashboard:** Modernisiert ohne Sidebar (Design-Entscheidung)
            *   ✅ **Feedback einklappbar:** In "Meine Aufgaben" standardmäßig eingeklappt
            *   ✅ **Kursverwaltung verbessert:** (2025-08-10)
                *   ✅ Benutzerfreundliche Kurserstellung direkt auf der Hauptseite
                *   ✅ Neuer "Kurs-Einstellungen" Tab mit Umbenennen/Löschen-Funktionen
                *   ✅ Berechtigungsprüfung für Kurs-Verwaltung implementiert
                *   ✅ Bug-Fix: Kurs-Ersteller wird automatisch zu course_teacher hinzugefügt
        *   **Optimierung des KI-generierten Feedbacks:** `[DONE]`
            *   ✅ Neue zweistufige "Atomare Analyse"-Pipeline implementiert (siehe feedback_implementation.md)
            *   ✅ Struktur in `feedback_focus` aufgeteilt: `assessment_criteria` (JSONB Array) und `solution_hints` (TEXT)
            *   ✅ Template-basiertes Parsing für robuste LLM-Antworten implementiert
            *   ✅ Separate Feed-Back und Feed-Forward Generierung für bessere pädagogische Struktur
            *   ✅ DSPy Signaturen: `AnalyseSingleCriterion` und `GeneratePedagogicalFeedback` erstellt
            *   ✅ Migration 20250801123332 für neue Datenbankstruktur durchgeführt
            *   ✅ AI-Modul Refactoring (2025-08-11):
                *   Von 5 auf 3 Dateien reduziert (40% weniger Code)
                *   Klarere Struktur: config.py, feedback.py, mastery.py
                *   Deprecated Code in Archiv-Ordner verschoben
                *   DSPy-Optimizer Kompatibilität erhalten
                *   Prompts optimiert: Gymnasiallehrer-Perspektive, strukturiertes Feedback
        *   **Kritische System-Reparaturen (2025-08-20):** `[DONE]`
            *   ✅ **Feedback-Worker Threading-Problem behoben:** "No LM is loaded" Fehler komplett eliminiert durch DSPy-Konfiguration im Hauptthread
            *   ✅ **DateTime-Parsing-Bug:** ValueError bei variablen Mikrosekunden-Stellen in Timestamps korrigiert
            *   ✅ **Wissensfestiger-Feedback-Persistierung:** Kritisches UX-Problem behoben - Feedback geht nicht mehr verloren bei Seitenwechsel:
                *   DB-Schema erweitert um `feedback_viewed_at` Tracking-Spalte
                *   Intelligente Task-Auswahl priorisiert ungelesenes Feedback vor neuen Aufgaben
                *   Minimalinvasiver "Nächste Aufgabe"-Button markiert automatisch Feedback als gelesen
                *   Legacy-Code vollständig bereinigt für saubere Architektur
        *   **Wissensfestiger-Modul implementiert & refactored:** `[DONE]`
            *   ✅ **Refactoring (2025-08-13):** Umstellung auf FSRS-inspirierten Algorithmus mit kontinuierlicher Stabilitäts- und Schwierigkeitsanpassung. Neues Datenmodell und differenzierte KI-Bewertung.
            *   ✅ Alle kritischen Bugs im Zusammenhang mit dem Refactoring behoben, einschließlich des Problems, dass fällige Aufgaben nicht korrekt angezeigt wurden.
            *   ✅ System vollständig getestet und einsatzbereit.
            *   ✅ Pädagogisches Feedback (Feed-Back/Feed-Forward) wird nun statt technischem "Reasoning" angezeigt.
            *   TODO: Dashboard-Integration für Lehrer-Übersicht (verschoben).
        *   **Feedback-System für Schüler implementiert:** `[DONE]`
            *   ✅ Anonymes Feedback-System für Schüler implementiert
            *   ✅ Neue Seite "8_Feedback_geben.py" für Schüler
            *   ✅ Neue Seite "9_Feedback_einsehen.py" für Lehrer
            *   ✅ Unterscheidung zwischen Unterrichts- und Plattform-Feedback
        *   **E-Mail-Domain-Validierung implementiert:** `[DONE]`
            *   ✅ Registrierung auf @gymalf.de E-Mail-Adressen beschränkt
            *   ✅ Frontend-Validierung mit benutzerfreundlichen Fehlermeldungen
            *   ✅ Backend-Validierung via erweiterten handle_new_user Trigger
            *   ✅ Flexible Domain-Verwaltung über neue allowed_email_domains Tabelle
            *   ✅ Migration: 20250807215415_restrict_signup_to_gymalf_domain.sql
            *   ✅ Hilfsskript für Domain-Management erstellt
        *   **E-Mail-Bestätigung konfiguriert:** `[DONE]`
            *   ✅ SMTP-Konfiguration in supabase/config.toml vorbereitet
            *   ✅ Professionelle E-Mail-Templates erstellt (confirmation.html, recovery.html)
            *   ✅ Umgebungsvariable SMTP_PASSWORD in .env.example dokumentiert
            *   ✅ Lokale Entwicklung mit InBucket funktioniert (Port 54324)
            *   ✅ E-Mail-Bestätigung bereits aktiv (enable_confirmations = true)
            *   ✅ E-Mail-Bestätigungslinks über nginx-Proxy repariert (2025-08-09)
                *   Problem: Links führten zu weißem Bildschirm
                *   Lösung: Minimaler nginx-Proxy für /auth/v1/verify
                *   Sicherheit: Rate-Limiting (5req/min), nur GET, strikte Filterung
        *   **Registrierungs-UX verbessert:** `[DONE]`
            *   ✅ Kein automatischer Tab-Wechsel nach Registrierung
            *   ✅ Klare Erfolgs- und Fehlermeldungen bleiben sichtbar
            *   ✅ Formular-Verhalten optimiert (clear_on_submit)
            *   ✅ Benutzerfreundliche Hinweise und Platzhalter
            *   ✅ Einfache Datenbankstruktur ohne komplexe RLS-Policies
            *   ✅ Session-State für Bestätigungsnachrichten
            *   ✅ Robuste Datum-Anzeige ohne Parsing-Fehler
        *   **Dashboard zu Startseite umgestaltet:** `[DONE]` (2025-01-09)
            *   ✅ Dashboard.py in Startseite.py umbenannt
            *   ✅ Komplette Überarbeitung als Orientierungs- und Informationsseite
            *   ✅ Rollenspezifische Inhalte (Lehrer/Schüler sehen nur relevante Features)
            *   ✅ Wissenschaftlich fundierte Feature-Beschreibungen für Schüler
            *   ✅ Systemstatus-Anzeige mit Ollama-Verfügbarkeitsprüfung
            *   ✅ Seite "Meine Ergebnisse" für Schüler entfernt (wird später neu aufgebaut)
            *   ✅ Navigation und Fallback-Pfade angepasst
        *   **Sicherheitsverbesserungen:** `[TODO]`
            *   TODO: Service Role Key aus Anwendung entfernen
                *   **Problem:** Der `SERVICE_ROLE_KEY` wird aktuell im Python-Code verwendet, um RLS für administrative Aufgaben (z.B. KI-Feedback speichern) zu umgehen. Dies ist ein hohes Sicherheitsrisiko.
                *   **Lösung:** Ersetzen durch sichere `SECURITY DEFINER` PostgreSQL-Funktionen
            *   TODO: Row Level Security (RLS) vollständig implementieren
            *   ✅ **Storage Policies für sichere Datei-Uploads implementiert:**
            *   TODO: Input-Validierung verstärken
            *   TODO: Rate Limiting implementieren
            *   TODO: E-Mail-Bestätigungslink zeigt keine Erfolgsmeldung
                *   **Problem:** Query-Parameter werden nicht korrekt erkannt/verarbeitet nach Klick auf Bestätigungslink
                *   **Mögliche Ursache:** Supabase verarbeitet den Link intern bevor Weiterleitung zur App erfolgt
                *   **Debug:** Query-Parameter in Konsole loggen und analysieren welche Parameter ankommen
            *   ✅ E-Mail-Links verweisen immer auf 127.0.0.1 statt auf konfigurierte SITE_URL
                *   **Problem:** Trotz SITE_URL=https://gymalf-gustav.duckdns.org wurden Links mit 127.0.0.1 generiert
                *   **Ursache:** Supabase CLI hardcoded API_EXTERNAL_URL zu 127.0.0.1:54321 (bekannter Bug)
                *   **Lösung:** E-Mail-Templates angepasst - verwenden jetzt {{ .SiteURL }} statt {{ .ConfirmationURL }}
                *   **Status:** GELÖST - Links zeigen jetzt korrekt auf https://gymalf-gustav.duckdns.org
        *   **Weitere UI-Features:** `[PARTIALLY DONE]`
            *   TODO: Bearbeiten/Löschen für Kurse, Einheiten, Abschnitte. (Bearbeiten von Aufgaben ist bereits implementiert).
            *   TODO: Passwort-Zurücksetzen-Funktion in UI integrieren
            *   TODO: E-Mail erneut senden Button bei Registrierung
            *   ✅ **Mehrfacheinreichungen für Aufgaben implementiert:** `[DONE]` (2025-08-11)
            *   ✅ **Erweiterte Materialtypen (Dateien):** Lehrer können Bilder, PDFs und andere Dateien als Material hochladen. `[DONE]` (2025-08-11)
*   ✅ **Erweiterte Materialtypen (Applets):** Einbetten von interaktiven HTML/JS-Applets. `[DONE]` (2025-08-11)
                *   **Ergebnis:** Schüler können Aufgaben mehrfach einreichen, um ihr Feedback zu verbessern.
                *   **Details:**
                    *   Lehrer können pro Aufgabe eine maximale Anzahl an Versuchen festlegen.
                    *   Die Schüler-UI zeigt die komplette Abgabehistorie an.
                    *   Das KI-Feedback berücksichtigt den vorherigen Versuch, um kontextbezogenes, aufbauendes Feedback zu geben.
                    *   Die Datenbank wurde entsprechend migriert (neue Spalten, geänderte Constraints).
        *   **HTTPS-Deployment:** `[DONE]`
            *   ✅ nginx und Let's Encrypt Integration erfolgreich implementiert
            *   ✅ DuckDNS für dynamische DNS konfiguriert
            *   ✅ docker-compose.yml erweitert für Produktion
            *   ✅ SSL-Zertifikate erfolgreich ausgestellt und installiert
            *   ✅ HTTPS läuft stabil in Produktion
            *   📋 Deployment-Anleitung in DEPLOYMENT.md dokumentiert

11. **Phase 10: Testing & Performance** `[TODO]`
    *   **Ziel:** Sicherstellung der Stabilität und Effizienz der Anwendung.
    *   **Detaillierte Schritte:**
        *   **Performance:** Überprüfung und Optimierung von Datenbankabfragen, ggf. Hinzufügen von Indizes.
        *   **Testing:** Erstellung von Unit-Tests für kritische Backend-Funktionen (insb. `db_queries.py` und die neuen Sicherheitsfunktionen).

12. **Phase 11: Dokumentation** `[TODO]`
    *   **Ziel:** `README.md` und `GEMINI.md` vervollständigen.
    *   **Detaillierte Schritte:** Setup, Architektur, Benutzung und vor allem das neue Sicherheitskonzept dokumentieren.
    *   **Artefakte:** `README.md`, `GEMINI.md`.

## 8. Zukünftige Ideen & Erweiterungen (Post-Prototyp)

*   Hilfe-Button für zusätzliches Material
*   Adaptive Lernpfade
*   Vielfältigere Aufgabentypen (MC, Lückentext, Code...)
*   Direkte Lehrer-Bewertung/Kommentare
*   Realtime-Benachrichtigungen/Kollaboration
*   Verbesserte KI (Modelle, Prompts, Inhaltserstellung)
*   Analytics-Dashboard
*   Mobile App
*   Produktionsreifes Deployment

## Backlog (Priorisierung bei Bedarf)

### UI/UX Verbesserungen

**Moderne Wissensfestiger-Fortschrittsanzeige** `[DONE]`
- ✅ **Problem gelöst:** Kompakte Fortschrittsanzeige implementiert mit dreifarbigem Plotly-Balken (gemeistert/lernend/neu)
- ✅ **Datenmodell:** Optimierte SQL-Funktionen (`get_mastery_summary`, `get_due_tomorrow_count`) über korrekte Join-Pfade
- ✅ **UI-Komponente:** Neue Datei `app/components/mastery_progress.py` mit Metriken, Lernstreak und Meilensteinen
- ✅ **Integration:** Eingebunden in Wissensfestiger-Sidebar (`7_Wissensfestiger.py`) mit Caching
