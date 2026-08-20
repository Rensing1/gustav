# Intuitive Hauptaktionen im KI-Dialog

**Status:** umgesetzt
**Datum:** 20. August 2026

## User Story

Als lernende Person möchte ich „Dialog beenden“ dort finden, wo ich den Dialog fortsetze oder eine fehlgeschlagene KI-Antwort wiederhole, und keine nutzlose Wiederholungsaktion sehen, wenn alle Wiederholungen verbraucht sind.

## BDD-Szenarien und Testzuordnung

1. **Dialog nach einer fertigen Runde beenden**
   - Given mindestens eine Runde ist vollständig beantwortet und keine Generierung läuft
   - When die Gesprächsphase angezeigt wird
   - Then steht „Dialog beenden“ unten im Hauptbereich bei den Dialogaktionen und nicht in der linken Seitenleiste
   - Nachweis: Svelte-Komponententest und visuelle Browserprüfung
2. **Fehlgeschlagene KI-Antwort wiederholen**
   - Given eine KI-Antwort ist fehlgeschlagen und weniger als drei Generierungsversuche wurden genutzt
   - When der Dialog angezeigt wird
   - Then steht „KI-Antwort erneut versuchen“ im Hauptaktionsbereich
   - Nachweis: Svelte-Komponententest
3. **Wiederholungslimit erreicht**
   - Given drei Generierungsversuche wurden verbraucht
   - When der Dialog angezeigt wird
   - Then wird kein deaktivierter Wiederholungsbutton gerendert; stattdessen erklärt ein kurzer Status den ausgeschöpften Zustand
   - Nachweis: Svelte-Komponententest
4. **Noch keine abgeschlossene Runde**
   - Given noch keine Runde wurde vollständig abgeschlossen
   - When die Gesprächsphase angezeigt wird
   - Then wird keine vorzeitige Abschlussaktion angeboten; der sichere Abbruch ohne Abgabe bleibt erreichbar
   - Nachweis: Svelte-Komponententest
5. **Responsive Anordnung**
   - Given Desktop-, iPad-Querformat- und Smartphonebreite
   - When die Aktionszeile angezeigt wird
   - Then sind Hauptaktionen sichtbar, erreichbar und ohne Überlauf angeordnet
   - Nachweis: Designvertrag und `@feature-acceptance`-Playwright-Test

## API- und Datenbankbewertung

Die Änderung betrifft nur Darstellung und erlaubte Sichtbarkeit bereits vorhandener Aktionen. OpenAPI, Use Cases und Datenbankschema bleiben unverändert; eine Migration ist nicht erforderlich.

## Red–Green–Refactor

1. Rote Komponenten- und CSS-Vertragstests für Position und Wiederholungsgrenze schreiben.
2. Markup minimal in eine gemeinsame Hauptaktionszone verschieben und ausgeschöpfte Aktionen nicht mehr rendern.
3. Tastatur-, Fokus-, Light-/Dark- und responsive Zustände prüfen.
4. Gezielte Tests, visuelle Browserabnahme und `make verify-feature` ausführen.

## Umsetzungsergebnis

- „Dialog beenden“ steht nach mindestens einer vollständig beantworteten Runde in der Hauptaktionszone unter dem Dialog und nicht mehr in der Material-/Partnerseitenleiste.
- „Antwort senden“, „KI-Antwort erneut versuchen“ und „Dialog beenden“ verwenden dieselbe responsive Aktionszone. Dadurch bleiben die zum aktuellen Arbeitsschritt gehörenden Aktionen räumlich zusammen.
- Nach drei fehlgeschlagenen Generierungsversuchen wird kein funktionsloser, deaktivierter Retry-Button mehr gerendert. Eine kurze Meldung erklärt stattdessen, dass die KI-Antwort nicht erneut erzeugt werden kann.
- Vor der ersten abgeschlossenen Runde bleibt „Dialog beenden“ verborgen; der sichere Abbruch ohne Abgabe bleibt in der Seitenleiste verfügbar.
- API und Datenbankschema wurden nicht geändert.

## Verifikation

- Rote Komponententests bestätigten die alte Position in der Seitenleiste, den Retry im Dialogverlauf und den deaktivierten Button nach ausgeschöpftem Limit.
- 17 gezielte `LearningDialogWorkspace`-Tests bestanden; die neuen Fälle prüfen Position, zulässigen Retry und ausgeschöpftes Limit.
- Der authentifizierte Playwright-Rundlauf bestand bei Desktop-, iPad-Querformat- und Smartphonebreite. Die bewusst geänderten Desktop- und Tablet-Referenzbilder wurden nach visueller Prüfung aktualisiert.
- `make verify-feature`: 2.430 Backend-Tests bestanden (78 übersprungen), 583 Frontend-Tests bestanden, Produktionsbuild erfolgreich, 62 H5P-Tests bestanden und alle 21 `@feature-acceptance`-Szenarien bestanden.
