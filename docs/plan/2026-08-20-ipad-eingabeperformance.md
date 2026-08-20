# Flüssige Texteingabe auf iPads

**Status:** umgesetzt
**Datum:** 20. August 2026

## Ausgangslage

Bei jeder Tiptap-Änderung wird das vollständige Dokument zu Markdown serialisiert. Der zurückgemeldete Wert läuft anschließend als Prop erneut in den Editor und löst dort eine zweite vollständige Serialisierung zum Gleichheitsvergleich aus. Zusätzlich entfernt und schreibt `LearningTaskCard` synchron Browserspeichereinträge für jedes einzelne Zeichen. Diese Arbeit läuft im Hauptthread und kann die Bildschirmtastatur bei längeren Antworten sichtbar blockieren.

## User Story

Als Schüler auf einem iPad möchte ich längere Antworten mit der Bildschirmtastatur ohne merkliche Verzögerung eingeben, während mein Entwurf weiterhin zuverlässig erhalten und beim Absenden vollständig synchronisiert wird.

## BDD-Szenarien und Testzuordnung

1. **Kein doppeltes Serialisieren bei internem Prop-Rücklauf**
   - Given Tiptap meldet einen neuen Markdownwert
   - When der Elternzustand denselben Wert als Prop zurückgibt
   - Then fragt der Wrapper den Editor nicht erneut zur Gleichheitsprüfung ab und setzt den Inhalt nicht neu
   - Nachweis: Komponententest mit instrumentiertem Editor
2. **Entwurfsspeicherung ist getaktet**
   - Given mehrere Zeichen werden schnell eingegeben
   - When der Eingabestrom noch läuft
   - Then erfolgen nicht für jedes Zeichen synchrone Storage-Schreibzugriffe; nach kurzer Ruhe steht der neueste vollständige Wert im Speicher
   - Nachweis: Unit-/Komponententest mit Fake-Timern
3. **Navigation verliert keinen Entwurf**
   - Given ein noch nicht abgelaufener Speichertimer
   - When die Komponente verlassen oder die Seite verborgen wird
   - Then wird der letzte Wert vor dem Verlassen geschrieben
   - Nachweis: Komponententest
4. **Formular enthält den aktuellen Text**
   - Given der Speichertimer ist noch offen
   - When „Rückmeldung einholen“ gewählt wird
   - Then synchronisiert das `formdata`-Ereignis den aktuell sichtbaren Markdowntext in die Anfrage
   - Nachweis: bestehender und erweiterter Editor-Komponententest
5. **Reale iPad-nahe Eingabesequenz**
   - Given ein langer Entwurf im Touch-Kontext
   - When Zeichen einzeln eingegeben werden
   - Then erscheinen sie in Reihenfolge, ohne Mehrsekundenpausen oder Long Tasks aus GUSTAVs Speicherpfad
   - Nachweis: `@feature-acceptance`-Playwright-Test mit Zeit-/Long-Task-Diagnostik; Schwellenwert als Regressionssignal, nicht als Hardware-Benchmark

## API- und Datenbankbewertung

Formularvertrag, Backend-API und Datenbank bleiben unverändert. Die Optimierung betrifft ausschließlich Editor-Adaption und tab-lokale Entwurfspersistenz; eine Migration ist nicht erforderlich.

## Red–Green–Refactor

1. Rote instrumentierte Tests für Prop-Rücklauf und getaktete Speicherung schreiben.
2. Intern zurückgemeldete Werte markieren, damit der Prop-Effekt keine zweite Serialisierung ausführt.
3. Entwurfsspeicherung mit einem kleinen, testbaren Scheduler verzögern und bei Submit/Destroy/Seitenwechsel flushen.
4. Korrektheit von Dirty-Zustand, Finalisierungssperre und Formularinhalt regressionsprüfen.
5. Browserprofil, gezielte Tests, authentifizierte Feature-Abnahme und `make verify-feature` ausführen.

## Umsetzung und Ergebnis

- Der Markdown-Wrapper erkennt Werte, die Tiptap gerade selbst gemeldet hat. Beim reaktiven Rücklauf aus dem Elternzustand serialisiert und ersetzt er dieses Dokument nicht erneut.
- `LearningTaskCard` hält den aktuellen Text weiterhin sofort im Svelte- und Formularzustand, fasst synchrone Browserspeicherzugriffe aber mit einer Ruhezeit von 200 ms zusammen.
- Der letzte vollständige Entwurf wird vor Formularabgabe, Aufgabenwechsel, `pagehide` und Komponentenabbau sofort geschrieben. Dabei bleibt der bestehende schüler-, kurs- und aufgabenspezifische Sitzungsschlüssel erhalten.
- Der authentifizierte Touch-Browserlauf gibt in iPad-Landschaft 244 Zeichen einzeln ein, begrenzt Storage-Schreibzugriffe als Regressionssignal und prüft den vollständigen Entwurf nach Aufgabenwechsel und Neuladen.

## Verifikation

- Gezielte Editor- und Aufgabenkartentests: 54 bestanden
- Svelte-Diagnostik: 0 Fehler, 0 Warnungen
- Gezielter authentifizierter Touch-Browsertest: 1 bestanden
- `make verify-feature`: 2435 Backendtests bestanden, 78 übersprungen; 587 Frontendtests bestanden; 62 H5P-Tests bestanden; 22 Feature-Acceptance-Browsertests bestanden

Der erste vollständige Lauf traf parallel angelegte Handbuchdateien in einem unvollständigen Zwischenstand und scheiterte ausschließlich an vier neuen Dokumentationsverträgen. Nach Abschluss dieser fremden Änderung waren der gezielte Vertrag mit 4/4 Tests und der unveränderte vollständige Wiederholungslauf grün; Handbuchdateien sind nicht Bestandteil dieses Fixes.
