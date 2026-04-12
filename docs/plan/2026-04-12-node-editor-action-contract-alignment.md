# Teaching-Node-Editor: Action-Contract angleichen und Live-Update reparieren

## Zusammenfassung
- Root Cause ist ein inkonsistenter SvelteKit-Action-Contract im Node-Editor.
- Der Teaching-Workspace liefert Success-Responses pro Action namespaced zurück; der Node-Editor liefert Success aktuell flach.
- Dadurch erkennt `+page.svelte` erfolgreiche Aktionen nicht zuverlässig, aktualisiert den Editor nicht live und räumt vorbereitete Upload-Zustände nicht auf.

## User Story
- Als Lehrkraft möchte ich nach dem Anlegen, Bearbeiten, Löschen oder Umordnen von Materialien und Aufgaben sofort den aktualisierten Zustand im Node-Editor sehen, ohne die Seite neu laden zu müssen.

## BDD-Szenarien
- Given ein erfolgreich angelegtes Datei-Material, when die Create-Action erfolgreich zurückkehrt, then erscheint das Material sofort in der Liste, wird geöffnet und der vorbereitete Upload-Zustand verschwindet.
- Given ein erfolgreich angelegtes Markdown-Material, when die Create-Action erfolgreich zurückkehrt, then erscheint das Material sofort in der Liste ohne manuellen Reload.
- Given eine erfolgreich gespeicherte oder gelöschte Aufgabe oder ein erfolgreich gespeichertes Material, when die jeweilige Action erfolgreich zurückkehrt, then übernimmt der Node-Editor den neuen `editor`-State unmittelbar.
- Given ein Fehler bei einer Action, when die Action mit `fail(...)` zurückkehrt, then bleiben Error- und Value-Handling namespaced pro Action erhalten.

## Implementierungsentscheidungen
- Der Node-Editor übernimmt denselben Success-Contract wie `teaching/units/[unitId]`:
  - `saveMaterial: { ok, message, editor, ... }`
  - `createMaterial: { ok, message, editor, ... }`
  - analog für Node-, Material- und Task-Actions.
- `+page.svelte` bleibt auf `form.<actionName>` ausgerichtet; geändert wird der Server-Return-Shape, nicht die UI auf einen Sonderweg.
- Bei erfolgreichem Datei-Material-Create wird zusätzlich lokaler Upload-State zurückgesetzt.

## Testplan
- `page.server.test.ts` prüft namespaced Success-Responses für `createMaterial` und mindestens eine weitere Node-Editor-Action.
- `page-interaction.test.ts` prüft, dass ein erfolgreicher `createMaterial`-Submit sofort Success-Message und Material rendert und kein vorbereiteter Upload-Hinweis stehen bleibt.
- Danach gezielte `frontend`-Tests für Node-Editor-Server, Interaction und Contract.
