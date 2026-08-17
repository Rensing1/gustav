# Implementierungsplan: Zuverlässige und sichtbare endgültige Aufgabenabgabe

**Status:** umgesetzt
**Datum:** 17. August 2026

## Ausgangslage

Das Einholen einer Rückmeldung setzt sofort einen sichtbaren Verarbeitungszustand. Beim Klick auf „Endgültig abgeben“ geschieht dies derzeit nicht. Während der Serveranfrage bleibt der Button aktiv, eine wiederholte Abgabe ist möglich und bei Fehlern kann für Lernende der Eindruck entstehen, es sei überhaupt nichts geschehen.

Die bestehende Fachlogik finalisiert den neuesten vollständig ausgewerteten Rückmeldungsentwurf über `POST /api/learning/courses/{course_id}/tasks/{task_id}/submissions/finalize`.

## User Story

Als lernende Person möchte ich nach „Endgültig abgeben“ sofort eine eindeutige Reaktion und schließlich ein verständliches Ergebnis sehen, damit ich weiß, ob meine Abgabe verarbeitet, erfolgreich gespeichert oder aus einem konkreten Grund abgelehnt wurde.

## BDD-Szenarien und Testzuordnung

1. **Sofortige Reaktion auf den Klick**

   Given eine vollständig ausgewertete Rückmeldungsfassung kann finalisiert werden, when „Endgültig abgeben“ gewählt wird, then erscheint unmittelbar „Abgabe wird verarbeitet …“ und alle konkurrierenden Abgabeaktionen sind bis zum Ergebnis gesperrt.

   Nachweis: Seiten-/Komponententest mit verzögerter Antwort und authentifizierter `@feature-acceptance`-Playwright-Test.

2. **Erfolgreiche endgültige Abgabe**

   Given die Finalisierung wird serverseitig gespeichert, when die Antwort eintrifft, then erscheint „Aufgabe abgegeben“, die finale Abgabe steht im Verlauf und der Aufgabenstatus wird aktualisiert.

   Nachweis: bestehender API-Vertragstest und erweiterter Playwright-Rundlauf.

3. **Mehrfachklick oder wiederholte Anfrage**

   Given eine Finalisierung läuft bereits, when erneut geklickt oder dieselbe Browseraktion wiederholt wird, then entsteht höchstens eine finale Abgabe für diese Benutzeraktion.

   Nachweis: Frontend-Test, der die Zahl der Anfragen prüft; falls die Reproduktion eine Backend-Lücke zeigt, zusätzlicher Datenbank-Integrationstest vor der Backend-Korrektur.

4. **Entwurf noch nicht bereit**

   Given der neueste Rückmeldungsentwurf ist noch nicht vollständig ausgewertet, when eine Finalisierung versucht wird, then wird verständlich erklärt, dass die Rückmeldung noch verarbeitet wird und später erneut finalisiert werden kann.

   Nachweis: Seitenaktionstest für HTTP 409 `draft_not_ready` und bestehender API-Negativtest.

5. **Versuchslimit oder technische Störung**

   Given das Versuchslimit ist erreicht oder die Speicherung ist vorübergehend nicht verfügbar, when finalisiert wird, then erscheint eine deutschsprachige, handlungsorientierte Fehlermeldung und die Oberfläche wird wieder bedienbar.

   Nachweis: Seitenaktionstests für bekannte Backend-Fehler und Komponentenprüfung des entsperrten Zustands.

6. **Text- und Dateiantworten**

   Given eine Text- oder Dateiantwort hat eine vollständige Rückmeldung, when sie finalisiert wird, then verwendet die endgültige Abgabe exakt diese Fassung und verhält sich in beiden Modi gleich.

   Nachweis: API-Integrationstests für Text und Datei sowie Playwright-Test für beide Antwortformen.

## API-Entwurf

Der vorhandene REST-Endpunkt und seine Methode bleiben bestehen:

```yaml
/api/learning/courses/{course_id}/tasks/{task_id}/submissions/finalize:
  post:
    summary: Finalisiert den neuesten vollständig ausgewerteten Rückmeldungsentwurf
    responses:
      '201':
        description: Endgültige Abgabe gespeichert
      '409':
        description: Rückmeldungsentwurf fehlt oder ist noch nicht bereit
```

Zunächst ist keine Vertragsänderung vorgesehen. Die bekannten maschinenlesbaren Fehler werden im Browser-BFF in verständliche deutsche Meldungen übersetzt. Sollte der rote Mehrfachanfrage-Test eine serverseitige Race Condition belegen, wird vor der Backend-Änderung zuerst `api/openapi.yml` um den dafür notwendigen idempotenten Request-Vertrag ergänzt.

## Datenbankentwurf

Nach aktuellem Befund ist keine Schemaänderung erforderlich. Die bestehende Idempotenzunterstützung wird zuerst gegen den realen Fehlerfall geprüft. Nur wenn eine eindeutige Bindung zwischen Rückmeldungsentwurf und finaler Abgabe notwendig wird, wird vor der Implementierung eine eigene Supabase-Migration mit referenzieller und eindeutiger Einschränkung entworfen.

## Red-Green-Refactor

1. Den beobachteten Fall mit verzögerter und fehlerhafter Finalisierungsantwort als rote Frontend-Tests festhalten.
2. Sofortigen Pending-Zustand, Sperre gegen Mehrfachaktionen und verständliche Fehlermeldungen minimal implementieren.
3. Text- und Dateiweg sowie bekannte 409-/400-/503-Antworten prüfen.
4. Nur bei belegter Backend-Race-Condition Contract und gegebenenfalls Migration zuerst erweitern, danach API-/Repository-Test rot schreiben und minimal implementieren.
5. Relevante Backend-, Frontend- und Playwright-Tests sowie abschließend `make verify-feature` ausführen.

## Umsetzungsergebnis

- „Rückmeldung einholen“ und „Endgültig abgeben“ starten nun denselben klaren Pending-Lebenszyklus; bei der Finalisierung erscheint sofort „Abgabe wird verarbeitet ...“.
- Während einer laufenden Anfrage sind Editor, Moduswahl und beide Abgabeaktionen gesperrt. Eine zweite Formularanfrage wird bereits vor dem Netzwerkzugriff abgebrochen.
- Bekannte Backend-Fehler wie `draft_not_ready`, `draft_missing`, `max_attempts_exceeded` und eine vorübergehend nicht erreichbare Speicherung werden in verständliche, handlungsorientierte deutsche Meldungen übersetzt.
- Der bestehende REST-Vertrag, die transaktionale Finalisierung und die Datenbank-Idempotenz sind ausreichend; `api/openapi.yml` und das Schema mussten nicht verändert werden.
- Der authentifizierte Browsernachweis prüft verzögerte Antwort, sichtbaren Pending-Zustand, gesperrte Aktionen, Doppelklickschutz, erfolgreichen Abschluss, aktualisierten Aufgabenstatus und die Entwurfsbereinigung.
- Automatisierter Nachweis: `frontend/e2e/learner-task-finalization.spec.ts` mit `@feature-acceptance`; die vorhandenen Datenbank-Integrationstests für Text- und Datei-Finalisierung sind ebenfalls grün.
