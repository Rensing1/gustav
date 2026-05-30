# Ticket: Session-Bootstrap erzeugt 401-Bursts im Klassenbetrieb

**Status:** offen
**Beobachtet am:** 2026-05-28
**Betroffene Umgebung:** Produktion
**Komponenten:** SvelteKit Browser-BFF, FastAPI Session-Bootstrap, Auth-Recovery

## Kurzbeschreibung

Während des Unterrichtsfensters am 2026-05-28 wurden viele `GET /api/app/session-bootstrap`-Antworten mit HTTP 401 gezählt. Ein Teil davon ist im Klassenbetrieb erwartbar, etwa vor oder während Login/Continuation. Die Menge ist aber hoch genug, um als eigenes Beobachtungs- und Triageproblem dokumentiert zu werden.

Dieses Ticket ergänzt bestehende Auth-Continuity-Tickets mit neuer Evidenz aus einem realen Unterrichtstag.

## Verwandte Tickets

- `docs/tickets/auth-session-continuity-classroom-regression-2026-05-11.md`
- `docs/tickets/session-bootstrap-hard-reload-forces-relogin-with-active-sso-2026-04-21.md`
- `docs/tickets/auth-session-continuity-reopened-session-bootstrap-asset-regression-2026-05-18.md`

## Beobachtung

- Im Unterrichtsfenster 07:45 bis 13:00 Uhr wurden 2.054 `GET /api/app/session-bootstrap`-Antworten mit HTTP 401 gezählt.
- Zusätzlich gab es 5 HTTP-401 auf Learning-Materialdateien und 1 HTTP-401 auf einen Upload-Intent.
- Direkt im selben Fenster gab es auch erfolgreiche `session-bootstrap`-Antworten und insgesamt stabile Lernverarbeitung.
- Alle 1.474 Learning-Submissions wurden abgeschlossen; es gab keine failed Submissions.

## Technischer Befund

Der aktuelle SvelteKit-Layout-Loader ruft `session-bootstrap` als Shell-Bootstrap auf. Geschützte Routen nutzen Guard- und Backend-Request-Helfer, die bei recoverable Auth-Zuständen teilweise auf `/auth/continue` ausweichen.

Relevante Codepfade:

- `frontend/src/routes/+layout.server.ts`
- `frontend/src/lib/server/api.ts`
- `frontend/src/lib/server/session.ts`
- `frontend/src/lib/server/guards.ts`
- `backend/web/routes/app.py`

Die heutige Evidenz sagt noch nicht, ob die 401-Bursts ein reines erwartbares Login-Rauschen oder eine recoverable Mixed-Session-Race sind. Aktuell fehlen dafür feinere, tokenfreie Reason-Codes und clientseitige Burst-Grenzen.

## Impact

- Auth-Triage im Klassenbetrieb bleibt schwer interpretierbar.
- Recoverable Auth-Zustände können wie echte Logout- oder API-Probleme wirken.
- Einzelne geschützte Learning-Requests können während des Recovery-Fensters fehlschlagen, obwohl Keycloak/App-Session später wiederhergestellt wird.

## Vorschlag

- `session-bootstrap`-401s mit tokenfreien Reason-Codes unterscheiden:
  - kein BFF-Bearer vorhanden,
  - BFF-Session fehlt,
  - Token-Refresh fehlgeschlagen,
  - App-Session aktiv, aber BFF-Bootstrap temporär nicht verfügbar,
  - wirklich unauthentifiziert.
- Clientseitig prüfen, ob der Layout-Bootstrap bei vielen parallelen Loads unnötig mehrfach feuert.
- Learning-Material- und Upload-Intent-401s im Recovery-Fenster gezielt retryen oder auf `/auth/continue` führen.
- Monitoring so gruppieren, dass erwartbare Login-Probes nicht als Unterrichtsfehler gezählt werden.

## Akzeptanzkriterien

- Betreiber können in Logs erkennen, welcher Anteil der `session-bootstrap`-401s erwartbarer unauthentifizierter Zugriff und welcher Anteil recoverable Session-State ist.
- Klassenstart erzeugt keine ungebremsten parallelen Bootstrap-Bursts pro Client.
- Geschützte Learning-Requests nach recoverable 401 führen zu Retry oder `/auth/continue`, nicht zu stillen Verlaufs-, Material- oder Uploadfehlern.
- Logs bleiben frei von Access Tokens, Refresh Tokens, Session-IDs, Benutzernamen, E-Mail-Adressen und Cookies.
