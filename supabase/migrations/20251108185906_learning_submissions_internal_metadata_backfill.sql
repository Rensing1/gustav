-- Move extracted page keys into internal_metadata and keep analysis_json null until feedback.
set search_path = public, pg_temp;

do $$
begin
    -- 1) Copy historical page_keys entries from analysis_json into internal_metadata.
    update public.learning_submissions
       set internal_metadata = coalesce(internal_metadata, '{}'::jsonb)
                               || jsonb_build_object('page_keys', analysis_json->'page_keys')
     where analysis_json ? 'page_keys'
       and coalesce((analysis_json->>'page_keys')::text, '') <> '';

    -- 2) Remove page_keys from analysis_json to keep the public contract aligned.
    update public.learning_submissions
       set analysis_json = analysis_json - 'page_keys'
     where analysis_json ? 'page_keys';

    -- 3) Ensure non-completed submissions expose `null` analysis_json.
    update public.learning_submissions
       set analysis_json = null
     where analysis_status in ('pending', 'extracted', 'failed')
       and analysis_json is not null;
end;
$$;
