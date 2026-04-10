# ADR: SvelteKit als Browser-BFF

Datum: 2026-03-23

## Status

Akzeptiert

## Entscheidung

`frontend/` wird als eigenständige `SvelteKit`-Anwendung aufgebaut und trägt die
primäre Web-Oberfläche von GUSTAV. Der Browser spricht künftig primär mit
`SvelteKit`; `FastAPI` wird auf klare API-Verträge reduziert.

## Begründung

- Die bestehende SSR-/HTMX-Schicht in `backend/web` ist zu groß und zu stark mit
  Fachlogik und Seitendarstellung vermischt.
- Komplexe Räume wie `learning`, `teaching`, `diagnostics` und `live` brauchen
  ein eigenes UI-Kompositionslayer.
- `SvelteKit` erlaubt serverseitige Web-Logik, ohne dass `FastAPI` wieder zum
  neuen Frontend-Monolithen wird.

## Konsequenzen

- `Caddy` routet `app.localhost` standardmäßig an `frontend`.
- `FastAPI` bleibt für objektorientierte Mutationen, Rechte und Persistenz
  verantwortlich.
- Neue Produktpfade werden nicht mehr als SSR-Seiten in `backend/web/main.py`
  gebaut.

