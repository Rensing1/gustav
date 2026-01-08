Title: Learning Submit: Aufgabenlösung-Submit liefert 401 (Session abgelaufen) und Texteingabe geht verloren

Status: Open

Problem:
- In der Lernansicht können Schüler:innen längere Zeit an einer Aufgabe im Textfeld arbeiten.
- Wenn die App-Session (`gustav_session`) währenddessen abläuft, liefert der Submit-Endpunkt (z. B. `POST /learning/.../submit`) `401 Unauthorized`.
- UX-Problem: Beim Redirect zum Login geht die gerade eingetippte Lösung im Textfeld verloren.
- Dieses Verhalten tritt auch dann auf, wenn im Keycloak-Login „Angemeldet bleiben“ (Remember-me) angehakt wurde, da Remember-me die IdP-Session betrifft, nicht die App-Session.

Beobachtung (Prod, 2026-01-08):
- Mehrfach `POST /learning/.../submit` → `401 Unauthorized` in Web-Logs.
- Auftreten typischerweise nach ~60–75 Minuten seit Login (entspricht der Default-Session-TTL von 3600s).
- Nach dem 401 ist ein erneuter Login erforderlich; in der Praxis muss häufig Benutzername/Passwort erneut eingegeben werden.

Technischer Kontext:
- App verwendet eine eigene serverseitige Session (opaque Cookie `gustav_session`), Sessiondaten serverseitig (DB-backed in Prod).
- Default-TTL: 3600 Sekunden (`backend/identity_access/stores.py`, `backend/identity_access/stores_db.py`).
- In Prod wird beim Login ein Cookie-Max-Age aus der Session-TTL gesetzt (`backend/web/main.py`).
- Keycloak/Remember-me verlängert die IdP-SSO-Session, aber verhindert nicht, dass die App-Session abläuft.

Impact:
- Hoher Frust/Folgeschäden im Unterricht: eingegebene Lösungen gehen verloren.
- Support-Aufwand, da der Logout „ohne erkennbaren Grund“ wirkt.

Workaround:
- Regelmäßig zwischenspeichern/kopieren (manuell) oder vor Ablauf der Stunde neu laden/einloggen.

Vorschlag:
1. **App-Session-TTL unterrichtstauglich machen**
   - TTL deutlich erhöhen (z. B. 6–8h) oder als Deployment-Setting konfigurierbar machen (ENV).
2. **Sliding Sessions / Activity Refresh**
   - Bei aktiver Nutzung (mindestens bei schreibenden Requests; optional generell) `expires_at` verlängern und Cookie-Max-Age aktualisieren.
   - Optional zusätzlich eine harte Max-Lifetime (z. B. 7d) zur Begrenzung.
3. **Draft-Sicherung gegen Textverlust**
   - Textfeld-Inhalte lokal (z. B. `localStorage`) als Draft speichern (keyed by `task_id`/`course_id`/user) und nach Reload/Login wiederherstellen.
   - Zusätzlich: Vor Submit `/api/me` preflighten; bei `401` gezielt re-login mit Hinweis „Sitzung abgelaufen“ (ohne Submit zu verlieren).
4. **UX/Kommunikation**
   - Bei 401 auf Submit: explizite Meldung „Sitzung abgelaufen – bitte neu anmelden. Deine Eingabe wurde gespeichert.“ (in Kombination mit Draft).

Abgrenzung / Related:
- Ähnliches Symptom existiert für Uploads (401 bei `upload-intents`), siehe `docs/tickets/learning-upload-intents-401-session-expired-2025-12-16.md`.

Akzeptanzkriterien:
- Keine Re-Auth im normalen Unterrichtsfenster (mind. 2–3h, Ziel 6–8h) bei aktiver Nutzung.
- Wenn Session tatsächlich abläuft, geht keine Texteingabe verloren (Draft wird nach Login wiederhergestellt).
