# Robustes Scrollen am Spaltentrenner der Schüler-Aufgabenansicht

## User Story

Als Schüler möchte ich die Kontext- und Bearbeitungsspalte unabhängig voneinander scrollen können, auch wenn eine Berührung oder Stiftgeste nahe am Spaltentrenner beginnt. Gleichzeitig möchte ich die Spaltenbreite mit einer bewussten horizontalen Geste, mit der Maus oder mit der Tastatur weiterhin anpassen können.

Die Änderung betrifft ausschließlich das Eingabeverhalten und die Trefferflächen des bestehenden Spaltentrenners. API-Vertrag, Datenbank, gespeichertes Spaltenverhältnis und Berechtigungen bleiben unverändert.

## BDD-Szenarien und automatisierte Nachweise

1. **Vertikales Scrollen mit Touch oder Stift**
   - **Given** eine breite Aufgabenansicht mit unabhängig scrollbaren Spalten ist geöffnet, **when** eine vertikale Touch- oder Stiftbewegung nahe am Trenner beginnt, **then** bleibt die Spaltenbreite unverändert und der Browser kann die betreffende Spalte nativ scrollen.
   - Nachweis: Komponententest für die Gestenerkennung und authentifizierter `@feature-acceptance`-Playwright-Test mit langen Inhalten.
2. **Bewusste horizontale Größenänderung**
   - **Given** der sichtbare mittlere Griff wird mit Touch oder Stift berührt, **when** die horizontale Bewegung mindestens acht Pixel beträgt und stärker als die vertikale Bewegung ist, **then** beginnt die Vorschau der Spaltenbreite und der fertige Wert wird beim Loslassen gespeichert.
   - Nachweis: Komponenten- und Browserinteraktionstest.
3. **Mausbedienung**
   - **Given** der Trenner wird mit der primären Maustaste gezogen, **when** sich der Zeiger horizontal bewegt, **then** wird die Breite ohne Gestenverzögerung innerhalb von 35 bis 65 Prozent angepasst und beim Loslassen gespeichert.
   - Nachweis: Komponententest und bestehender Responsive-Browsertest.
4. **Tastatur und Grenzwerte**
   - **Given** der Trenner besitzt den Tastaturfokus, **when** Pfeiltasten, Umschalt+Pfeiltasten, Pos1 oder Ende verwendet werden, **then** ändert sich die Breite in den vorgesehenen Schritten innerhalb der bestehenden Grenzen.
   - Nachweis: Komponenten-/Accessibility-Test.
5. **Abgebrochene Geste**
   - **Given** eine mögliche oder aktive Touch-/Stiftgeste läuft, **when** der Browser `pointercancel` oder verlorenen Pointer-Capture meldet, **then** bleibt kein aktiver Drag-Zustand zurück und ohne abgeschlossenen Drag wird kein Wert gespeichert.
   - Nachweis: Komponententest.
6. **Unabhängige Scrollflächen**
   - **Given** beide Spalten enthalten mehr Inhalt als ihre sichtbare Höhe, **when** der Schüler links beziehungsweise rechts mit Rad oder Touch scrollt, **then** bewegt sich nur die jeweils angesprochene Spalte.
   - Nachweis: authentifizierter `@feature-acceptance`-Playwright-Test in einem Touch-fähigen Browserkontext.

## Implementierungsentwurf

- Touch und Stift starten zunächst nur einen Gestenkandidaten. Erst eine horizontal dominierende Bewegung ab acht Pixeln aktiviert den Drag, nimmt Pointer-Capture und verhindert die Browserstandardaktion.
- Eine vertikal dominierende Bewegung verwirft den Kandidaten. `touch-action: pan-y` lässt das native vertikale Scrollen zu.
- Die Maus startet die Größenänderung weiterhin unmittelbar mit der primären Taste.
- Der vollflächige 44-Pixel-Überhang entfällt. Präzise Zeiger erhalten einen zwölf Pixel breiten, zentrierten Trefferbereich; grobe Zeiger bedienen einen 44 × 44 Pixel großen Griff in der Mitte.
- Abbruch- und Capture-Verlust räumen den Interaktionszustand auf. Nur ein tatsächlich gestarteter und regulär beendeter Drag wird gespeichert.
- Bestehende ARIA-Eigenschaften, Tastatursteuerung, Grenzwerte und Local-Storage-Struktur bleiben kompatibel.

## Red-Green-Refactor und Abnahme

1. Komponenten- und Browserverträge zuerst fehlschlagend ergänzen.
2. Die minimale Gestenerkennung und die neuen Trefferflächen implementieren.
3. Zustandsübergänge vereinfachen und nicht offensichtliche Pointer-Logik auf Englisch kommentieren.
4. Zunächst gezielte Vitest- und Playwright-Prüfungen ausführen und die Darstellung im vorhandenen Schüler-Arbeitsbereich visuell kontrollieren.
5. Nach visueller Freigabe auf einem Windows-11-Convertible prüfen und anschließend `make verify-feature` ausführen. Erst nach diesem Nachweis committen.
