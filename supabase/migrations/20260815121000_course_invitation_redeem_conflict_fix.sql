-- Use the named membership key to avoid ambiguity with the function's
-- `course_id` output column in PL/pgSQL.

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
  on conflict on constraint course_memberships_pkey do update
    set ended_at = null, ended_by = null, created_at = now();
  return query select 'joined'::text, target_course_id;
end;
$$;

revoke all on function public.redeem_course_invitation(uuid, text) from public;
grant execute on function public.redeem_course_invitation(uuid, text) to gustav_limited;
