# Ticket: Lernverlauf ruft Submission-API mit `course_id=undefined` auf

**Status:** offen
**Beobachtet am:** 2026-05-28
**Betroffene Umgebung:** Produktion
**Komponenten:** Learning-Frontend, Submission-History, Learning-API

## Kurzbeschreibung

Während des Unterrichtsfensters am 2026-05-28 wurde ein einzelner API-Aufruf beobachtet, bei dem das Frontend die Submission-History mit einem ungültigen Kurssegment `undefined` angefragt hat. Der Backend-Response war korrekt ein HTTP 400, aber der Client sollte solche Requests gar nicht erst absetzen.

## Beobachtung

- Im Web-Log wurde ein Requestmuster auf `/api/learning/courses/undefined/.../submissions` gezählt.
- Der Request endete mit HTTP 400.
- Im selben Unterrichtsfenster wurden alle Learning-Submissions erfolgreich verarbeitet; der Fehler scheint also kein systemischer Datenverlust zu sein.

## Technischer Befund

Mehrere Frontendpfade bauen Submission-History-URLs aus `courseId` und `taskId`.

Relevante Codepfade:

- `frontend/src/routes/learning/courses/[courseId]/units/[unitId]/+page.svelte`
- `frontend/src/lib/components/learning-unit/LearningSubmissionWorkspace.svelte`
- `frontend/src/lib/components/learning-unit/LearningUnitContentWorkspace.svelte`
- `frontend/src/lib/components/learning-unit/LearningTaskCard.svelte`

Die produktiv genutzte Lernseite gibt `data.courseId` an Arbeitsflächen und Task-Karten weiter. Der isolierte `undefined`-Aufruf deutet deshalb eher auf einen Client-State-Edge-Case hin, zum Beispiel stale component state, eine alte noch montierte Workspace-Komponente, eine Race-Condition beim Modulwechsel oder Altcode, der noch in Tests existiert und wiederverwendet werden könnte.

## Impact

- Einzelne Lernende können beim Öffnen des Verlaufs eine generische Fehlermeldung sehen.
- Die API erhält unnötige Bad-Request-Last.
- Der Fehler kann echte Auth- oder Datenprobleme verdecken, wenn er im selben Unterrichtsfenster auftritt.

## Vorschlag

- Alle clientseitigen Submission-History-Fetches vor dem Request auf gültige `courseId` und `taskId` prüfen.
- Bei fehlender `courseId` lokal abbrechen und eine recoverable UI-Meldung anzeigen, statt `/api/learning/courses/undefined/...` aufzurufen.
- Altkomponente `LearningSubmissionWorkspace.svelte` prüfen: Wenn sie nicht mehr produktiv verwendet wird, entweder entfernen oder dieselben Guards ergänzen, damit Tests keine veraltete Semantik konservieren.
- Regressionstest ergänzen, der bei fehlender `courseId` keinen Fetch absetzt.

## Akzeptanzkriterien

- Kein Frontendpfad setzt einen Submission-History-Request ab, wenn `courseId` leer, `null`, `undefined` oder der String `"undefined"` ist.
- Die UI bleibt bedienbar und zeigt eine lokale, verständliche Verlauf-Fehlermeldung.
- Backend bleibt fail-closed und gibt für ungültige Kurs-IDs weiter HTTP 400 zurück.
- Regressionstest deckt den fehlenden Kurskontext ohne Netzwerkrequest ab.
