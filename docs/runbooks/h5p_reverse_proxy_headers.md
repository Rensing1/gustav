# H5P Sidecar: Reverse Proxy Headers (CSRF Same-Origin)

Status: Stable

## Kontext
Der H5P Sidecar (`h5p-service/`) läuft **nicht** direkt am Internet, sondern wird
vom Reverse Proxy (Caddy) unter `https://app.localhost/h5p/*` bereitgestellt.

Der Sidecar erzwingt für Browser-**Write**-Requests (z. B. `POST /ajax`) einen
strikten **Same-Origin**-Check via `Origin`/`Referer` (CSRF defense-in-depth).

Damit dieser Check zuverlässig funktioniert, muss der Proxy die korrekten
Forwarded-Header setzen.

## Erwartete Header-Invarianten
Der Proxy muss (mindestens) diese Header korrekt setzen:

- `X-Forwarded-Proto`: `https` (oder `http` bei non-TLS)
- `X-Forwarded-Host`: `app.localhost` (optional inkl. Port)
- `X-Forwarded-Port`: `443` (oder der externe Port, falls nicht Standard)

Der Sidecar normalisiert Default-Ports (80/443) so, dass die erwartete Origin
dem Browser-Verhalten entspricht (Default-Port wird in `Origin` i. d. R. nicht
angezeigt).

## `trust proxy` Policy
Der Sidecar setzt `trust proxy` bewusst auf **single hop** (`1`), d. h. er
vertraut Forwarded-Headern nur für genau einen Reverse-Proxy-Hop
(Defense-in-depth, falls der Service jemals ohne Proxy erreichbar wäre).

## Fehlerbild / Triage
Typisches Symptom bei fehlenden/inkonsistenten Proxy-Headern:

- `403 {"error":"csrf_violation"}` bei `POST /h5p/ajax` oder anderen Write-Routen

Checkliste:
1) Im Proxy sicherstellen, dass `X-Forwarded-Proto/Host/Port` gesetzt sind.
2) Prüfen, ob `Origin`/`Referer` des Browsers zur erwarteten Origin passt
   (inkl. Port bei non-standard Ports).
3) Prüfen, ob der Sidecar direkt erreichbar ist (sollte er nicht sein).
