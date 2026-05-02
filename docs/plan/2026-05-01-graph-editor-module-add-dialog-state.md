# Graph-Editor: Modul-Hinzufügen ohne Reload

Status: umgesetzt; `svelte-check` ist durch bestehende Fremdfehler außerhalb des Graph-Editors blockiert

## Ziel

- Im Graph-Editor soll der Klick auf `Modul hinzufügen` den Dialog sofort öffnen.
- Ein Seiten-Reload darf nicht mehr nötig sein.
- Fachliche Auswahl im Graphen bleibt stabil; temporäre Dialoge werden lokal gesteuert.

## Ursache

- Der ursprüngliche Editor leitete Dialogzustände aus `window.location.href` ab.
- Diese URL-Lesung ist in Svelte nicht reaktiv.
- Zusätzlich umgeht direkter Zugriff auf `window.history.replaceState(...)` den SvelteKit-Router.
- Dadurch kann die URL sichtbar aktualisiert sein, ohne dass der Dialog gerendert wird.
- Folgefund nach dem ersten Fix: Die `createModule`-Action liefert zwar eine frische Workspace-View, aber der Client kann diese wieder durch stale `data.workspace`-Load-Daten überschreiben.
- Der zwischenzeitliche Remount-Fix war fehlerhaft: `{#key flowRenderKey}` mountet den kompletten SvelteFlow-Canvas neu und kann dessen internen Viewport-/Node-State nach dem Anlegen eines Moduls destabilisieren.
- `rebuildFlow(...)` läuft asynchron; ohne Sequenzschutz kann ein älterer Layout-Lauf neuere Node-/Edge-Daten überschreiben.
- Zweiter Folgefund: Nach erfolgreicher `createModule`-Action wird der frische Action-Workspace direkt wieder durch den schon vorhandenen `data.workspace`-Load-Workspace überschrieben. Sichtbares Symptom: Erfolgsmeldung erscheint, der Dialog schließt, aber das neue Modul fehlt und Module sind nicht anklickbar.
- Dritter Folgefund: Der Marker für angewendete Load-Daten darf nicht auf Action-Workspaces gesetzt werden. Sonst wird der alte Load-Workspace wieder als neu betrachtet und überschreibt den frischen Action-Workspace.
- Vierter Folgefund: Das gleiche Überschreiben betrifft auch `deleteModule` und grundsätzlich alle mutierenden Graph-Actions, weil sie alle über `applyWorkspaceUpdate(...)` laufen.
- Architekturentscheidung für den finalen Fix: Nach mutierenden Graph-Actions gibt es nur noch eine autoritative Quelle für den Graph-Zustand: `data.workspace` aus dem SvelteKit-Route-Load. Actions liefern keine parallele Workspace-Kopie mehr, sondern nur `ok`, `message` und `next`. Der Client patcht zuerst die URL und invalidiert danach die Route.
- Fünfter Folgefund nach Browser-Verifikation: Das neue Modul erscheint sofort und der Dialog schließt, aber danach ist der SvelteFlow-Canvas unresponsiv. Module lassen sich nicht anklicken und der Graph lässt sich nicht mehr mit der Maus verschieben.
- Wahrscheinliche Ursache: Der Action-Erfolg verarbeitet `next` aktuell doppelt und hält zusätzlich einen eigenen `currentHref`-Cache neben dem SvelteKit-Router. Dadurch können URL-State, Route-Invalidierung und der gemountete SvelteFlow-Canvas nach einer Mutation auseinanderlaufen.
- Review-Nacharbeit: Erfolgreiche Graph-Actions dürfen SvelteKits `form`-State nicht umgehen. Sonst können alte Validierungsfehler nach einem korrigierten Submit erneut sichtbar werden. Der stabile Pfad ist: URL anhand von `next` patchen, Success-Result mit `applyAction(result)` in den Form-State übernehmen, danach die Route explizit invalidieren.
- Review-Nacharbeit: Der Workspace-Sync darf keinen zweiten Flow-Rebuild planen. Ein zentraler Rebuild-Effect reicht aus und verhindert unnötige parallele Layout-Läufe.
- Review-Nacharbeit: Der Guard gegen doppelte Formverarbeitung darf selbst nicht reaktiv sein. Ein `$state`-Guard im Form-Effect kann nach Action-Fehlern eine Svelte-Effect-Schleife auslösen.

## User Story

Als Lehrkraft möchte ich im Graph-Editor per erstem Klick auf `Modul hinzufügen` sofort das Formular sehen, damit ich Module ohne Hard Reload anlegen kann.

## BDD-Szenarien

- Given eine Lehrkraft ist in einer modularen Lerneinheit im Graph-Editor, When sie in der Commandbar `Modul hinzufügen` klickt, Then erscheint der Dialog sofort ohne Reload.
- Given eine Phase ist ausgewählt, When die Lehrkraft aus dem Inspector `Modul hinzufügen` öffnet, Then bleibt die Phase als vorausgewählte Phase erhalten.
- Given der Dialog ist geöffnet, When die Lehrkraft `Schließen` klickt, Then verschwindet der Dialog sofort.
- Given ein Modul wurde erfolgreich angelegt, When die Action-Antwort verarbeitet wird, Then verschwindet der Dialog und das neue Modul ist ausgewählt.
- Given ein Modul wurde erfolgreich angelegt, When die Action-Antwort verarbeitet wird, Then erscheint das neue Modul ohne Page Reload sichtbar im Graph.
- Given ein Modul wurde erfolgreich gelöscht, When die Action-Antwort verarbeitet wird, Then verschwindet das Modul ohne Page Reload aus dem Graph und die verbleibenden Module bleiben anklickbar.
- Given eine beliebige Graph-Action ist erfolgreich, When der Client die Antwort verarbeitet, Then lädt der Graph seine neue Struktur ausschließlich über die Route-Invalidierung aus `data.workspace`.
- Given ein Modul wurde erfolgreich angelegt, When das neue Modul sichtbar ist, Then bleiben Module anklickbar und der Graph bleibt per Maus verschiebbar.
- Given die Seite wird direkt mit `?create-module=1` geöffnet, Then rendert der Dialog initial weiterhin.

## Umsetzung

- `frontend/src/routes/teaching/units/[unitId]/+page.svelte`
  - Lokalen State für Create-Dialoge einführen: `createPhaseOpen`, `createModuleOpen`, `createSectionOpen`.
  - Initialwerte aus `data.showCreate*Dialog` übernehmen, damit vorhandene Direktlinks beim ersten Laden nicht brechen.
  - Commandbar-Aktionen und Inspector-Aktion auf lokale Button-Handler umstellen.
  - Beim Öffnen von `Modul hinzufügen` die aktuell ausgewählte Phase über `selectedPhaseId()` als Default verwenden.
  - Nach erfolgreicher Graph-Action nur `message` und `next` auswerten; die neue Workspace-Struktur kommt anschließend aus `data.workspace`.
  - `enhanceGraphForm(...)` patcht bei Erfolg die URL anhand von `next`, schließt betroffene lokale Create-Dialoge sofort, übernimmt den Success-Result mit `applyAction(result)` und ruft danach `invalidateAll()` auf. Dadurch nutzt die Route die bereits gepatchte URL und alte `form`-Fehler werden durch den neuen Action-Result ersetzt.
  - `applyWorkspaceUpdate(...)`, `lastAppliedLoadWorkspace` und der Action-Workspace-Reconcile werden entfernt.
  - Drag-Reorder und Edge-Create nutzen denselben `reloadWorkspace(next)`-Pfad: URL patchen, `invalidateAll()` ausführen, dann reagiert der `data.workspace`-Effect.
  - Keinen SvelteFlow-Remount erzwingen; der Canvas bleibt gemountet und erhält kontrolliert neue `nodes`/`edges`.
  - `rebuildFlow(...)` mit einem Sequenzzähler absichern, damit ältere asynchrone Layout-Ergebnisse nicht nachträglich den aktuellen Graph überschreiben.
  - Follow-up: `success.next` nur noch an einer Stelle für URL-Patches verarbeiten. Der Enhance-Handler patcht die URL vor der Standard-Invalidierung; der Form-Effect zeigt danach Meldungen und verarbeitet No-JS-/Fallback-Erfolge.
  - Follow-up: Den lokalen `currentHref`-Cache entfernen. URL-Hilfsfunktionen lesen aus `page.url` und bekommen bei Bedarf eine explizite Basis-URL, damit keine Svelte-Effect-Schleife einen gerade gepatchten URL-Stand überschreibt.
  - Follow-up-Fallback: Falls SvelteFlow nach der URL-Bereinigung weiterhin unresponsiv bleibt, gezielten Canvas-Reset nur nach Workspace-Identitätswechsel einführen und den Viewport vorher sichern.
  - Fachliche Auswahl (`section`, `phase`, `module`, `edgeFrom`, `edgeTo`) bleibt URL-synchronisiert.
  - Direkte `window.history.replaceState(...)`-Nutzung entfernen.
  - Review-Fix: Der `data.workspace`-Effect setzt nur Workspace, Selection und Viewport-Reset-Marker. Der zentrale Rebuild-Effect ist der einzige automatische Pfad, der `scheduleFlowRebuild(...)` aufruft.
  - Review-Fix: `handledForm` ist ein nicht-reaktiver lokaler Guard, damit der Form-Effect nicht durch seine eigene Guard-Aktualisierung erneut getrieben wird.

- `frontend/src/lib/components/teacher-unit-graph/TeacherGraphCommandBar.svelte`
  - Aktionen mit `onClick` als Button rendern.
  - Link-Aktionen für echte Navigation weiterhin unterstützen.

- `frontend/src/lib/components/teacher-unit-graph/GraphUnitNode.svelte`
  - Lokale `enhanceGraphForm`-Implementierung entfernen.
  - Quick-Edit- und Delete-Forms nutzen `data.enhanceGraphForm`.

- `frontend/src/lib/components/teacher-unit-graph/TeacherGraphEdge.svelte`
  - Lokale `enhanceGraphForm`-Implementierung entfernen.
  - Edge-Delete-Form nutzt `data.enhanceGraphForm`.

- `frontend/src/routes/teaching/units/[unitId]/+page.server.ts`
  - Graph-Actions geben keine `workspace`-Property mehr zurück.
  - Der nicht mehr benötigte `loadWorkspace(...)`-Helper entfällt.

## Tests

- Commandbar-Test: Eine Aktion mit `onClick` rendert einen Button und ruft den Handler beim Klick auf.
- Route-Contract-Test: Die Graph-Route nutzt lokale Create-Dialog-States und keine direkte `window.location.href`-/`window.history.replaceState`-Logik mehr.
- Route-Contract-Test: Erfolgreiche Graph-Actions aktualisieren den lokalen Workspace aus `data.workspace`, ohne den SvelteFlow-Canvas per `{#key}` neu zu mounten.
- Route-Contract-Test: Der `data.workspace`-Sync setzt keinen Action-Workspace und plant keinen zweiten Rebuild.
- Route-Contract-Test: `rebuildFlow(...)` verwirft veraltete asynchrone Layout-Ergebnisse über einen Sequenzzähler.
- Route-Contract-Test: Graph-Actions liefern keine `workspace`-Property mehr.
- Route-Contract-Test: Graph-Canvas-Forms verwenden keine `invalidateAll: false`-Option mehr. Die Node-Editor-Detailseite `nodes/[nodeId]` bleibt außerhalb dieses Graph-Canvas-Fixes und behält vorerst ihren eigenen Editor-Enhance-Pfad.
- Route-Contract-Test: Der Action-Success-Pfad patcht `next` genau einmal, übernimmt den Success-Result mit `applyAction(result)` und invalidiert danach die Route.
- Route-Contract-Test: `handledForm` bleibt nicht-reaktiv, damit Action-Fehler keine Effect-Update-Schleife auslösen.
- Component-Contract-Test: Graph-Node- und Graph-Edge-Forms verwenden den route-eigenen Enhance-Handler.
- Playwright-E2E: Der Test nutzt `WEB_BASE` und `KC_BASE`, legt über die Keycloak-Admin-Umgebung eine Lehrkraft an und seedet Login sowie modulare Einheit selbst.
- Playwright-E2E-Follow-up: Nach `Modul hinzufügen` prüft der Test zusätzlich Modul-Klickbarkeit und Pane-Drag über eine Änderung des SvelteFlow-Transforms.
- Playwright-E2E-Regression: Nach einem fehlgeschlagenen `Modul hinzufügen`-Submit verschwindet die alte Fehlermeldung nach einem erfolgreichen korrigierten Submit dauerhaft.
- Regression: Bestehende Commandbar- und WorkspaceFrame-Tests bleiben grün.

## Verifikation

- `npm --prefix frontend test -- --run src/lib/components/teacher-unit-graph/TeacherGraphCommandBar.test.ts src/routes/teaching/units/[unitId]/page-contract.test.ts src/lib/components/ui/TeacherGraphWorkspaceFrame.test.ts`
- `npm --prefix frontend run test:e2e -- teacher-graph-module-actions.spec.ts`
- `npm --prefix frontend run check`

## Annahmen

- OpenAPI, Backend und Datenbank bleiben unverändert.
- Deep-Linking für fachliche Auswahl ist weiterhin nützlich.
- Deep-Linking für temporäre Create-Dialoge ist nicht erforderlich; initiale Direktlinks werden aus Kompatibilitätsgründen weiter ausgewertet.

## Reparaturplan – 2026-05-02 14:34

- Finding `Playwright-Artefakte`: weiter offen, weil `frontend/test-results/` nach E2E-Läufen untracked erscheint. Kontext: `teaching`-Frontend, Public-Repo-Hygiene. Keine OpenAPI-, Migrations- oder Konfigurationsänderung außer `.gitignore`. Test-first: Contract-Test für `frontend/.gitignore`; minimaler Fix: `test-results/` und `playwright-report/` ignorieren; Akzeptanz: `git status --short` zeigt keine Playwright-Artefakte.
- Finding `Plandoku zu breit`: weiter offen, weil der Plan pauschal Graph-Forms nennt, während der Node-Editor außerhalb dieses Graph-Canvas-Fixes weiterhin eigene Editor-Form-Invalidierung nutzt. Kontext: `teaching`-Dokumentation. Test-first: bestehender Route-Contract bleibt auf Graph-Route begrenzt; minimaler Fix: Formulierung auf Graph-Canvas-Forms begrenzen und Node-Editor als separaten Folgepunkt benennen; Akzeptanz: Review-Aussage ist präzise.
- Finding `E2E-Doku veraltet`: weiter offen, weil `TEACHER_GRAPH_UNIT_URL` noch genannt wird, obwohl der Playwright-Test User, Login und modulare Einheit selbst seedet. Kontext: `teaching`-E2E. Test-first: bestehender E2E-Test bleibt kanonisch; minimaler Fix: Verifikationshinweise auf `WEB_BASE`, `KC_BASE`, Keycloak-Admin-Env und den konkreten Playwright-Befehl aktualisieren; Akzeptanz: Dokumentation entspricht dem Test.
- Finding `Commandbar-Typ`: Nice-to-have, aber trivial bei offenem Code. Kontext: Svelte UI im `teaching`-Frontend; Designvertrag bleibt unverändert, weil Rendering und Klassen nicht geändert werden. Test-first: bestehende Link- und Button-Tests sichern beide Varianten; minimaler Fix: `TeacherGraphCommandBarAction` als Link- oder Button-Union modellieren; Akzeptanz: TypeScript verhindert Aktionen ohne `href` und ohne `onClick`.
- Zusatzscope `svelte-check`: weiter offen, weil `submission-artifacts.test.ts` und die Node-Editor-Detailseite bestehende Union-Typen nicht sauber verengen. Kontext: `teaching`-Frontend und testnahe Darstellung von `learning`-Submission-Artefakten. Keine OpenAPI- oder Migrationsänderung. Test-first: `npm --prefix frontend run check` ist rot; minimaler Fix: Union-Narrowing im Test, Action-Result-Guards im Node-Editor und ein enger Cast für den generischen Server-Action-Erfolg; Akzeptanz: `svelte-check` läuft grün.

## Umsetzungsstand – 2026-05-02 14:38

- Geschlossen: Playwright-Artefakte sind über `frontend/.gitignore` ignoriert; `frontend/test-results/` erscheint nicht mehr in `git status --short`.
- Geschlossen: Das Plandokument grenzt `invalidateAll: false` jetzt auf Graph-Canvas-Forms ein und beschreibt den Node-Editor als separaten Pfad.
- Geschlossen: Die E2E-Dokumentation nennt nun den selbst-seedenden Playwright-Test mit `WEB_BASE`, `KC_BASE` und Keycloak-Admin-Umgebung statt `TEACHER_GRAPH_UNIT_URL`.
- Geschlossen: `TeacherGraphCommandBarAction` ist als Link- oder Button-Union typisiert; das Rendering blieb unverändert.
- Geschlossen: `svelte-check` ist grün. Die Node-Editor-Action-Daten werden über kleine Type-Guards für `error`, `material_id` und `task_id` gelesen; der Submission-Artifact-Test verengt vor Zugriff auf `html` auf `kind === "scratch"`.
- Tests: `npm --prefix frontend run check` → grün, 0 Fehler.
- Tests: `npm --prefix frontend test -- --run src/lib/test-hygiene-contract.test.ts src/lib/utils/submission-artifacts.test.ts src/lib/components/teacher-unit-graph/TeacherGraphCommandBar.test.ts src/routes/teaching/units/[unitId]/page-contract.test.ts src/lib/components/ui/TeacherGraphWorkspaceFrame.test.ts` → grün, 12 Tests.
- Tests: `npm --prefix frontend run test:e2e -- teacher-graph-module-actions.spec.ts` → grün, 1 Chromium-Test. Chromium musste außerhalb der Sandbox laufen.
- Tests: `git diff --check` → grün.
- Architektur: Änderungen bleiben im `teaching`-Frontend und in testnaher `learning`-Darstellung; keine OpenAPI-, Backend-API- oder Migrationsänderung.
- Restrisiko: Node-Editor-Verhalten wurde typseitig bereinigt, aber nicht durch einen neuen Browser-E2E erweitert. Das ist akzeptiert, weil der Fix keine Form-Invalidierungslogik ändert.
