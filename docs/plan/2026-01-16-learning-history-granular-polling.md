# Plan: Fix Scroll-Jump beim Auto-Refresh der Schüler-History (Option B: Granulare Updates pro Submission)

Datum: 2026-01-16  
Autor: Codex (mit Felix)  
Status: Plan (noch nicht implementiert)  
Bezug: `docs/tickets/learning-history-polling-scroll-jump-image-preview-2026-01-15.md`

## Kontext / Problem
- In der Schüler-UI wird das Aufgaben-History-Fragment während laufender Analyse (`analysis_status ∈ {pending, extracted}`) **alle 2 Sekunden** per HTMX neu geladen.
- Aktuell wird dabei der **gesamte History-Wrapper** per `hx-swap="outerHTML"` ersetzt (`backend/web/main.py` → `learning_task_history_fragment`).
- Für Upload-Abgaben wird im HTML ein **presigned Download-Link** als `img.src` gerendert; der Link ändert sich bei jedem Rendern. Dadurch lädt der Browser das Bild immer wieder neu.
- Ergebnis: wiederholtes Neuladen + Layout-Shifts → der Viewport „springt“ und die Seite wirkt wie „Reload“, obwohl nur ein Fragment ersetzt wird.

## Ziel(e)
1. Während `pending/extracted` sollen sich Status/Feedback weiterhin automatisch aktualisieren, **ohne** dass Preview/History-DOM ständig ersetzt wird.
2. Die Scroll-Position bleibt stabil; Lernende können während der Analyse weiter lesen/scrollen und andere Aufgaben bearbeiten.
3. Polling endet automatisch, sobald die Submission nicht mehr `pending/extracted` ist.
4. Keine Security-Regression (Artefakte bleiben privat; Zugriff bleibt an Auth/Membership gebunden).
5. Polling-Frequenz ist bewusst moderat (alle **10 Sekunden** reichen), um unnötige Last/„Unruhe“ zu vermeiden.
6. Nutzer-Zustand bleibt stabil: Was aufgeklappt war, bleibt aufgeklappt; was eingeklappt war, bleibt eingeklappt (Polling darf nichts „aufklappen“).
7. PDFs werden im Verlauf **inline** angezeigt (eingebettet) statt nur per „in neuem Tab öffnen“.
8. Bei Fehlern werden **Fehlercode + Abgabe-ID + Zeitstempel** angezeigt (damit Lehrkräfte/Admins konkret debuggen können).

## User Story
Als Schüler:in möchte ich nach dem Upload sehen, dass die Analyse läuft und später automatisch meine Rückmeldung erscheint, ohne dass die Seite ständig „springt“ oder das Bild neu geladen wird, damit ich währenddessen weiterarbeiten kann.

## BDD-Szenarien (Given–When–Then)
1) **Happy Path – Pending, kein Scroll-Jump**
- Given die neueste Abgabe ist `pending` und das History-Panel ist sichtbar  
- When die UI im Hintergrund pollt  
- Then bleibt die Scroll-Position stabil  
- And das Preview-Bild wird nicht alle 2s neu geladen.

2) **Zwischenstatus – Extracted**
- Given die neueste Abgabe ist `extracted`  
- When die UI pollt  
- Then wird weiterhin „Analyse läuft …“ angezeigt  
- And kein Full-Fragment-Replace der History findet statt.

3) **Polling endet bei Completed/Failed**
- Given die neueste Abgabe wechselt zu `completed` oder `failed`  
- When der nächste Poll läuft  
- Then stoppt das Polling automatisch  
- And die UI zeigt die fertige Rückmeldung (oder den Fehlerblock).

4) **User-Interaktion bleibt erhalten**
- Given der/die Schüler:in klappt einen bestimmten Versuch in `<details>` auf  
- When Status/Feedback aktualisiert werden  
- Then bleibt die Auswahl (welcher Versuch offen ist) erhalten (keine „Zuklapp“-Regression).

5) **User-Interaktion: zugeklappt bleibt zugeklappt**
- Given alle Versuche sind eingeklappt (kein `<details open>`)  
- When Status/Feedback aktualisiert werden  
- Then wird kein Versuch automatisch aufgeklappt (keine „Aufklapp“-Regression).

6) **Sicherheit**
- Given der/die Nutzer:in ist nicht als Schüler:in authentifiziert  
- When der Poll-/Fragment-Endpunkt aufgerufen wird  
- Then kommt 403 (oder Redirect gemäß bestehendem SSR-Verhalten)  
- And es werden keine privaten Artefakte ausgeliefert.

## Entscheidung
Wir wählen **Option B (granulare Updates pro Submission)**, weil sie am robustesten gegen Scroll-Jumps ist:
- Das Preview (`<img src=...>`) wird während des Pollings **nicht** mehr ersetzt → kein Reload/Flackern.
- Wir vermeiden auch beim Übergang zu `completed/failed` den „großen“ DOM-Replace eines kompletten History-Blocks (maximal kleine Teilblöcke ändern sich).
- Bereits geöffnete `<details>` bleiben offen, weil die `<details>`-Elemente nicht mehr regelmäßig ausgetauscht werden.

## Geklärte Anforderungen (mit Felix, 2026-01-17)
- **Stabiles Artefakt:** Upload (Bild/PDF) bleibt sichtbar ohne Flackern; Polling darf das Artefakt-HTML nicht ersetzen.
- **Reihenfolge der Inhalte:** Unter dem Artefakt erscheint (bei Text-Aufgaben) der extrahierte Text; darunter Rückmeldung und Auswertung (wie bisher).
- **Polling-Text:** Während der Verarbeitung bleibt der Hinweis „Analyse läuft …“ (aktueller Text) bestehen.
- **Polling-Frequenz:** Alle **10 Sekunden** reicht (statt 2s).
- **Polling läuft im Hintergrund:** Auch wenn der Schüler den Verlauf gerade nicht aktiv nutzt (z. B. gescrollt/alles zugeklappt), läuft die Aktualisierung weiter.
- **Open/Closed-State bleibt:** Was offen/zu ist, bleibt offen/zu; Polling darf nicht automatisch öffnen oder schließen.
- **PDF-Preview:** PDFs sollen im Verlauf **inline** angezeigt werden; optional zusätzlich „in neuem Tab öffnen“ als Fallback.
- **Fehleranzeige:** Bei Fehlern sollen **Fehlercode + Abgabe-ID + Zeitstempel** sichtbar sein (für Support/Admin).
- **„Neu laden“ nur bei Ladefehler:** Ein „Neu laden“-Button/Link soll nur sichtbar werden, wenn das Artefakt nicht lädt.

## Technischer Ansatz (Option B: Granulare Updates pro Submission)

### Leitidee
Statt den gesamten History-Wrapper alle 2s zu ersetzen, ersetzen wir während `pending/extracted` **nur die dynamischen Teilbereiche** einer Submission (extrahierter Text, Status/Hint, Feedback/Auswertung). Das Upload-Preview bleibt in einem stabilen DOM-Knoten unangetastet.

### Konkretes UI-Design (SSR + HTMX, robust)
1. **History-Wrapper bleibt stabil (kein Polling am Wrapper)**
   - `section#task-history-{task_id}.task-panel__history` wird weiterhin serverseitig gerendert, aber **ohne** `hx-trigger="every 2s"` + `hx-swap="outerHTML"` am Wrapper.
   - Die `<details>`-Einträge (und damit Scroll-/Open-State) bleiben stabil im DOM.

2. **Stabile Preview-/Artefakt-Zone pro Submission**
   - In jedem History-Eintrag wird das Upload-Preview in einen eigenen, stabilen Container gerendert, z. B.:
     - `div#submission-artifact-{submission_id}` enthält `<img class="submission-preview" ...>` oder den PDF-Link.
   - Dieser Container wird durch Polling **nie** getargetet/ersetzt.

3. **Dynamische Text-/Feedback-Zonen pro Submission**
   - Die Bereiche, die sich während der Analyse ändern können, erhalten stabile IDs, z. B.:
     - `div#submission-text-{submission_id}` (OCR-/extrahierter Text oder Platzhalter)
     - `div#submission-result-{submission_id}` (Spinner/Status, Feedback, Auswertung, Fehlerblock)
   - Nur diese Zonen werden aktualisiert.

4. **Ein Poller pro Aufgabe, der OOB-Updates für Teilblöcke liefert**
   - Im History-Wrapper gibt es ein (optisch neutrales) Poll-Element, das nur existiert, solange die **neueste** Submission `pending/extracted` ist, z. B.:
     - `div#task-history-poll-{task_id}`
     - `hx-get="/learning/courses/{course_id}/tasks/{task_id}/history/poll"`
     - `hx-trigger="every 10s"`
     - `hx-target="this" hx-swap="outerHTML"`
   - Der Poll-Endpunkt liefert **keine kompletten History-Einträge**, sondern nur:
     - sich selbst (mit oder ohne weiterem `hx-trigger`, um Polling zu stoppen), und
     - `hx-swap-oob`-Fragmente für `#submission-text-{id}` und `#submission-result-{id}` der betroffenen (idR neuesten) Submission.
   - Wichtig: Der Poller darf **keinen** `<details>`-State verändern (kein Auto-Open/Close).

5. **`open_attempt_id` / User-Interaktion**
   - Der bestehende Mechanismus (`gustav.js handleHistoryToggle`) kann bestehen bleiben (für initiales Rendering und Konsistenz).
   - Vorteil von Option B: Da `<details>` nicht mehr regelmäßig ersetzt werden, bleibt der Open-State im DOM typischerweise ohnehin stabil.

### Mehrere parallele Pending-Aufgaben (wichtiger Robustheitsfall)
- Wenn ein:e Schüler:in mehrere Uploads in verschiedenen Aufgaben einreicht, existiert pro Aufgabe maximal **ein** Poller (nur wenn die jeweilige History geladen/visible ist).
- Jeder Poller aktualisiert ausschließlich Teilblöcke dieser Aufgabe (keine Cross-Task-Swaps), wodurch die Seite auch bei mehreren parallelen Pending-States ruhig bleibt.

## API Contract / OpenAPI
- Keine Änderung an `api/openapi.yml` geplant, solange wir im SSR-Raum bleiben (HTML-Fragmente unter `/learning/...`).
- Falls wir stattdessen ein neues JSON-Polling unter `/api/...` einführen würden, müsste das contract-first in `api/openapi.yml` modelliert werden (nicht Teil dieses Plans).

## Datenbank / Migrationen
- Keine Schemaänderungen.

## Tests (TDD, „Red → Green → Refactor“)
Erweiterung der bestehenden UI-Tests, z. B. `backend/tests/test_learning_ui_auto_refresh.py`:
- **Red**: Test anpassen/neu schreiben:
  - History-Wrapper darf beim Pending-Status **nicht** mehr `hx-swap="outerHTML"` + `hx-trigger="every 2s"` tragen.
  - Stattdessen muss `#task-history-poll-{task_id}` die Polling-Attribute tragen.
  - Poll-Response darf **kein** `<img class="submission-preview"...>` enthalten (damit Preview nicht neu gerendert wird), sondern nur OOB-Updates für `#submission-text-*`/`#submission-result-*`.
  - Polling-Frequenz: `hx-trigger` ist `every 10s` (nicht 2s).
  - Open/Closed-State: Poll-Response darf keinen Versuch automatisch öffnen/schließen.
- **Green**: Minimal-Implementierung: neue DOM-Struktur + Poll-Endpunkt liefert OOB-Fragmente.
- **Refactor**: HTML-Struktur vereinfachen, IDs konsistent machen, doppelte Logik reduzieren.

Zusätzliche Assertions (UX-relevant):
- Pending: Poll-Response aktualisiert nur Teilblöcke (kein Preview-HTML, kein History-Wrapper-Replace).
- Completed: Polling-Attribute verschwinden; der finale Zustand wird über OOB-Updates der Teilblöcke sichtbar.

## Tasks / Umsetzungsschritte
- [ ] Plan umsetzen: neuen SSR-Endpunkt `/learning/courses/{course_id}/tasks/{task_id}/history/poll` ergänzen (liefert OOB-Teilupdates).
- [ ] History-HTML refactoren: Preview/Artefakt in `#submission-artifact-*` auslagern; dynamische Zonen `#submission-text-*` und `#submission-result-*` einführen.
- [ ] `learning_task_history_fragment`: Polling vom Wrapper entfernen; Poller `#task-history-poll-*` nur bei `pending/extracted` rendern.
- [ ] Poll-Endpunkt: Status prüfen, Teilblöcke für die betroffene Submission (idR neueste) serverseitig neu rendern und per `hx-swap-oob` zurückgeben; Poller stoppt sich selbst bei `completed/failed`.
- [ ] `gustav.js`: prüfen, ob `open_attempt_id` für Initialzustand reicht (bei Option B ist DOM stabiler; ggf. Vereinfachung möglich).
- [ ] PDF-Preview: PDFs inline anzeigen (eingebettet) + optional „in neuem Tab öffnen“.
- [ ] „Neu laden“-Fallback: Wenn Bild/PDF nicht lädt, sichtbaren „Neu laden“-Link anbieten (erzeugt neue Signed URL und aktualisiert nur Artefakt-Zone).
- [ ] Fehleranzeige: Fehlercode + Abgabe-ID + Zeitstempel im UI sichtbar machen.
- [ ] Tests erweitern/anpassen (Red/Green).
- [ ] Manuell verifizieren: Upload-Abgabe (Bild/PDF), scrollen während Pending, kein Jumping; Feedback erscheint nach Abschluss.

## Risiken / Offene Punkte
- **Signed-URL-Expiry vs. stabiles Preview:** Wenn das Preview nicht regelmäßig neu „frisch“ presigned wird, kann eine URL ablaufen, falls ein:e Schüler:in das Bild sehr spät erst lädt/neu lädt. Mögliche Mitigations (separater Follow-up):
  - `expires_in` moderat erhöhen (UX) vs. Security-Abwägung,
  - „Preview neu laden“-Link, der gezielt eine neue presigned URL anfordert (ohne Polling),
  - langfristig: stabiler App-Download-Endpunkt (Option 4 aus Ticket).
- **PDF inline + Fehlererkennung:** Ein eingebettetes PDF (z. B. per `<iframe>`) lässt Ladefehler nicht in allen Browsern zuverlässig erkennen (Cross-Origin/Viewer). Wir brauchen ggf. eine pragmatische UX:
  - immer „in neuem Tab öffnen“ als Fallback,
  - und ggf. „Neu laden“ als manuellen Link (auch wenn „nur bei Fehler“ technisch schwer sicher erkennbar ist).
- **Mehr Template-Struktur:** Option B erfordert saubere, stabile IDs pro Submission und klar getrennte Render-Funktionen (sonst wird es schwer testbar).
- **Mehrere parallele Pending-Tasks:** Pro Aufgabe maximal ein Poller; trotzdem entsteht bei vielen parallelen Pending-Aufgaben Netzlast. Optionaler Follow-up: Polling nur aktivieren, wenn die jeweilige History tatsächlich geladen/benutzt wird.
