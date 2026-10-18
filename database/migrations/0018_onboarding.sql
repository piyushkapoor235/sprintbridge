-- 0018 onboarding: how a new account becomes a recruiter, university admin or mentor, and how a
-- signed-up student is linked to their university's roster.
--
-- Roles are still never self-assigned (docs/threat-model.md): a user *applies*, and only an operator
-- approves. Approval creates the membership / role grant in one transaction and is audited.
-- Students need no approval: a confirmed email that matches a roster row links automatically.

create type public.role_application_kind as enum ('recruiter', 'university_admin', 'mentor');
create type public.role_application_status as enum ('pending', 'approved', 'rejected');

create table public.role_applications (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null default auth.uid() references auth.users (id) on delete cascade,
  kind               public.role_application_kind not null,
  organization_name  text check (char_length(organization_name) between 2 and 200),
  job_title          text not null default '' check (char_length(job_title) <= 120),
  website            text check (website ~* '^https?://[^\s]+$' and char_length(website) <= 300),
  niche              text check (char_length(niche) between 2 and 120),
  experience_summary text not null default '' check (char_length(experience_summary) <= 2000),
  status             public.role_application_status not null default 'pending',
  decision_note      text check (char_length(decision_note) <= 1000),
  reviewed_by        uuid references auth.users (id) on delete set null,
  reviewed_at        timestamptz,
  organization_id    uuid references public.organizations (id) on delete set null,
  created_at         timestamptz not null default now(),
  check ((kind = 'mentor' and niche is not null) or (kind <> 'mentor' and organization_name is not null))
);

-- One open application per role per user.
create unique index role_applications_one_pending on public.role_applications (user_id, kind)
  where status = 'pending';
create index role_applications_pending_idx on public.role_applications (created_at) where status = 'pending';

alter table public.role_applications enable row level security;
revoke all on public.role_applications from anon, authenticated;
grant select on public.role_applications to authenticated;  -- writes only through the functions below

create policy role_applications_read on public.role_applications for select to authenticated
  using (user_id = (select auth.uid()) or public.has_grant('operator'));

create function public.has_role_for(p_user uuid, p_kind public.role_application_kind)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select case p_kind
    when 'recruiter' then exists (select 1 from public.memberships where user_id = p_user and role = 'recruiter')
    when 'university_admin' then exists (select 1 from public.memberships where user_id = p_user and role = 'admin')
    when 'mentor' then exists (select 1 from public.role_grants where user_id = p_user and role = 'mentor')
  end
$$;

create function public.submit_role_application(
  p_kind public.role_application_kind,
  p_organization_name text default null,
  p_job_title text default '',
  p_website text default null,
  p_niche text default null,
  p_experience_summary text default ''
)
returns public.role_applications
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_uid uuid := (select auth.uid());
  v_row public.role_applications;
begin
  if v_uid is null then
    raise exception 'Sign in first.' using errcode = 'PT401', hint = 'UNAUTHENTICATED';
  end if;
  if public.has_role_for(v_uid, p_kind) then
    raise exception 'You already have this role.' using errcode = 'PT409', hint = 'ALREADY_GRANTED';
  end if;
  if exists (select 1 from public.role_applications where user_id = v_uid and kind = p_kind and status = 'pending') then
    raise exception 'Your application is already being reviewed.' using errcode = 'PT409', hint = 'ALREADY_APPLIED';
  end if;
  if p_kind <> 'mentor' and char_length(btrim(coalesce(p_organization_name, ''))) < 2 then
    raise exception 'Enter the organization name.' using errcode = 'PT422', hint = 'VALIDATION_ERROR';
  end if;
  if p_kind = 'mentor' and char_length(btrim(coalesce(p_niche, ''))) < 2 then
    raise exception 'Enter your area of expertise.' using errcode = 'PT422', hint = 'VALIDATION_ERROR';
  end if;

  insert into public.role_applications (user_id, kind, organization_name, job_title, website, niche, experience_summary)
  values (v_uid, p_kind,
          case when p_kind <> 'mentor' then btrim(p_organization_name) end,
          btrim(coalesce(p_job_title, '')),
          nullif(btrim(coalesce(p_website, '')), ''),
          case when p_kind = 'mentor' then btrim(p_niche) end,
          btrim(coalesce(p_experience_summary, '')))
  returning * into v_row;

  perform public.log_event('role_application.submitted', 'role_application', v_row.id,
                           jsonb_build_object('kind', p_kind, 'organization', v_row.organization_name));
  return v_row;
end;
$$;

-- Operator queue: pending applications with who applied and whether the organization already exists
-- (joining an existing company/university needs extra care: the operator checks the applicant works there).
create function public.operator_role_applications()
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if not public.has_grant('operator') then
    raise exception 'Operators only.' using errcode = 'PT403', hint = 'FORBIDDEN';
  end if;
  return coalesce((
    select jsonb_agg(jsonb_build_object(
             'id', a.id, 'kind', a.kind, 'organization_name', a.organization_name, 'job_title', a.job_title,
             'website', a.website, 'niche', a.niche, 'experience_summary', a.experience_summary,
             'created_at', a.created_at,
             'applicant_name', coalesce(nullif(p.name, ''), 'New user'),
             'applicant_email', u.email,
             'existing_organization', (
               select o.name from public.organizations o
               where a.kind <> 'mentor'
                 and lower(o.name) = lower(a.organization_name)
                 and o.type = case a.kind when 'recruiter' then 'company'::public.org_type
                                          else 'university'::public.org_type end
               limit 1))
           order by a.created_at)
    from public.role_applications a
    join auth.users u on u.id = a.user_id
    left join public.profiles p on p.user_id = a.user_id
    where a.status = 'pending'), '[]'::jsonb);
end;
$$;

create function public.review_role_application(p_id uuid, p_approve boolean, p_note text default null)
returns public.role_applications
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_app  public.role_applications;
  v_type public.org_type;
  v_org  uuid;
begin
  if not public.has_grant('operator') then
    raise exception 'Operators only.' using errcode = 'PT403', hint = 'FORBIDDEN';
  end if;
  select * into v_app from public.role_applications where id = p_id for update;
  if not found then
    raise exception 'Application not found.' using errcode = 'PT404', hint = 'NOT_FOUND';
  end if;
  if v_app.status <> 'pending' then
    raise exception 'This application was already decided.' using errcode = 'PT409', hint = 'ALREADY_DECIDED';
  end if;

  if p_approve then
    if v_app.kind = 'mentor' then
      insert into public.mentors (user_id, niche, experience_summary)
      values (v_app.user_id, v_app.niche, v_app.experience_summary)
      on conflict (user_id) do update set is_active = true;
      insert into public.role_grants (user_id, role) values (v_app.user_id, 'mentor') on conflict do nothing;
    else
      v_type := case v_app.kind when 'recruiter' then 'company'::public.org_type else 'university'::public.org_type end;
      select id into v_org from public.organizations
      where lower(name) = lower(v_app.organization_name) and type = v_type
      order by created_at limit 1;
      if v_org is null then
        insert into public.organizations (name, type) values (v_app.organization_name, v_type) returning id into v_org;
      end if;
      insert into public.memberships (user_id, organization_id, role)
      values (v_app.user_id, v_org,
              case v_app.kind when 'recruiter' then 'recruiter'::public.membership_role else 'admin'::public.membership_role end)
      on conflict do nothing;
    end if;
  end if;

  update public.role_applications
  set status = case when p_approve then 'approved'::public.role_application_status else 'rejected' end,
      decision_note = nullif(btrim(coalesce(p_note, '')), ''),
      reviewed_by = (select auth.uid()),
      reviewed_at = now(),
      organization_id = v_org
  where id = p_id
  returning * into v_app;

  perform public.log_event(case when p_approve then 'role_application.approved' else 'role_application.rejected' end,
                           'role_application', v_app.id,
                           jsonb_build_object('kind', v_app.kind, 'organization_id', v_org));
  return v_app;
end;
$$;

-- Students: a university imports a roster with emails; when a student with that email signs up and
-- confirms it, the rows link to their account (the university's record becomes theirs to apply with).
-- Only unclaimed rows, and only for a confirmed email, so nobody can claim someone else's record.
create function public.claim_roster_records()
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_uid   uuid := (select auth.uid());
  v_email text;
  v_count integer;
begin
  select lower(email) into v_email from auth.users where id = v_uid and email_confirmed_at is not null;
  if v_email is null then
    return 0;
  end if;
  update public.student_roster r
  set verified_user_id = v_uid
  where r.id in (select distinct on (c.university_id) c.id  -- at most one record per university
                 from public.student_roster c
                 where c.email = v_email and c.verified_user_id is null
                   and not exists (select 1 from public.student_roster o
                                   where o.university_id = c.university_id and o.verified_user_id = v_uid)
                 order by c.university_id, c.created_at);
  get diagnostics v_count = row_count;
  if v_count > 0 then
    perform public.log_event('roster.claimed', 'user', v_uid, jsonb_build_object('rows', v_count));
  end if;
  return v_count;
end;
$$;

revoke all on function public.has_role_for(uuid, public.role_application_kind) from public, anon, authenticated;
revoke all on function public.submit_role_application(public.role_application_kind, text, text, text, text, text) from public, anon;
revoke all on function public.operator_role_applications() from public, anon;
revoke all on function public.review_role_application(uuid, boolean, text) from public, anon;
revoke all on function public.claim_roster_records() from public, anon;
grant execute on function public.submit_role_application(public.role_application_kind, text, text, text, text, text) to authenticated;
grant execute on function public.operator_role_applications() to authenticated;
grant execute on function public.review_role_application(uuid, boolean, text) to authenticated;
grant execute on function public.claim_roster_records() to authenticated;
