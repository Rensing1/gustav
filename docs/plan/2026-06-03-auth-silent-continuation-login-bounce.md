# Auth Silent Continuation Login-Bounce Implementation Plan

Status: technisch umgesetzt; manuelle prod-like QA offen
Datum: 2026-06-03

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover aktive Keycloak-SSO-Sitzungen automatisch über `/auth/continue`, bevor GUSTAV Nutzer auf die sichtbare Login-Seite mit Rücksprunglink schickt.

**Architecture:** `session-bootstrap` bleibt bearer-only; wir reparieren den Browser-BFF-Zustand über den bestehenden, loop-geschützten Silent-Continuation-Flow. Sichtbarer Login bleibt der Fail-closed-Fallback, wenn Keycloak `login_required` meldet oder der Continuation-Loop-Guard greift.

**Tech Stack:** SvelteKit Server-Loader/Request-Handler, FastAPI Auth-Middleware, Vitest, bestehende Browser-BFF-Session-Helpers.

---

## Kontext

- Das Ticket `docs/tickets/auth-session-bootstrap-classroom-401-bursts-2026-05-28.md` dokumentiert am 28.05.2026 zwischen 07:45 und 13:00 Uhr 2.054 `GET /api/app/session-bootstrap -> 401`, aber gleichzeitig 1.474 abgeschlossene Learning-Submissions ohne failed Submissions.
- `frontend/src/routes/+layout.server.ts` ruft `GET /api/app/session-bootstrap` für die App-Shell auf. Wenn das fehlschlägt, prüft es nur noch `readAppSessionActive(...)`.
- `backend/web/main.py` erzwingt für `/api/app/session-bootstrap` bewusst Bearer-Auth. Ein vorhandenes `gustav_session`-Cookie darf diesen Endpoint nicht authentifizieren.
- `frontend/src/lib/server/backend-auth.ts` hat bereits `/auth/continue` mit `prompt=none`, Safe-Redirect-Prüfung und Loop-Guard. Wenn Keycloak-SSO aktiv ist, kommt der Nutzer ohne Passwort zurück; wenn nicht, fällt der Flow auf die sichtbare Login-Seite zurück.
- Das sichtbare UX-Problem „Rücksprunglink + Anmelden drücken + sofort wieder drin“ bedeutet meist: GUSTAV hat vor dem sichtbaren Login keine Silent Continuation versucht oder zu früh aufgegeben.
- Zusätzlich ist ein kleiner UX-Bug vorhanden: `loginEntryHref(...)` erzeugt `reason=session_expired`, die Root-Login-Seite prüft aber `session-expired`.

## User Story und BDD

**User Story:** Als Schüler möchte ich beim Öffnen eines geschützten Lernlinks automatisch zurück in meinen Lernraum kommen, wenn meine Keycloak-SSO-Sitzung noch aktiv ist, damit GUSTAV nicht wie fehlerhaft ausgeloggt wirkt.

- **Given** ein geschützter Lernlink wird geöffnet und `session-bootstrap` kann keinen Bearer liefern, **When** eine sichere Redirect-Path vorhanden ist, **Then** startet GUSTAV zuerst `/auth/continue?redirect=<path>` statt die sichtbare Login-Seite zu zeigen.
- **Given** Keycloak-SSO ist noch aktiv, **When** `/auth/continue` mit `prompt=none` zurückkehrt, **Then** werden BFF- und App-Session neu gesetzt und der Nutzer landet direkt am ursprünglichen Link.
- **Given** Keycloak-SSO ist nicht aktiv, **When** `/auth/continue` mit `login_required` zurückkommt, **Then** zeigt GUSTAV sichtbar die Login-Seite mit freundlicher Session-Hinweis-Meldung.
- **Given** derselbe Continuation-Redirect läuft erneut, **When** der Loop-Guard greift, **Then** fällt GUSTAV kontrolliert auf sichtbaren Login zurück.
- **Given** ein API-/maschinenartiger Request hat keinen Browser-Redirect-Pfad, **When** ein finaler `401` auftritt, **Then** bleibt die API-artige `401`-Antwort erhalten.

## Task 1: Serverseitige Fallbacks auf Silent Continuation umstellen

**Files:**
- Modify: `frontend/src/lib/server/guards.ts`
- Modify: `frontend/src/lib/server/api.ts`
- Test: `frontend/src/lib/server/guards.test.ts`
- Test: `frontend/src/lib/server/api.test.ts`

- [x] Schreibe zuerst Tests: Parent- und Direct-Guards leiten bei fehlendem Bootstrap auch ohne aktive App-Session nach `/auth/continue`, nicht direkt nach `/?redirect=...`.
- [x] Schreibe zuerst Tests: `backendRequest(...)` leitet bei finalem `401` mit `authRedirectPath` nach `/auth/continue`, auch wenn weder BFF- noch App-Session-Cookie vorhanden ist.
- [x] Behalte unverändert: Ohne `authRedirectPath` gibt `backendRequest(...)` weiterhin die `401`-Response zurück.
- [x] Implementiere minimal: `loginHref(...)` in den geschützten Browser-Fallbacks durch `continuationHref(...)` ersetzen, wo ein sicherer Seitenpfad aus dem Loader/Action-Kontext vorliegt.
- [x] Run: `npm test -- src/lib/server/guards.test.ts src/lib/server/api.test.ts`.

## Task 2: Sichtbaren Login-Fallback sauber beschriften

**Files:**
- Modify: `frontend/src/lib/server/backend-auth.ts`
- Modify: `frontend/src/routes/+page.svelte`
- Test: `frontend/src/lib/server/backend-auth.test.ts`
- Test: `frontend/src/routes/page-contract.test.ts`

- [x] Schreibe zuerst Tests: `login_required` aus Silent Continuation und der Loop-Guard erzeugen `/?redirect=...&reason=session-expired`.
- [x] Schreibe zuerst Test/Contract: Die Root-Login-Seite zeigt die freundliche Session-Meldung für `session-expired` und akzeptiert `session_expired` weiterhin als Legacy-Wert.
- [x] Implementiere minimal: `loginEntryHref(...)` nutzt kanonisch `session-expired`.
- [x] Implementiere robust: Root-Login-Seite prüft `data.reason === "session-expired" || data.reason === "session_expired"`.
- [x] Run: `npm test -- src/lib/server/backend-auth.test.ts src/routes/page-contract.test.ts`.

## Task 3: Tokenfreie Observability ergänzen

**Files:**
- Modify: `frontend/src/lib/server/backend-auth.ts`
- Test: `frontend/src/lib/server/backend-auth.test.ts`
- Optional docs: `docs/references/auth_sessions_and_cookies.md`

- [x] Schreibe zuerst Test: `startContinuationFlow(...)` loggt `console.info("auth.continuity", { reason: "continuation_started" })` ohne Redirect-Pfad, Cookies, Session-IDs oder Token.
- [x] Implementiere das Log direkt beim Start eines neuen Silent-Continuation-Flows, nicht beim Loop-Guard.
- [x] Dokumentiere kurz: Geschützte Browser-Routen probieren Silent Continuation vor sichtbarem Login; `session-bootstrap` bleibt bearer-only.
- [x] Run: `npm test -- src/lib/server/backend-auth.test.ts`.

## Task 4: Integration und Regression

**Files:**
- Existing frontend/backend tests only; keine Migration.
- No OpenAPI change expected, because FastAPI contracts bleiben gleich.

- [x] Run focused frontend auth suite: `npm test -- src/lib/server/api.test.ts src/lib/server/guards.test.ts src/lib/server/backend-auth.test.ts src/lib/server/session.test.ts src/routes/protected-page-bootstrap-contract.test.ts src/routes/page-contract.test.ts`.
- [x] Run type/static checks: `npm run check`.
- [x] Run backend auth contract checks if docs/OpenAPI touched: `.venv/bin/pytest -q backend/tests/test_session_bootstrap_api.py backend/tests/test_openapi_session_bootstrap_contract.py`.
- [x] Run final verification according to repo standard: `make verify`.
- [ ] Manual QA in prod-like setup: Öffne eine tiefe Learning-URL mit aktiver Keycloak-SSO, aber fehlender/kaputter GUSTAV-BFF-Session; erwartet ist direkte Rückkehr über `/auth/continue` ohne sichtbaren „Anmelden“-Zwischenschritt.

## Annahmen

- Kein Supabase-Schema und keine Migration nötig.
- `session-bootstrap` bleibt aus Security-Gründen bearer-only.
- `/auth/continue` ist der einzige automatische Reparaturpfad; es gibt kein blindes Auto-Submit auf der Login-Seite.
- Sichtbarer Login bleibt notwendig, wenn Keycloak keine aktive SSO-Sitzung mehr hat oder der Loop-Guard greift.
