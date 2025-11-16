# Deployment Notes – 15 Nov 2025

## Overview
- Goal: bring the new GUSTAV alpha-2 stack online under `app.gustav-lernplattform.de` / `id.gustav-lernplattform.de`.
- Environment: Ubuntu host with Docker + Supabase CLI; legacy repo `/home/felix/gustav` used as reference for DNS/DDNS values.
- Result: All containers (`web`, `learning-worker`, `keycloak`, `caddy`, `ollama`, `ddns`) are running; Caddy holds valid Let’s Encrypt certs for apex + subdomains; Supabase is seeded with current migrations and bucket placeholders.

## DNS, Certificates & Proxy
- DNS A-records for `app.` and `id.` point to `92.72.74.100`. DynDNS helper from legacy setup replicated as new `ddns` service (`docker-compose.yml`) using `IONOS_UPDATE_URL` from `.env`.
- `reverse-proxy/Caddyfile` now serves `app.`, `id.`, and apex redirect; `email hennecke@gymalf.de` configured for ACME account.
- `docker compose logs caddy` confirms HTTP-01 challenges succeeded and certs were downloaded for all three hosts on startup.

## Supabase & Database Roles
- `supabase db reset` applied all migrations and seeded storage via placeholder files (`materials/placeholder.png`, `submissions/.placeholder.pdf`).
- Service-role key synchronized into `.env` with `scripts/sync_supabase_env.py`.
- DB logins created:
  - `gustav_ops_admin` (superuser) – used by automation scripts.
  - `gustav_app` (IN ROLE `gustav_limited`) – shared by `web` + `learning-worker`.
  - `gustav_root` for session store DSN.
- Verified connectivity: `psql -h 127.0.0.1 -p 54322 -U gustav_app` and `gustav_ops_admin` both succeed with credentials from `.env`.
- Legacy import: `docs/migration/supabase_backup_20251101_103457.tar.gz` restored into `legacy_import`. User import and data import required overriding Makefile defaults to hit the public Keycloak host (`KC_BASE_URL=https://id.gustav-lernplattform.de`, `KC_HOST_HEADER=id.gustav-lernplattform.de`) and passing the actual master admin credentials plus a trusted CA bundle (`KEYCLOAK_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt`). Running `backend.tools.legacy_user_import` + `scripts/import_legacy_backup.py` with those params succeeded (107 users recreated).

## Application Stack
- `docker compose up -d --build` succeeded after pulling images (notably `ollama/ollama:latest` ~2 GB). Worker initially failed due to outdated password; fixed by altering `gustav_app`.
- `scripts/preflight.sh` passes when sourcing `.env` (ensures health checks on `https://app.gustav-lernplattform.de/health` and Keycloak OIDC discovery). The script skips pytest if `.venv` not prepared.
- `.venv` created for future testing and `backend/web/requirements.txt` installed. Running `pytest -q` currently fails because prod guards expect `GUSTAV_ENV=prod` (set to `prod` in `.env`); a separate test env or overrides are needed to run the suite.
- Login flow fix: `SESSION_DATABASE_URL` must point to `postgresql://…@supabase_db_gustav-alpha2:5432/postgres` so the FastAPI container reaches Supabase. After every `supabase db reset`, recreate the privileged roles (`gustav_root`, `gustav_app`, `gustav_ops_admin`)—missing roles manifest as 500 errors or `{"error":"invalid_code_or_state"}` on `/auth/callback`.
- Ollama now runs with Vulkan passthrough: `docker-compose.yml` mounts `/dev/kfd` and `/dev/dri` and keeps `OLLAMA_VULKAN=1` set so upstream Vulkan support works out of the box. Update `devices`/groups if the host lacks AMD GPU hardware.

## Outstanding / Next Steps
1. **Testing:** Prepare `.env.test` (set `GUSTAV_ENV=dev`, `WEB_BASE=https://app.localhost`, etc.), `source` it, then run `make test` and `make test-e2e`. Document results in `docs/runbooks/preflight_checklist.md`.
2. **Monitoring:** Tail `docker compose logs -f ddns` after IP changes; ensure `HTTP 200` updates. Consider alerting if DDNS fails repeatedly.
3. **Backups:** Schedule fresh Supabase DB + storage backups now that prod credentials changed; see `docs/backups/`.
4. **Keycloak Admin:** Change default passwords (`gustav-admin`, `gustav-maint`) via the console and update `.env`.

With these items tracked, future deployments should follow: update DNS (or confirm DDNS), sync `.env`, run `supabase db reset`, `docker compose up -d --build`, `scripts/preflight.sh`, then regression tests. Document outcomes in this runbook folder for traceability.

## 2025-11-16 – Upload/AI Fix
- Beobachtung: Datei-Uploads liefen zwar an (`POST /storage/v1/object/upload/sign/...` über `app.gustav-lernplattform.de`), aber der Learning-Worker konnte die PDF nicht aus Supabase laden. `public.learning_submissions` zeigte `error_code=vision_failed` + `vision_last_error=pdf_images_unavailable`, und `docker compose logs learning-worker` meldete `reason=untrusted_host`.
- Ursache: Der `web`-Container signierte URLs auf die öffentliche Domain, der Worker kannte aber nur `SUPABASE_URL=http://supabase_kong_…` und lehnte Hosts außerhalb der Allowlist ab.
- Lösung: `docker-compose.yml` so angepasst, dass sowohl `web` als auch `learning-worker` `SUPABASE_PUBLIC_URL=${SUPABASE_PUBLIC_URL:-https://app.gustav-lernplattform.de}` aus `.env` beziehen (`docker-compose.yml:42-60` und `docker-compose.yml:96-110`). Danach `docker compose up -d --build web learning-worker`, wodurch neue Container mit korrekter Host-Allowlist starten.
- Folgeaktion: Letzte gescheiterte Einreichung (`d322f7ca-3bfd-57c4-b6b0-8a331478cb74`) bleibt fehlgeschlagen; Lehrkraft bittet den Schüler um erneuten Upload, damit die Vision-Pipeline mit der korrigierten Konfiguration läuft.

## 2025-11-16 – Vision-Worker HTTP 400 Fix
- Befund: Trotz erlaubter Hosts brachen Folge-Uploads mit `vision_failed remote_fetch_failed` ab. Logs (`learning.vision.storage`) zeigten `reason=http_error:400 stage=pdf_page` schon beim Versuch, die abgeleiteten PDF-Seiten (`.../derived/.../page_0001.png`) zu holen. Supabase antwortet bei nicht vorhandenen Objekten leider mit HTTP 400 + JSON `statusCode=404`, weshalb `_download_supabase_object` das als Fehler deutete und die Worker-Jobs abbrachen, bevor die Original-PDF verarbeitet werden konnte.
- Änderung: `backend/learning/adapters/local_vision.py` aktualisiert, so dass die Fetch-Schleife für PDF-Derivate `http_error:400` als „Seite existiert nicht“ interpretiert und weiterfährt. Anschließend lädt `_ensure_pdf_stitched_png` die eigentliche PDF über den Service-Role-Key (`fetch_remote_pdf`), erstellt die Seiten lokal und die Analyse läuft weiter.
- Umsetzung: Codeänderung + `docker compose restart learning-worker`. Anschließend erneut per API eine Submission erzeugt `POST /api/learning/.../tasks/.../submissions` mit existierendem Storage-Key (Session-ID `27d290fc-30f4-404f-a509-85459c946da8`). Neue Submission `6ab35bb7-ec51-5b7e-84cf-9e1941e89804` durchlief Vision + Feedback erfolgreich (`analysis_status=completed`).
