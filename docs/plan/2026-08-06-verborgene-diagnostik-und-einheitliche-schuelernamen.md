# Verborgene Diagnostik und einheitliche Schülernamen

## User Story

Als Lehrkraft möchte ich in allen Arbeitsbereichen dieselbe verlässliche Schülerbezeichnung sehen und in der Hauptnavigation nur freigegebene Funktionen vorfinden, damit ich Lernende eindeutig wiedererkenne und nicht in unfertige Bereiche geführt werde.

## Fachlicher Vertrag

- Die Lehrkraft-Navigation enthält Kurse, Lerneinheiten und Live, aber keine Diagnostik.
- Direkte Diagnostikrouten und ihre Berechtigungen bleiben bestehen.
- Ein lehrkraftsichtbarer Schülername ist `Vorname Nachname`, wenn beide Felder gepflegt sind.
- Fehlt eines der beiden Felder, wird exakt der Teil vor `@` aus E-Mail oder E-Mail-artigem Benutzernamen gezeigt.
- Frei gesetzte Anzeigenamen und rohe Subjects werden nicht verwendet; ohne sicheren Fallback erscheint `Unbekannt`.
- Schülerprofil und Account-Anzeige behalten ihre bisherige Anzeigenamenlogik.

## BDD-Szenarien und Testzuordnung

1. **Given** eine Lehrkraft öffnet eine beliebige Hauptseite, **when** die Kopfzeile erscheint, **then** enthält sie Kurse, Lerneinheiten und Live, aber keine Diagnostik.
   → statischer Shell-Vertrag, Layout-Komponententest und authentifizierte Browserabnahme.
2. **Given** eine Diagnostik-URL wird direkt aufgerufen, **when** die Lehrkraft berechtigt ist, **then** bleibt die Route erreichbar.
   → bestehende Diagnostik-Vertrags- und API-Tests.
3. **Given** Vor- und Nachname sowie ein abweichender Anzeigename sind vorhanden, **when** eine Lehrkraft den Lernenden sieht, **then** erscheint ausschließlich `Vorname Nachname`.
   → reiner Formatter- und Directory-Test.
4. **Given** genau ein Namensteil fehlt, **when** die Bezeichnung gebildet wird, **then** erscheint der unveränderte E-Mail-Präfix.
   → parametrisierter Formatter-Test.
5. **Given** nur ein E-Mail-artiger Benutzername oder `legacy-email:` ist verfügbar, **when** die Bezeichnung gebildet wird, **then** erscheint dessen Präfix.
   → Formatter- und Directory-Test.
6. **Given** kein sicherer Identifier ist verfügbar oder das Directory fällt aus, **when** eine Lehrkraftansicht geladen wird, **then** erscheint `Unbekannt` und niemals das rohe Subject.
   → Formatter-, Adapter- und API-Fehlertest.
7. **Given** derselbe Lernende erscheint in Kursverwaltung, Live, Sorgenfach und Diagnostik, **when** die Read-Models geladen werden, **then** liefern alle dieselbe kanonische Bezeichnung.
   → API-Integrationstests und authentifizierte Browserabnahme für Kurs und Live.
8. **Given** Desktop, Tablet oder Smartphone sowie Light oder Dark, **when** die Lehrkraft-Navigation dargestellt wird, **then** bleibt sie ohne Diagnostik ausgewogen und ohne Überlauf.
   → Visual-Smoke-Referenzen.

## Schnittstellen und Datenhaltung

Die bestehenden JSON-Felder und Endpunkte bleiben unverändert. OpenAPI dokumentiert ihre gemeinsame Semantik über `TeacherStudentLabel`. Es gibt keine Migration und keine zusätzliche Speicherung personenbezogener Daten.
