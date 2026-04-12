# Plan: Auth-Dokumentation konsolidieren und aktualisieren

## Ziel

Die aktuelle Auth-Dokumentation von GUSTAV ist funktional vorhanden, aber auf
mehrere Dateien verteilt und in zentralen Punkten veraltet. Insbesondere seit
dem SvelteKit-Browser-BFF und dem Auth-Hardening vom 2026-04-11 ist nicht mehr
eine einzige Referenz vorhanden, die Login-Flow, Cookies, Session-TTLs,
interne BFF-Grenzen und typische Fehlerbilder kohärent erklärt.

Ziel dieser Änderung ist daher:

- eine kanonische technische Referenz für Auth, Sessions und Cookies zu schaffen,
- bestehende Auth-Dokumente auf diese Referenz auszurichten,
- veraltete Aussagen zu TTL, Cookie-Modell und Session-Verantwortung zu entfernen.

## Umsetzungsentscheidung

- Neue kanonische Referenz: `docs/references/auth_sessions_and_cookies.md`
- Bestehende Dateien werden nicht parallel voll ausgebaut, sondern gezielt
  gekürzt, korrigiert und auf die neue Referenz verlinkt:
  - `docs/references/user_management.md`
  - `docs/ARCHITECTURE.md`
  - `docs/auth_legacy.md`

## Inhalt der neuen Referenz

Die neue Referenz beschreibt den aktuellen Ist-Zustand:

- Systemgrenzen zwischen Keycloak, SvelteKit-BFF, FastAPI und H5P
- Login-, Callback- und Logout-Flow
- Cookie-Modell:
  - `gustav_bff_oidc_flow`
  - `gustav_bff_session`
  - `gustav_session`
- Session-Modell:
  - Access-Token-Ablauf
  - BFF-Session-Ablauf
  - App-Session-TTL
- Sicherheitsmechanismen:
  - PKCE, `state`, `nonce`
  - host-only `HttpOnly; Secure; SameSite=lax`
  - interner Shared-Secret-Schutz für `/backend-internal/app/bff-session`
- typische Fehlerbilder und Debugging-Hinweise
- relevante ENV-Variablen

## Akzeptanzkriterien

- Es gibt eine klar erkennbare kanonische Auth-Referenz.
- Keine bestehende Doku behauptet mehr, dass nur `gustav_session` existiert.
- Keine bestehende Doku behauptet mehr pauschal eine Standard-TTL von 3600s.
- `docs/ARCHITECTURE.md` bleibt Überblicksdokument und verweist für Auth-Details
  auf die neue Referenz.
- `docs/references/user_management.md` fokussiert wieder auf Identität,
  Rollen und UserContext statt auf verstreute Session-Mechanik.
