-- Keep transient SMTP failures retryable while permanent failures stay final.
-- The column is internal to the worker boundary and is never exposed by table grants.

alter table public.course_invite_mail_deliveries
  add column retryable boolean not null default false;

drop index if exists public.idx_course_invite_mail_claim;
create index idx_course_invite_mail_claim
  on public.course_invite_mail_deliveries(next_attempt_at, created_at)
  where status in ('pending', 'processing') or (status = 'failed' and retryable);

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
  if not exists (
    select 1
      from public.course_invitations i
      join public.courses c on c.id = i.course_id
     where i.id = p_invitation_id
       and i.course_id = p_course_id
       and i.revoked_at is null
       and i.expires_at > now()
       and c.status = 'active'
       and c.teacher_id = actor_sub
  ) then
    return -1;
  end if;

  update public.course_invite_mail_deliveries d
     set status = 'pending',
         retryable = false,
         next_attempt_at = now(),
         error_code = null,
         failed_at = null,
         purge_after = null,
         lease_token = null,
         leased_until = null
   where d.invitation_id = p_invitation_id
     and d.status = 'failed'
     and d.retryable
     and d.retry_count < 5
     and d.recipient_email is not null;
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
       or (
         d.status = 'failed' and d.retryable and d.retry_count < 5
         and d.next_attempt_at <= now()
       )
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
     set status = 'processing', retryable = false, lease_token = new_lease,
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
     set status = 'sent', recipient_email = null, retryable = false, sent_at = now(),
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
   where d.id = p_delivery_id
     and d.lease_token = p_lease_token
     and d.status = 'processing'
   for update of d;
  if not found then
    return false;
  end if;

  if p_retryable and invite_valid and current_retry + 1 < 5 then
    update public.course_invite_mail_deliveries
       set status = 'failed',
           retryable = true,
           retry_count = current_retry + 1,
           next_attempt_at = now() + make_interval(
             secs => least(3600, 60 * power(2, current_retry)::integer)
           ),
           error_code = left(coalesce(p_error_code, 'smtp_transient'), 100),
           failed_at = now(),
           purge_after = now() + interval '7 days',
           lease_token = null,
           leased_until = null
     where id = p_delivery_id;
  else
    update public.course_invite_mail_deliveries
       set status = 'failed',
           retryable = false,
           retry_count = least(current_retry + 1, 5),
           error_code = left(coalesce(p_error_code, 'smtp_failed'), 100),
           failed_at = now(),
           purge_after = now() + interval '7 days',
           lease_token = null,
           leased_until = null
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
     set status = 'failed', retryable = false, error_code = 'invitation_inactive',
         failed_at = coalesce(failed_at, now()),
         purge_after = coalesce(purge_after, now() + interval '7 days'),
         lease_token = null, leased_until = null
   where (d.status in ('pending', 'processing') or d.retryable)
     and exists (
       select 1
         from public.course_invitations i
         join public.courses c on c.id = i.course_id
        where i.id = d.invitation_id
          and (i.revoked_at is not null or i.expires_at <= now() or c.status <> 'active')
     );

  update public.course_invite_mail_deliveries
     set recipient_email = null, retryable = false
   where recipient_email is not null and purge_after <= now();
  get diagnostics changed = row_count;
  return changed;
end;
$$;
