# Lernmodul: Choice Cards für Abgabeart (Text | Upload)

Datum: 2025-11-01
Autor: GUSTAV Team (Lehrer/Entwickler)
Status: Plan (Contract- und Test-First), noch nicht implementiert

## Hintergrund & Ziel
Die bisherige UI bietet drei Optionen zum Einreichen von Lösungen: Text, Bild, Dokument. Für Lernende ist das zu fein granuliert. Wir vereinfachen auf zwei Modi:

- Text: Eingabefeld für Freitext.
- Upload: Datei-Upload (Bild JPG/PNG oder PDF), max. 10 MB.

Die Auswahl wird als Choice Cards (zwei klickbare Karten mit Icon, Titel, kurzer Erklärung) umgesetzt, gemäß docs/UI-UX-Leitfaden.md: klar, zugänglich, mobilfreundlich. Bildvorschau ist nicht nötig; ein Erfolgshinweis reicht. In der Historie ist der neueste Eintrag automatisch geöffnet (wie bisher).

Nicht-Ziele: Änderungen an API-Verträgen oder Datenbankschema (keine). Funktionale Upload-Flows bleiben wie im bestehenden MVP (Upload-Intents → PUT → Submission anlegen). OCR erfolgt später.

## User Story
Als Schülerin möchte ich bei jeder Aufgabe einfach wählen können, ob ich eine Textlösung schreibe oder eine Datei hochlade, damit ich ohne Verwirrung schnell die passende Abgabeform nutze. Nach dem Absenden möchte ich eine klare Bestätigung sehen und in der Verlaufsliste meinen neuesten Versuch direkt geöffnet finden.

## BDD-Szenarien (Given-When-Then)
1) Happy Path — Text
- Given eine freigeschaltete Aufgabe in einem Kurs, in dem ich Mitglied bin
- And die Choice Cards „Text“ und „Upload“ werden angezeigt, „Text“ ist vorausgewählt
- When ich Text eingebe und absende
- Then erhalte ich einen Erfolgshinweis (Banner)
- And auf der Folgeseite ist der neueste Verlaufseintrag automatisch geöffnet

2) Happy Path — Upload (PNG/JPEG/PDF ≤ 10 MB)
- Given die Auswahl „Upload“ ist aktiv
- When ich eine zulässige Datei auswähle und abschließe
- Then erhalte ich einen Erfolgshinweis
- And auf der Folgeseite ist der neueste Verlaufseintrag automatisch geöffnet

3) Edge — Zu große Datei (> 10 MB)
- Given „Upload“ ist aktiv
- When ich eine Datei > 10 MB auswähle
- Then wird die Abgabe mit verständlicher Fehlermeldung abgelehnt (keine Vorschau nötig)
- And das Formular bleibt im Upload-Modus

4) Edge — Nicht unterstützter Typ (z. B. GIF)
- Given „Upload“ ist aktiv
- When ich eine GIF-Datei auswähle
- Then wird die Abgabe mit Fehlermeldung abgelehnt
- And das Formular bleibt im Upload-Modus

5) Edge — Umschalten erhält Texteingabe
- Given ich habe Text in das Textfeld eingegeben
- When ich auf Upload und wieder auf Text umschalte
- Then ist meine Texteingabe weiterhin vorhanden (kein Datenverlust im UI)

6) Zugriff — Nicht-Mitglied oder Abschnitt nicht freigeschaltet
- Given ich sehe die Aufgabenliste, bin aber nicht Kursmitglied oder der Abschnitt ist nicht freigeschaltet
- Then werden Choice Cards nicht angezeigt (nur Aufgabenstammdaten), bzw. Formular ist nicht verfügbar

7) Barrierefreiheit — Tastatur- und Screenreader
- Given ich navigiere nur mit Tastatur
- When ich zwischen „Text“ und „Upload“ wechsle
- Then sind Fokus- und Auswahlzustände sichtbar und korrekt angesagt (fieldset/legend, Labels, ausreichender Kontrast)

8) Fallback — Kein JavaScript
- Given mein Browser führt kein JS aus
- When ich „Text“ oder „Upload“ auswähle
- Then werden die jeweils zugehörigen Formularfelder server- oder CSS-seitig korrekt sichtbar/unsichtbar geschaltet

## API-Vertrag (OpenAPI)
- Änderungen: keine. Die bestehenden Endpunkte bleiben unverändert:
  - Upload-Intents (POST …/upload-intents)
  - Submissions (POST …/submissions)
  - UI nutzt weiterhin diese APIs. Die UI-Form sendet `mode=text` oder startet den Upload-Intent-Flow bei `mode=upload`.
- Hinweis: Keine neue Migration erforderlich.

## Datenbank (Migration)
Keine Änderungen erforderlich.

## Tests (Pytest, Rot-Phase)
Wir ergänzen/erweitern die UI-Tests. Fokus: Markup der Choice Cards, korrekte Umschaltung, PRG und Historie.

Neue/angepasste Tests (nur Beispiele, konkrete Dateien können konsolidiert werden):
1) backend/tests/test_learning_ui_student_submissions.py
   - test_ui_renders_task_choice_cards
     - Erwartet zwei Choice Cards (Text/Upload) mit zugrunde liegendem `name="mode"` (Werte: `text`, `upload`).
     - Prüft `accept` am Datei-Input: `image/png,image/jpeg,application/pdf` und Hinweis „bis 10 MB“.
   - test_ui_submit_text_prg_and_history_shows_latest_open (weiterverwenden)
     - Unverändert grün halten; ggf. Selektoren für Banner/Details anpassen.
   - test_ui_toggle_preserves_text_input
     - Simuliert Umschalten (SSR: über zwei Post-Backs oder DOM-Check), prüft, dass eingegebener Text nicht verloren geht.

2) backend/tests/test_learning_upload_intents_behavior.py (bestehend)
   - Unverändert. Verifikation der erlaubten Typen und Größenlimit bleibt bestehen.

Rot-Kriterium: Die neuen Tests schlagen fehl, bis UI/Markup/CSS angepasst sind.

Erweiterte Testfälle (Robustheit/Security/A11y):
- UI ohne JS: „Text“ ist Default; Upload-Felder sind zugänglich und submitbar (reines SSR/CSS, kein JS nötig).
 - PRG-Determinismus: Nach erfolgreicher Abgabe ist ein bestimmter Versuch gezielt geöffnet (festgelegt: via `?open_attempt_id=...`).
- Fehlerbanner: Für >10 MB, nicht erlaubte Typen und Intent-/Upload-Fehler erscheint ein deutliches `role="alert"`-Banner; Formular bleibt im richtigen Modus.
- Doppel-Klick/Repeat: Kein doppelter Versuch entsteht; Submit-Button wird temporär disabled (UI), API bleibt idempotent.
- Lazy-Load-Historie: Fällt das Nachladen aus, erscheint eine freundliche Meldung (kein „ungelöst“-Fehlschluss).
- XSS-Escape: Inhalt einer Textabgabe mit Sonderzeichen/HTML wird sicher als Text angezeigt.
- Upload-Intent Guard: Nicht-Mitglieder bzw. nicht freigegebene Abschnitte erhalten 403/404 bereits beim Intent.
- Speicher-Key/Dateiname: Unerlaubte Muster/zu lange Namen werden abgelehnt (Server), UI zeigt klare Fehlermeldung.

## Implementierung (Green-Phase, minimal für Tests)
Komponenten/Dateien:
- backend/web/components/cards/task.py
  - Ersetzt die bisherige Radio-Gruppe durch zwei Choice Cards (Icon, Titel, Kurztext).
  - Beibehaltung semantischer Grundlagen: `fieldset/legend`, `input type="radio"` mit `name="mode"` und Werten `text|upload`.
  - Sichtumschaltung der Formularabschnitte per CSS (ohne JS erforderlich; progressive Enhancement möglich).

- backend/web/static/css/components/choice-cards.css (neu oder Integration in bestehende Utilities)
  - Card-Styling gemäß UI-UX-Leitfaden (Kontrast, Fokus-Ring, Hover, aktiver Zustand).
  - Touch-Ziele ≥ 44px; responsive 1–2 Spalten.

- backend/web/main.py (SSR-Route für die Einheiten-/Aufgabenansicht)
  - Aktualisierte Markup-Integration der Choice Cards.
  - Upload-Hinweise (Formbeschriftung „JPG/PNG/PDF, bis 10 MB“), `accept`-Attribut setzen.
  - PRG/Banner und „neuester Verlaufseintrag geöffnet“ unverändert beibehalten.

- optional: backend/web/static/js/learning_upload.js (nur Enhancement)
  - Keine Pflicht. Falls vorhanden, Sync Card-Click ↔ Radio-Checked; Fallback bleibt CSS/SSR.

Sicherheit & Datenschutz:
- Kein neuer Endpunkt, keine neuen Daten. CSRF/Same-Origin unverändert; RLS/ACL bleiben in Kraft.

Performance:
- Minimaler Einfluss (statisches Markup/CSS). Lazy-Load der Historie bleibt.

Ergänzende Architektur-/Code-Anpassungen (Wartbarkeit/Konsistenz):
- ChoiceCard-Komponente: Auslagern einer kleinen, wiederverwendbaren Komponente statt Inline-Markup in mehreren Stellen (z. B. `backend/web/components/choice_card.py` oder als Unterkomponente der Task-Card).
- Zentrale Upload-Konstanten: Erlaubte MIME-Typen und Max-Bytes in eine Quelle auslagern (z. B. `backend/web/config_uploads.py`) und in SSR/JS/Tests verwenden, um Inkonsistenzen zu vermeiden.
- Stabile Selektoren: Einführung robuster Klassen/`data-testid` (z. B. `.choice-card--text`, `.choice-card--upload`, `.submission-file-input`) für Tests statt fragiler Text-Matches.
- CSRF-Token: Ergänzung eines Synchronizer-Tokens in SSR-Formularen (UI), ergänzender Test.
- Früher Intent-Guard: Mitgliedschafts- und Sichtbarkeitsprüfung bereits im Upload-Intent-Handler (keine API-Änderung, nur frühere Prüfung).

## Refactor & Qualität (nach dem ersten Grün)
- UI-Konsolidierung: Wiederverwendung von Card/Focus/Spacing-Utilities aus dem Leitfaden.
- Zentralisierung von Textbausteinen (Upload-Hinweis) zur Mehrfachverwendung.
- A11y-Check: Kontrast, Label-Zuordnung, Screenreader-Texte.

Kritische Reflexion und Ergänzungen:
- Komplexität: SSR/CSS-Umschaltung ohne JS detailliert dokumentieren (IDs, :checked-Sibling-Strategie). Optional: Batch-API für Historien von mehreren Aufgaben als Follow-up zur N+1-Reduktion.
- Wartbarkeit: ChoiceCard als Komponente; zentrale Konstanten; klare Selektor-Strategie; prägnante Docstrings in SSR-Funktionen (Absicht, Parameter, Berechtigungen).
- Robustheit: No-JS-Default „Text“; deterministische PRG-Öffnung des neuesten Versuchs; sichtbare Fehlerbanner; Button-Disable gegen Doppelklick; freundlicher Fallback bei Historie-Fehlern.
- Sicherheit: Client-Hinweise (`accept`, Texte) sind nicht autoritativ; serverseitige Validierung bleibt maßgeblich. CSRF-Token ergänzen; Intent-Guard früh; XSS-sicheres Rendering; strikte Validierung von Speicher-Key/Dateinamen; Same-Origin & RLS beibehalten.

## Definition of Done (DoD)
- Tests: Alle neuen/angepassten UI-Tests grün, bestehende Upload/Contract-Tests weiterhin grün.
- UI: Choice Cards sichtbar, Tastaturbedienung möglich, Fokuszustände klar erkennbar.
- PRG: Erfolgshinweis sichtbar; Historie zeigt neuesten Eintrag geöffnet.
- Doku: CHANGELOG-Eintrag, Verweis und kurze Beschreibung in docs/UI-UX-Leitfaden.md (falls nötig), Kommentarblöcke in den relevanten Server-Render-Funktionen.

DoD — Erweiterung:
- A11y: Kontrast geprüft, `fieldset/legend` korrekt, Fokus via Tastatur sichtbar, Labels korrekt verknüpft.
- Security: CSRF-Token aktiv; Intent-Guard greift; XSS-Escaping nachweislich wirksam; Speicher-Key/Dateiname validiert; Same-Origin aktiv; RLS/ACL unverändert wirksam.
- Performance: Lazy-Load bestätigt; optionalen Batch-Ansatz als Follow-up dokumentiert (kein Blocker).

## Aufgaben & Reihenfolge (TDD)
1) Tests schreiben/aktualisieren (Rot): Choice Cards-Markup, Accept-Attribute, PRG/History unverändert.
2) Minimal-Implementierung (Grün): Markup in `task.py`, CSS-Basis, SSR-Integration in `main.py`.
3) Refactor: UI-Utilities nutzen, Barrierefreiheit feinjustieren, Kommentare ergänzen.
4) Doku: CHANGELOG aktualisieren; Plan-Dokument als erledigt markieren.

## Offene Punkte / Risiken
- Alte Selektoren in bestehenden Tests könnten auf Radio-Buttons abzielen; wir mappen die neue Struktur so, dass `input[name="mode"]` weiterhin vorhanden ist.
- Ohne JS-Umschaltung müssen wir CSS-Selektoren robust wählen (Sibling/ID-Bezug) und SSR-Defaults sinnvoll setzen (Text als Default).

Weitere Risiken/Beobachtungen:
- PRG-„open“-Zustand: Wenn mehrere Versuche dicht aufeinander folgen, muss die Ermittlung des gezielt zu öffnenden Eintrags deterministisch sein (ID-basiert > Zeitstempel).
- Upload-Fehler: Netzwerk-/Storage-Ausfälle sollten verständliche UI-Meldungen erzeugen, ohne Datenverlust im Formular.

## Rückfragen an Felix
- Icons/Text der Cards: „📝 Text“ und „⬆️ Upload“ ok? Kurzer Hilfetext „JPG/PNG/PDF · bis 10 MB“ ausreichend?
- Sollen Cards pro Aufgabe immer angezeigt werden, oder bei Aufgaben ohne Upload-Erlaubnis (falls später konfigurierbar) nur „Text“?
