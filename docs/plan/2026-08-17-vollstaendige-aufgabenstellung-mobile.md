# Implementierungsplan: Lange und mobile Aufgabenstellungen eindeutig anzeigen

**Status:** zur Umsetzung freigegeben  
**Datum:** 17. August 2026

## Ausgangslage

In der Modul-Arbeitsansicht zeigt eine Aufgabenzeile nur die erste nichtleere Markdown-Zeile und begrenzt sie visuell auf zwei Zeilen. Es ist nicht eindeutig erkennbar, ob weitere Angaben folgen. In der kompakten Bearbeitungsansicht steht die vollständige Aufgabenstellung im Bereich „Materialien“ und ist deshalb verborgen, solange „Aufgabe“ aktiv ist.

## User Story

Als lernende Person möchte ich erkennen, wenn eine Aufgabenstellung in der Übersicht gekürzt ist, und beim Bearbeiten die vollständige Aufgabenstellung direkt bei meiner Lösung sehen, damit ich keine wichtigen Angaben übersehe.

## BDD-Szenarien und Testzuordnung

1. **Lange Aufgabe in der Übersicht**

   Given eine Aufgabenstellung enthält mehr Inhalt als die Vorschau zeigt, when die Modul-Arbeitsansicht dargestellt wird, then kennzeichnet die Aufgabenzeile sichtbar und zugänglich, dass die vollständige Aufgabe beim Öffnen folgt.

   Nachweis: Komponenten-Renderingtest und authentifizierter `@feature-acceptance`-Playwright-Test.

2. **Kurze Aufgabe in der Übersicht**

   Given die vollständige Aufgabenstellung passt in die Vorschau, when die Modul-Arbeitsansicht dargestellt wird, then erscheint kein irreführender Kürzungshinweis.

   Nachweis: Komponenten-Renderingtest.

3. **Vollständige Aufgabenstellung auf dem Smartphone**

   Given eine native Aufgabe wird bei 390 px bearbeitet und „Aufgabe“ ist aktiv, when die Bearbeitung erscheint, then steht die vollständige Aufgabenstellung oberhalb beziehungsweise unmittelbar bei der Eingabe; der Materialtab ist dafür nicht erforderlich.

   Nachweis: Komponentenprüfung und Playwright-Test bei 390 px.

4. **Vollständige Aufgabenstellung auf dem iPad im Hochformat**

   Given die kompakte Ansicht gilt bei höchstens 820 px, when eine Aufgabe bearbeitet wird, then bleibt die vollständige Aufgabenstellung im aktiven Aufgabenbereich sichtbar und die Seite scrollt ohne horizontales Überlaufen.

   Nachweis: Playwright-Geometrie- und Sichtbarkeitsprüfung.

5. **Keine störende Dopplung auf breiten Bildschirmen**

   Given die zweispaltige Ansicht zeigt die Aufgabenstellung bereits in der Kontextspalte, when die Aufgabe auf Desktop oder iPad im Querformat bearbeitet wird, then wird dieselbe Aufgabenstellung nicht zusätzlich im Bearbeitungsbereich wiederholt.

   Nachweis: CSS-/Komponentenvertrag und Playwright-Sichtbarkeitsprüfung.

6. **Dialog- und Spezialaufgaben**

   Given eine Dialog-, H5P- oder Uploadaufgabe wird kompakt bearbeitet, when der Aufgabenbereich aktiv ist, then bleibt auch dort die vollständige Aufgabenstellung ohne Wechsel zum Materialbereich zugänglich.

   Nachweis: Komponentenvertrag für Aufgabentypen und bestehender Dialog-Playwright-Test.

## API- und Datenbankbewertung

Die vollständige `instruction_md` ist bereits Teil der Learning-Antwort. Es werden weder neue Felder noch neue Endpunkte benötigt. `api/openapi.yml`, Backend und Datenbankschema bleiben unverändert; eine Migration ist nicht erforderlich.

## Red-Green-Refactor

1. Rote Komponenten- und Browsertests für Kürzungshinweis und mobile Sichtbarkeit der vollständigen Aufgabenstellung schreiben.
2. Aus der gesamten Aufgabenstellung eine verständliche Vorschau plus fachlichen Kürzungszustand ableiten.
3. Die vollständige Aufgabenstellung in der kompakten Aufgabenfläche ergänzen und auf zweispaltigen Ansichten gezielt ausblenden.
4. Dieselbe Regel für native, Dialog- und Spezialaufgaben verwenden, ohne Inhalte dauerhaft zu duplizieren.
5. Komponenten-, Layout- und Playwright-Tests sowie abschließend `make verify-feature` ausführen.
