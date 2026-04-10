# ADR: Objekte schreiben, Räume lesen

Datum: 2026-03-23

## Status

Akzeptiert

## Entscheidung

GUSTAV trennt zwischen objektorientierten Kernverträgen und expliziten
raumbezogenen Read-Models:

- Objektverträge: `courses`, `units`, `tasks`, `memberships`, `releases`,
  `submissions`
- Raumverträge: `session-bootstrap`, `learner-home`, `teacher-home`,
  `course-context-view`, `diagnostics-*`, `live-*`

## Begründung

- Dieselben Fachobjekte werden in unterschiedlichen Produkträumen verschieden
  zusammengesetzt.
- Alte SSR-Pfade haben Objektdaten und Oberflächenlogik zu stark vermischt.
- Dedizierte Read-Models halten `SvelteKit` schlank und verhindern, dass
  Objekt-APIs mit UI-spezifischen Payloads überladen werden.

## Konsequenzen

- Neue Raumdaten kommen als eigene API-Endpunkte in `api/openapi.yml`.
- Objekt-APIs bleiben Quelle der Wahrheit für CRUD, Validierung und Mutationen.
- `SvelteKit` setzt komplexe Räume aus Read-Models und Mutationsaufrufen
  zusammen.

