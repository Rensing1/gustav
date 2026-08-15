# Implementierungsplan: Responsive Schülerarbeitsflächen und Practice-Layout

**Status:** freigegeben
**Freigabedatum:** 15. August 2026

## User Story

Als Lernender möchte ich GUSTAV auf Desktop, Tablet und Smartphone ohne ungenutzte Restspalten oder horizontales Scrollen verwenden, während Texte und Formulare weiterhin angenehm lesbar bleiben.

## Entscheidungen

- Arbeitsfläche und Lesebreite werden getrennt. Der Seitenkörper nutzt seine gesamte Hülle; Text- und Formularmaße werden lokal begrenzt.
- Der interne Layoutvertrag verwendet `compact` (42 rem), `standard` (80 rem), `wide` (112 rem) und `canvas` (144 rem).
- Practice-Auswahl und Practice-Sitzung wechseln ab 64 rem Containerbreite in ein zweispaltiges Layout. Tablet und Mobilansicht bleiben einspaltig und füllen den verfügbaren Raum.
- Lernraum, Kursübersicht, Lernarchiv und Lerneinheit verwenden die Standardarbeitsfläche. Profil und Kummerkasten bleiben bewusst kompakt.
- URL-Muster und überlappende Wide-Booleans bestimmen nicht länger die Breite einer Route.
- API, Datenbank, Scheduler, Practice-Fachlogik, Authoring und CLI bleiben unverändert.

Dieser Plan ergänzt den [Practice-Implementierungsplan](./2026-08-03-uebungs-und-wiederholungsaufgaben.md) um den querschnittlichen responsiven Layoutvertrag.

## BDD-Szenarien und Testzuordnung

1. **Standardarbeitsfläche auf Desktop**

   Given eine Standard-Schülerseite, when sie auf Desktop dargestellt wird, then teilen sich Header und Inhalt eine zentrierte Arbeitsfläche bis 80 rem.

   Nachweis: Layout-Contract-Test und authentifizierter Playwright-Breitentest.

2. **Practice auf Tablet**

   Given eine Tabletbreite unter 64 rem, when Auswahl oder Sitzung angezeigt wird, then ist die Darstellung einspaltig, füllt die verfügbare Breite und erzeugt kein horizontales Scrollen.

   Nachweis: Komponentenvertrag, visuelle Regression und Playwright-Breitentest.

3. **Practice auf Desktop**

   Given mindestens 64 rem Containerbreite, when Auswahl oder Sitzung angezeigt wird, then stehen Hauptinhalt und Konfiguration beziehungsweise Kontextleiste zweispaltig.

   Nachweis: CSS-Contract-Test und visuelle Regression.

4. **Bewusst kompakte Seiten**

   Given Profil oder Kummerkasten, when der neue Shell-Vertrag greift, then bleibt die Seite auf 42 rem begrenzt und zentriert.

   Nachweis: Route- und Playwright-Breitentest.

5. **Bestehende Spezialarbeitsflächen**

   Given eine Wide-, Canvas- oder Auth-Seite, when die Shell umgestellt wird, then behält sie ihre vorgesehene Maximalbreite und ihr bisheriges Verhalten.

   Nachweis: Layout-Contract- und bestehende visuelle Tests.

6. **Practice-Fachverhalten**

   Given eine native oder H5P-Sitzung, when Aufgabe, Auswertung, Rückmeldung oder Abschluss dargestellt werden, then bleiben Polling, Reload-Persistenz und Informationsschutz unverändert.

   Nachweis: bestehender und erweiterter `@feature-acceptance`-Test.

## Umsetzung

1. Layouttyp und Design-Tokens testgetrieben einführen, alle Routen zuordnen und die strukturellen Shell-Regeln an einer Stelle bündeln.
2. Practice-Auswahl mit Container Query, breiter Themenliste und eigener Konfigurationsspalte umsetzen.
3. Practice-Sitzung mit Hauptbereich und Kontextleiste sowie adaptivem Abschlussraster umsetzen.
4. Übrige Schülerseiten auditieren, Listen nur im Lernkontext adaptiv verbreitern und kompakte Seiten ausdrücklich kennzeichnen.
5. Bei 390 px, 1024 px und Desktopbreite live mit den vorhandenen Dev-Accounts prüfen; danach `make verify-feature` ausführen.

## Auslieferung

- Umsetzung direkt auf dem lokalen `master` in logisch getrennten grünen Commits.
- Kein Push, Pull Request oder Deployment ohne gesonderten Auftrag.
