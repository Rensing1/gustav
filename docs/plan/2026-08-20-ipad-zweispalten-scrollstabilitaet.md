# Stabiles Scrollen in der iPad-Zwei-Spalten-Ansicht

**Status:** umgesetzt
**Datum:** 20. August 2026

## Ausgangslage

Die drei internen Scrollflächen spiegeln bei jedem Scrollereignis ihre Position in reaktiven Seitenzustand und Browserspeicher. Gleichzeitig setzen reaktive Effekte `scrollTop` wieder aus diesem Zustand. Bei WebKit-Momentum-Scrollen können verzögert verarbeitete Werte dadurch eine noch laufende Touchbewegung zurücksetzen. Das erklärt Zurückspringen und schwer erreichbare obere oder untere Enden.

## User Story

Als Schüler auf einem iPad möchte ich Aufgabenstellung und Bearbeitung in der Zwei-Spalten-Ansicht unabhängig und flüssig bis ganz oben und unten scrollen können, ohne dass die Oberfläche zu einer älteren Position zurückspringt.

## BDD-Szenarien und Testzuordnung

1. **Arbeitsbereich bis zum Ende scrollen**
   - Given eine lange Aufgabe bei 1024 px Breite und Touch-Eingabe
   - When die rechte Spalte bis unten und wieder nach oben gescrollt wird
   - Then bleibt jede erreichte Position stabil und beide Enden sind erreichbar
   - Nachweis: `@feature-acceptance`-Playwright-Test mit Touch-Kontext und numerischen Scrollprüfungen
2. **Kontextspalte unabhängig scrollen**
   - Given lange Materialien links und ein Editor rechts
   - When nur die linke Spalte gescrollt wird
   - Then verändert sich die rechte Position nicht
   - Nachweis: Browser-Geometrie-/Scrolltest
3. **Kein reaktives Zurückschreiben während Momentum-Scrollen**
   - Given eine Scrollfläche ist bereits montiert
   - When fortlaufende Scrollwerte gemeldet werden
   - Then schreibt die Komponente keine älteren Prop-Werte in `scrollTop` zurück
   - Nachweis: Komponenten-/Hilfslogiktest
4. **Wiederherstellung nach Navigation**
   - Given eine gespeicherte Position und ein neu geöffneter Aufgabenarbeitsraum
   - When die Scrollfläche neu montiert wird
   - Then wird die gespeicherte Position einmalig wiederhergestellt
   - Nachweis: Komponententest
5. **Einspaltenansicht**
   - Given 820 px oder Smartphonebreite
   - When zwischen Aufgabe und Materialien gewechselt wird
   - Then bleibt die jeweilige Position erhalten und es entsteht kein verschachteltes unbedienbares Scrollen
   - Nachweis: Browser-Test

## API- und Datenbankbewertung

Die Änderung ist rein clientseitig. OpenAPI und Datenbankschema bleiben unverändert; eine Migration ist nicht erforderlich.

## Red–Green–Refactor

1. Rote Hilfs-/Komponententests für einmalige Wiederherstellung und fehlendes Zurückschreiben erstellen.
2. Reaktive `scrollTop`-Synchronisation durch einmalige, schlüsselgebundene Wiederherstellung ersetzen.
3. Zustands- und Browserspeicheraktualisierung takten, ohne die letzte Position zu verlieren.
4. Touch-Scroll, Spaltenunabhängigkeit, Viewport-Fit und visuelle Stabilität prüfen.
5. Gezielte Tests, authentifizierte Feature-Abnahme und `make verify-feature` ausführen.

## Umsetzung und Ergebnis

- Materialien, Bearbeitungsbereich und Dokumentleser übernehmen ihre gespeicherte Position nur noch einmal, wenn die jeweilige DOM-Scrollfläche neu eingehängt wird.
- Später eintreffende reaktive Zustandswerte schreiben dadurch während eines laufenden WebKit-Momentum-Scrolls keine ältere Position mehr zurück.
- Die bestehende unabhängige Speicherung der drei Positionen bleibt erhalten; Navigation und erneutes Einhängen stellen weiterhin den zuletzt gespeicherten Wert wieder her.
- Der authentifizierte iPad-nahe Browsertest erzeugt deterministisch lange Scrollinhalte, erreicht beide Enden und prüft, dass die jeweils andere Spalte unverändert bleibt.

## Verifikation

- Komponentenregression: 8 bestanden
- Svelte-Diagnostik: 0 Fehler, 0 Warnungen
- Gezielter authentifizierter iPad-naher Browsertest: 1 bestanden
- `make verify-feature`: 2431 Backendtests bestanden, 78 übersprungen; 585 Frontendtests bestanden; 62 H5P-Tests bestanden; 22 Feature-Acceptance-Browsertests bestanden
