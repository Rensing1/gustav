# Sichtbares und zuverlässiges Abschlussfeedback im KI-Dialog

**Status:** umgesetzt
**Datum:** 20. August 2026

## Ausgangslage

Der Abschlussendpunkt gibt atomar die abgeschlossene Dialogsitzung und die neu angelegte finale Abgabe zurück. `LearningDialogWorkspace` reduziert diese Antwort jedoch auf die Sitzung und verwirft insbesondere die Abgabe-ID. Der Eltern-Arbeitsraum lädt danach höchstens vorhandene Historie, startet aber keine gezielte Statusabfrage. Bei einer ersten Abgabe oder bei weiteren Dialogversuchen kann die Oberfläche deshalb dauerhaft „Die Rückmeldung wird erstellt“ anzeigen, obwohl der Worker die Abgabe verarbeitet.

## User Story

Als lernende Person möchte ich nach dem endgültigen Abschluss eines KI-Dialogs den Verarbeitungsstand und anschließend die erzeugte Rückmeldung sehen, damit ich erkenne, dass meine Abschlussaufgabe angekommen und ausgewertet worden ist.

## BDD-Szenarien und Testzuordnung

1. **Abschluss liefert Abgabe-ID**
   - Given ein Dialog mit mindestens einer abgeschlossenen Runde
   - When er endgültig abgegeben wird
   - Then übernimmt die Komponente Sitzung und finale Abgabe aus der dokumentierten Abschlussantwort
   - Nachweis: Komponenten- und Routenvertragstest
2. **Rückmeldung wird gezielt verfolgt**
   - Given die Abschlussabgabe ist `pending`
   - When der Serverabschluss erfolgreich war
   - Then fragt der Lernraum genau diese Abgabe-ID bis `completed` oder `failed` ab
   - Nachweis: Komponenten-/Seitenlogiktest und `@feature-acceptance`-Playwright-Test
3. **Fertige Rückmeldung wird angezeigt**
   - Given der Worker markiert die Dialogabgabe als `completed`
   - When die nächste Statusabfrage eintrifft
   - Then erscheint „Rückmeldung ist bereit“ und die neue Dialogabgabe steht in der Historie
   - Nachweis: authentifizierter Browser-Rundlauf über Oberfläche, Server, Worker und produktionsnahe Datenbank
4. **Fehlgeschlagene Auswertung**
   - Given die Dialogauswertung endet mit `failed`
   - When der Status geladen wird
   - Then endet der Wartezustand und eine handlungsorientierte Fehlermeldung erscheint
   - Nachweis: Seitenlogiktest
5. **Mehrerer Dialogversuch**
   - Given es gibt bereits eine ältere Dialogabgabe
   - When ein neuer Dialog abgeschlossen wird
   - Then wird nicht die alte Historie wiederverwendet, sondern die neue Abgabe-ID verfolgt
   - Nachweis: Komponenten-/Seitenlogiktest

## API- und Datenbankbewertung

Der vorhandene `DialogSessionCompletionResult` dokumentiert bereits `session` und `submission`; der Server persistiert Sitzung, Abgabe und Workerjob atomar. OpenAPI und Datenbankschema müssen nicht geändert werden. Die Korrektur liegt in der Frontend-Adaption und Statusverfolgung.

## Red–Green–Refactor

1. Rote Komponententests für die vollständige Abschlussantwort und den Callback mit Abgabe-ID schreiben.
2. Rote Seitenlogik-/Browserprüfungen für `pending → completed` und einen zweiten Versuch ergänzen.
3. Antworttyp und Callback minimal erweitern und die bestehende Pollinglogik wiederverwenden.
4. Fehler- und Wiederaufnahmezustände prüfen, ohne eine zweite Feedbacklogik einzuführen.
5. Gezielte Tests, authentifizierte Feature-Abnahme und `make verify-feature` ausführen.

## Umsetzungsergebnis

- `LearningDialogWorkspace` übernimmt aus der dokumentierten Abschlussantwort sowohl die Sitzung als auch die neu erzeugte finale Abgabe. Die Abgabe wird über den Komponentenbaum an den Lernraum weitergereicht.
- Der Lernraum legt die neue Abgabe sofort in der lokalen Historie ab und verfolgt gezielt ihre ID. Eine bereits geladene ältere Historie kann den neuen Dialogversuch daher nicht mehr verdecken.
- Nach erfolgreicher Analyse erscheint „Rückmeldung ist bereit“. Der Rückmeldungstext wird direkt im Hauptbereich des abgeschlossenen Dialogs dargestellt; bei einem Workerfehler endet der Wartezustand mit einer verständlichen Fehlermeldung.
- API-Vertrag und Datenbankschema blieben unverändert, da `DialogSessionCompletionResult` die benötigten Daten bereits vollständig und atomar bereitstellt.

## Verifikation

- Roter Komponententest bestätigte, dass der Abschluss-Callback zuvor ohne Abgabe aufgerufen wurde.
- Roter Darstellungstest bestätigte, dass ein abgeschlossener Dialog trotz fertiger Historie dauerhaft nur den Wartehinweis zeigte.
- Gezielte Komponenten- und Routenvertragstests: 40 bestanden.
- Gezielter authentifizierter Playwright-Rundlauf: bestanden; die Browserstrecke prüft `pending → completed`, die sichtbare Statusmeldung und den Rückmeldungstext über Oberfläche, Server und produktionsnahe Datenbank.
- `make verify-feature`: 2.430 Backend-Tests bestanden (78 übersprungen), 581 Frontend-Tests bestanden, Produktionsbuild erfolgreich, 62 H5P-Tests bestanden und alle 21 `@feature-acceptance`-Szenarien bestanden.
