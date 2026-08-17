# Implementierungsplan: Zweispaltige Aufgabenbearbeitung auf iPads im Querformat

**Status:** zur Umsetzung freigegeben  
**Datum:** 17. August 2026

## Ausgangslage

Die Schülerarbeitsfläche wechselt derzeit erst ab einer Containerbreite von 72 rem in die zweispaltige Ansicht. Dadurch erhalten handelsübliche iPads selbst im Querformat die kompakte Einspaltenansicht mit dem Umschalter „Aufgabe | Materialien“.

## User Story

Als lernende Person möchte ich GUSTAV auf einem iPad im Querformat zweispaltig verwenden, damit Aufgabenstellung und Materialien neben der Bearbeitung sichtbar bleiben und ich nicht ständig zwischen zwei Ansichten wechseln muss.

## BDD-Szenarien und Testzuordnung

1. **iPad im Querformat**

   Given eine authentifizierte lernende Person bearbeitet eine Aufgabe bei 1024 px Ansichtsbreite, when die Arbeitsfläche dargestellt wird, then stehen Aufgabe und Kontext links sowie die Bearbeitung rechts gleichzeitig sichtbar nebeneinander.

   Nachweis: CSS-Vertragstest und mit `@feature-acceptance` markierter Playwright-Test über echte Oberfläche, Server und produktionsnahe Datenhaltung.

2. **Größeres iPad im Querformat**

   Given eine Ansichtsbreite von 1080 oder 1180 px, when die Aufgabenbearbeitung geöffnet wird, then bleibt die Zweispaltenansicht aktiv und erzeugt kein horizontales Scrollen.

   Nachweis: Playwright-Geometrieprüfung und Screenshot-Prüfung.

3. **iPad oder Smartphone im Hochformat**

   Given eine Ansichtsbreite von höchstens 820 px, when die Aufgabenbearbeitung geöffnet wird, then bleibt die kompakte Einspaltenansicht mit zugänglichem Oberflächenumschalter erhalten.

   Nachweis: Komponenten-/CSS-Vertragstest und Playwright-Prüfung bei 820 px und 390 px.

4. **Dialogaufgabe**

   Given eine Dialogaufgabe auf einem iPad im Querformat, when der Dialog geöffnet wird, then gelten dieselben responsiven Grenzen wie bei einer nativen Aufgabe.

   Nachweis: bestehender Dialog-Playwright-Test mit angepasster Tablet-Erwartung.

## API- und Datenbankbewertung

Die Änderung betrifft ausschließlich die Darstellung. `api/openapi.yml`, Backend-Fachlogik, Supabase-Schema und RLS-Policies bleiben unverändert. Eine Migration ist nicht erforderlich.

## Red-Green-Refactor

1. Bestehende Layout-Vertragstests und Playwright-Erwartungen so erweitern, dass 1024 px zweispaltig und 820 px einspaltig sein müssen; Tests zunächst rot ausführen.
2. Den Container-Breakpoint an einer gemeinsamen Stelle minimal anpassen und denselben Vertrag für native und Dialogaufgaben verwenden.
3. Doppelte Fallback-Breakpoints vereinheitlichen und die Benennung des Layoutvertrags verständlich dokumentieren.
4. Komponenten-/CSS-Tests, relevante Playwright-Tests und abschließend `make verify-feature` ausführen.

## Abgrenzung

Die allgemeine Practice-Ansicht und die Lehrkraft-Oberfläche werden nicht verändert. Entscheidend ist die Aufgabenarbeitsfläche innerhalb einer Lerneinheit.
