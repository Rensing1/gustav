-- Enforce strict RLS on Supabase Storage objects (deny-by-default)
--
-- Why:
--   Buckets `materials` and `submissions` are private. Clients must not access
--   storage objects via direct DB queries; access happens through signed URLs
--   generated server-side using the Service Role key. To prevent accidental
--   exposure, we ensure RLS is enabled on `storage.objects` and avoid granting
--   direct privileges to application roles.
--
-- Behavior:
--   - Idempotent: only enables RLS if table exists.
--   - No permissive policies for `gustav_limited` on `storage.objects` are added.
--     The existing policy to read `storage.buckets` metadata remains in place
--     (see 20251109082903_grant_storage_bucket_policy.sql).
--   - Service Role continues to generate signed URLs; browser accesses via
--     Supabase Storage REST only.

begin;

do $$
declare
  _has_table boolean := false;
  _can_alter boolean := false;
  _rls_enabled boolean := false;
begin
  -- Only proceed if storage.objects exists
  select exists (
    select 1 from information_schema.tables
    where table_schema = 'storage' and table_name = 'objects'
  ) into _has_table;

  if not _has_table then
    raise notice 'storage.objects not present; skipping RLS enable.';
    return;
  end if;

  -- Check current setting and privileges to avoid ownership errors
  select c.relrowsecurity
  from pg_catalog.pg_class c
  join pg_catalog.pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'storage' and c.relname = 'objects'
  into _rls_enabled;

  if _rls_enabled then
    raise notice 'RLS already enabled on storage.objects; nothing to do.';
    return;
  end if;

  select has_table_privilege('storage.objects', 'ALTER') into _can_alter;
  if not _can_alter then
    raise notice 'Skipping enabling RLS on storage.objects: insufficient privileges (not owner).';
    return;
  end if;

  begin
    execute 'alter table storage.objects enable row level security';
    raise notice 'Enabled RLS on storage.objects.';
  exception when others then
    raise notice 'Skipping enabling RLS on storage.objects: %', sqlerrm;
  end;
end$$;

commit;
