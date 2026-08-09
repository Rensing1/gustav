# Einheitlicher Arbeitsraum für Entwurf und Rückmeldung

## User Story

Als Schüler möchte ich meinen bisherigen Entwurf weiterbearbeiten und Rückmeldung, Auswertung sowie die zugehörige Abgabe auf demselben Bildschirm erreichen, damit ich Hinweise unmittelbar in eine verbesserte Fassung umsetzen kann.

## BDD-Szenarien

1. **Neue Textaufgabe**
   - Given es gibt noch keine Abgabe
   - When der Schüler `Aufgabe beginnen` auswählt
   - Then erscheint ein leerer Editor ohne Ergebnisbereiche.

2. **Entwurf fortsetzen**
   - Given es gibt eine gespeicherte Textabgabe
   - When der Schüler `Entwurf weiterbearbeiten` auswählt
   - Then enthält der Editor zuerst einen vorhandenen tab-lokalen Entwurf, andernfalls den Text der neuesten Abgabe
   - And vorhandene Rückmeldung, Auswertung und die zugehörige Abgabe sind als Offenlegungen erreichbar.

3. **Rückmeldung einholen**
   - Given der Editor enthält einen Entwurf
   - When der Schüler Rückmeldung anfordert
   - Then bleibt derselbe Aufgabenarbeitsraum sichtbar
   - And Editor und Abgabeaktionen sind während der Verarbeitung gesperrt
   - And nach Abschluss öffnet sich die Rückmeldung inline, ohne den Tastaturfokus zu verschieben.

4. **Entwurf überarbeiten**
   - Given eine fertige Rückmeldung liegt vor
   - When der Schüler die sichtbare Fassung verändert
   - Then bleibt die Rückmeldung erreichbar
   - And `Endgültig abgeben` ist bis zur nächsten Rückmeldung deaktiviert.

5. **Dateiabgabe fortsetzen**
   - Given die letzte Abgabe ist eine Datei
   - When der Schüler den Entwurf weiterbearbeitet
   - Then wird die gespeicherte Datei als aktuelles Dateiobjekt angezeigt
   - And der Browser versucht nicht, ein natives Dateifeld vorzufüllen
   - And eine neue Datei kann bewusst ausgewählt werden.

6. **Optionale Auswertung**
   - Given eine Abgabe besitzt Rückmeldung, aber keine Kriterienergebnisse
   - Then wird keine Offenlegung `Auswertung` gerendert.

7. **Fehler und Direktlink**
   - Given die Rückmeldung schlägt fehl
   - Then bleibt der Entwurf erhalten und der Editor wird wieder freigegeben
   - And der Fehler erscheint über `StatusMessage`.
   - Given ein bestehender Link enthält `panel=result`
   - When der Link geöffnet wird
   - Then erscheint der einheitliche Arbeitsraum mit geöffneter Offenlegung `Meine Abgabe`.

8. **Rückkehr zum Modulgraphen**
   - Given ein Entwurf wird noch bearbeitet
   - When der Schüler zum Lernpfad wechselt
   - Then wird im Modulgraphen keine tab-lokale Rückkehrhilfe angezeigt
   - And der Entwurf bleibt über seinen eigenen tab-lokalen Entwurfsspeicher erhalten
   - And die Aufgabe kann über ihre reguläre Aufgabenzeile wieder geöffnet werden.
   - Given die Aufgabe wurde endgültig abgegeben
   - When der Schüler zum Lernpfad wechselt
   - Then endet der aktive Arbeitszustand und es wird keine Rückkehrhilfe gerendert
   - And ein weiterer Versuch beginnt ausschließlich über `Erneut bearbeiten` in der Aufgabenzeile.

9. **Veralteter Tab-Zustand**
   - Given ein älterer Tab-Zustand enthält noch einen aktiven Aufgabenzeiger
   - When der Schüler den Modulgraphen direkt oder nach einem Neuladen öffnet
   - Then wird der Aufgabenzeiger verworfen
   - And es gibt keinen Rücksprung zu einer nicht geladenen oder nicht mehr verfügbaren Aufgabe.

## Umsetzung

- Die separate Ergebnisfläche in `LearningTaskCard` wird durch eine gemeinsame Disclosure-Familie oberhalb der weiterhin montierten Text- oder Datei-Bearbeitung ersetzt.
- Die Offenlegungen heißen in dieser Reihenfolge `Rückmeldung`, optional `Auswertung` und `Meine Abgabe`. Leere fachliche Bereiche werden nicht gerendert.
- Ein gerade fertiggestellter Feedbacklauf öffnet `Rückmeldung`; ein bestehender `panel=result`-Einstieg öffnet `Meine Abgabe`; beim normalen Wiedereinstieg bleiben die Offenlegungen geschlossen.
- Textentwürfe verwenden den vorhandenen schüler- und tabbezogenen Session-Speicher. Fehlt dort ein Wert, dient die neueste Abgabe als Ausgangsfassung. Dateien bleiben ausschließlich serverseitige Artefakte und werden über die bestehende Vorschau dargestellt.
- Während eines Feedbacklaufs erhalten Markdown-Editor und Dateiauswahl einen echten deaktivierten Zustand. Danach sind sie wieder bearbeitbar.
- `Endgültig abgeben` ist nur aktiv, wenn die sichtbare Fassung exakt der letzten erfolgreich rückgemeldeten Abgabe entspricht. Nach einer Änderung erklärt ein kurzer Hinweis den notwendigen nächsten Feedbacklauf.
- Der Modulgraph hält grundsätzlich keine Aufgabe als aktiven Arbeitsraum. Beim Wechsel zum Lernpfad sowie beim Wiederherstellen einer Graph-URL wird `activeTask` beendet. Damit kann ein veralteter tab-lokaler Zeiger weder eine irreführende Meldung noch einen Rückweg zu einer nicht geladenen Aufgabe erzeugen. Textentwürfe bleiben unabhängig davon im vorhandenen aufgabenbezogenen Tab-Speicher erhalten und werden beim regulären Öffnen der Aufgabe wiederhergestellt.
- Bestehende API-Endpunkte, OpenAPI-Vertrag und Datenbankschema bleiben unverändert.

## Testzuordnung

- `LearningTaskCard.test.ts`: Szenarien 1 bis 6 sowie Fehlerzustand aus Szenario 7.
- `MarkdownWysiwygEditor.test.ts` und `tiptap-markdown-editor.test.ts`: echter deaktivierter Zustand für Toolbar, Editoroberfläche und Fallback.
- `learner-navigation.spec.ts`: authentifizierter vollständiger Textablauf einschließlich inline erscheinender Rückmeldung und Überarbeitung.
- Datei-Akzeptanztest mit echter Testdatei: Wiederaufnahme, Austausch und erneute Rückmeldung.
- `page.server.test.ts` beziehungsweise Navigationstests: kompatibler `panel=result`-Direktlink.
- `learner-workspace-state.test.ts`, `page-contract.test.ts` und `learner-navigation.spec.ts`: Der Graph verwirft aktive und veraltete Aufgabenzeiger, zeigt keine Rückkehrhilfe und ein Entwurf wird beim regulären Wiederöffnen der Aufgabe wiederhergestellt.

## Verifikation

- Gezielte Frontend-Komponententests im Red-Green-Refactor-Ablauf.
- Visuelle Prüfung in Light und Dark sowie auf Desktop und Smartphone.
- Vor Fertigmeldung muss `make verify-feature` erfolgreich sein.
