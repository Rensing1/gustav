# 2026-04-13 - `/live` app-artig aktualisieren und Namenspriorität korrigieren

Status: geplant
Datum: 2026-04-13

## Kontext

- Die kanonische Lehrkraft-Ansicht für den Live-Unterricht ist inzwischen `/live`.
- Kurs- und Lerneinheitswechsel laufen dort schon per `goto()`, aber Klicks auf Schüler- und Aufgabenlinks lösen weiterhin eine vollständige Loader-Navigation aus.
- Die Seite fühlt sich dadurch weniger wie ein zusammenhängender Arbeitsraum an, obwohl Tabelle und Detailpanel bereits als gemeinsames Dashboard-Read-Model vorliegen.
- Zusätzlich zeigt `/live` in der Tabelle heute nicht zuverlässig Vor- und Nachname. Fachlich soll dort zuerst der Personenname erscheinen; der technische Mail-Localpart bleibt nur Fallback.
- Für Live-Updates existiert bereits ein Delta-Endpunkt im Teaching-Kontext. Das Top-Level-Dashboard `/live` nutzt ihn bisher aber noch nicht.

## Ziel

- `/live` aktualisiert die Tabelle automatisch.
- Ein offenes Schülerdetail bleibt bei den Live-Aktualisierungen mit aktuell.
- Klicks auf Schülernamen und Aufgabenleisten wirken app-artig und laden nicht mehr die gesamte Seite neu.
- Die Tabelle zeigt primär `Vorname Nachname`; nur wenn beide fehlen, fällt `/live` auf den Mail-Localpart zurück.

## Nicht-Ziele

- keine Änderung am öffentlichen OpenAPI-Vertrag
- keine Datenbankschema- oder Migrationsänderung
- keine Umstellung der älteren `/live/courses/...`-Seiten
- keine globale Änderung der Namenssemantik in allen Teaching-Live-Endpunkten

## User Story

Als Lehrkraft
möchte ich in `/live` ohne Seiten-Neuladungen zwischen Lernenden und Aufgaben wechseln
und gleichzeitig korrekte Personennamen sehen,
damit ich den Unterrichtsstand wie in einer zusammenhängenden App beobachten kann.

## BDD-Szenarien

1. Namen in der Tabelle
   - Given für einen Lernenden sind `firstName` und `lastName` vorhanden
   - When `/api/live/views/.../dashboard` die Tabellenzeile rendert
   - Then verwendet `/live` genau `Vorname Nachname`
   - And nicht den technischen Localpart

2. Fallback bei fehlendem Personenname
   - Given für einen Lernenden fehlen `firstName` und `lastName`
   - When `/api/live/views/.../dashboard` die Tabellenzeile rendert
   - Then verwendet `/live` den Mail-Localpart
   - And bleibt bei fehlenden Directory-Daten benutzbar

3. Klick auf Schülerzeile
   - Given `/live` ist mit geladener Tabelle geöffnet
   - When die Lehrkraft auf einen Schüler klickt
   - Then lädt nur der Workspace-Zustand nach
   - And die URL wird ohne vollständige Navigation synchronisiert

4. Klick auf Aufgabenleiste
   - Given im Detailpanel ist ein Lernender geöffnet
   - When die Lehrkraft eine andere Aufgabe in der Aufgabenleiste klickt
   - Then aktualisiert sich nur das Detailpanel im selben Workspace
   - And der Sortierzustand der Tabelle bleibt erhalten

5. Automatische Aktualisierung
   - Given `/live` zeigt eine gewählte Kurs-Lerneinheit
   - When der Delta-Endpunkt eine Änderung meldet
   - Then lädt das Dashboard mit aktueller `student_sub`/`task_id`-Auswahl nach
   - And Tabelle und offenes Detail sind wieder konsistent

6. Keine Änderungen seit letztem Cursor
   - Given der Delta-Endpunkt antwortet mit `204`
   - When das Polling ausgeführt wird
   - Then bleibt der lokale Workspace-Zustand unverändert
   - And es wird kein unnötiger Dashboard-Reload ausgelöst

## Technischer Plan

1. Backend: gezielte Namensauflösung nur für `/live`
   - Im App-Read-Model für `/api/live/views/.../dashboard` eine eigene Helper-Auflösung für sichtbare Namen einführen.
   - Priorität: `firstName + lastName` -> Localpart aus `email`/`username` -> `Unbekannt`.
   - `display_name` wird in diesem Helper bewusst ignoriert.

2. Frontend: SSR-Bootstrap + lokaler Workspace-State
   - Die Seite behält SSR für den initialen Aufruf und tiefe Links.
   - Nach dem ersten Rendern verwaltet die Komponente das Dashboard lokal weiter.
   - Schüler- und Aufgabenklicks laden das Dashboard per Fetch nach und synchronisieren nur die URL.

3. Polling
   - `/live` pollt den bestehenden Teaching-Delta-Endpunkt im konfigurierbaren Intervall.
   - Bei `200` wird der Cursor fortgeschrieben und das Dashboard mit der aktuellen Auswahl neu geladen.
   - Bei `204` bleibt der Zustand unverändert.

4. Konfiguration
   - Das Polling-Intervall wird serverseitig aus `GUSTAV_TEACHING_LIVE_POLL_INTERVAL_SECONDS` in die Page-Daten injiziert.
   - `.env.example` dokumentiert die Variable.

## Tests

- `backend/tests/test_live_view_api.py`
  - Dashboard priorisiert `Vorname Nachname`.
  - Dashboard fällt auf Localpart zurück.
  - `display_name` wird für `/live` nicht bevorzugt.
- `frontend/src/routes/live/page-interaction.test.ts`
  - Schülerklick aktualisiert nur den Workspace-Zustand.
  - Aufgabenklick hält den Sortierzustand.
  - Polling ignoriert `204` und lädt bei `200` das Dashboard nach.
  - ältere Antworten dürfen neuere Klicks nicht überschreiben.
- `backend/tests/packaging/test_sveltekit_live_dashboard_contract.py`
  - prüft die neuen Workspace-/Polling-Helfer im SvelteKit-Page-Source.

## Verifikation

```bash
.venv/bin/pytest -q backend/tests/test_live_view_api.py backend/tests/packaging/test_sveltekit_live_dashboard_contract.py
(cd frontend && npm test -- src/routes/live/page-interaction.test.ts)
```
