# Security Checklist

Status: Stable

## Auth & Cookies
- HttpOnly; Prod: Secure + SameSite=strict; Dev: SameSite=lax.
- Keine Domain‑Attribute (host‑only).

## OAuth/OIDC
- Nonce + State validiert; Redirect-Sanitization (nur In‑App‑Pfad).
- Logout: `id_token_hint` wenn verfügbar.

## DB
- `gustav_limited NOLOGIN`; Logins IN ROLE.
- RLS aktiviert auf allen App‑Tabellen; Policies referenzieren keine app‑kontrollierten GUCs.

## Transport/Caching
- PROD: TLS enforced; keine `sslmode=disable`.
- `Cache-Control: no-store` für sensitive Endpunkte.
- CSRF: State-changing Responses setzen `Vary: Origin`.
