-- Grant read-only access for the limited application role (environment-agnostic).
-- Important: Do NOT reference environment-specific LOGIN roles here. The login
-- user (e.g., gustav_app) is created outside migrations and is IN ROLE
-- `gustav_limited`. Grants must target `gustav_limited` so `supabase db reset`
-- works in all environments without pre-provisioned login roles.

grant usage on schema storage to gustav_limited;

-- Existing tables (buckets, objects, etc.) become selectable for the limited role.
grant select on all tables in schema storage to gustav_limited;

-- Future tables created inside the storage schema inherit the same select privilege.
alter default privileges in schema storage grant select on tables to gustav_limited;
