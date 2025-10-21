# Database Schema Overview

This document summarizes the production session table introduced for persistent sessions.

## public.app_sessions

- Columns
  - `session_id` text PRIMARY KEY — opaque random identifier stored in the httpOnly cookie.
  - `sub` text NOT NULL — stable subject ID from the IdP.
  - `roles` jsonb NOT NULL — array of realm roles filtered to ["student", "teacher", "admin"].
  - `name` text NOT NULL — display name used in the UI.
  - `id_token` text NULL — optional; if stored, consider at‑rest protection and short TTL.
  - `expires_at` timestamptz NOT NULL — server‑side expiry.

- Indexes
  - `idx_app_sessions_sub (sub)`
  - `idx_app_sessions_expires_at (expires_at)`

- Security
  - Row Level Security enabled; no grants to `anon`/`authenticated`. Access via service role only.

- Retention
  - Expired rows should be purged regularly, e.g.: `delete from public.app_sessions where expires_at < now();`

## Teaching (Unterrichten)

- DSN usage
  - Runtime (app): Use a limited-role DSN (e.g., `gustav_limited`) so RLS is always active.
  - Migrations: Apply via `supabase migration up` (runs as owner/service). The app does not need to switch DSNs.
  - Sessions note: If `SESSIONS_BACKEND=db` is enabled, `public.app_sessions` requires a service-role DSN. Otherwise keep in-memory sessions to avoid service-role in the app.

- RLS policies
  - Policies are defined in `supabase/migrations/20251020154107_teaching_rls_policies.sql`.
  - They rely on `SET LOCAL app.current_sub = '<sub>'` per transaction to identify the acting user.
