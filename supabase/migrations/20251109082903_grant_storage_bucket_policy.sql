-- Allow the application role to read Supabase Storage bucket metadata.

-- Use the environment-agnostic limited role; login users inherit via IN ROLE.
create policy "gustav_app_can_read_storage_buckets"
    on storage.buckets
    for select
    to gustav_limited
    using (true);
