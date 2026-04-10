# Auth-Design an `docs/DESIGN.md` angleichen

## Ziel

Die Auth-Flächen in Svelte und Keycloak sollen dieselbe Produktsprache wie die
neue Svelte-Oberfläche sprechen. Maßgeblich ist `docs/DESIGN.md`, nicht der
ältere beige/türkise Plattformstil und nicht eine eigenständige Keycloak-Optik.

## Entscheidungen

- Auth bleibt architektonisch unverändert:
  - Svelte rendert Einstiegsseiten
  - Keycloak bleibt Formularhost
- Die bestehende Zentrierung unter der Top-Bar bleibt erhalten.
- Die visuelle Sprache wird auf den Mistral-Vertrag zurückgeführt:
  - Orange als Primärakzent
  - harte Kanten
  - minimale Radien
  - technische Meta-Typografie
  - klare Rahmen und harte Schatten
- Texte bleiben knapp und statusbezogen.

## Umsetzung

- `frontend/src/lib/styles/auth-theme.css` wird auf die Farb-, Radius-,
  Typografie- und Shadow-Regeln aus `docs/DESIGN.md` umgestellt.
- Die gemeinsame Auth-CSS bleibt die Quelle für Svelte und Keycloak.
- Der Stil-Contract-Test wird von der beige/türkisen Plattformannahme auf den
  Designvertrag umgestellt.
- Unnötige Feld- und Statushinweise auf den Svelte-Auth-Seiten werden weiter
  gekürzt.

## Verifikation

- Vitest für Auth-Stil- und Routen-Contracts
- `npm run check`
- visueller Smoke-Test über `app.localhost` und `id.localhost`
