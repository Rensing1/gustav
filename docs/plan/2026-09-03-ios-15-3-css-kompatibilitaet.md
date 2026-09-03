# Gezielter CSS-Fix für iPadOS 15.3.1

## Ausgangslage

Der globale CSS-Einstiegspunkt ordnet GUSTAVs Styles mit Cascade Layers. Der Produktionsbuild übernimmt diese Struktur und legt fast alle Regeln in `@layer`-Blöcke. Safari auf iPadOS 15.3.1 unterstützt Cascade Layers noch nicht und verwirft deshalb die Blöcke vollständig. Das serverseitig gerenderte HTML bleibt sichtbar, wirkt aber ungestaltet.

Vites bestehendes JavaScript-Ziel umfasst Safari 14. Dieser Fix verändert daher weder das JavaScript-Bundle noch den fachlichen Lernablauf. Neuere, nicht kritische CSS-Funktionen dürfen auf iPadOS 15.3.1 weiterhin kontrolliert degradieren; Ziel ist die Beseitigung des vollständigen Stylesheet-Ausfalls.

## User Story

Als Schülerin mit iPadOS 15.3.1 möchte ich die reguläre GUSTAV-Oberfläche gestaltet und bedienbar laden können, damit ich ohne gesonderte Ersatzansicht am Unterricht teilnehmen kann.

## BDD-Szenarien und automatisierte Nachweise

1. **Inkompatibler Build wird abgelehnt**

   Given ein erzeugtes Client-Stylesheet enthält eine Cascade Layer, when der CSS-Kompatibilitätschecker läuft, then meldet er die betroffene Datei und beendet sich mit einem Fehler.

   Automatisierter Nachweis: Node-Unit-Test des Checkers mit einem `@layer`-Fixture.

2. **Kompatibler Build wird akzeptiert**

   Given erzeugte Client-Stylesheets enthalten gewöhnliche Regeln und andere CSS-At-Rules, aber keine Cascade Layers, when der Checker läuft, then akzeptiert er den Build.

   Automatisierter Nachweis: Node-Unit-Test mit kompatiblen Fixtures und Integration des Checkers in den Produktionsbuild.

3. **Authentifizierter Lernraum bleibt gestaltet**

   Given ein authentifizierter Lernender öffnet eine tiefe Lernraumseite im iPad-nahen WebKit-Projekt, when GUSTAV alle Stylesheets lädt, then antworten die CSS-Assets erfolgreich, enthalten keine `@layer`-Regeln und repräsentative Shell-, Navigations- und Workspace-Elemente besitzen berechnete GUSTAV-Styles.

   Automatisierter Nachweis: `@feature-acceptance`-Playwright-Spec `ios-15-3-css-compatibility.spec.ts` gegen den freigegebenen lokalen Stack.

4. **Aktuelle Browser behalten das Design**

   Given ein aktueller unterstützter Browser, when er das kompatible CSS lädt, then bleibt die aktuelle Gestaltung unverändert.

   Automatisierter Nachweis: bestehende visuelle Smoke-Tests.

5. **Nicht authentifizierte Zugriffe bleiben geschützt**

   Given keine gültige Sitzung, when eine geschützte Lernraumseite aufgerufen wird, then gilt weiterhin der bestehende Login- und Berechtigungsablauf.

   Automatisierter Nachweis: bestehende Auth- und Feature-Acceptance-Tests; der Fix ändert keine Route oder Authentifizierungslogik.

## Contract- und Datenbankentscheidung

Der Fix verändert ausschließlich den Frontend-Build. Es gibt keine neue oder geänderte HTTP-Schnittstelle, keinen Request Body und keine fachliche Datenstruktur. Deshalb bleiben `api/openapi.yml`, Supabase/PostgreSQL-Schema, Migrationen und RLS-Policies unverändert.

## Umsetzung nach Red–Green–Refactor

1. Red: Einen kleinen, getrennt testbaren CSS-Kompatibilitätschecker erstellen, der erzeugtes CSS mit PostCSS parst und `@layer`-Regeln findet. Den Checker in das bestehende Build-Gate einhängen; der aktuelle Build muss damit fehlschlagen.
2. Green: Die Layer-Deklaration und die `layer(...)`-Zusätze am einzigen globalen CSS-Einstieg entfernen. Die bestehende Stylesheet-Reihenfolge bleibt als gewöhnliche Importreihenfolge erhalten.
3. Refactor: Einen zunächst erprobten PostCSS-Übersetzer wieder entfernen. Er verlangt laut eigener Dokumentation ein einziges vollständiges CSS-Bündel; Svelte erzeugt jedoch zusätzlich seitenabhängige CSS-Dateien. Normale Imports sind kleiner, leichter verständlich und vermeiden mögliche Prioritätsverschiebungen gegenüber komponentenlokalen Regeln.
4. Dokumentation: In `docs/DESIGN.md` die verbindliche Importreihenfolge und das Verbot von Cascade Layers im globalen beziehungsweise erzeugten CSS erklären.

## Abschluss und Grenzen

- Vor Browserprüfungen: `make local-ca-status`.
- Verbindliches Feature-Gate: `make verify-feature FEATURE=ios-15-3-css-compatibility`.
- Zusätzlicher visueller Nachweis: `make test-visual-smoke`.
- Manueller Smoke-Test auf dem betroffenen iPadOS-15.3.1-Gerät nach einem vollständigen Neuladen beziehungsweise Löschen der Website-Daten.
- `color-mix()`, Container Queries und andere jüngere CSS-Komfortfunktionen sind nicht Bestandteil dieses gezielten Fixes. Ihre fehlende Unterstützung darf Details vereinfachen, aber nicht mehr das gesamte Stylesheet entfernen.
- Eine Betriebssystemaktualisierung bleibt aus Sicherheitsgründen dringend empfohlen; Browserkompatibilität ersetzt keine Sicherheitsupdates.

## Umsetzungsnachweis

- `make local-ca-status`: Die aktuelle lokale Caddy-CA ist in System, Chromium/Codex und Firefox als vertrauenswürdig registriert.
- Red: Der unveränderte Layer-Build wurde vom neuen parserbasierten Build-Gate mit den betroffenen Layer-Namen abgelehnt.
- Green: Der Produktionsbuild enthält keine Cascade Layers mehr; die Haupt-CSS bleibt mit rund 37 KiB komprimiert praktisch gleich groß.
- `make verify-feature FEATURE=ios-15-3-css-compatibility`: erfolgreich. Darin bestanden 2.556 Backendtests, 653 Frontendtests, sieben Tooling-Tests sowie der authentifizierte Feature-Acceptance-Lauf in Chromium und iPad-WebKit. Die erzeugten Testdaten wurden vollständig bereinigt.
- `make test-visual-smoke`: Der aktuelle Stand besitzt zehn bereits unabhängige visuelle Altfehler. Die gespeicherten Referenzen vom 8. August enthalten den am 9. August ergänzten Kummerkasten-Link noch nicht, ältere Graph-Referenzen bilden spätere Layoutänderungen nicht ab, und das UI-Labor stellt das vom Test erwartete Dialogelement nicht mehr bereit. Die Pixelabweichungen waren vor und nach dem abschließenden Vereinfachungsrefactor identisch; die fremden Baselines wurden in diesem Fix bewusst nicht verändert.
- Ausstehender externer Nachweis: vollständiges Neuladen beziehungsweise Löschen der Website-Daten auf dem konkret betroffenen iPadOS-15.3.1-Gerät.
