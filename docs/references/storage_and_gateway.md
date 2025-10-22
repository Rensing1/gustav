# Storage & Gateway (Supabase, self-hosted)

This doc explains how to run Supabase Storage locally (self-hosted) and wire the app to use it for file materials.

## Local setup (CLI)
- Prereqs: Supabase CLI installed; Docker running.
- Ensure storage is enabled: `supabase/config.toml` has `[storage] enabled = true` and the bucket config:
  - `[storage.buckets.materials]` with `public = false`, `file_size_limit = "20MiB"`, `allowed_mime_types = ["application/pdf","image/png","image/jpeg"]`, `objects_path = "./storage/materials"`.
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
  - See `.env.example` for a ready-to-copy template; store real values in `.env` (gitignored).

## Security
- Use Service Role key only in the backend. Never expose keys to the browser.
- Buckets must be private; the app uses signed URLs with short TTLs (upload: 3 min, download: 45 s).
- Download URL responses include `Cache-Control: no-store` to avoid caching.
- Filenames and path segments are sanitized in the service to avoid traversal and odd characters.

## Gateway
- Current reverse proxy: Caddy (see `reverse-proxy/Caddyfile`).
- No extra Kong layer needed for the app traffic at this stage.
- Supabase’s internal stack may use Kong for its own services; this is separate from the app.
- Later (optional): add gateway policies (CORS/HSTS/rate limiting) if needed.

## Tests / E2E
- Optional E2E smoke test: set `RUN_SUPABASE_E2E=1` and provide `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`. See pytest marker `supabase_integration`.

## E2E checklist
- `supabase start -x studio`
- Apply DB migrations: `supabase migration up`
- Run app, ensure `Upload-Intent → PUT upload → Finalize → Download/Delete` works.
- Confirm delete error path: storage failure → API returns 502 and DB row remains.
