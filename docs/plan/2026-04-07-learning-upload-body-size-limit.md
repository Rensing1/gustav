# Lernraum-Dateiupload: SvelteKit-Body-Limit an den Uploadvertrag anpassen

## Ziel
- Gültige Datei-Uploads im Lernraum dürfen nicht mehr am `frontend`-Server mit `500 Internal Error` scheitern.

## Ursache
- `adapter-node` nutzt ohne Konfiguration `BODY_SIZE_LIMIT=512K`.
- Der Lernraum sendet Uploads aktuell als `multipart/form-data` zuerst an die SvelteKit-Action.
- Das Learning-Backend erlaubt bereits Uploads bis 10 MiB.

## Umsetzung
- `frontend`-Service in `docker-compose.yml` erhält `BODY_SIZE_LIMIT=11M`.
- 11 MiB ist ein technisches Transportlimit für Multipart-Overhead; der fachliche Learning-Vertrag bleibt bei 10 MiB.
- Ein Compose-Contract-Test sichert die Konfiguration gegen Regression.

## Verifikation
- Pytest für den neuen Compose-Contract.
- Relevante Learning-Frontend-Tests und `svelte-check`.
- `docker compose up -d --build frontend`.
