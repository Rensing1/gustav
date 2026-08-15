-- Secure, time-limited course invitations with privacy-preserving mail jobs.
--
-- The browser carries a signed capability token. PostgreSQL stores only the
-- invitation id and random nonce; application code verifies the HMAC before it
-- invokes the SECURITY DEFINER helpers below.

create table public.course_invitations (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references public.courses(id) on delete cascade,
  created_by text not null check (length(btrim(created_by)) > 0),
  token_nonce text not null check (length(token_nonce) between 20 and 128),
  expires_at timestamptz not null,
  revoked_at timestamptz null,
  revoked_by text null,
  created_at timestamptz not null default now(),
  constraint course_invitations_expiry_check check (expires_at > created_at),
  constraint course_invitations_revocation_shape check (
    (revoked_at is null and revoked_by is null)
    or (revoked_at is not null and revoked_by is not null)
  )
);

create unique index course_invitations_one_unrevoked_per_course
  on public.course_invitations(course_id)
  where revoked_at is null;
create index idx_course_invitations_expiry
  on public.course_invitations(expires_at)
  where revoked_at is null;

create table public.course_invite_redemptions (
  invitation_id uuid not null references public.course_invitations(id) on delete cascade,
  student_sub text not null check (length(btrim(student_sub)) > 0),
  redeemed_at timestamptz not null default now(),
  primary key (invitation_id, student_sub)
);

create table public.course_invite_mail_batches (
  id uuid primary key default gen_random_uuid(),
  invitation_id uuid not null references public.course_invitations(id) on delete cascade,
  requested_by text not null check (length(btrim(requested_by)) > 0),
  requested_count integer not null check (requested_count between 1 and 100),
  created_at timestamptz not null default now()
);

create table public.course_invite_mail_deliveries (
  id uuid primary key default gen_random_uuid(),
  batch_id uuid not null references public.course_invite_mail_batches(id) on delete cascade,
  invitation_id uuid not null references public.course_invitations(id) on delete cascade,
  recipient_email text null check (recipient_email is null or length(recipient_email) between 3 and 254),
  recipient_digest text not null check (length(recipient_digest) between 32 and 128),
  status text not null default 'pending' check (status in ('pending', 'processing', 'sent', 'failed')),
  retry_count integer not null default 0 check (retry_count between 0 and 5),
  next_attempt_at timestamptz not null default now(),
  lease_token uuid null,
  leased_until timestamptz null,
  error_code text null,
  created_at timestamptz not null default now(),
  sent_at timestamptz null,
  failed_at timestamptz null,
  purge_after timestamptz null,
  unique (invitation_id, recipient_digest)
);

create index idx_course_invite_mail_claim
  on public.course_invite_mail_deliveries(next_attempt_at, created_at)
  where status in ('pending', 'processing');
create index idx_course_invite_mail_purge
  on public.course_invite_mail_deliveries(purge_after)
  where recipient_email is not null and purge_after is not null;

alter table public.course_invitations enable row level security;
alter table public.course_invite_redemptions enable row level security;
alter table public.course_invite_mail_batches enable row level security;
alter table public.course_invite_mail_deliveries enable row level security;

revoke all on table public.course_invitations from public;
revoke all on table public.course_invite_redemptions from public;
revoke all on table public.course_invite_mail_batches from public;
revoke all on table public.course_invite_mail_deliveries from public;

create or replace function public.create_course_invitation(p_course_id uuid, p_nonce text)
returns table (
  id uuid,
  course_id uuid,
  token_nonce text,
  expires_at timestamptz,
  created_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  actor_sub text := coalesce(current_setting('app.current_sub', true), '');
  course_row public.courses%rowtype;
begin
  select * into course_row
    from public.courses
   where courses.id = p_course_id
   for update;

  if not found or course_row.teacher_id <> actor_sub then
    return;
  end if;
  if course_row.status <> 'active' then
    raise exception 'course_not_active' using errcode = 'P0001';
  end if;
  if not public.course_metadata_complete(p_course_id) then
    raise exception 'course_metadata_incomplete' using errcode = 'P0001';
  end if;
  if length(coalesce(p_nonce, '')) < 20 then
    raise exception 'invalid_invitation_nonce' using errcode = '22023';
  end if;

  update public.course_invitations
     set revoked_at = now(), revoked_by = actor_sub
   where course_invitations.course_id = p_course_id
     and revoked_at is null;

  return query
  insert into public.course_invitations(course_id, created_by, token_nonce, expires_at)
  values (p_course_id, actor_sub, p_nonce, now() + interval '24 hours')
  returning course_invitations.id, course_invitations.course_id,
            course_invitations.token_nonce, course_invitations.expires_at,
            course_invitations.created_at;
end;
$$;

create or replace function public.get_active_course_invitation(p_course_id uuid)
returns table (
  id uuid,
  course_id uuid,
  token_nonce text,
  expires_at timestamptz,
  created_at timestamptz,
  redemption_count bigint,
  pending_count bigint,
  sent_count bigint,
  failed_count bigint
)
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select i.id, i.course_id, i.token_nonce, i.expires_at, i.created_at,
         (select count(*) from public.course_invite_redemptions r where r.invitation_id = i.id),
         (select count(*) from public.course_invite_mail_deliveries d where d.invitation_id = i.id and d.status in ('pending', 'processing')),
         (select count(*) from public.course_invite_mail_deliveries d where d.invitation_id = i.id and d.status = 'sent'),
         (select count(*) from public.course_invite_mail_deliveries d where d.invitation_id = i.id and d.status = 'failed')
    from public.course_invitations i
    join public.courses c on c.id = i.course_id
   where i.course_id = p_course_id
     and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
     and c.status = 'active'
     and i.revoked_at is null
     and i.expires_at > now()
$$;

create or replace function public.revoke_course_invitation(p_course_id uuid, p_invitation_id uuid)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  actor_sub text := coalesce(current_setting('app.current_sub', true), '');
  changed boolean := false;
begin
  update public.course_invitations i
     set revoked_at = now(), revoked_by = actor_sub
   where i.id = p_invitation_id
     and i.course_id = p_course_id
     and i.revoked_at is null
     and public.course_exists_for_owner(actor_sub, i.course_id);
  changed := found;
  return changed;
end;
$$;

create or replace function public.preview_course_invitation(p_invitation_id uuid, p_nonce text)
returns table (course_title text, expires_at timestamptz)
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select c.title, i.expires_at
    from public.course_invitations i
    join public.courses c on c.id = i.course_id
   where i.id = p_invitation_id
     and i.token_nonce = p_nonce
     and i.revoked_at is null
     and i.expires_at > now()
     and c.status = 'active'
$$;

create or replace function public.redeem_course_invitation(p_invitation_id uuid, p_nonce text)
returns table (result text, course_id uuid)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  actor_sub text := coalesce(current_setting('app.current_sub', true), '');
  target_course_id uuid;
  prior_redemption boolean;
  active_membership boolean;
begin
  if actor_sub = '' then
    return;
  end if;

  select i.course_id into target_course_id
    from public.course_invitations i
    join public.courses c on c.id = i.course_id
   where i.id = p_invitation_id
     and i.token_nonce = p_nonce
     and i.revoked_at is null
     and i.expires_at > now()
     and c.status = 'active'
   for update of i;
  if not found then
    return;
  end if;

  select exists (
    select 1 from public.course_invite_redemptions r
     where r.invitation_id = p_invitation_id and r.student_sub = actor_sub
  ) into prior_redemption;
  select exists (
    select 1 from public.course_memberships m
     where m.course_id = target_course_id and m.student_id = actor_sub and m.ended_at is null
  ) into active_membership;

  if prior_redemption and not active_membership then
    raise exception 'invite_already_used_membership_removed' using errcode = 'P0001';
  end if;
  if prior_redemption then
    return query select 'already_member'::text, target_course_id;
    return;
  end if;

  insert into public.course_invite_redemptions(invitation_id, student_sub)
  values (p_invitation_id, actor_sub)
  on conflict (invitation_id, student_sub) do nothing;

  if active_membership then
    return query select 'already_member'::text, target_course_id;
    return;
  end if;

  insert into public.course_memberships(course_id, student_id)
  values (target_course_id, actor_sub)
  on conflict (course_id, student_id) do update
    set ended_at = null, ended_by = null, created_at = now();
  return query select 'joined'::text, target_course_id;
end;
$$;

create or replace function public.queue_course_invite_mail_batch(
  p_course_id uuid,
  p_invitation_id uuid,
  p_deliveries jsonb
)
returns table (batch_id uuid, queued integer, skipped_duplicates integer)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  actor_sub text := coalesce(current_setting('app.current_sub', true), '');
  new_batch_id uuid;
  requested integer;
  inserted integer;
begin
  if jsonb_typeof(p_deliveries) <> 'array' then
    raise exception 'invalid_recipients' using errcode = '22023';
  end if;
  requested := jsonb_array_length(p_deliveries);
  if requested < 1 or requested > 100 then
    raise exception 'invalid_recipient_count' using errcode = '22023';
  end if;
  if not exists (
    select 1 from public.course_invitations i
    join public.courses c on c.id = i.course_id
    where i.id = p_invitation_id and i.course_id = p_course_id
      and i.revoked_at is null and i.expires_at > now()
      and c.status = 'active' and c.teacher_id = actor_sub
  ) then
    return;
  end if;

  insert into public.course_invite_mail_batches(invitation_id, requested_by, requested_count)
  values (p_invitation_id, actor_sub, requested)
  returning id into new_batch_id;

  insert into public.course_invite_mail_deliveries(
    batch_id, invitation_id, recipient_email, recipient_digest
  )
  select new_batch_id, p_invitation_id,
         btrim(item->>'email'), btrim(item->>'digest')
    from jsonb_array_elements(p_deliveries) item
   where length(btrim(item->>'email')) between 3 and 254
     and length(btrim(item->>'digest')) between 32 and 128
  on conflict (invitation_id, recipient_digest) do nothing;
  get diagnostics inserted = row_count;
  return query select new_batch_id, inserted, requested - inserted;
end;
$$;

create or replace function public.get_course_invite_mail_status(
  p_course_id uuid,
  p_invitation_id uuid
)
returns table (pending bigint, sent bigint, failed bigint, failed_recipients text[])
language sql
stable
security definer
set search_path = pg_catalog, public
as $$
  select
    count(*) filter (where d.status in ('pending', 'processing')),
    count(*) filter (where d.status = 'sent'),
    count(*) filter (where d.status = 'failed'),
    coalesce(array_agg(d.recipient_email order by d.created_at)
      filter (where d.status = 'failed' and d.recipient_email is not null), array[]::text[])
  from public.course_invitations i
  join public.courses c on c.id = i.course_id
  left join public.course_invite_mail_deliveries d on d.invitation_id = i.id
  where i.id = p_invitation_id and i.course_id = p_course_id
    and c.teacher_id = coalesce(current_setting('app.current_sub', true), '')
  group by i.id
$$;

create or replace function public.retry_course_invite_mail_deliveries(
  p_course_id uuid,
  p_invitation_id uuid
)
returns integer
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  actor_sub text := coalesce(current_setting('app.current_sub', true), '');
  changed integer := 0;
begin
  update public.course_invite_mail_deliveries d
     set status = 'pending', next_attempt_at = now(), error_code = null,
         failed_at = null, purge_after = null
   where d.invitation_id = p_invitation_id
     and d.status = 'failed' and d.retry_count < 5
     and d.recipient_email is not null
     and exists (
       select 1 from public.course_invitations i join public.courses c on c.id = i.course_id
        where i.id = d.invitation_id and i.course_id = p_course_id
          and i.revoked_at is null and i.expires_at > now()
          and c.status = 'active' and c.teacher_id = actor_sub
     );
  get diagnostics changed = row_count;
  return changed;
end;
$$;

create or replace function public.claim_course_invite_mail_delivery()
returns table (
  delivery_id uuid,
  lease_token uuid,
  recipient_email text,
  invitation_id uuid,
  token_nonce text,
  course_title text,
  expires_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  selected_id uuid;
  new_lease uuid := gen_random_uuid();
begin
  select d.id into selected_id
    from public.course_invite_mail_deliveries d
    join public.course_invitations i on i.id = d.invitation_id
    join public.courses c on c.id = i.course_id
   where (
       (d.status = 'pending' and d.next_attempt_at <= now())
       or (d.status = 'processing' and d.leased_until < now())
     )
     and d.recipient_email is not null
     and i.revoked_at is null and i.expires_at > now()
     and c.status = 'active'
   order by d.next_attempt_at, d.created_at
   for update of d skip locked
   limit 1;
  if selected_id is null then
    return;
  end if;

  update public.course_invite_mail_deliveries
     set status = 'processing', lease_token = new_lease,
         leased_until = now() + interval '2 minutes'
   where id = selected_id;

  return query
  select d.id, d.lease_token, d.recipient_email, i.id, i.token_nonce,
         c.title, i.expires_at
    from public.course_invite_mail_deliveries d
    join public.course_invitations i on i.id = d.invitation_id
    join public.courses c on c.id = i.course_id
   where d.id = selected_id;
end;
$$;

create or replace function public.complete_course_invite_mail_delivery(
  p_delivery_id uuid,
  p_lease_token uuid
)
returns boolean
language sql
security definer
set search_path = pg_catalog, public
as $$
  update public.course_invite_mail_deliveries
     set status = 'sent', recipient_email = null, sent_at = now(),
         lease_token = null, leased_until = null, error_code = null,
         purge_after = null
   where id = p_delivery_id and lease_token = p_lease_token and status = 'processing'
  returning true
$$;

create or replace function public.fail_course_invite_mail_delivery(
  p_delivery_id uuid,
  p_lease_token uuid,
  p_error_code text,
  p_retryable boolean
)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  current_retry integer;
  invite_valid boolean;
begin
  select d.retry_count,
         i.revoked_at is null and i.expires_at > now() and c.status = 'active'
    into current_retry, invite_valid
    from public.course_invite_mail_deliveries d
    join public.course_invitations i on i.id = d.invitation_id
    join public.courses c on c.id = i.course_id
   where d.id = p_delivery_id and d.lease_token = p_lease_token
   for update of d;
  if not found then
    return false;
  end if;

  if p_retryable and invite_valid and current_retry + 1 < 5 then
    update public.course_invite_mail_deliveries
       set status = 'pending', retry_count = current_retry + 1,
           next_attempt_at = now() + make_interval(secs => least(3600, 60 * power(2, current_retry)::integer)),
           error_code = left(coalesce(p_error_code, 'smtp_transient'), 100),
           lease_token = null, leased_until = null
     where id = p_delivery_id;
  else
    update public.course_invite_mail_deliveries
       set status = 'failed', retry_count = least(current_retry + 1, 5),
           error_code = left(coalesce(p_error_code, 'smtp_failed'), 100),
           failed_at = now(), purge_after = now() + interval '7 days',
           lease_token = null, leased_until = null
     where id = p_delivery_id;
  end if;
  return true;
end;
$$;

create or replace function public.purge_course_invite_mail_recipients()
returns integer
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  changed integer := 0;
begin
  update public.course_invite_mail_deliveries d
     set status = 'failed', error_code = 'invitation_inactive',
         failed_at = coalesce(failed_at, now()),
         purge_after = coalesce(purge_after, now() + interval '7 days'),
         lease_token = null, leased_until = null
   where d.status in ('pending', 'processing')
     and exists (
       select 1 from public.course_invitations i join public.courses c on c.id = i.course_id
        where i.id = d.invitation_id
          and (i.revoked_at is not null or i.expires_at <= now() or c.status <> 'active')
     );

  update public.course_invite_mail_deliveries
     set recipient_email = null
   where recipient_email is not null and purge_after <= now();
  get diagnostics changed = row_count;
  return changed;
end;
$$;

create or replace function public.revoke_course_invitation_on_course_archive()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  if old.status = 'active' and new.status <> 'active' then
    update public.course_invitations
       set revoked_at = now(), revoked_by = coalesce(new.archived_by, new.teacher_id)
     where course_id = new.id and revoked_at is null;
  end if;
  return new;
end;
$$;

drop trigger if exists trg_courses_revoke_invitation on public.courses;
create trigger trg_courses_revoke_invitation
after update of status on public.courses
for each row execute function public.revoke_course_invitation_on_course_archive();

revoke all on function public.create_course_invitation(uuid, text) from public;
revoke all on function public.get_active_course_invitation(uuid) from public;
revoke all on function public.revoke_course_invitation(uuid, uuid) from public;
revoke all on function public.preview_course_invitation(uuid, text) from public;
revoke all on function public.redeem_course_invitation(uuid, text) from public;
revoke all on function public.queue_course_invite_mail_batch(uuid, uuid, jsonb) from public;
revoke all on function public.get_course_invite_mail_status(uuid, uuid) from public;
revoke all on function public.retry_course_invite_mail_deliveries(uuid, uuid) from public;
revoke all on function public.claim_course_invite_mail_delivery() from public;
revoke all on function public.complete_course_invite_mail_delivery(uuid, uuid) from public;
revoke all on function public.fail_course_invite_mail_delivery(uuid, uuid, text, boolean) from public;
revoke all on function public.purge_course_invite_mail_recipients() from public;

grant execute on function public.create_course_invitation(uuid, text) to gustav_limited;
grant execute on function public.get_active_course_invitation(uuid) to gustav_limited;
grant execute on function public.revoke_course_invitation(uuid, uuid) to gustav_limited;
grant execute on function public.preview_course_invitation(uuid, text) to gustav_limited;
grant execute on function public.redeem_course_invitation(uuid, text) to gustav_limited;
grant execute on function public.queue_course_invite_mail_batch(uuid, uuid, jsonb) to gustav_limited;
grant execute on function public.get_course_invite_mail_status(uuid, uuid) to gustav_limited;
grant execute on function public.retry_course_invite_mail_deliveries(uuid, uuid) to gustav_limited;

grant execute on function public.claim_course_invite_mail_delivery() to gustav_worker;
grant execute on function public.complete_course_invite_mail_delivery(uuid, uuid) to gustav_worker;
grant execute on function public.fail_course_invite_mail_delivery(uuid, uuid, text, boolean) to gustav_worker;
grant execute on function public.purge_course_invite_mail_recipients() to gustav_worker;
