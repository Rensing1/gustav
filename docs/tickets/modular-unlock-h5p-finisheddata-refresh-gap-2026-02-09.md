# Ticket: Modularer Graph aktualisiert nicht zuverlässig nach H5P-Abschluss (finishedData vs. xAPI)

## Datum
2026-02-09

## Zusammenfassung
Im modularen Schueler-Workspace werden neu freigeschaltete Module nach H5P-Abschluss weiterhin nicht immer sofort als `offen` angezeigt. Der Graph aktualisiert sich in diesen Faellen erst nach einem manuellen Reload.

Die Analyse zeigt: Der aktuelle Frontend-Fix triggert den Graph-Refresh nur im Browser-`xAPI`-Pfad. Die Freischaltung entsteht jedoch haeufig ueber den serverseitigen H5P-`finishedData`-Pfad. Dann fehlt im Browser das `modularGraphRefresh`-Event.

## Impact
- Schueler sehen einen veralteten Modulstatus trotz bereits erfolgter Freischaltung.
- UX wirkt inkonsistent (Backend-Status korrekt, UI-Status stale).
- Erhoehtes Risiko fuer Mehrfachklicks/Reloads und Verwirrung im Unterricht.

## Reproduktion (PII-frei)
1. Modulare Unit mit Kante `A -> B` oeffnen, wobei `A` eine H5P-Aufgabe ist.
2. H5P in `A` abschliessen.
3. Beobachten: `B` bleibt in manchen Faellen im aktuellen View als gesperrt sichtbar.
4. Seite neu laden: `B` erscheint als offen.

## Verifizierte Befunde
- Der Listener fuer UI-Refresh sitzt auf `modularGraphRefresh`:
  - `backend/web/static/js/student_modular_workspace.js:798`
- Der H5P-Player emittiert `modularGraphRefresh` nur nach erfolgreichem Browser-`xAPI`-Submit:
  - `backend/web/static/js/h5p_task_player.js:155`
  - `backend/web/static/js/h5p_task_player.js:163`
  - `backend/web/static/js/h5p_task_player.js:165`
- Architektur/Plan dokumentiert `finishedData` als Primaersignal, weil `xAPI` im Browser nicht immer zuverlaessig ankommt:
  - `docs/plan/2025-12-15-h5p-integration.md:356`
- E2E deckt den serverseitigen `finishedData`-Persistenzpfad explizit ab:
  - `backend/tests_e2e/test_h5p_finisheddata_origin_null_e2e.py:291`
- Live-Log-Befund (docker-intern, IPs weggelassen):
  - `POST /api/learning/.../submissions` kommt vom H5P-Service (Container `gustav-h5p`).
  - `GET /api/learning/.../modules/graph` kommt vom Browser (via Caddy).
  - Daraus folgt: Submissions werden oft serverseitig erzeugt, ohne Browser-`xAPI`-Trigger.

## Root Cause
Der UI-Refresh ist an einen nicht-kanonischen Trigger gekoppelt:
- implementiert: Browser-`xAPI`-Event -> `submitAttempt` -> `modularGraphRefresh`
- tatsaechlicher dominanter Persistenzpfad: `finishedData` serverseitig (H5P-Service)

Wenn `finishedData` die Submission/Freischaltung erzeugt und kein passendes `xAPI`-Event im Browser durchlaeuft, bleibt die UI bis zum Reload stale.

## Erwartetes Verhalten
Nach erfolgreicher H5P-Abgabe (unabhaengig davon, ob via Browser-`xAPI` oder serverseitig via `finishedData`) muss der modulare Graph im gleichen View aktualisiert werden, ohne Reload.

## Umsetzungsvorschlag
1. Eventing robust machen:
   - Einen zuverlaessigen Refresh-Trigger nach dem serverseitigen `finishedData`-Erfolg in die Schueler-UI rueckfuehren.
2. Optional zusaetzlich Poll/Fallback:
   - Kurzes, gedrosseltes `refreshGraphRuntime()` nach H5P-Abschluss, falls kein Event ankommt.
3. Deduplizierung:
   - Mehrfach-Trigger (xAPI + finishedData) idempotent behandeln, damit keine Event-Stuermung entsteht.

## Akzeptanzkriterien
1. Nach H5P-Abschluss wird der Graph ohne Reload aktualisiert, auch wenn die Submission nur ueber `finishedData` entsteht.
2. Neu freigeschaltete Module erscheinen im aktuellen View unmittelbar als `offen`.
3. Kein Regression im bestehenden HTMX-Submit-Flow.
4. Keine unkontrollierten Mehrfach-Refreshes bei schnellen Folge-Events.

## Testbedarf
- Integrationstest fuer den `finishedData`-Pfad + UI-Refresh (nicht nur Source-String-Contract).
- Regressionstest: bestehender `xAPI`-Pfad bleibt funktionsfaehig.
- Negativfall: fehlgeschlagener Persistenzpfad darf keinen false-positive Unlock-Refresh anzeigen.

## Hinweis zu bestehenden Tests
Der aktuelle Test `backend/tests/test_h5p_task_player_refresh_event_contract.py` ist ein Source-Contract (String-Guard) und prueft das Laufzeitverhalten ueber `finishedData` nicht.
