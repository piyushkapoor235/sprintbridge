-- 0015 independent mentor skill verification (docs/threat-model.md §4, docs/skill-intelligence.md §1).
--
--   * The candidate never chooses: the system picks a random eligible verifier, weighted by quality.
--   * Eligible = active mentor, calibrated expertise in the skill at >= the requested level,
--     quality score >= 0.6, no conflict of interest, and under the per-institution monthly cap.
--   * Conflict = same person; shared organization (membership or roster); any prior mentor request
--     or venture collaboration between them; this verifier already verified the candidate;
--     reciprocity (the candidate, as a mentor, has verified this verifier).
--   * The verifier's identity is revealed to the candidate only when the session starts.
--   * Fee is the same for pass and fail; the verifier's 60% share is held, not paid on the spot.
--   * A sample of results (default 20%) goes to a second, independent verifier; disagreement puts
--     the badge under review, claws back the payout, and lowers the first verifier's quality score.
--   * Failed attempts start a 30-day cooldown per skill; passed badges expire after 18 months.
-- Everything goes through these functions: users have no direct access to the request tables.

create type public.verification_status as enum ('assigned', 'in_session', 'passed', 'failed', 'under_review');

create table public.mentor_expertise (
  mentor_id uuid not null references public.mentors (id) on delete cascade,
  skill     text not null check (skill = lower(btrim(skill)) and char_length(skill) between 1 and 80),
  level     smallint not null check (level between 1 and 4),
  primary key (mentor_id, skill)
);

alter table public.mentors
  add column quality_score numeric(4, 3) not null default 1.000 check (quality_score between 0 and 1);

create table public.verification_requests (
  id                 uuid primary key default gen_random_uuid(),
  candidate_id       uuid not null references auth.users (id) on delete cascade,
  skill              text not null check (skill = lower(btrim(skill)) and char_length(skill) between 1 and 80),
  level_requested    smallint not null check (level_requested between 1 and 4),
  verifier_id        uuid not null references public.mentors (id),
  status             public.verification_status not null default 'assigned',
  payment_id         uuid not null unique references public.payments (id),
  session_started_at timestamptz,
  decided_at         timestamptz,
  result_level       smallint check (result_level between 1 and 4),
  notes              text check (char_length(notes) <= 2000),
  expires_at         timestamptz,
  created_at         timestamptz not null default now()
);
create index verification_requests_candidate_idx on public.verification_requests (candidate_id, skill);
create index verification_requests_verifier_idx on public.verification_requests (verifier_id, created_at desc);

create table public.verification_audits (
  id           uuid primary key default gen_random_uuid(),
  request_id   uuid not null unique references public.verification_requests (id) on delete cascade,
  auditor_id   uuid not null references public.mentors (id),
  passed       boolean,
  result_level smallint check (result_level between 1 and 4),
  agrees       boolean,
  created_at   timestamptz not null default now(),
  decided_at   timestamptz
);

-- ---------------------------------------------------------------------------
-- Conflict-of-interest checks and verifier selection
-- ---------------------------------------------------------------------------

create function public.user_orgs(p_user uuid)
returns setof uuid
language sql
stable
security definer
set search_path = ''
as $$
  select organization_id from public.memberships where user_id = p_user
  union
  select university_id from public.student_roster where verified_user_id = p_user
$$;

create function public.verifier_conflict(p_mentor_id uuid, p_candidate uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  with m as (select user_id from public.mentors where id = p_mentor_id)
  select (select user_id from m) = p_candidate
      or exists (select 1 from public.user_orgs((select user_id from m)) a
                 join public.user_orgs(p_candidate) b on a = b)
      or exists (select 1 from public.mentor_requests r join public.mentors rm on rm.id = r.mentor_id
                 where (r.mentor_id = p_mentor_id and r.requester_id = p_candidate)
                    or (rm.user_id = p_candidate and r.requester_id = (select user_id from m)))
      or exists (select 1 from public.collaboration_requests c join public.ventures v on v.id = c.venture_id
                 where (c.requester_id = (select user_id from m) and v.founder_id = p_candidate)
                    or (c.requester_id = p_candidate and v.founder_id = (select user_id from m)))
      or exists (select 1 from public.verification_requests v
                 where v.verifier_id = p_mentor_id and v.candidate_id = p_candidate)
      or exists (select 1 from public.verification_requests v join public.mentors cm on cm.id = v.verifier_id
                 where cm.user_id = p_candidate and v.candidate_id = (select user_id from m))
$$;

-- At most 3 verifications a month per verifier for candidates from the same institution.
create function public.verifier_at_cap(p_mentor_id uuid, p_candidate uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select (select count(*) from public.verification_requests v
          where v.verifier_id = p_mentor_id and v.created_at > now() - interval '30 days'
            and exists (select 1 from public.user_orgs(v.candidate_id) a
                        join public.user_orgs(p_candidate) b on a = b)) >= 3
$$;

create function public.pick_verifier(p_candidate uuid, p_skill text, p_level int, p_exclude uuid default null)
returns uuid
language sql
volatile
security definer
set search_path = ''
as $$
  select m.id
  from public.mentors m
  join public.mentor_expertise e on e.mentor_id = m.id and e.skill = p_skill and e.level >= p_level
  where m.is_active and m.quality_score >= 0.6
    and m.id is distinct from p_exclude
    and not public.verifier_conflict(m.id, p_candidate)
    and not public.verifier_at_cap(m.id, p_candidate)
  order by random() * (0.5 + m.quality_score) desc
  limit 1
$$;

create function public.verification_fee(p_user uuid)
returns int
language sql
stable
security definer
set search_path = ''
as $$
  select case when public.seeker_audience(p_user) = 'student' then 499 else 999 end
$$;

-- ---------------------------------------------------------------------------
-- Candidate side
-- ---------------------------------------------------------------------------

create function public.request_skill_verification(p_skill text, p_level int, p_confirm_test_payment boolean default false)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_uid      uuid := auth.uid();
  v_skill    text := lower(btrim(p_skill));
  v_last     public.verification_requests;
  v_previous uuid[];
  v_verifier uuid;
  v_fee      int;
  v_pay      uuid;
  v_req      public.verification_requests;
begin
  if v_uid is null then
    raise exception 'Login required.' using errcode = 'PT401', hint = 'UNAUTHENTICATED';
  end if;
  if v_skill = '' or char_length(v_skill) > 80 or p_level not between 1 and 4 then
    raise exception 'Choose a skill and a level from 1 to 4.' using errcode = 'PT422', hint = 'VALIDATION_ERROR';
  end if;
  if exists (select 1 from public.verification_requests
             where candidate_id = v_uid and skill = v_skill and status in ('assigned', 'in_session')) then
    raise exception 'You already have an open verification for %.', v_skill using errcode = 'PT409', hint = 'ALREADY_REQUESTED';
  end if;
  if exists (select 1 from public.verification_requests
             where candidate_id = v_uid and skill = v_skill and status = 'passed'
               and result_level >= p_level and expires_at > now()) then
    raise exception 'You are already mentor-verified in % at this level.', v_skill using errcode = 'PT409', hint = 'ALREADY_VERIFIED';
  end if;
  select * into v_last from public.verification_requests
  where candidate_id = v_uid and skill = v_skill and status = 'failed'
  order by decided_at desc limit 1;
  if v_last.id is not null and v_last.decided_at > now() - interval '30 days' then
    raise exception 'You can retry % after %.', v_skill, to_char(v_last.decided_at + interval '30 days', 'DD Mon YYYY')
      using errcode = 'PT409', hint = 'COOLDOWN';
  end if;

  v_verifier := public.pick_verifier(v_uid, v_skill, p_level);  -- conflict check also excludes past verifiers
  if v_verifier is null then
    raise exception 'No independent verifier is available for % at level % yet. You have not been charged.', v_skill, p_level
      using errcode = 'PT409', hint = 'NO_VERIFIER_AVAILABLE';
  end if;

  v_fee := public.verification_fee(v_uid);
  if not p_confirm_test_payment then
    raise exception 'Verification costs ₹% (test mode), the same whether you pass or not. Confirm the test payment to continue.', v_fee
      using errcode = 'PT402', hint = 'PAYMENT_REQUIRED';
  end if;
  v_pay := public.capture_test_payment_for(v_uid, 'verification', v_fee, v_skill);

  insert into public.verification_requests (candidate_id, skill, level_requested, verifier_id, payment_id)
  values (v_uid, v_skill, p_level, v_verifier, v_pay)
  returning * into v_req;
  perform public.log_event('verification.requested', 'verification', v_req.id,
    jsonb_build_object('skill', v_skill, 'level', p_level, 'verifier_id', v_verifier));
  return jsonb_build_object('id', v_req.id, 'skill', v_skill, 'level_requested', p_level,
                            'status', v_req.status, 'fee_inr', v_fee);
end;
$$;

create function public.my_verifications()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(jsonb_agg(jsonb_build_object(
      'id', v.id, 'skill', v.skill, 'level_requested', v.level_requested, 'status', v.status,
      'created_at', v.created_at, 'session_started_at', v.session_started_at, 'decided_at', v.decided_at,
      'result_level', v.result_level, 'notes', v.notes, 'expires_at', v.expires_at,
      'fee_inr', (select amount_inr from public.payments p where p.id = v.payment_id),
      'retry_after', case when v.status = 'failed' then v.decided_at + interval '30 days' end,
      'verifier', case when v.session_started_at is not null then jsonb_build_object(
          'name', coalesce((select nullif(pr.name, '') from public.mentors m join public.profiles pr on pr.user_id = m.user_id
                            where m.id = v.verifier_id), 'Mentor'),
          'niche', (select niche from public.mentors m where m.id = v.verifier_id)) end)
    order by v.created_at desc), '[]'::jsonb)
  from public.verification_requests v
  where v.candidate_id = (select auth.uid())
$$;

-- Passed, unexpired, not under review: the only source of the Mentor-verified label.
create function public.my_verified_skills()
returns table (skill text, level smallint, verified_at timestamptz, expires_at timestamptz)
language sql
stable
security definer
set search_path = ''
as $$
  select distinct on (v.skill) v.skill, v.result_level, v.decided_at, v.expires_at
  from public.verification_requests v
  where v.candidate_id = (select auth.uid()) and v.status = 'passed' and v.expires_at > now()
  order by v.skill, v.result_level desc
$$;

-- ---------------------------------------------------------------------------
-- Verifier side
-- ---------------------------------------------------------------------------

create function public.my_mentor_id()
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select id from public.mentors where user_id = (select auth.uid())
$$;

create function public.verifier_queue()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'expertise', coalesce((select jsonb_agg(jsonb_build_object('skill', e.skill, 'level', e.level) order by e.skill)
                           from public.mentor_expertise e where e.mentor_id = public.my_mentor_id()), '[]'::jsonb),
    'quality_score', (select quality_score from public.mentors where id = public.my_mentor_id()),
    'assignments', coalesce((
      select jsonb_agg(jsonb_build_object(
               'id', v.id, 'skill', v.skill, 'level_requested', v.level_requested, 'status', v.status,
               'candidate_name', coalesce((select nullif(name, '') from public.profiles where user_id = v.candidate_id), 'Candidate'),
               'created_at', v.created_at, 'session_started_at', v.session_started_at,
               'decided_at', v.decided_at, 'result_level', v.result_level)
             order by v.created_at desc)
      from public.verification_requests v where v.verifier_id = public.my_mentor_id()), '[]'::jsonb),
    'audits', coalesce((
      select jsonb_agg(jsonb_build_object(
               'id', a.id, 'skill', v.skill, 'level_requested', v.level_requested,
               'candidate_name', coalesce((select nullif(name, '') from public.profiles where user_id = v.candidate_id), 'Candidate'),
               'created_at', a.created_at, 'decided_at', a.decided_at)  -- blind: the first result is not shown
             order by a.created_at desc)
      from public.verification_audits a join public.verification_requests v on v.id = a.request_id
      where a.auditor_id = public.my_mentor_id()), '[]'::jsonb))
$$;

create function public.start_verification_session(p_request_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_req public.verification_requests;
begin
  select * into v_req from public.verification_requests where id = p_request_id for update;
  if not found or v_req.verifier_id is distinct from public.my_mentor_id() then
    raise exception 'Verification not found.' using errcode = 'PT404', hint = 'NOT_FOUND';
  end if;
  if v_req.status <> 'assigned' then
    raise exception 'This session has already started or finished.' using errcode = 'PT409', hint = 'INVALID_TRANSITION';
  end if;
  update public.verification_requests set status = 'in_session', session_started_at = now() where id = p_request_id;
  perform public.log_event('verification.session_started', 'verification', p_request_id, '{}'::jsonb);
  return jsonb_build_object('id', p_request_id, 'status', 'in_session');
end;
$$;

create function public.submit_verification_result(p_request_id uuid, p_passed boolean, p_level int, p_notes text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_req     public.verification_requests;
  v_max     int;
  v_pay     public.payments;
  v_share   int;
  v_auditor uuid;
  v_rate    numeric := coalesce(nullif(current_setting('sprintbridge.audit_rate', true), '')::numeric, 0.2);
begin
  select * into v_req from public.verification_requests where id = p_request_id for update;
  if not found or v_req.verifier_id is distinct from public.my_mentor_id() then
    raise exception 'Verification not found.' using errcode = 'PT404', hint = 'NOT_FOUND';
  end if;
  if v_req.status <> 'in_session' then
    raise exception 'Start the session before recording a result.' using errcode = 'PT409', hint = 'INVALID_TRANSITION';
  end if;
  select level into v_max from public.mentor_expertise where mentor_id = v_req.verifier_id and skill = v_req.skill;
  if p_passed and (p_level is null or p_level < 1 or p_level > v_max) then
    raise exception 'A pass needs a level from 1 to % (your own verified level).', v_max using errcode = 'PT422', hint = 'VALIDATION_ERROR';
  end if;

  update public.verification_requests
  set status = case when p_passed then 'passed'::public.verification_status else 'failed'::public.verification_status end,
      result_level = case when p_passed then p_level end,
      notes = left(nullif(btrim(p_notes), ''), 2000),
      decided_at = now(),
      expires_at = case when p_passed then now() + interval '18 months' end
  where id = p_request_id;

  -- Same pay for pass and fail; held until the audit window closes.
  select * into v_pay from public.payments where id = v_req.payment_id;
  v_share := round(v_pay.amount_inr * 0.6);
  insert into public.payouts (payment_id, mentor_id, source, gross_inr, commission_inr, net_inr)
  values (v_pay.id, v_req.verifier_id, 'verification', v_pay.amount_inr, v_pay.amount_inr - v_share, v_share);

  if random() < v_rate then
    v_auditor := public.pick_verifier(v_req.candidate_id, v_req.skill, v_req.level_requested, v_req.verifier_id);
    if v_auditor is not null then
      insert into public.verification_audits (request_id, auditor_id) values (p_request_id, v_auditor);
    end if;
  end if;
  perform public.log_event('verification.decided', 'verification', p_request_id,
    jsonb_build_object('passed', p_passed, 'level', p_level, 'audited', v_auditor is not null));
  return jsonb_build_object('id', p_request_id, 'status', case when p_passed then 'passed' else 'failed' end,
                            'result_level', case when p_passed then p_level end, 'audited', v_auditor is not null);
end;
$$;

create function public.submit_verification_audit(p_audit_id uuid, p_passed boolean, p_level int)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_audit  public.verification_audits;
  v_req    public.verification_requests;
  v_agrees boolean;
begin
  select * into v_audit from public.verification_audits where id = p_audit_id for update;
  if not found or v_audit.auditor_id is distinct from public.my_mentor_id() then
    raise exception 'Audit not found.' using errcode = 'PT404', hint = 'NOT_FOUND';
  end if;
  if v_audit.decided_at is not null then
    raise exception 'This audit is already recorded.' using errcode = 'PT409', hint = 'INVALID_TRANSITION';
  end if;
  if p_passed and (p_level is null or p_level not between 1 and 4) then
    raise exception 'A pass needs a level from 1 to 4.' using errcode = 'PT422', hint = 'VALIDATION_ERROR';
  end if;
  select * into v_req from public.verification_requests where id = v_audit.request_id for update;
  v_agrees := (p_passed = (v_req.status = 'passed'))
              and (not p_passed or abs(p_level - v_req.result_level) <= 1);

  update public.verification_audits
  set passed = p_passed, result_level = case when p_passed then p_level end, agrees = v_agrees, decided_at = now()
  where id = p_audit_id;

  if v_agrees then
    update public.payouts set status = 'released', released_at = now()
    where payment_id = v_req.payment_id and source = 'verification' and status = 'held';
  else
    update public.verification_requests set status = 'under_review' where id = v_req.id and status = 'passed';
    update public.payouts set status = 'clawed_back'
    where payment_id = v_req.payment_id and source = 'verification' and status = 'held';
  end if;
  update public.mentors m
  set quality_score = (select round(avg(case when a.agrees then 1 else 0 end), 3)
                       from public.verification_audits a join public.verification_requests r on r.id = a.request_id
                       where r.verifier_id = m.id and a.agrees is not null)
  where m.id = v_req.verifier_id;
  perform public.log_event('verification.audited', 'verification', v_req.id, jsonb_build_object('agrees', v_agrees));
  return jsonb_build_object('audit_id', p_audit_id, 'agrees', v_agrees);
end;
$$;

-- ---------------------------------------------------------------------------
-- Mentor directory: calibrated experts for the skill rank first; price shown (pay never ranks)
-- ---------------------------------------------------------------------------

create or replace function public.list_mentors(
  p_niche text default null, p_skill text default null, p_limit int default 20, p_offset int default 0)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with wanted as (select lower(btrim(p_skill)) as skill),
  matches as (
    select m.id, m.user_id, coalesce(nullif(p.name, ''), 'Mentor') as name, m.niche,
           m.experience_summary, coalesce(p.skills, '{}') as skills, m.session_price_inr,
           exists (select 1 from public.mentor_expertise e where e.mentor_id = m.id and e.skill = (select skill from wanted)) as expert,
           coalesce((select jsonb_agg(jsonb_build_object('skill', e.skill, 'level', e.level) order by e.skill)
                     from public.mentor_expertise e where e.mentor_id = m.id), '[]'::jsonb) as expertise
    from public.mentors m
    left join public.profiles p on p.user_id = m.user_id
    where m.is_active
      and (select auth.uid()) is not null
      and (p_niche is null or m.niche ilike '%' || p_niche || '%')
      and (p_skill is null
           or (select skill from wanted) = any(coalesce(p.skills, '{}'))
           or exists (select 1 from public.mentor_expertise e where e.mentor_id = m.id and e.skill = (select skill from wanted)))
  )
  select jsonb_build_object(
    'total', (select count(*) from matches),
    'items', coalesce((
      select jsonb_agg(jsonb_build_object(
               'id', id, 'user_id', user_id, 'name', name, 'niche', niche,
               'experience_summary', experience_summary, 'skills', to_jsonb(skills),
               'mentor_verified', expert, 'expertise', expertise, 'session_price_inr', session_price_inr,
               'match_reason', case when p_skill is null then null
                                    when expert then 'Verified expert in ' || (select skill from wanted)
                                    else 'Matches skill: ' || (select skill from wanted) end)
             order by expert desc, name, id)
      from (select * from matches order by expert desc, name, id
            limit least(greatest(p_limit, 1), 100) offset greatest(p_offset, 0)) page
    ), '[]'::jsonb))
$$;

-- ---------------------------------------------------------------------------
-- Privileges: expertise is public; requests and audits only through the functions above.
-- ---------------------------------------------------------------------------

alter table public.mentor_expertise enable row level security;
alter table public.verification_requests enable row level security;
alter table public.verification_audits enable row level security;
revoke all on public.mentor_expertise, public.verification_requests, public.verification_audits from anon, authenticated;
grant select on public.mentor_expertise to authenticated;
create policy mentor_expertise_read on public.mentor_expertise for select to authenticated using (true);

revoke all on function public.user_orgs(uuid) from public, anon, authenticated;
revoke all on function public.verifier_conflict(uuid, uuid) from public, anon, authenticated;
revoke all on function public.verifier_at_cap(uuid, uuid) from public, anon, authenticated;
revoke all on function public.pick_verifier(uuid, text, int, uuid) from public, anon, authenticated;
revoke all on function public.verification_fee(uuid) from public, anon, authenticated;
revoke all on function public.my_mentor_id() from public, anon, authenticated;

revoke all on function public.request_skill_verification(text, int, boolean) from public, anon;
revoke all on function public.my_verifications() from public, anon;
revoke all on function public.my_verified_skills() from public, anon;
revoke all on function public.verifier_queue() from public, anon;
revoke all on function public.start_verification_session(uuid) from public, anon;
revoke all on function public.submit_verification_result(uuid, boolean, int, text) from public, anon;
revoke all on function public.submit_verification_audit(uuid, boolean, int) from public, anon;
grant execute on function public.request_skill_verification(text, int, boolean) to authenticated;
grant execute on function public.my_verifications() to authenticated;
grant execute on function public.my_verified_skills() to authenticated;
grant execute on function public.verifier_queue() to authenticated;
grant execute on function public.start_verification_session(uuid) to authenticated;
grant execute on function public.submit_verification_result(uuid, boolean, int, text) to authenticated;
grant execute on function public.submit_verification_audit(uuid, boolean, int) to authenticated;
