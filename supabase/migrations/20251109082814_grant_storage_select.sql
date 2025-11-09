-- Grant read-only access for the application role to Supabase Storage metadata.
-- This allows runtime health checks and tests to verify bucket provisioning.

grant usage on schema storage to gustav_app;

-- Existing tables (buckets, objects, etc.) become selectable for the app role.
grant select on all tables in schema storage to gustav_app;

-- Future tables created inside the storage schema inherit the same select privilege.
alter default privileges in schema storage grant select on tables to gustav_app;
