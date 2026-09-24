# H5P-Rückmeldung und eindeutiger Abschlussstatus

## User Story

Als Schüler möchte ich die H5P-interne Rückmeldung in Ruhe lesen und eindeutig erkennen, ob eine Aufgabe nur bearbeitet oder mit voller Punktzahl abgeschlossen ist, damit ich die Freischaltung des nächsten Moduls nachvollziehen kann.

## Befunde

- Im Übungsmodul invalidiert der Client direkt nach einer gespeicherten H5P-Abgabe die Seite. Dadurch wird der Player mit seiner internen Rückmeldung sofort durch die allgemeine Practice-Rückmeldung ersetzt.
- Die Freischaltlogik zählt eine H5P-Aufgabe erst bei `score_raw = score_max` als abgeschlossen.
- Lernenden-Tasks liefern bisher nur `has_submission`; die Oberfläche kann Bearbeitung und Abschluss daher nicht unterscheiden.
- Die Abgabenvorschau bezeichnet jeden H5P-Versuch als abgegeben, obwohl ein Teilversuch das Folgemodul nicht freischaltet.

## BDD-Szenarien

1. **Lesbare H5P-Rückmeldung:** Given eine H5P-Aufgabe in einem Übungsmodul, when der Schüler die Antwort prüfen lässt, then bleiben Player und H5P-Rückmeldung sichtbar, bis er bewusst zur nächsten Aufgabe weitergeht.
2. **Speicherfehler:** Given eine fehlgeschlagene H5P-Submission, when H5P ein Abschlussereignis sendet, then erscheint eine Fehlermeldung und keine Weiter-Aktion.
3. **Teilversuch:** Given ein H5P-Ergebnis von 0/1, when der Schüler die Modulübersicht sieht, then wird die Aufgabe als noch nicht abgeschlossen angezeigt und das Folgemodul bleibt gesperrt.
4. **Vollständiger Versuch:** Given ein H5P-Ergebnis von 1/1, when die Submission gespeichert wurde, then wird die Aufgabe als abgeschlossen angezeigt und das Folgemodul öffnet sich ohne Seitenreload.
5. **Dauerhafter Abschluss:** Given ein voller und danach ein unvollständiger Versuch, when der Task-Status gelesen wird, then bleibt der Abschluss erhalten und der neueste Punktestand wird separat angezeigt.
6. **Keine Bearbeitung:** Given keine H5P-Submission, when ein Task gelesen wird, then ist `h5p_completed=false` und der Punktestand leer.
7. **Bestehende Grenzen:** Given eine Nicht-H5P-Aufgabe oder ein unberechtigter Benutzer, when Inhalte gelesen werden, then bleiben Darstellung und fail-closed Zugriff unverändert.

## Umsetzung

1. `LearningTask` wird contract-first um `h5p_completed`, `score_raw` und `score_max` erweitert.
2. Die bestehende Submission-Summary-Abfrage liefert den neuesten H5P-Punktestand und aggregiert, ob jemals volle Punktzahl erreicht wurde.
3. Eine gemeinsame Frontend-Funktion trennt Bearbeitung und Abschluss. Task-Zeile und Abgabenvorschau verwenden dieselbe Semantik.
4. Practice-H5P hält den Player nach erfolgreicher Speicherung sichtbar, lädt die dauerhafte Practice-Rückmeldung nach und bietet erst dann die bewusste Weiter-Aktion an.
5. Mehrere xAPI-Ereignisse derselben Practice-Präsentation erzeugen keinen zweiten Abschluss.

Es sind weder neue Endpunkte noch Schemaänderungen erforderlich. Daher wird keine Migration angelegt.

## Tests und Abschluss

- OpenAPI-Vertragstest und DB-Integrationstest für H5P-Status und neuesten Punktestand.
- Frontend-Unit-Tests für Abschlusshelfer, Task-Zeile, Abgabenvorschau und Practice-Player-Lebenszyklus.
- Authentifizierte Playwright-Spec `h5p-learner-feedback-progress.spec.ts` für Practice-Rückmeldung und modulare Freischaltung.
- Abschluss mit `make verify-feature FEATURE=h5p-learner-feedback-progress`.
