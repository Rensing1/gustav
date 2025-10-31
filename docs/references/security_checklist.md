# Security Checklist

Status: Stable

## Auth & Cookies
- HttpOnly; Prod: Secure + SameSite=strict; Dev: SameSite=lax.
- Keine Domain‑Attribute (host‑only).

## OAuth/OIDC
- Nonce + State validiert; Redirect-Sanitization (nur In‑App‑Pfad).
- Logout: `id_token_hint` wenn verfügbar.
 - Produktion: `KC_BASE_URL` und `KC_PUBLIC_BASE_URL` müssen HTTPS verwenden (Startup‑Guard erzwingt dies).

## DB
- `gustav_limited NOLOGIN`; Logins IN ROLE.
- RLS aktiviert auf allen App‑Tabellen; Policies referenzieren keine app‑kontrollierten GUCs.
 - Learning‑Helper (SECURITY INVOKER): PUBLIC hat kein EXECUTE; nur `gustav_limited` besitzt EXECUTE.

## Transport/Caching
- PROD: TLS enforced; keine `sslmode=disable`.
 - `Cache-Control: private, no-store` für API‑Erfolg und Fehler (inkl. 201/204) in Auth/Teaching/Learning.
 - CSRF: State‑changing Responses setzen `Vary: Origin` (Same‑Origin‑Durchsetzung bei Browsern).
