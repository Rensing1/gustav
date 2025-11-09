-- Allow the application role to read Supabase Storage bucket metadata.

create policy "gustav_app_can_read_storage_buckets"
    on storage.buckets
    for select
    to gustav_app
    using (true);
