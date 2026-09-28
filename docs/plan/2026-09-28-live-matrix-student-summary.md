# Implementierungsplan: kompakter Schülerstand in der Live-Matrix

Status: Abgeschlossen und technisch nachgewiesen.

## User Story

Als Lehrkraft möchte ich in jeder Schülerzeile sofort erkennen, wie viele reguläre Lernaufgaben abgegeben wurden und wie hoch die Durchschnittsbewertung ist, ohne die Namen oder einzelnen Aufgabenspalten zu verbreitern.

## BDD-Szenarien

1. Given reguläre Lern- und getrennte Übungsaufgaben, when die Lernmatrix erscheint, then zeigt `Stand` ausschließlich `abgegeben/gesamt` der Lernaufgaben. Nachweis: `live-matrix-view.test.ts` und `live-summary.spec.ts`.
2. Given bewertete native und H5P-Lernaufgaben, then zeigt `Stand` den Mittelwert auf der Zehnerskala mit höchstens einer Nachkommastelle; unbewertete Abgaben zählen als abgegeben, aber nicht zum Mittelwert. Nachweis: `live-matrix-view.test.ts`.
3. Given keine bewertete Lernaufgabe, then erscheint `Ø –` statt eines erfundenen Werts. Nachweis: `live-matrix-view.test.ts`, `LiveOverviewMatrix.test.ts` und `live-summary.spec.ts`.
4. Given eine breite oder schmale Ansicht, then bleiben `Stand` (88 px) und `Üben` (72 px) rechts fixiert; Schülernamen bleiben einzeilig und nur der beschriftete Tabellenbereich scrollt horizontal. Nachweis: `live-summary.spec.ts` sowie manuelle Browserprüfung bei 1600 × 900 und 390 × 844.
5. Given assistive Technik, then nennt die Zusammenfassung abgegebene, gesamte und bewertete Aufgaben sowie den Durchschnitt ausgeschrieben. Nachweis: `LiveOverviewMatrix.test.ts`.

## Umsetzung und Nachweise

- Die reine Ableitung liegt in `live-matrix-view.ts`; es gibt keine API- oder Datenbankänderung. H5P-Punkte werden wie die bestehende Zellfarbe auf 0–10 normalisiert.
- `LiveOverviewMatrix.svelte` erhält eine einzelne ruhige Spalte `Stand`: starke tabellarische Fortschrittszahl, kleinere Durchschnittszeile, nur der Durchschnittsakzent nutzt die bestehenden Bewertungsfarben. Keine Karte, kein zusätzlicher Rahmen und kein Text in der Namensspalte.
- Zuerst fehlschlagende View-Model- und Komponententests; danach minimale Implementierung und Refactoring.
- Gezielte Frontendtests und Typprüfung, anschließend echte Browserprüfung bei 1600 × 900 und 390 × 844. Kontrolliert werden 88-/72-px-Spalten, Zeilenhöhe, Innenabstände, Sticky-Verhalten, Tabellenüberlauf, Hell/Dunkel und Aufgaben-/Übungsumschaltung.
- Da sich kein öffentlicher Vertrag ändert, bleiben `api/openapi.yml` und Migrationen unverändert. Vor Fertigmeldung läuft `make verify-feature FEATURE=live-summary`; kein Push.

## Umsetzungsstand

- Red: View-Model- und Komponententests schlugen erwartungsgemäß wegen der fehlenden Lernzusammenfassung und Spalte fehl.
- Green: Die reine Zusammenfassung, Darstellung, zugängliche Beschriftung und die exakten Spaltenbreiten sind implementiert; 15 gezielte Tests sowie `npm run check` bestehen.
- Refactor: Die vorhandenen Bewertungsschwellen werden zentral wiederverwendet. Die neue Logik bleibt im frameworkunabhängigen View-Model und verändert weder API noch Datenhaltung.
- Browser: Der authentifizierte Chromium-Rundlauf misst `Stand` mit 88 px und `Üben` mit 72 px, aktualisiert den Stand ohne Lehrer-Neuladen von `0/3 · Ø –` auf `1/3 · Ø 8` und bestätigt auf 390 × 844 fehlenden Seitenüberlauf. Die Screenshots bei 1600 × 900 sowie mobil in Hell und Dunkel wurden visuell geprüft; Kennzahlen, Zeilenrhythmus und Detailbereich bleiben kollisionsfrei.
- Abschluss: `make verify-feature FEATURE=live-summary` bestand auf dem finalen Stand mit 3.042 Backendtests, 802 Frontendtests, Svelte-Typprüfung, Produktionsbuild, H5P-Sidecar-Tests und dem zugeordneten `@feature-acceptance`-Rundlauf. Die 33 Backend-Skips sind erwartete, im Harness deklarierte Auslassungen.
