# Teaching-CLI: Diagnostikabfragen

## User Story

Als Lehrkraft möchte ich Diagnostikdaten über Kurs-, Lerneinheits-, Aufgaben- und Schülerperspektiven lesen können, damit ich den aktuellen Lernstand untersuchen und die jeweils neueste Abgabe samt formativer Auswertung und Rückmeldung nachvollziehen kann.

## BDD-Szenarien und Testzuordnung

1. **Vollständige Kurs- und Lerneinheitsübersichten**
   - Given eine Lehrkraft besitzt einen Kurs und verwendet ein CLI-Token mit `read`-Scope
   - When sie die Kurs- oder Lerneinheitsdiagnostik abruft
   - Then erhält sie alle automatisch paginierten Schülerzeilen mit IDs, Namen, Abgabestatus und formativen Scores
   - Nachweis: CLI-Unit-Tests, API-/Capability-Contracttests und `@feature-acceptance`-Playwright-Rundlauf
2. **Aufgabenbezogener Drill-down**
   - Given eine Lerneinheitsmatrix enthält mehrere Aufgaben und Schüler mit sowie ohne Abgabe
   - When die Lehrkraft mit `--task-id` filtert
   - Then enthält die Antwort genau diese Aufgabe und weiterhin jeden sichtbaren Schüler
   - Nachweis: CLI-Unit-Test
3. **Schülerperspektive**
   - Given ein Schüler ist in owner-sichtbaren aktiven Kursen eingeschrieben
   - When die Lehrkraft ohne Kursfilter abfragt
   - Then erhält sie das kursübergreifende Diagnostikprofil
   - And When sie zusätzlich einen Kurs und optionale Lerneinheiten angibt
   - Then erhält sie die Aufgabenübersicht dieses Kurskontexts
   - Nachweis: CLI-Unit-Tests und API-Tests
4. **Nur die neueste Abgabe**
   - Given ein Schüler hat mehrere unveränderliche Versuche für eine Aufgabe
   - When die Lehrkraft die Abgabediagnostik liest
   - Then erscheinen nur Inhalt, Auswertung und Rückmeldung der neuesten Abgabe
   - And bei fehlender Abgabe erscheint ein erfolgreicher leerer Zustand
   - Nachweis: DB-gestützter API-Test, CLI-Unit-Test und Feature-Acceptance-Rundlauf
5. **Aufgabentypgerechte Details**
   - Given die neueste Abgabe enthält `criteria.v1` oder `criteria.v2`, formative Rückmeldung, H5P-Punkte oder ein Dialogtranskript
   - When die CLI das Detail ausgibt
   - Then werden formative Werte nicht als Note bezeichnet, Dialoge enthalten keine internen Instruktionen und H5P-CLI-Antworten enthalten kein Review-Credential
   - Nachweis: Serialisierungs-, API- und CLI-Tests
6. **Sicherer Dateidownload**
   - Given die neueste Abgabe ist eine Datei, ein Bild oder ein PDF
   - When die Lehrkraft sie herunterlädt
   - Then wird sie binärtreu und atomar mit Rechten `0600` geschrieben
   - And ein vorhandenes Ziel wird nur mit `--force` ersetzt
   - And Fehler oder Größenüberschreitungen hinterlassen keine Teildatei
   - Nachweis: CLI-Dateisystemtests
7. **Autorisierung bleibt fail-closed**
   - Given ein Token fehlt, ist abgelaufen, widerrufen oder besitzt kein `read`-Scope, oder die Lehrkraft besitzt den Kurs nicht
   - When ein Diagnostikendpunkt aufgerufen wird
   - Then antwortet GUSTAV privat mit `401`, `403`, `404` beziehungsweise bei Repository-Ausfall mit `503`, ohne Inhalte oder Secrets zu protokollieren
   - Nachweis: Capability-, Middleware-, API- und DB-/RLS-Tests

## API- und Datenbankentwurf

Die bestehenden Read Models und Owner-Projektionen bleiben die fachliche Quelle. Folgende GET-Endpunkte erhalten zusätzlich `cliTokenAuth` und `x-required-cli-scopes: [read]`:

- Kursmatrix und Lernendenprofil unter `/api/diagnostics/views/...`;
- Unit-Summary und Schülerübersicht unter `/api/teaching/courses/.../submissions/...`;
- neueste Abgabe, neuester Dateidownload und abgeschlossenes Dialogtranskript.

Die bestehenden Cookie-/BFF-Bearer-Flows bleiben erhalten. `limit` und `offset` der Diagnostik-Read-Models werden im OpenAPI-Vertrag begrenzt dokumentiert. Für H5P wird bei CLI-Authentifizierung kein kurzlebiges Browser-Review-Credential erzeugt.

Es ist keine Migration nötig: Abgaben, Auswertungen, Dialogtranskripte und die owner-gebundenen PostgreSQL-Helper existieren bereits. Die Erweiterung ändert ausschließlich Verträge, Auth-Capabilities und den CLI-Adapter.

## Red–Green–Refactor

1. OpenAPI-Sicherheits- und Paginierungsvertrag ergänzen.
2. Rote Tests für Capability-Abgleich, Parser, automatische Paginierung, Detailausgabe, Dialog/H5P und Download schreiben.
3. Diagnostik-Capabilities sowie minimale CLI-Kommandos implementieren.
4. Ausgabe- und Downloadhelfer refaktorieren, ohne Geschäftslogik in die CLI zu verschieben.
5. Dokumentation und authentifizierten Feature-Acceptance-Rundlauf ergänzen.

## Abnahme

- OpenAPI, Laufzeit-Capabilities und CLI-Operationsregister sind deckungsgleich.
- Menschliche Ausgabe und `--json` sind vollständig, Unicode-sicher und datensparsam.
- Rollen-, Ownership-, RLS- und `read`-Scope-Prüfungen bleiben fail-closed.
- `make verify-feature FEATURE=cli-diagnostics` und anschließend `make verify` sind erfolgreich.

## Umsetzungsergebnis

- Der OpenAPI-Vertrag, das allgemeine Capability-Register und das CLI-Operationsregister sind deckungsgleich.
- Alle Übersichten aggregieren Seiten vor der Ausgabe; wiederholte Seiten und Folgeseitenfehler liefern keine Teilergebnisse.
- Der DB-gestützte pytest weist die echte Owner-/RLS-Grenze und die Auswahl des neuesten Versuchs nach.
- Der authentifizierte Chromium-Rundlauf erstellt ein read-only Token im Lehrkraftprofil, erzeugt eine echte Lernendenabgabe und liest Kurs-, Aufgaben-, Lernenden- und Detaildiagnostik über die CLI.
- `make verify-feature FEATURE=cli-diagnostics` ist mit 2.538 bestandenen Python-Tests, 642 bestandenen Frontend-Tests, Produktionsbuild, H5P-Suite und einem bestandenen Feature-Acceptance-Test erfolgreich.
- Das anschließend erneut ausgeführte `make verify` ist ebenfalls erfolgreich.
