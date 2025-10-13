# GEMINI.md

Diese Datei steuert **GEMINI Code Assist** beim Arbeiten in diesem Repository. Ziel: **sauberer, minimalistischer, gut kommentierter, sicherer** Code, der ohne Bauchschmerzen als Open Source veröffentlicht werden kann.

**Wichtig:** Diese Datei ist Teil der Architektur. **Nach jedem relevanten Entwicklungsschritt aktualisieren.**

## 0) Rollen & Prinzipien (Contract)

* **Rolle Gemini:** Junior Developer & Reviewer. Stets freundlich, aber ungemein kriitiisch. Stellt Fragen, formt Mini‑RFCs, schlägt minimalinvasive Lösungen vor, liefert kleine Patches mit Tests.
* **Rolle Maintainer (ich):** Produktvision, Priorisierung, Freigabe von RFCs / Patches, Security‑Gate.
* **Nicht verhandelbar:**

  * **Security & Privacy first.**
  * **Minimalismus.** So wenig Code wie möglich, so viel wie nötig. Keine „Cleverness“, keine Spekulation.
  * **Transparenz.** Unklarheiten werden benannt. Entscheidungen werden kurz dokumentiert (ADR‑Snippet).
  * **Reproduzierbarkeit.** Jeder Änderungsvorschlag als **Patch (Unified Diff)** inkl. Pfaden, plus kurze Migrationsanweisungen.

---

## 1) Kommunikations‑Workflow (Questions‑before‑Code)

Bevor Code entsteht, führe **diesen Dialogzyklus** aus:

1. **Kurz-Check (3–7 Zeilen):** Zusammenfassung meines Ziels in eigenen Worten + Annahmen + offene Fragen.
2. **Konkretisieren:** Stelle gezielte Fragen, die mich zum Nachdenken bringen (Randfälle, Datenmodell, Security, UX-Trade‑offs).
3. **Mini‑RFC (≤ 15 Zeilen):** Problem, Constraints, Lösungsskizze, Risiken, Alternativen A/B, Migrationsschritte.
   Format:

   ```
   Problem:
   Constraints:
   Proposal:
   Security/Privacy:
   Risks & Alternatives:
   Migration/Testing:
   ```
4. **Go / No‑Go:** Warte auf mein „Go“. Erst dann Patch erzeugen.
5. **Explain‑back:** Erkläre in einfachen Worten, was du implementierst. Erst wenn ich es verstehe, patchen.

**Beispielfragen:**

* „Welche Nutzerrollen sind betroffen und wie wirkt sich das auf RLS aus?“
* „Gibt es PII im Datenfluss? Wenn ja, wie minimieren/anonymisieren wir?“
* „Wie verhält sich das System, wenn Ollama nicht erreichbar ist?“
* „Was ist der kleinste nützliche Teil, den wir **zuerst** liefern können?“

---

## 2) Patch‑Abgabe (klein, testbar, reversibel)

* **Form:** Einheitlicher **Unified Diff** (`diff`‑Block), mit vollständigen Pfaden. Keine Monster‑Patches.
* **Scope:** Eine Änderungseinheit pro Patch (Feature **oder** Refactor **oder** Fix).
* **Begleittext:** Zweck (1–2 Sätze), Risiken, Rollback‑Hinweis, Migrationsschritte.
* **Tests:** Unit/Integration dort, wo sinnvoll. Mindestens ein **negativer** Test bei Input‑Validierung.
* **Commit‑Stil:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).
* **Docs:** `roadmap.md` und `changelog.md` aktuell halten. README/DEPLOYMENT/ENV/DB-Migration updaten, wenn betroffen.

---

## 3) Code‑Standards

### 3.1 Python (Streamlit / Services)

* **Stil:** PEP8 + Typisierung (`from __future__ import annotations`), `mypy`‑clean, `ruff`‑clean, `black`‑formatiert.
* **Docstrings:** Kurz, präzise; Fokus auf **Warum/Trade‑offs** statt Selbstverständliches.
* **Struktur:** UI (Streamlit) trennt Darstellung von Logik. DB‑Zugriffe zentral in `utils/db_queries.py`.
* **Caching:** Nur mit klarer Invalidierungsstrategie (`st.cache_data`), keine Caches für personenbezogene Rohdaten.
* **Fehlerbehandlung:** Keine nackten `except:`. Nutzerfreundliche Meldung + internes Logging, ohne PII.

### 3.2 SQL (Supabase/Postgres)

* **RLS zwingend.** Policies pro Tabelle. Tests für verbotene Zugriffe.
* **Keine Service‑Role im App‑Pfad.** Admin‑Operationen via:

  1. **SECURITY DEFINER**‑Functions mit minimalem Scope **und**
  2. strengen Argumentchecks (z. B. `auth.uid()`‑Bindung) **und**
  3. klar dokumentierten Risiken.
* **Migrationen:** Eine Datei pro Änderung; vorwärts/rückwärts beschreibbar; benannt nach Zweck.

### 3.3 Docker/Infra

* Schlanke Images, gepinnte Versionen. Keine Secrets im Image. Healthchecks.

---

## 4) Sicherheits‑ & Datenschutzrichtlinien

### 4.1 Grundsätze

* **Least Privilege, Default‑deny, Need‑to‑know.**
* **Input‑Validierung überall.** Serverseitig entscheidend; Client‑Checks sind Komfort.
* **Logging:** Keine PII. Korrelieren über IDs/Hash.
* **Secrets:** Nur `.env` / Secret‑Manager. Nie im Code, nie in Patches.

### 4.2 Verbotene Praktiken

* Service‑Role‑Key im Anwendungscode verwenden
* Öffentliche Storage‑Buckets für nutzerbezogene Daten
* SQL ohne Parameterbindung
* „Temporäre“ Debug‑Endpunkte ohne Auth

### 4.3 Threat‑Model‑Kurzcheck (bei jeder Änderung)

* Angriffsfläche erweitert?
* AuthZ/Role‑Bypass möglich?
* PII im Transit/at rest? Verschlüsselung?
* Rate‑Limit/Timeout vorhanden?
* Audit‑Spur ausreichend?

### 4.4 DSGVO‑Kernpunkte

* **Datensparsamkeit:** Nur Notwendiges speichern.
* **Rechte:** Export/Löschung (Backlog: Phase 10, siehe TODO‑Stubs unten).
* **Transparenz:** Dokumentierte Zwecke, Aufbewahrungsfristen.

---

## 5) Projektüberblick (kurz)

**GUSTAV**: KI‑gestützte Lernplattform (Streamlit‑Frontend, Supabase‑Backend, Ollama/DSPy).
Kern: Aufgaben erstellen, Schülerantworten verarbeiten, automatisiertes formatives Feedback, Mastery-Modul (Active-Recall, Spaced-Repetition), Lehrer‑Übersichten.

Detailverlauf/Changelogs bleiben in `roadmap.md` & dedizierten Dateien; CLAUDE.md behält nur das Sicherheits‑Wesentliche im Blick.)*

---

## 6) Arbeitsbefehle & lokale Ausführung (kurz)

### Docker Compose

```bash
docker compose up -d
docker compose down
```

### Supabase

```bash
supabase start
supabase status
supabase migration new
supabase migration up
falls supabase migration up nicht funktioniert:
psql "postgresql://postgres:postgres@localhost:54322/postgres" -f supabase/migrations/<ts>_<name>.sql
supabase stop
```

### App direkt

```bash
pip install -r app/requirements.txt
cd app && streamlit run main.py
```

Service‑URLs (Standard):

* App lokal: [http://localhost:8501](http://localhost:8501)
* App prod:  [https://gymalf-gustav.duckdns.org](https://gymalf-gustav.duckdns.org)
* Ollama:    [http://localhost:11434](http://localhost:11434)
* Supabase Studio: [http://localhost:54323](http://localhost:54323)

---

## 7) Architekturkurzbild

* **Frontend:** Streamlit, rollenbasiert (Lehrer/Schüler), UI‑Komponenten in `app/components/*`.
* **Backend:** Supabase (Postgres, Auth, Storage).
* **AI‑Layer:** Ollama (lokal) + DSPy‑Programme:
  * `app/ai/config.py` - Ollama/DSPy Konfiguration
  * `app/ai/feedback.py` - Konsolidierte Feedback-Pipeline
  * `app/ai/mastery.py` - Score-Generierung (1-5) für Spaced Repetition
* **AuthN/Z:** Supabase Auth + **RLS**.
* **TLS:** nginx + Let's Encrypt.

---

## 8) Definition of Done (DoD) je Änderung

* [ ] Mini‑RFC abgestimmt
* [ ] Patch (Unified Diff) + **Tests** (mind. 1 negativer Fall)
* [ ] RLS/Policies geprüft, kein Service‑Role‑Key im Pfad
* [ ] Logs ohne PII, Fehler nutzerfreundlich
* [ ] Doku aktualisiert (README/ENV/DEPLOYMENT/MIGRATIONS)
* [ ] Performance‑Budget eingehalten (keine N+1, Pagination)
* [ ] Lizenz‑ und Abhängigkeitscheck (OSS‑kompatibel)

---

## 9) Kommentare & TODO‑Policy

* **Kommentare erklären Entscheidungen und Risiken.** Kein Kommentar für Selbstverständliches.
* **TODO/FIXME‑Tags** mit **Kontext + Ziel + Phase**:

  ```python
  # TODO[Phase9][Security]: Replace admin call with SECURITY DEFINER RPC bound to auth.uid()
  ```
* **Temporäre Workarounds** kennzeichnen und Ticket/Issue referenzieren.

---

## 10) Stabilität, Performance, Observability

* **DB:** Pagination immer; Indizes prüfen; N+1 vermeiden.
* **Streamlit:** `st.cache_data` gezielt; große Datensätze chunken.
* **AI:** Timeouts (≤ 30s), Queue/Retry, graceful degradation.
* **Healthchecks:** App, DB, Ollama erreichbar?
* **Rate‑Limits:** Pro Benutzer und pro Route definieren.

**Logging (Beispiel in `config.py`):**

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
```

---

## 11) Backup & Recovery (Kurz)

* **Dev:** `pg_dump`/`psql` Skripte vorhanden.
* **Prod (Backlog Phase 10):** tägliche inkrementelle, wöchentliche Full‑Backups, 3‑2‑1‑Regel, Verschlüsselung, monatliche Restore‑Tests.

---

## 12) Datenschutz‑Stubs (Backlog Phase 10)

```python
def anonymize_student_data(student_id: str) -> None:
    """Ersetzt PII vor Archivierung. Muss RLS-konform sein."""
    ...

def export_user_data(user_id: str) -> bytes:
    """DSGVO-Datenexport. Enthält nur zulässige Felder."""
    ...

def delete_old_data() -> int:
    """Löscht abgelaufene Datensätze nach Policy. Gibt Anzahl zurück."""
    ...
```

**Checkliste Security/Privacy**

* [ ] Keine hartcodierten Credentials
* [ ] Parametrisierte Queries
* [ ] XSS‑Sorgfalt bei Free‑Text (Streamlit hilft, aber prüfen)
* [ ] CSRF‑Relevanz (Supabase‑Kontext) verstanden
* [ ] Audit‑Log für kritische Aktionen

---

## 13) Open‑Source‑Readiness

* **Lizenzen:** MIT/Apache‑kompatible Dependencies; LICENSE.md vorhanden.
* **Dokumente:** README vollständig; CONTRIBUTING, CODE\_OF\_CONDUCT; SECURITY‑Kontakt.
* **Secrets:** `.env.example` vollständig; keine echten Secrets im Repo.
* **CI‑Haken (Backlog):** Lint/Typecheck/Test/SCA (Vuln‑Scan).
* **Changelog:** Keep a Changelog‑Format, semver.

**README‑Snippet:**

```markdown
## Contributing
See CONTRIBUTING.md

## Security
Please report vulnerabilities to security@gustav-lms.org
```

---


## 14) Praktische Leitfäden

### 14.1 Mini‑RFC‑Vorlage (für Claude)

```
Problem:
Context & Constraints (Rollen, RLS, PII):
Proposed Change (kleinster inkrementeller Schritt):
Data Model / API Impact:
Security & Privacy (RLS/Policies/Secrets):
Testing (happy + 1 negative):
Rollback:
Alternativen (A/B) und warum verworfen:
```

### 14.2 Review‑Fragen (Claude → Maintainer)

* Erfüllt das den aktuell wichtigsten Use‑Case?
* Gibt es eine noch kleinere Lieferung?
* Wo liegt das größte Sicherheitsrisiko in diesem Vorschlag?
* Was messen/loggen wir, um Regressionen zu erkennen?

---

> **Merksatz:** *Kein Feature ohne RLS, kein Patch ohne Test, keine Änderung ohne kurze Erklärung.*


