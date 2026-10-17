-- 0010 transactional operations behind the API (docs/api-contract.md §4).
-- Steps S09-S14. Each function:
--   * is SECURITY DEFINER with search_path = '' and fully qualified names,
--   * derives the caller from auth.uid() and checks ownership itself,
--   * signals API errors with SQLSTATE PTxxx (PostgREST uses the digits as the HTTP status)
--     and puts the API error code in HINT, which backend/app/db.py maps to the error body.
-- A direct Data API call therefore enforces exactly what the FastAPI endpoint enforces.

-- ---------------------------------------------------------------------------
-- Eligibility: the one authoritative predicate (architecture.md §6, §8)
-- ---------------------------------------------------------------------------

create function public.evaluate_drive_eligibility(p_drive_id uuid)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_uid     uuid := auth.uid();
  v_drive   public.campus_drives%rowtype;
  v_roster  public.student_roster%rowtype;
  v_skills  text[];
  v_reasons jsonb := '[]'::jsonb;
  v_missing text[];
  v_match   text[];
  v_skill   text;
begin
  if v_uid is null then
    raise exception 'Login required.' using errcode = 'PT401', hint = 'UNAUTHENTICATED';
  end if;

  select * into v_drive from public.campus_drives where id = p_drive_id;
  if not found
     or not (public.is_verified_student(v_drive.university_id)
             or public.is_member(v_drive.university_id, 'admin')) then
    raise exception 'Drive not found.' using errcode = 'PT404', hint = 'NOT_FOUND';
  end if;

  select * into v_roster from public.student_roster
  where university_id = v_drive.university_id and verified_user_id = v_uid;

  select coalesce(p.skills, '{}') into v_skills from public.profiles p where p.user_id = v_uid;
  v_skills := coalesce(v_skills, '{}');
  v_match := array(select s from unnest(v_drive.required_skills) s where s = any(v_skills) order by s);
  v_missing := array(select s from unnest(v_drive.required_skills) s where not (s = any(v_skills)) order by s);

  if v_roster.id is null then
    v_reasons := v_reasons || jsonb_build_object('code', 'NOT_ON_ROSTER',
      'message', 'You are not on this university''s roster.');
  else
    if cardinality(v_drive.allowed_branches) > 0 and not (v_roster.branch = any(v_drive.allowed_branches)) then
      v_reasons := v_reasons || jsonb_build_object('code', 'BRANCH_NOT_ALLOWED',
        'message', format('Branch %s is not eligible for this drive.', upper(v_roster.branch)));
    end if;
    if v_roster.batch <> v_drive.batch then
      v_reasons := v_reasons || jsonb_build_object('code', 'BATCH_MISMATCH',
        'message', format('This drive is for batch %s.', v_drive.batch));
    end if;
    if v_drive.min_cgpa is not null then
      if v_roster.cgpa is null then
        v_reasons := v_reasons || jsonb_build_object('code', 'CGPA_MISSING',
          'message', 'Your university record has no CGPA.');
      elsif v_roster.cgpa < v_drive.min_cgpa then
        v_reasons := v_reasons || jsonb_build_object('code', 'CGPA_BELOW_MINIMUM',
          'message', format('Minimum CGPA is %s.', v_drive.min_cgpa));
      end if;
    end if;
  end if;

  foreach v_skill in array v_missing loop
    v_reasons := v_reasons || jsonb_build_object('code', 'MISSING_REQUIRED_SKILL',
      'message', format('%s is required.', initcap(v_skill)));
  end loop;

  if v_drive.deadline < now() then
    v_reasons := v_reasons || jsonb_build_object('code', 'DEADLINE_PASSED',
      'message', 'The drive deadline has passed.');
  end if;

  return jsonb_build_object(
    'drive_id', v_drive.id,
    'opportunity_id', v_drive.opportunity_id,
    'eligible', jsonb_array_length(v_reasons) = 0,
    'reasons', v_reasons,
    'matching_skills', to_jsonb(v_match),
    'missing_skills', to_jsonb(v_missing),
    'rules_version', v_drive.rules_version,
    'evaluated_at', now(),
    'record', case when v_roster.id is null then null else jsonb_build_object(
      'branch', v_roster.branch, 'batch', v_roster.batch, 'cgpa', v_roster.cgpa) end
  );
end;
$$;

-- ---------------------------------------------------------------------------
-- Application submission (architecture.md §6 rule 4)
-- ---------------------------------------------------------------------------

create function public.submit_application(p_opportunity_id uuid, p_drive_id uuid default null)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_uid     uuid := auth.uid();
  v_opp     public.opportunities%rowtype;
  v_profile public.profiles%rowtype;
  v_elig    jsonb;
  v_app     public.applications%rowtype;
begin
  if v_uid is null then
    raise exception 'Login required.' using errcode = 'PT401', hint = 'UNAUTHENTICATED';
  end if;

  select * into v_opp from public.opportunities where id = p_opportunity_id;
  if not found
     or (v_opp.visibility = 'campus'
         and not public.can_view_campus_opportunity(v_opp.id)
         and not public.is_member(v_opp.company_id, 'recruiter')) then
    raise exception 'Opportunity not found.' using errcode = 'PT404', hint = 'NOT_FOUND';
  end if;
  if v_opp.status <> 'open' then
    raise exception 'This listing is closed.' using errcode = 'PT409', hint = 'LISTING_CLOSED';
  end if;
  if v_opp.deadline < now() then
    raise exception 'The application deadline has passed.' using errcode = 'PT409', hint = 'DEADLINE_PASSED';
  end if;
  if v_opp.visibility = 'campus' and p_drive_id is null then
    raise exception 'Campus listings require applying through an authorized drive.'
      using errcode = 'PT403', hint = 'DRIVE_REQUIRED';
  end if;

  if p_drive_id is not null then
    v_elig := public.evaluate_drive_eligibility(p_drive_id);
    if (v_elig ->> 'opportunity_id')::uuid <> p_opportunity_id then
      raise exception 'That drive is not for this opportunity.' using errcode = 'PT422', hint = 'VALIDATION_ERROR';
    end if;
    if not (v_elig ->> 'eligible')::boolean then
      raise exception 'You do not meet this drive''s eligibility rules.' using errcode = 'PT403', hint = 'NOT_ELIGIBLE';
    end if;
  end if;

  select * into v_profile from public.profiles where user_id = v_uid;

  begin
    insert into public.applications
      (opportunity_id, applicant_id, drive_id, eligibility_snapshot, profile_snapshot)
    values (
      p_opportunity_id, v_uid, p_drive_id, v_elig,
      jsonb_build_object(
        'name', v_profile.name,
        'specialization', v_profile.specialization,
        'education_summary', v_profile.education_summary,
        'skills', to_jsonb(coalesce(v_profile.skills, '{}')),
        'portfolio_url', v_profile.portfolio_url)
    )
    returning * into v_app;
  exception when unique_violation then
    raise exception 'You have already applied to this opportunity.' using errcode = 'PT409', hint = 'ALREADY_APPLIED';
  end;

  return jsonb_build_object(
    'id', v_app.id, 'opportunity_id', v_app.opportunity_id, 'title', v_opp.title,
    'applicant_id', v_app.applicant_id, 'drive_id', v_app.drive_id, 'status', v_app.status,
    'created_at', v_app.created_at, 'updated_at', v_app.updated_at, 'profile_snapshot', null);
end;
$$;

-- ---------------------------------------------------------------------------
-- Roster commit: all rows or none; preserves account links (architecture.md §6 rule 5)
-- ---------------------------------------------------------------------------

create function public.commit_roster(p_university_id uuid, p_rows jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_row       jsonb;
  v_existing  public.student_roster%rowtype;
  v_inserted  int := 0;
  v_updated   int := 0;
  v_unchanged int := 0;
  v_name text; v_email text; v_branch text; v_batch int; v_cgpa numeric;
begin
  if not public.is_member(p_university_id, 'admin') then
    raise exception 'Only this university''s admins can import its roster.' using errcode = 'PT403', hint = 'FORBIDDEN';
  end if;
  if jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) > 100 then
    raise exception 'Rows must be an array of at most 100 records.' using errcode = 'PT422', hint = 'VALIDATION_ERROR';
  end if;

  for v_row in select * from jsonb_array_elements(p_rows) loop
    v_name := btrim(v_row ->> 'name');
    v_email := lower(btrim(v_row ->> 'email'));
    v_branch := lower(btrim(v_row ->> 'branch'));
    v_batch := (v_row ->> 'batch')::int;
    v_cgpa := nullif(v_row ->> 'cgpa', '')::numeric;

    select * into v_existing from public.student_roster
    where university_id = p_university_id and student_id = btrim(v_row ->> 'student_id')
    for update;

    if not found then
      insert into public.student_roster (university_id, student_id, name, email, branch, batch, cgpa)
      values (p_university_id, btrim(v_row ->> 'student_id'), v_name, v_email, v_branch, v_batch, v_cgpa);
      v_inserted := v_inserted + 1;
    elsif (v_existing.name, v_existing.email, v_existing.branch, v_existing.batch, v_existing.cgpa)
          is distinct from (v_name, v_email, v_branch, v_batch, v_cgpa) then
      update public.student_roster
      set name = v_name, email = v_email, branch = v_branch, batch = v_batch, cgpa = v_cgpa
      where id = v_existing.id;  -- verified_user_id is never touched
      v_updated := v_updated + 1;
    else
      v_unchanged := v_unchanged + 1;
    end if;
  end loop;

  return jsonb_build_object('inserted', v_inserted, 'updated', v_updated, 'unchanged', v_unchanged);
end;
$$;

-- ---------------------------------------------------------------------------
-- University reporting: drive-sourced applications only (architecture.md §9)
-- ---------------------------------------------------------------------------

create function public.university_report_rows(
  p_university_id uuid, p_branch text default null, p_batch int default null, p_drive_id uuid default null)
returns table (
  application_id uuid, student_id text, student_name text, branch text, batch int,
  opportunity_title text, company_name text, status public.application_status, applied_at timestamptz,
  applicant_id uuid)
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if not public.is_member(p_university_id, 'admin') then
    raise exception 'Only this university''s admins can view its report.' using errcode = 'PT403', hint = 'FORBIDDEN';
  end if;
  return query
    select a.id, r.student_id, r.name, r.branch, r.batch, o.title, c.name, a.status, a.created_at, a.applicant_id
    from public.applications a
    join public.campus_drives d on d.id = a.drive_id and d.university_id = p_university_id
    join public.opportunities o on o.id = a.opportunity_id
    join public.organizations c on c.id = o.company_id
    left join public.student_roster r on r.university_id = p_university_id and r.verified_user_id = a.applicant_id
    where (p_drive_id is null or a.drive_id = p_drive_id)
      and (p_branch is null or r.branch = lower(btrim(p_branch)))
      and (p_batch is null or r.batch = p_batch)
    order by a.created_at, a.id;
end;
$$;

create function public.university_report(
  p_university_id uuid, p_branch text default null, p_batch int default null, p_drive_id uuid default null)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'university_id', p_university_id,
    'branch', lower(btrim(p_branch)),
    'batch', p_batch,
    'drive_id', p_drive_id,
    'applications', count(*),
    'shortlisted', count(*) filter (where status = 'shortlisted'),
    'offered', count(*) filter (where status = 'offered'),
    'students_with_offers', count(distinct applicant_id) filter (where status = 'offered'))
  from public.university_report_rows(p_university_id, p_branch, p_batch, p_drive_id)
$$;

-- ---------------------------------------------------------------------------
-- Mentor directory: consented public projection of active mentors (architecture.md §6)
-- ---------------------------------------------------------------------------

create function public.list_mentors(
  p_niche text default null, p_skill text default null, p_limit int default 20, p_offset int default 0)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with matches as (
    select m.id, m.user_id, coalesce(nullif(p.name, ''), 'Mentor') as name, m.niche,
           m.experience_summary, coalesce(p.skills, '{}') as skills
    from public.mentors m
    left join public.profiles p on p.user_id = m.user_id
    where m.is_active
      and (select auth.uid()) is not null
      and (p_niche is null or m.niche ilike '%' || p_niche || '%')
      and (p_skill is null or lower(btrim(p_skill)) = any(coalesce(p.skills, '{}')))
  )
  select jsonb_build_object(
    'total', (select count(*) from matches),
    'items', coalesce((
      select jsonb_agg(jsonb_build_object(
               'id', id, 'user_id', user_id, 'name', name, 'niche', niche,
               'experience_summary', experience_summary, 'skills', to_jsonb(skills),
               'mentor_verified', false,
               'match_reason', case when p_skill is null then null
                                    else 'Matches skill: ' || lower(btrim(p_skill)) end)
             order by name, id)
      from (select * from matches order by name, id limit least(greatest(p_limit, 1), 100)
            offset greatest(p_offset, 0)) page
    ), '[]'::jsonb))
$$;

-- ---------------------------------------------------------------------------
-- Display names for people the caller legitimately interacts with
-- ---------------------------------------------------------------------------

create function public.display_names(p_user_ids uuid[])
returns table (user_id uuid, name text)
language sql
stable
security definer
set search_path = ''
as $$
  select p.user_id, p.name
  from public.profiles p
  where p.user_id = any(p_user_ids)
    and (
      p.is_public
      or p.user_id = (select auth.uid())
      or exists (select 1 from public.mentors m where m.user_id = p.user_id and m.is_active)
      or exists (select 1 from public.mentor_requests r join public.mentors m on m.id = r.mentor_id
                 where (r.requester_id = p.user_id and m.user_id = (select auth.uid()))
                    or (r.requester_id = (select auth.uid()) and m.user_id = p.user_id))
      or exists (select 1 from public.collaboration_requests c join public.ventures v on v.id = c.venture_id
                 where (c.requester_id = p.user_id and v.founder_id = (select auth.uid()))
                    or (c.requester_id = (select auth.uid()) and v.founder_id = p.user_id))
      or exists (select 1 from public.applications a
                 where a.applicant_id = p.user_id and public.is_opportunity_recruiter(a.opportunity_id))
    )
$$;

-- ---------------------------------------------------------------------------
-- Execute grants: signed-in users only
-- ---------------------------------------------------------------------------

revoke all on function public.evaluate_drive_eligibility(uuid) from public, anon;
revoke all on function public.submit_application(uuid, uuid) from public, anon;
revoke all on function public.commit_roster(uuid, jsonb) from public, anon;
revoke all on function public.university_report_rows(uuid, text, int, uuid) from public, anon;
revoke all on function public.university_report(uuid, text, int, uuid) from public, anon;
revoke all on function public.list_mentors(text, text, int, int) from public, anon;
revoke all on function public.display_names(uuid[]) from public, anon;

grant execute on function public.evaluate_drive_eligibility(uuid) to authenticated;
grant execute on function public.submit_application(uuid, uuid) to authenticated;
grant execute on function public.commit_roster(uuid, jsonb) to authenticated;
grant execute on function public.university_report_rows(uuid, text, int, uuid) to authenticated;
grant execute on function public.university_report(uuid, text, int, uuid) to authenticated;
grant execute on function public.list_mentors(text, text, int, int) to authenticated;
grant execute on function public.display_names(uuid[]) to authenticated;
