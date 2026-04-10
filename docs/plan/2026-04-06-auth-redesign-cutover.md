# Plan: Auth Redesign Cutover

Stand: 2026-04-06

## Ziel

- `app.localhost` zeigt unangemeldet zuerst eine neue Svelte-Einstiegsfläche.
- Keycloak bleibt Host für echte Auth-Formulare und Action-Token-Flows.
- Auth bleibt funktional robust für Redirects, Session-Sync und H5P.

## Umsetzung

- Neue öffentliche Svelte-Seiten für Einstieg, Registrierungsvorstufe und
  Passwort-Reset-Vorstufe.
- Root-Loader leitet nur noch bei aktiver Session direkt in den Zielraum.
- Gemeinsame Auth-CSS-Basis für Svelte und Keycloak-Theme.
- Keycloak-Templates auf die neue Produktsprache aus `docs/DESIGN.md`
  umstellen, ohne bestehende Backlink-Hardening-Logik zu verlieren.
- Schul-Domain sowohl in der App-Vorstufe als auch im Realm-Export erzwingen.

## Risiken

- Redirect-Regressionen zwischen Svelte, Keycloak und FastAPI.
- Inkonsistente Session-Zustände zwischen `gustav_bff_session` und
  `gustav_session`.
- Theme-Brüche auf seltenen Keycloak-Seiten wie `error` oder
  `login-page-expired`.

## Verifikation

- Source-/Packaging-Contracts für neue Svelte-Auth-Routen und Root-Verhalten.
- Keycloak-Theme-Tests für neue CSS-Quelle und vorhandene Templates.
- Frontend-Vitest für Auth-Komponenten.
- Selektive pytest- und vitest-Läufe für Auth- und Theme-Verträge.
