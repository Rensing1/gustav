# Storage & Gateway (Supabase, self-hosted)

This doc explains how to run Supabase Storage locally (self-hosted) and wire the app to use it for file materials.

## Local setup (CLI)
- Prereqs: Supabase CLI installed; Docker running.
- Ensure storage is enabled: `supabase/config.toml` has `[storage] enabled = true`.
- Buckets werden durch Migrationen provisioniert (privat): `materials`, `submissions`. RLS ist auf `storage.objects` aktiv (deny‑by‑default); direkte DB‑Zugriffe durch App‑Rollen sind nicht erlaubt.
- Start services without Studio:
  - `supabase stop`
  - `supabase start -x studio`
  - Check: `supabase status` (expect storage: running; rest: running; db: running)

## App wiring
- Adapter: `backend/teaching/storage_supabase.py` implements `SupabaseStorageAdapter`.
- Inject at app boot (example):
  - Create client: `from supabase import create_client; client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)`
  - Instantiate adapter: `adapter = SupabaseStorageAdapter(client)`
  - Set in routes: `from routes import teaching; teaching.set_storage_adapter(adapter)`
- Env vars (server-side only):
  - `SUPABASE_URL` (e.g., `http://127.0.0.1:54321`)
  - `SUPABASE_SERVICE_ROLE_KEY` (from `supabase start` output)
  - `SUPABASE_STORAGE_BUCKET` (default: `materials`)
  - `LEARNING_STORAGE_BUCKET` (default: `submissions`)
  - `MATERIALS_MAX_UPLOAD_BYTES` (default: 20 MiB)
  - `LEARNING_MAX_UPLOAD_BYTES` (default: 10 MiB)
  - See `.env.example` for a ready-to-copy template; store real values in `.env` (gitignored).

## Security
- Use Service Role key only in the backend. Never expose keys to the browser.
- Buckets are private; the app uses signed URLs with short TTLs (upload: 3 min, download: 45 s).
- Download URL responses include `Cache-Control: private, no-store` to avoid caching.
- Filenames and path segments are sanitized in the service to avoid traversal and odd characters.

## Governance & Provisioning
- Quelle der Wahrheit: SQL‑Migrationen legen `materials` und `submissions` privat an.
- Dev‑Convenience: Optional `AUTO_CREATE_STORAGE_BUCKETS=true` zum Nachprovisionieren fehlender Buckets beim App‑Start. **Nur in Dev/Test setzen**; beim Start wird ein Hinweis ins Log geschrieben, falls das Flag aktiv ist, damit Prod/Stage es nicht versehentlich nutzen.

## Gateway
- Current reverse proxy: Caddy (see `reverse-proxy/Caddyfile`).
- TLS/HSTS: Caddy terminates TLS locally (tls internal). The app middleware always
  sends `Strict-Transport-Security: max-age=31536000; includeSubDomains` in dev and prod
  (dev = prod) to keep behaviour consistent across environments.
- No extra Kong layer needed for the app traffic at this stage.
- Supabase’s internal stack uses Kong for its own services; this is separate from the app.
- Later (optional): add gateway policies (CORS/rate limiting) if needed.

## Tests / E2E
- Optional E2E smoke test: set `RUN_SUPABASE_E2E=1` and provide `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`. See pytest marker `supabase_integration`.

## E2E checklist
- `supabase start -x studio`
- Apply DB migrations: `supabase migration up`
- Run app, ensure `Upload-Intent → PUT upload → Finalize → Download/Delete` works.
- Confirm delete error path: storage failure → API returns 502 and DB row remains.
