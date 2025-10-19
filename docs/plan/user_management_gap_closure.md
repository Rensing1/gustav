# Plan: Close Gaps in User Management (Identity & Access)

Status: approved direction — introduce stable `sub`, display name, and DTO; prepare persistent sessions.

## User Story
Als Lehrkraft (Felix) möchte ich, dass GUSTAV eine stabile Nutzerkennung (`sub`) und einen datenschutzfreundlichen Anzeigenamen bereitstellt und Sessions zuverlässig verwaltet, damit nachfolgende Kontexte (z. B. „Unterrichten“) Nutzer eindeutig referenzieren können, ohne E‑Mail als Schlüssel zu verwenden.

## BDD Szenarien (Auszug)
- Given gültige Session, When GET /api/me, Then 200 mit `{ sub, roles, name, expires_at }` und ohne `email`.
- Given ID‑Token mit Claim `gustav_display_name`, When Callback verarbeitet, Then Session speichert `name=gustav_display_name`.
- Given ID‑Token ohne `gustav_display_name` aber mit `name`, When Callback, Then `name` aus Token übernehmen.
- Given kein Anzeigename im Token, When Callback, Then Fallback `name = lokalteil(email)`.
- Given keine Session, When GET /api/me, Then 401 `{ error: unauthenticated }` mit `Cache-Control: no-store`.

## Contract-First (OpenAPI)
- Schema `Me` anpassen: Felder `sub` (string), `roles` (array), `name` (string), `expires_at` (date-time). `email` und `email_verified` entfallen.

## Datenbank/Migration (Supabase/Postgres)
- Tabelle `app_sessions` (persistente Sessions, minimal PII):
  - `session_id` (text, PK)
  - `sub` (text, not null)
  - `roles` (jsonb, not null)
  - `name` (text, not null)
  - `id_token` (text)
  - `expires_at` (timestamptz, not null)
  - Indizes: (`sub`), (`expires_at`)
  - RLS ON; Policies: nur Service‑Rolle (Server‑Zugriff), kein anonymer Zugriff.

## Tests (TDD)
1) RED: Neuer Test für `/api/me` Form (sub, roles, name, expires_at). Kein `email`.
2) GREEN: Minimaler Code — SessionRecord erweitert (`sub`, `name`), Callback extrahiert und speichert, `/api/me` liefert neues Schema.
3) Refactor: UI‑Sidebar zeigt `name` statt `email`.
4) (Vorbereitung) Migration SQL + DB‑SessionStore (psycoPG3/async) hinter Feature‑Flag `SESSIONS_BACKEND` (default: memory). Eigene Tests gegen lokale Test‑DB folgen in nachgelagertem Schritt.

## Security
- Privacy by design: `email` nicht mehr im DTO, nur `sub` und `name` (anzeigbar).
- Cookie unverändert httpOnly; Secure/SameSite in PROD; `Cache-Control: no-store` für authnahe Antworten.

## Done-Kriterien
- OpenAPI aktualisiert; pytest‑Suite grün mit neuem `/api/me`‑Schema.
- Sidebar zeigt `name` an.
- Referenzdokument `docs/references/user_management.md` beschreibt DTO, Flows und Mapping.

