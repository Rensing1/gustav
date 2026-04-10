# Plan: Node-Editor Toggle-Schließen und Kriterienfelder

Status: abgeschlossen

## Zusammenfassung

- Die Inline-Bereiche `Material hinzufügen` und `Aufgabe hinzufügen` sollen per erneutem Klick auf denselben Sektionsbutton wieder geschlossen werden.
- Kriterien für Aufgaben sollen als feste Liste von maximal 10 Feldern statt als einzelnes Freitextfeld erfasst werden.
- Die Backend-Nutzlast bleibt `criteria: string[]`; nur die Formularschicht ändert sich.

## Umsetzung

- Route-Interaktion im Lehrenden-Node-Editor so anpassen, dass die Sektionsbuttons echte Toggle-Aktionen sind.
- Task-Formulare für `native`, `visual`, `scratch` und `calliope` auf 10 sichtbare Kriterienfelder umstellen.
- Serverseitige Formularauswertung von `criteria_text` auf wiederholte `criteria[]`-Felder umstellen.

## Tests

- UI-Test für Toggle-Schließen von `Material hinzufügen` und `Aufgabe hinzufügen`
- UI-Test für 10 sichtbare Kriterienfelder
- Servertest für das Parsen von wiederholten Kriterienfeldern zu `string[]`
