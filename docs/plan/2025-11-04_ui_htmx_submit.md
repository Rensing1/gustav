# Plan: HTMX-Submit für Lernaufgaben (UI)

Datum: 2025-11-04
Autor: Lehrkraft-Dev

## User Story

Als Schüler möchte ich meine Lösung (Text oder Upload) abgeben, ohne dass die
gesamte Seite neu lädt, damit ich in der Aufgabe bleibe. Nach der Abgabe soll
der Verlauf automatisch aktualisiert werden, solange die Vision-Extraktion und
die KI-Auswertung noch laufen. Sobald das Ergebnis da ist, soll es ohne Reload
sichtbar werden.

## BDD-Szenarien

- Given eine Aufgabenkarte, When ich Text abgebe, Then sendet das Formular via
  HTMX und der Aufgabenverlauf aktualisiert sich inline; While pending, pollt
  der Verlauf alle 2s bis completion; And es erscheint eine Erfolgsnachricht.
- Given Upload-Modus mit vorbereiteten Hidden-Fields, When ich abgebe, Then
  Verhalten wie oben (inline-Update + ggf. Polling).
- Given neuester Versuch ist bereits completed, Then kein Polling (keine
  `hx-trigger`-Attribute) im Verlauf.
- Given kein HTMX (Progressive Enhancement), When ich abgebe, Then PRG (303) auf
  die Einheitenseite mit Banner und `open_attempt_id`.
- Given API-Fehler, Then UI zeigt Fehlermeldung via `HX-Trigger` und ersetzt den
  Verlauf nicht.

## API-Vertrag (openapi)

Keine Änderungen am API-Vertrag erforderlich. Die SSR-Schicht (Web-UI) tauscht
nur die Abgabe-Mechanik clientseitig (HTMX) aus und konsumiert bestehende
Endpoints:

- POST `/api/learning/courses/{course_id}/tasks/{task_id}/submissions`
- GET  `/api/learning/courses/{course_id}/tasks/{task_id}/submissions`

## Datenbank / Migration

Keine Änderungen am Schema notwendig.

## Testentwurf (TDD)

- test_unit_task_form_has_htmx_attributes: Form enthält `hx-post`, `hx-target`
  (auf History-Fragment) und `hx-swap="outerHTML"`.
- test_htmx_submit_returns_history_fragment_and_message: HTMX-POST liefert
  HTML-Fragment des Verlaufs inkl. Polling-Attributen und `HX-Trigger` für
  Success.
- test_non_htmx_submit_keeps_prg: Ohne HTMX bleibt PRG-Redirect erhalten.

## Umsetzung (minimal)

- Formular in der Aufgabenkarte um HTMX-Attribute erweitert
  (`hx-post`, `hx-target`, `hx-swap`).
- Verlauf-Wrapper erhält stabiles `id="task-history-{task_id}"` (TaskCard,
  Placeholder, Fragment-Endpoint).
- Submit-Handler erkennt `HX-Request` und liefert direkt das History-Fragment
  (mit Polling bei pending) sowie `HX-Trigger` für eine Erfolgsnachricht.
- Nicht-HTMX: unverändert PRG.

## Sicherheit

- Same-Origin-Check bleibt vor POST erhalten.
- API bleibt der Ort der Autorisierung (RLS, Sichtbarkeit, Versuchs-Limits).

## Offene Punkte / Nice-to-have

- Visueller Ladespinner im Verlauf während Polling.
- Exponentielles Backoff/Timeout für Polling.
- Vereinheitlichung der Upload-Enhancement-Logik in `learning_upload.js` vs.
  allgemeinem Init in `gustav.js`.

