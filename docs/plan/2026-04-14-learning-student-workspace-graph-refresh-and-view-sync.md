# Lernraum: Graph-Refresh und View-Sync im Schüler-Workspace

## Ausgangslage

Im modularen Lernraum traten zwei gekoppelte Probleme auf:

1. Nach erfolgreichem Abschluss eines Moduls wurde das nächste Modul im Graphen nicht sofort freigeschaltet.
2. Nach einem manuellen Reload sprang der Workspace vom Graphen zurück in die Inhaltsansicht.

Beides führte zu unnötiger Reibung im Schüler-Flow.

## Ursachen

### 1. Veralteter Graph-Zustand im Client

Die Seite arbeitete nach dem Initial-Load weiterhin gegen `data.graph`. Fortschrittsänderungen aktualisierten zwar Submission-Historie und Statusmeldungen, aber nicht den Graph-Zustand des Workspace. Dadurch blieb der Unlock-Status im UI veraltet, bis ein kompletter Reload stattfand.

### 2. URL kodierte nur das Modul, nicht die sichtbare Ansicht

Der Workspace persistierte den `module`-Query-Parameter, auch wenn der Schüler wieder in die Graph-Ansicht gewechselt hatte. Beim nächsten Server-Load wurde dieser Parameter erneut als aktives Modul interpretiert. Das führte dazu, dass der Workspace wieder in `content` startete.

### 3. H5P meldete erfolgreiche Persistierung nicht an den Workspace zurück

H5P-Aufgaben speicherten den Fortschritt, hatten aber keinen expliziten Callback zurück an den Seitenzustand. Dadurch blieb auch dort der Graph bis zum Reload veraltet.

## Zielbild

- Der modulare Workspace besitzt einen eigenen clientseitigen `graphState`.
- Nach jeder erfolgreichen Fortschrittspersistierung wird der aktuelle Modulgraph mit `cache: "no-store"` neu geladen.
- Die URL beschreibt explizit die sichtbare Ansicht über `view=overview|content`.
- Legacy-Links mit nur `?module=` bleiben kompatibel.

## Umsetzung

### Red

Ergänzte Tests:

- `workspace.test.ts`
  - Reconciliation entfernt gesperrte Tabs.
  - Explizite `overview`-Anforderung überschreibt stale lokalen Content-State.
  - Content-Tabs werden nach Graph-Reihenfolge sortiert.
- `page.server.test.ts`
  - `view=overview&module=...` lädt kein Modul vor.
  - Legacy-Link `?module=...` bleibt ein valider Einstieg in die Inhaltsansicht.
- `H5PTaskPlayer.test.ts`
  - Erfolgreich persistierte H5P-Versuche triggern genau einen Workspace-Callback.

### Green

Implementierte Änderungen:

- Reine Helper-Funktion `reconcileModularWorkspaceState(...)` in `workspace.ts`.
- `initialView` im Server-Load, inklusive Legacy-Fallback.
- Clientseitiger `graphState` statt dauerhafter Bindung an `data.graph`.
- Gekapselter `refreshModularGraph()`-Pfad mit koaleszierten parallelen Requests.
- URL-Sync über `view` und optional `module`.
- Refresh nach:
  - erfolgreicher Finalisierung,
  - erfolgreicher Feedback-Erstellung vor dem Polling,
  - erfolgreichem Abschluss des Feedback-Pollings,
  - erfolgreicher Upload-Submission,
  - erfolgreicher H5P-Persistierung.

### Refactor

- Workspace-Reconciliation ist jetzt als pure Funktion testbar.
- View-Sync und Modul-Sync laufen über einen gemeinsamen URL-Helper.
- H5P kommuniziert Fortschrittsänderungen explizit statt implizit.

## Verifikation

Erfolgreich ausgeführt:

- `npm test -- --run src/lib/learning-unit/workspace.test.ts src/routes/learning/courses/[courseId]/units/[unitId]/page.server.test.ts src/lib/components/H5PTaskPlayer.test.ts src/routes/learning/courses/[courseId]/units/[unitId]/page-contract.test.ts src/lib/components/learning-unit/LearningUnitContentWorkspace.test.ts`

Ergebnis:

- 5 Testdateien grün
- 33 Tests grün

## Offene Punkte außerhalb dieses Fixes

`npm run check` bleibt aktuell wegen bereits bestehender, fachfremder TypeScript-/Svelte-Fehler rot, unter anderem in:

- `src/lib/utils/submission-artifacts.test.ts`
- `src/routes/teaching/units/[unitId]/nodes/[nodeId]/+page.server.ts`
- `src/routes/teaching/units/[unitId]/nodes/[nodeId]/+page.svelte`
- `src/routes/teaching/units/[unitId]/+page.svelte`

Diese Fehler wurden durch den vorliegenden Lernraum-Fix nicht verursacht.
