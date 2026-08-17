# Implementierungsplan: Entwurfsstatus im Materialeditor nur bei echten Änderungen

**Status:** zur Umsetzung freigegeben  
**Datum:** 17. August 2026

## Ausgangslage

Der Moduleditor speichert bei jedem `input`- oder `change`-Ereignis einen Browserentwurf. Er vergleicht die erfassten Felder nicht mit dem gespeicherten Material. Dadurch kann nach dem bloßen Öffnen und Verlassen eines vorhandenen Materials in der Übersicht fälschlich „Entwurf“ erscheinen.

## User Story

Als Lehrkraft möchte ich den Entwurfsstatus nur bei tatsächlich geänderten Materialdaten sehen, damit die Inhaltsübersicht zuverlässig zwischen gespeicherten Materialien und ungespeicherten Änderungen unterscheidet.

## BDD-Szenarien und Testzuordnung

1. **Material nur ansehen**

   Given ein vorhandenes Material ohne lokalen Entwurf, when die Lehrkraft es öffnet und ohne Änderung zu „Inhalte“ zurückkehrt, then erscheint kein Entwurfsstatus.

   Nachweis: Komponenten-Interaktionstest und authentifizierter `@feature-acceptance`-Playwright-Test.

2. **Material tatsächlich ändern**

   Given ein vorhandenes Material, when Titel, Inhalt oder Alternativtext geändert wird, then erscheint „Entwurf“ und die Änderung wird im selben Tab wiederhergestellt.

   Nachweis: Komponenten-Interaktionstest und bestehender Draft-Restore-Test, erweitert um vorhandenes Material.

3. **Änderung vollständig zurücknehmen**

   Given ein Material wurde lokal geändert, when alle Felder wieder exakt dem gespeicherten Stand entsprechen, then wird der lokale Entwurf entfernt und der Status verschwindet.

   Nachweis: Unit-Test der semantischen Snapshot-Prüfung und Komponenten-Interaktionstest.

4. **Unterschiedliche Materialien**

   Given zwei Materialien existieren, when nur eines geändert wird, then trägt ausschließlich dieses Material den Entwurfsstatus.

   Nachweis: Komponenten-Interaktionstest.

5. **Fehlgeschlagenes Speichern**

   Given eine echte Änderung kann serverseitig nicht gespeichert werden, when die Fehlermeldung erscheint, then bleibt der lokale Entwurf erhalten und kann korrigiert oder verworfen werden.

   Nachweis: bestehender Seitenaktionstest und Draft-Vertragstest.

## API- und Datenbankbewertung

Der Entwurfsstatus ist lokaler UI-Zustand. Die bestehenden Material-Endpunkte in `api/openapi.yml`, das Teaching-Aggregat, Datenbankschema und RLS-Policies bleiben unverändert. Eine Migration ist nicht erforderlich.

## Red-Green-Refactor

1. Einen roten Interaktionstest für Öffnen und unverändertes Zurückkehren schreiben.
2. Gespeicherte Ausgangswerte und aktuellen Formular-Snapshot fachlich vergleichen; nur Unterschiede in `sessionStorage` sichern.
3. Bei vollständiger Rückkehr zum Ausgangszustand den vorhandenen Entwurf entfernen.
4. Snapshot- und Vergleichslogik in verständliche, frameworkfreie Hilfsfunktionen auslagern.
5. Komponenten-, Seiten- und Playwright-Tests sowie abschließend `make verify-feature` ausführen.
