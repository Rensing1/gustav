# Flexibel verschiebbare Spalten in der Schüler-Aufgabenansicht

## User Story

Als Schüler möchte ich den Trenner zwischen Aufgaben- und Materialkontext und der Bearbeitungsfläche mit Maus, Finger, Stift oder Tastatur verschieben, damit ich den verfügbaren Platz an die aktuelle Aufgabe anpassen kann.

Die Einstellung gilt für normale Aufgaben und KI-Dialoge. Sie wird nur im Browser und pro authentifiziertem Schüler gespeichert. API-Vertrag und Datenbank bleiben unverändert, weil weder fachliche Daten noch Serverkommunikation hinzukommen.

## BDD-Szenarien und automatisierte Nachweise

1. **Breite normale Aufgabenansicht**
   - **Given** eine normale Aufgabe ist in einer breiten Ansicht geöffnet, **when** der Schüler den Trenner mit Maus, Finger oder Stift verschiebt, **then** ändern sich beide Spalten unmittelbar und bleiben innerhalb von 35 bis 65 Prozent.
   - Nachweis: Komponenten-/Interaktionstest für Pointer Events und Grenzwerte; authentifizierter `@feature-acceptance`-Playwright-Test für den vollständigen Browser-Rundlauf.
2. **KI-Dialog**
   - **Given** ein KI-Dialog ist in einer breiten Ansicht geöffnet, **when** der Schüler den Trenner verschiebt, **then** verwendet der Dialog denselben Trenner und dieselbe gespeicherte Breite.
   - Nachweis: Komponententest des Dialog-Arbeitsbereichs und Browserprüfung des gemeinsamen Layoutvertrags.
3. **Dauerhafte Darstellungseinstellung**
   - **Given** der Schüler hat eine Spaltenbreite gewählt, **when** er eine andere Aufgabe öffnet oder die Seite neu lädt, **then** wird die Breite auf demselben Gerät wiederhergestellt.
   - Nachweis: Unit-Tests für den versionierten Local-Storage-Helfer und Playwright-Prüfung nach Reload.
4. **Tastaturbedienung**
   - **Given** der Trenner besitzt den Tastaturfokus, **when** Pfeil-, Pos1- oder Ende-Tasten verwendet werden, **then** verändert sich die Breite zugänglich in definierten Schritten innerhalb der Grenzen.
   - Nachweis: Komponenten-/Accessibility-Test.
5. **Kompakte Ansicht**
   - **Given** die Aufgabenansicht wird im Tablet-Hochformat oder auf einem Smartphone geöffnet, **when** die Oberfläche dargestellt wird, **then** bleibt die vorhandene Einspaltenansicht ohne Trenner und ohne horizontales Überlaufen erhalten.
   - Nachweis: Responsive Playwright-Prüfung bei 820 × 1180 und 390 × 844.
6. **Fehlerhafte Browserspeicherung**
   - **Given** die gespeicherte Einstellung ist ungültig oder Browser-Speicherung ist nicht verfügbar, **when** die Aufgabenansicht geladen wird, **then** verwendet sie die automatische Standardbreite und bleibt bedienbar.
   - Nachweis: Unit-Test des Speicher-Fallbacks.

## Implementierungsentwurf

- Ein wiederverwendbarer `LearnerTaskSplitDivider` verwendet Pointer Events und Pointer Capture für Maus, Touch und Stift. Der sichtbare Strich erhält ein mindestens 44 × 44 Pixel großes Interaktionsziel.
- Der Trenner wird als vertikaler ARIA-Separator mit Wertebereich 35 bis 65 ausgezeichnet. Pfeiltasten ändern den Wert um einen Prozentpunkt, Umschalt+Pfeil um fünf; Pos1 und Ende wählen die Grenzen.
- Normale Aufgaben und KI-Dialoge verwenden das Raster Kontext, Trenner, Bearbeitung. Unterhalb der bestehenden Containergrenze von 60 rem bleibt die Einspaltenansicht unverändert.
- Ohne gespeicherten Wert bleibt die bisherige automatische Kontextbreite `clamp(32rem, 44cqw, 38rem)` erhalten. Erst eine Interaktion erzeugt einen pro Schüler gespeicherten Prozentwert.
- Die versionierte Browserpräferenz enthält ausschließlich `taskColumnRatio`. Ungültige Werte werden verworfen; „Darstellung zurücksetzen“ löscht die Präferenz.
- Die bestehenden unabhängigen Scrollflächen, Aufgabenentwürfe und Berechtigungsprüfungen bleiben unverändert.

## Red-Green-Refactor und Abschluss

1. Speicher-, Komponenten- und Responsive-Verträge zunächst als fehlschlagende Tests formulieren.
2. Die minimale Zustands-, Trenner- und Rasterimplementierung ergänzen, bis die fokussierten Tests grün sind.
3. Gemeinsame Logik in den wiederverwendbaren Trenner refaktorieren und Kommentare auf nicht offensichtliche Pointer-/ARIA-Logik beschränken.
4. Fokussierte Vitest- und Playwright-Prüfungen ausführen; anschließend muss `make verify-feature` erfolgreich sein.
