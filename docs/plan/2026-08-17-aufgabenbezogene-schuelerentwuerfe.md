# Implementierungsplan: Aufgabenbezogene Schülerentwürfe im Texteditor

**Status:** umgesetzt
**Datum:** 17. August 2026

## Ausgangslage

Der Speicherschlüssel eines Textentwurfs enthält bereits Schüler-, Kurs- und Aufgaben-ID. Beim direkten Wechsel zwischen Aufgaben bleibt die Editor-Komponente jedoch aktiv und lädt den Entwurf der neu gewählten Aufgabe nicht erneut. Dadurch kann der sichtbare Text einer vorherigen Aufgabe irrtümlich in einer anderen Aufgabe erscheinen.

## User Story

Als lernende Person möchte ich für jede Aufgabe einen getrennten Textentwurf erhalten, damit beim Aufgabenwechsel ausschließlich der zu dieser Aufgabe gehörende Text erscheint und ich beim Zurückkehren genau an dieser Aufgabe weiterarbeiten kann.

## BDD-Szenarien und Testzuordnung

1. **Wechsel von Aufgabe A zu Aufgabe B**

   Given in Aufgabe A wurde ein Text eingegeben und Aufgabe B hat keinen Entwurf, when die lernende Person Aufgabe B öffnet, then ist deren Editor leer und zeigt niemals Text aus Aufgabe A.

   Nachweis: Komponenten-Interaktionstest mit zwei Aufgaben und authentifizierter `@feature-acceptance`-Playwright-Test.

2. **Rückkehr zu Aufgabe A**

   Given Aufgabe A und Aufgabe B besitzen unterschiedliche Entwürfe, when zwischen beiden Aufgaben gewechselt wird, then erscheint jeweils ausschließlich der zur aktiven Aufgabe gehörende Entwurf.

   Nachweis: Komponenten-Interaktionstest und Playwright-Test.

3. **Neuladen desselben Tabs**

   Given ein Entwurf wurde in einer Aufgabe gespeichert, when dieselbe Aufgabe im selben Browser-Tab neu geladen oder später erneut geöffnet wird, then wird ihr aufgabenbezogener Entwurf wiederhergestellt.

   Nachweis: bestehender Reload-Playwright-Test, erweitert um eine zweite Aufgabe.

4. **Trennung zwischen Lernenden und Kursen**

   Given derselbe Browser wird für unterschiedliche Lernende oder Kurse verwendet, when eine Aufgabe geöffnet wird, then werden Entwürfe anderer Identitäten oder Kurse nicht geladen.

   Nachweis: Unit-Test des Speicherschlüssels und Komponentenvertrag.

5. **Erfolgreiche endgültige Abgabe**

   Given ein Entwurf wurde endgültig abgegeben, when die Abgabe bestätigt ist, then wird der lokale Textentwurf genau dieser Aufgabe entfernt; Entwürfe anderer Aufgaben bleiben erhalten.

   Nachweis: Unit-Test der gezielten Speicherbereinigung und Seitenvertragstest; der vollständige Finalisierungsablauf wird zusätzlich im Akzeptanztest zu Problem 3 geprüft.

## API- und Datenbankbewertung

Der Entwurf bleibt bewusst tablokaler Browserzustand. Es werden keine Entwurfsinhalte an neue Endpunkte übertragen. `api/openapi.yml`, Datenbankschema und RLS-Policies bleiben unverändert; eine Migration ist nicht erforderlich.

## Sicherheits- und Datenschutzgrenzen

- Schlüssel bleiben nach Lernenden, Kurs und Aufgabe getrennt.
- Inhalte werden nur in `sessionStorage`, nicht dauerhaft in `localStorage`, gespeichert.
- Alte unscoped Schlüssel werden weiterhin entfernt.
- Es werden keine Inhalte in Logs oder Telemetrie geschrieben.

## Red-Green-Refactor

1. Einen fehlschlagenden Komponenten- und Browsertest für den Wechsel zwischen zwei Aufgaben schreiben.
2. Die Wiederherstellung an einen Wechsel der fachlichen Aufgabenidentität binden, nicht nur an das erstmalige Öffnen der Arbeitsfläche.
3. Nach erfolgreicher Finalisierung ausschließlich den Schlüssel der aktiven Aufgabe löschen.
4. Zustandswechsel und Speicherzugriff in kleine, verständlich benannte Hilfsfunktionen aufteilen.
5. Relevante Frontend-Tests, Playwright und abschließend `make verify-feature` ausführen.

## Umsetzungsergebnis

- Die geöffnete Aufgabenarbeitsfläche erkennt nun zusätzlich zur Sichtbarkeit auch einen Wechsel der fachlichen Aufgaben-ID und stellt daraufhin den passenden Entwurf wieder her.
- Ein gemeinsamer, frameworkfreier Helfer erzeugt die nach Lernendem, Kurs, Aufgabe und Modus getrennten Speicherschlüssel.
- Nach erfolgreicher endgültiger Abgabe werden ausschließlich der aufgabenbezogene Textentwurf und sein alter Legacy-Schlüssel entfernt; Entwürfe anderer Aufgaben bleiben bestehen.
- Der authentifizierte Browsernachweis wechselt zwischen zwei Aufgaben, prüft den zunächst leeren zweiten Editor, zwei unterschiedliche Entwürfe sowie die Wiederherstellung nach einem Neuladen.
- Automatisierter Nachweis: `frontend/e2e/learner-task-drafts.spec.ts` mit `@feature-acceptance`.
