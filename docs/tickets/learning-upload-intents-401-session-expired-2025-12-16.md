Title: Learning Uploads: Upload-Intents liefern 401 (Session abgelaufen) und UI zeigt nur „Upload fehlgeschlagen“

Status: Open

Problem:
- Datei-Uploads in der Lernansicht nutzen `POST /api/learning/courses/{course_id}/tasks/{task_id}/upload-intents`.
- Es gibt (mindestens) zwei JS-Pfade:
  - `backend/web/static/js/learning_upload.js` (Submit-Intercept) bricht bei `!intentResp.ok` ab (`preventDefault()`), ohne konkrete Erklärung/Recovery.
  - `backend/web/static/js/gustav.js` (File-Change-Prepare) zeigt bei `!intentResp.ok` eine generische Notification „Upload fehlgeschlagen. Bitte erneut versuchen.“ (`intent_failed_<status>`), ohne Hinweis auf „Session abgelaufen“ oder Auto-Redirect.
- Das Backend liefert für fehlende/abgelaufene Sessions korrekt `401 {"error":"unauthenticated"}` (Auth-Middleware in `backend/web/main.py`), daher bleibt der Upload-Flow stecken, obwohl die Seite ggf. noch offen ist.

Beobachtung (Prod, gemeldet für mathea.wolfram@gymalf.de):
- `2025-12-16T07:21:31Z` und `2025-12-16T07:21:49Z`: `POST /api/learning/courses/d6ced2b1-82a6-490c-bb0a-3d660ae4ba6f/tasks/3aea0299-9ea3-4e26-b9a7-14af6b8141f2/upload-intents` → `401 Unauthorized` (zweimal hintereinander).
- DB-Sessionstore (`public.app_sessions`) für den User-Sub `5e4d0813-4466-4b1e-9297-aa3078bbdf98` hatte zum Analysezeitpunkt keine aktive Session; letzte `expires_at` lag bei `2025-12-16 00:44:58+00` (passt zu Login-Callback `2025-12-15T23:44:58Z`).
- User-Feedback im Browser war „Upload fehlgeschlagen“ (konsistent mit `backend/web/static/js/gustav.js` Default-Error-Notification).

Impact:
- Schüler:innen können Dateien (JPG/PNG/PDF) nicht einreichen; nur Textabgaben funktionieren zuverlässig.
- Nur generische Fehlermeldung (keine klare Aktion wie „Neu einloggen“) führt zu Support-Tickets und Frust („eingeloggt, aber Upload geht nicht“), besonders bei länger geöffneten Tabs/Unterrichtssituationen.

Workaround:
- Neu einloggen (Seite neu laden, ggf. ausloggen + Cookies/Site-Data löschen) und Upload erneut starten.

Vorschlag:
1. **Frontend-Fehlerbehandlung ergänzen**: In `backend/web/static/js/learning_upload.js` bei `!intentResp.ok` differenzieren:
   - `401` → Redirect auf `/auth/login` (mit Rücksprung/`next=`) + Meldung „Sitzung abgelaufen“.
   - `403` mit `{"detail":"csrf_violation"}` → Meldung „Bitte Seite neu laden“ + optional Auto-Reload.
   - Sonst → sichtbare Fehlermeldung (Banner) mit kurzem Code.
2. **Vor dem Upload preflighten**: Optional vor `upload-intents` einmal `/api/me` abfragen; bei `401` direkt re-login statt erst beim Upload zu scheitern.
3. **Session-UX/TTL prüfen**:
   - Falls `SETTINGS.environment != "prod"` in Prod läuft: Cookie-`Max-Age` wird aktuell nicht gesetzt (`backend/web/main.py`), während DB-Sessions nach ~3600s ablaufen → Cookie kann „dranbleiben“, Server-Session aber nicht (führt zu „scheinbar eingeloggt“). Entweder `SETTINGS.environment` in Prod sauber auf `prod` setzen oder `Max-Age` immer an `ttl_seconds` koppeln.
   - Optional Sliding Sessions/Refresh (Expiry bei Aktivität verlängern) oder längere TTL für Unterrichts-Use-Cases.
4. **Observability**: Zähler/Alarm für `upload-intents`-401/403, damit es im Betrieb schneller auffällt.

Offene Fragen:
- Welche Session-TTL ist für reale Unterrichtsszenarien sinnvoll (1h vs. 4–8h vs. sliding)?
- Soll der Upload-Flow bei 401 automatisch einen Reload/Redirect machen oder erst einen expliziten Button „Neu anmelden“ anzeigen?
