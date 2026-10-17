-- 0014 plans, quotas, and test-mode payments with mentor escrow (docs/business-model.md).
--
-- Rules carried from the docs:
--   * Money buys access and time, never trust: no plan input reaches ranking or verification results.
--   * Quotas and listing limits are enforced here, so a direct Data API call cannot skip them.
--     They apply to signed-in user actions; owner/seed operations (no auth.uid()) are exempt.
--   * Payments are SIMULATED (provider = 'test'). No card data exists anywhere. A real provider
--     replaces capture_test_payment_for() later without changing the rest.
--   * Mentor session fees sit in escrow: refunded on decline; on completion the mentor's payout is
--     held for a 7-day dispute window, minus the plan commission.

create type public.plan_audience as enum ('student', 'job_seeker', 'recruiter', 'university', 'mentor', 'founder');
create type public.payment_purpose as enum ('subscription', 'mentor_session', 'verification');
create type public.payment_status as enum ('captured', 'refunded');
create type public.payout_status as enum ('held', 'released', 'disputed', 'refunded', 'clawed_back');

create table public.plans (
  code       text primary key,
  audience   public.plan_audience not null,
  name       text not null,
  price_inr  integer not null check (price_inr >= 0),
  period     text not null default 'month' check (period in ('month', 'student_year')),
  limits     jsonb not null default '{}'::jsonb,  -- metric -> int; a missing metric is unlimited
  features   text[] not null default '{}',
  sort       smallint not null default 0
);

insert into public.plans (code, audience, name, price_inr, period, limits, features, sort) values
  ('student_free', 'student', 'Student Free', 0, 'month',
   '{"mentor_requests": 2, "resume_analyses": 1, "jd_reports": 3}',
   '{"Profile and campus applications","Skill-gap view","2 mentor requests a month","1 resume analysis, 3 job-fit reports a month"}', 1),
  ('student_pro', 'student', 'Student Pro', 149, 'month', '{}',
   '{"Unlimited mentor requests","Unlimited resume and job-fit analysis","Detailed gap reports"}', 2),
  ('job_seeker_free', 'job_seeker', 'Job Seeker Free', 0, 'month',
   '{"mentor_requests": 2, "resume_analyses": 1, "jd_reports": 3}',
   '{"Profile and public applications","2 mentor requests a month","1 resume analysis, 3 job-fit reports a month"}', 3),
  ('job_seeker_pro', 'job_seeker', 'Job Seeker Pro', 299, 'month', '{}',
   '{"Unlimited mentor requests","Unlimited resume and job-fit analysis","Application insights"}', 4),
  ('recruiter_free', 'recruiter', 'Recruiter Free', 0, 'month', '{"active_listings": 1}',
   '{"1 active listing","Applicant review"}', 5),
  ('recruiter_starter', 'recruiter', 'Recruiter Starter', 4999, 'month', '{"active_listings": 5}',
   '{"5 active listings","Filter by verified skills","Partner campus drives"}', 6),
  ('recruiter_growth', 'recruiter', 'Recruiter Growth', 14999, 'month', '{}',
   '{"Unlimited listings","Fit-sorted applicants","All verified-data campus drives"}', 7),
  ('university_free', 'university', 'University Free', 0, 'month', '{"drives": 1}',
   '{"Roster import","1 campus drive","Basic report"}', 8),
  ('university_campus', 'university', 'University Campus', 400, 'student_year', '{}',
   '{"Unlimited campus drives","Full placement reports and CSV","Alumni-mentor programme"}', 9),
  ('mentor_free', 'mentor', 'Mentor Free', 0, 'month', '{"commission_percent": 20}',
   '{"Paid sessions with escrow","20% platform commission"}', 10),
  ('mentor_pro', 'mentor', 'Mentor Pro', 499, 'month', '{"commission_percent": 10}',
   '{"10% platform commission","Earnings analytics"}', 11),
  ('founder_free', 'founder', 'Founder Free', 0, 'month', '{"ventures": 1}',
   '{"1 venture","Collaboration requests"}', 12),
  ('founder_pro', 'founder', 'Founder Pro', 999, 'month', '{"ventures": 3}',
   '{"3 ventures","Verified-collaborator filter","Team management"}', 13);

create table public.subscriptions (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid references auth.users (id) on delete cascade,
  organization_id uuid references public.organizations (id) on delete cascade,
  audience        public.plan_audience not null,
  plan_code       text not null references public.plans (code),
  status          text not null default 'active' check (status in ('active', 'cancelled')),
  started_at      timestamptz not null default now(),
  renews_at       timestamptz,
  check ((user_id is null) <> (organization_id is null))
);
create unique index subscriptions_user_audience_idx on public.subscriptions (user_id, audience) where user_id is not null;
create unique index subscriptions_org_audience_idx on public.subscriptions (organization_id, audience) where organization_id is not null;

create table public.payments (
  id         uuid primary key default gen_random_uuid(),
  payer_id   uuid not null references auth.users (id) on delete cascade,
  purpose    public.payment_purpose not null,
  amount_inr integer not null check (amount_inr > 0),
  status     public.payment_status not null default 'captured',
  provider   text not null default 'test' check (provider = 'test'),
  reference  text,
  created_at timestamptz not null default now(),
  refunded_at timestamptz
);
create index payments_payer_idx on public.payments (payer_id, created_at desc);

alter table public.mentors
  add column session_price_inr integer check (session_price_inr between 0 and 100000);
grant update (session_price_inr) on public.mentors to authenticated;

alter table public.mentor_requests
  add column payment_id uuid unique references public.payments (id),
  add column session_status text not null default 'pending'
    check (session_status in ('pending', 'completed', 'disputed'));

create table public.payouts (
  id             uuid primary key default gen_random_uuid(),
  payment_id     uuid not null references public.payments (id),
  mentor_id      uuid not null references public.mentors (id) on delete cascade,
  source         text not null check (source in ('mentor_session', 'verification')),
  gross_inr      integer not null check (gross_inr >= 0),
  commission_inr integer not null check (commission_inr >= 0),
  net_inr        integer not null check (net_inr >= 0),
  status         public.payout_status not null default 'held',
  release_after  timestamptz not null default now() + interval '7 days',
  released_at    timestamptz,
  created_at     timestamptz not null default now()
);
create index payouts_mentor_idx on public.payouts (mentor_id, created_at desc);

create table public.usage_events (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references auth.users (id) on delete cascade,
  metric     text not null check (metric in ('mentor_requests', 'resume_analyses', 'jd_reports')),
  created_at timestamptz not null default now()
);
create index usage_events_user_metric_idx on public.usage_events (user_id, metric, created_at);

-- ---------------------------------------------------------------------------
-- Plan resolution and quotas
-- ---------------------------------------------------------------------------

-- Students on a university roster use student plans; everyone else seeking work uses job-seeker plans.
create function public.seeker_audience(p_user uuid)
returns public.plan_audience
language sql
stable
security definer
set search_path = ''
as $$
  select case when exists (select 1 from public.student_roster r where r.verified_user_id = p_user)
              then 'student'::public.plan_audience else 'job_seeker'::public.plan_audience end
$$;

create function public.active_plan(p_user uuid, p_org uuid, p_audience public.plan_audience)
returns public.plans
language sql
stable
security definer
set search_path = ''
as $$
  select p.* from public.plans p
  where p.code = coalesce(
    (select s.plan_code from public.subscriptions s
     where s.status = 'active' and s.audience = p_audience
       and ((p_org is not null and s.organization_id = p_org) or (p_org is null and s.user_id = p_user))
     limit 1),
    p_audience::text || '_free')
$$;

create function public.consume_quota_for(p_user uuid, p_metric text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_plan  public.plans;
  v_limit int;
  v_used  int;
begin
  v_plan := public.active_plan(p_user, null, public.seeker_audience(p_user));
  v_limit := (v_plan.limits ->> p_metric)::int;
  if v_limit is not null then
    select count(*) into v_used from public.usage_events
    where user_id = p_user and metric = p_metric and created_at >= date_trunc('month', now());
    if v_used >= v_limit then
      raise exception 'Your % plan includes % % a month. Upgrade to Pro for more.',
        v_plan.name, v_limit, replace(p_metric, '_', ' ')
        using errcode = 'PT402', hint = 'QUOTA_EXCEEDED';
    end if;
  end if;
  insert into public.usage_events (user_id, metric) values (p_user, p_metric);
end;
$$;

-- Callable by the API for resume and job-description analysis.
create function public.consume_quota(p_metric text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'Login required.' using errcode = 'PT401', hint = 'UNAUTHENTICATED';
  end if;
  perform public.consume_quota_for(auth.uid(), p_metric);
end;
$$;

create function public.enforce_listing_limit()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_plan  public.plans;
  v_limit int;
  v_open  int;
begin
  -- Non-members are rejected by row security; limits only concern the company's own recruiters.
  if auth.uid() is null or new.status <> 'open' or not public.is_member(new.company_id, 'recruiter') then
    return new;
  end if;
  v_plan := public.active_plan(null, new.company_id, 'recruiter');
  v_limit := (v_plan.limits ->> 'active_listings')::int;
  if v_limit is not null then
    select count(*) into v_open from public.opportunities
    where company_id = new.company_id and status = 'open' and deadline > now() and id <> new.id;
    if v_open >= v_limit then
      raise exception '% includes % active listing(s). Close one or upgrade.', v_plan.name, v_limit
        using errcode = 'PT402', hint = 'PLAN_LIMIT';
    end if;
  end if;
  return new;
end;
$$;

create trigger opportunities_listing_limit before insert or update of status on public.opportunities
  for each row execute function public.enforce_listing_limit();

create function public.enforce_drive_limit()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_plan  public.plans;
  v_limit int;
begin
  if auth.uid() is null or not public.is_member(new.university_id, 'admin') then
    return new;
  end if;
  v_plan := public.active_plan(null, new.university_id, 'university');
  v_limit := (v_plan.limits ->> 'drives')::int;
  if v_limit is not null and (select count(*) from public.campus_drives where university_id = new.university_id) >= v_limit then
    raise exception '% includes % campus drive(s). Upgrade to authorize more.', v_plan.name, v_limit
      using errcode = 'PT402', hint = 'PLAN_LIMIT';
  end if;
  return new;
end;
$$;

create trigger campus_drives_limit before insert on public.campus_drives
  for each row execute function public.enforce_drive_limit();

create function public.enforce_venture_limit()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_plan  public.plans;
  v_limit int;
begin
  if auth.uid() is null or new.founder_id is distinct from auth.uid() then
    return new;
  end if;
  v_plan := public.active_plan(new.founder_id, null, 'founder');
  v_limit := (v_plan.limits ->> 'ventures')::int;
  if v_limit is not null and (select count(*) from public.ventures where founder_id = new.founder_id) >= v_limit then
    raise exception '% includes % venture(s). Upgrade to post more.', v_plan.name, v_limit
      using errcode = 'PT402', hint = 'PLAN_LIMIT';
  end if;
  return new;
end;
$$;

create trigger ventures_limit before insert on public.ventures
  for each row execute function public.enforce_venture_limit();

-- ---------------------------------------------------------------------------
-- Test-mode payments and subscriptions
-- ---------------------------------------------------------------------------

create function public.capture_test_payment_for(p_payer uuid, p_purpose public.payment_purpose, p_amount int, p_reference text)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_id uuid;
begin
  insert into public.payments (payer_id, purpose, amount_inr, reference)
  values (p_payer, p_purpose, p_amount, p_reference)
  returning id into v_id;
  perform public.log_event('payment.captured', 'payment', v_id,
    jsonb_build_object('purpose', p_purpose, 'amount_inr', p_amount, 'provider', 'test'));
  return v_id;
end;
$$;

create function public.subscribe(p_plan_code text, p_organization_id uuid default null, p_confirm_test_payment boolean default false)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_uid    uuid := auth.uid();
  v_plan   public.plans;
  v_amount int;
  v_pay    uuid;
  v_sub    public.subscriptions;
begin
  if v_uid is null then
    raise exception 'Login required.' using errcode = 'PT401', hint = 'UNAUTHENTICATED';
  end if;
  select * into v_plan from public.plans where code = p_plan_code;
  if not found then
    raise exception 'Plan not found.' using errcode = 'PT404', hint = 'NOT_FOUND';
  end if;

  if v_plan.audience in ('recruiter', 'university') then
    if p_organization_id is null or not public.is_member(p_organization_id,
         case when v_plan.audience = 'recruiter' then 'recruiter'::public.membership_role
              else 'admin'::public.membership_role end) then
      raise exception 'Choose an organization you manage for this plan.' using errcode = 'PT403', hint = 'FORBIDDEN';
    end if;
  elsif p_organization_id is not null then
    raise exception 'This plan is for individuals.' using errcode = 'PT422', hint = 'VALIDATION_ERROR';
  elsif v_plan.audience = 'student' and public.seeker_audience(v_uid) <> 'student' then
    raise exception 'Student plans need a university roster link. Choose a job-seeker plan.' using errcode = 'PT403', hint = 'FORBIDDEN';
  elsif v_plan.audience = 'job_seeker' and public.seeker_audience(v_uid) = 'student' then
    raise exception 'You are on a university roster; choose a student plan.' using errcode = 'PT403', hint = 'FORBIDDEN';
  elsif v_plan.audience = 'mentor' and not public.has_grant('mentor') then
    raise exception 'Mentor plans are for mentors.' using errcode = 'PT403', hint = 'FORBIDDEN';
  end if;

  v_amount := case when v_plan.period = 'student_year'
                   then v_plan.price_inr * greatest(1, (select count(*) from public.student_roster where university_id = p_organization_id))::int
                   else v_plan.price_inr end;
  if v_amount > 0 then
    if not p_confirm_test_payment then
      raise exception 'This plan costs ₹% (test mode). Confirm the test payment to continue.', v_amount
        using errcode = 'PT402', hint = 'PAYMENT_REQUIRED';
    end if;
    v_pay := public.capture_test_payment_for(v_uid, 'subscription', v_amount, p_plan_code);
  end if;

  if p_organization_id is null then
    insert into public.subscriptions (user_id, audience, plan_code, renews_at)
    values (v_uid, v_plan.audience, v_plan.code, now() + interval '1 month')
    on conflict (user_id, audience) where user_id is not null
    do update set plan_code = excluded.plan_code, status = 'active', started_at = now(), renews_at = excluded.renews_at
    returning * into v_sub;
  else
    insert into public.subscriptions (organization_id, audience, plan_code, renews_at)
    values (p_organization_id, v_plan.audience, v_plan.code,
            now() + case when v_plan.period = 'student_year' then interval '1 year' else interval '1 month' end)
    on conflict (organization_id, audience) where organization_id is not null
    do update set plan_code = excluded.plan_code, status = 'active', started_at = now(), renews_at = excluded.renews_at
    returning * into v_sub;
  end if;
  perform public.log_event('subscription.changed', 'subscription', v_sub.id,
    jsonb_build_object('plan', v_plan.code, 'amount_inr', v_amount, 'organization_id', p_organization_id));
  return jsonb_build_object('plan_code', v_plan.code, 'audience', v_plan.audience, 'organization_id', p_organization_id,
                            'amount_inr', v_amount, 'payment_id', v_pay, 'renews_at', v_sub.renews_at);
end;
$$;

-- ---------------------------------------------------------------------------
-- Mentor sessions: request (with escrow), refund on decline, complete, dispute
-- ---------------------------------------------------------------------------

create function public.request_mentor(p_mentor_id uuid, p_note text, p_confirm_test_payment boolean default false)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_uid   uuid := auth.uid();
  v_price int;
  v_pay   uuid;
  v_req   public.mentor_requests;
begin
  if v_uid is null then
    raise exception 'Login required.' using errcode = 'PT401', hint = 'UNAUTHENTICATED';
  end if;
  if not public.can_request_mentor(p_mentor_id) then
    raise exception 'You cannot request this mentor.' using errcode = 'PT403', hint = 'FORBIDDEN';
  end if;
  if exists (select 1 from public.mentor_requests where mentor_id = p_mentor_id and requester_id = v_uid) then
    raise exception 'You have already requested this mentor.' using errcode = 'PT409', hint = 'ALREADY_REQUESTED';
  end if;
  select coalesce(session_price_inr, 0) into v_price from public.mentors where id = p_mentor_id;
  if v_price > 0 then
    if not p_confirm_test_payment then
      raise exception 'This mentor charges ₹% per session (test mode). Confirm the test payment to send your request.', v_price
        using errcode = 'PT402', hint = 'PAYMENT_REQUIRED';
    end if;
    v_pay := public.capture_test_payment_for(v_uid, 'mentor_session', v_price, p_mentor_id::text);
  end if;
  insert into public.mentor_requests (mentor_id, requester_id, note, payment_id)
  values (p_mentor_id, v_uid, p_note, v_pay)
  returning * into v_req;
  return to_jsonb(v_req);
end;
$$;

-- Quota + payment guard for every insert path (direct Data API inserts included).
create function public.guard_mentor_request()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    return new;
  end if;
  if coalesce((select session_price_inr from public.mentors where id = new.mentor_id), 0) > 0 and new.payment_id is null then
    raise exception 'This mentor charges per session; request through the app to pay (test mode).'
      using errcode = 'PT402', hint = 'PAYMENT_REQUIRED';
  end if;
  perform public.consume_quota_for(new.requester_id, 'mentor_requests');
  return new;
end;
$$;

create trigger mentor_requests_guard before insert on public.mentor_requests
  for each row execute function public.guard_mentor_request();

create function public.refund_declined_request()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.status = 'declined' and old.status <> 'declined' and new.payment_id is not null then
    update public.payments set status = 'refunded', refunded_at = now() where id = new.payment_id and status = 'captured';
    perform public.log_event('payment.refunded', 'payment', new.payment_id, jsonb_build_object('reason', 'mentor_declined'));
  end if;
  return new;
end;
$$;

create trigger mentor_requests_refund after update of status on public.mentor_requests
  for each row execute function public.refund_declined_request();

create function public.complete_mentor_session(p_request_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_req     public.mentor_requests;
  v_pay     public.payments;
  v_pct     int;
  v_comm    int;
  v_payout  uuid;
begin
  select * into v_req from public.mentor_requests where id = p_request_id for update;
  if not found or not public.is_mentor_owner(v_req.mentor_id) then
    raise exception 'Request not found.' using errcode = 'PT404', hint = 'NOT_FOUND';
  end if;
  if v_req.status <> 'accepted' or v_req.session_status <> 'pending' then
    raise exception 'Only an accepted, not-yet-completed session can be completed.' using errcode = 'PT409', hint = 'INVALID_TRANSITION';
  end if;
  update public.mentor_requests set session_status = 'completed' where id = p_request_id;
  if v_req.payment_id is not null then
    select * into v_pay from public.payments where id = v_req.payment_id;
    v_pct := coalesce(((public.active_plan((select user_id from public.mentors where id = v_req.mentor_id), null, 'mentor')).limits ->> 'commission_percent')::int, 20);
    v_comm := round(v_pay.amount_inr * v_pct / 100.0);
    insert into public.payouts (payment_id, mentor_id, source, gross_inr, commission_inr, net_inr)
    values (v_pay.id, v_req.mentor_id, 'mentor_session', v_pay.amount_inr, v_comm, v_pay.amount_inr - v_comm)
    returning id into v_payout;
  end if;
  perform public.log_event('mentor_session.completed', 'mentor_request', p_request_id, jsonb_build_object('payout_id', v_payout));
  return jsonb_build_object('request_id', p_request_id, 'session_status', 'completed', 'payout_id', v_payout);
end;
$$;

create function public.dispute_mentor_session(p_request_id uuid, p_reason text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_req public.mentor_requests;
begin
  select * into v_req from public.mentor_requests where id = p_request_id for update;
  if not found or v_req.requester_id is distinct from auth.uid() then
    raise exception 'Request not found.' using errcode = 'PT404', hint = 'NOT_FOUND';
  end if;
  if v_req.session_status <> 'completed'
     or not exists (select 1 from public.payouts where payment_id = v_req.payment_id and status = 'held') then
    raise exception 'Only a completed paid session inside its 7-day window can be disputed.' using errcode = 'PT409', hint = 'INVALID_TRANSITION';
  end if;
  update public.mentor_requests set session_status = 'disputed' where id = p_request_id;
  update public.payouts set status = 'disputed' where payment_id = v_req.payment_id and status = 'held';
  perform public.log_event('mentor_session.disputed', 'mentor_request', p_request_id,
    jsonb_build_object('reason', left(coalesce(p_reason, ''), 500)));
  return jsonb_build_object('request_id', p_request_id, 'session_status', 'disputed');
end;
$$;

-- Operators settle money: release held payouts that are past their window, or resolve one payout.
create function public.operator_release_due_payouts()
returns int
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_count int;
begin
  if not public.has_grant('operator') then
    raise exception 'Operators only.' using errcode = 'PT403', hint = 'FORBIDDEN';
  end if;
  update public.payouts set status = 'released', released_at = now()
  where status = 'held' and release_after <= now();
  get diagnostics v_count = row_count;
  perform public.log_event('payouts.released_due', 'payout', null, jsonb_build_object('count', v_count));
  return v_count;
end;
$$;

create function public.operator_resolve_payout(p_payout_id uuid, p_action text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_payout public.payouts;
begin
  if not public.has_grant('operator') then
    raise exception 'Operators only.' using errcode = 'PT403', hint = 'FORBIDDEN';
  end if;
  select * into v_payout from public.payouts where id = p_payout_id for update;
  if not found then
    raise exception 'Payout not found.' using errcode = 'PT404', hint = 'NOT_FOUND';
  end if;
  if v_payout.status not in ('held', 'disputed') then
    raise exception 'This payout is already settled.' using errcode = 'PT409', hint = 'INVALID_TRANSITION';
  end if;
  if p_action = 'release' then
    update public.payouts set status = 'released', released_at = now() where id = p_payout_id;
  elsif p_action = 'refund' then
    update public.payouts set status = 'refunded' where id = p_payout_id;
    update public.payments set status = 'refunded', refunded_at = now() where id = v_payout.payment_id;
  else
    raise exception 'Action must be release or refund.' using errcode = 'PT422', hint = 'VALIDATION_ERROR';
  end if;
  perform public.log_event('payout.' || p_action, 'payout', p_payout_id, '{}'::jsonb);
  return jsonb_build_object('payout_id', p_payout_id, 'action', p_action);
end;
$$;

-- One call for the billing page: plans in effect, this month's usage, payments, mentor earnings.
create function public.my_billing()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  with me as (select (select auth.uid()) as uid),
  aud as (select public.seeker_audience((select uid from me)) as a),
  seeker as (select p.* from public.active_plan((select uid from me), null, (select a from aud)) p)
  select jsonb_build_object(
    'seeker_audience', (select a from aud),
    'plans', jsonb_strip_nulls(jsonb_build_object(
      'seeker', (select code from seeker),
      'mentor', case when public.has_grant('mentor') then (select code from public.active_plan((select uid from me), null, 'mentor')) end,
      'founder', (select code from public.active_plan((select uid from me), null, 'founder')))),
    'organizations', coalesce((
      select jsonb_agg(jsonb_build_object(
        'organization_id', m.organization_id, 'name', o.name, 'role', m.role,
        'audience', case when m.role = 'recruiter' then 'recruiter' else 'university' end,
        'plan', (select code from public.active_plan(null, m.organization_id,
                   case when m.role = 'recruiter' then 'recruiter'::public.plan_audience else 'university'::public.plan_audience end))))
      from public.memberships m join public.organizations o on o.id = m.organization_id
      where m.user_id = (select uid from me)), '[]'::jsonb),
    'usage', (
      select jsonb_object_agg(metric, jsonb_build_object(
               'used', (select count(*) from public.usage_events u
                        where u.user_id = (select uid from me) and u.metric = metrics.metric
                          and u.created_at >= date_trunc('month', now())),
               'limit', (select (limits ->> metrics.metric)::int from seeker)))
      from (values ('mentor_requests'), ('resume_analyses'), ('jd_reports')) as metrics(metric)),
    'payments', coalesce((
      select jsonb_agg(to_jsonb(p) order by p.created_at desc)
      from (select id, purpose, amount_inr, status, provider, created_at from public.payments
            where payer_id = (select uid from me) order by created_at desc limit 20) p), '[]'::jsonb),
    'payouts', coalesce((
      select jsonb_agg(to_jsonb(x) order by x.created_at desc)
      from (select po.id, po.source, po.gross_inr, po.commission_inr, po.net_inr, po.status, po.release_after, po.created_at
            from public.payouts po join public.mentors mm on mm.id = po.mentor_id
            where mm.user_id = (select uid from me) order by po.created_at desc limit 20) x), '[]'::jsonb))
$$;

-- ---------------------------------------------------------------------------
-- Privileges
-- ---------------------------------------------------------------------------

alter table public.plans enable row level security;
alter table public.subscriptions enable row level security;
alter table public.payments enable row level security;
alter table public.payouts enable row level security;
alter table public.usage_events enable row level security;
revoke all on public.plans, public.subscriptions, public.payments, public.payouts, public.usage_events from anon, authenticated;

grant select on public.plans, public.subscriptions, public.payments, public.payouts, public.usage_events to authenticated;

create policy plans_read on public.plans for select to authenticated using (true);
create policy subscriptions_read on public.subscriptions for select to authenticated
  using (user_id = (select auth.uid())
         or (organization_id is not null and (public.is_member(organization_id, 'recruiter') or public.is_member(organization_id, 'admin'))));
create policy payments_read on public.payments for select to authenticated
  using (payer_id = (select auth.uid()) or public.has_grant('operator'));
create policy payouts_read on public.payouts for select to authenticated
  using (public.is_mentor_owner(mentor_id) or public.has_grant('operator'));
create policy usage_events_read on public.usage_events for select to authenticated
  using (user_id = (select auth.uid()));

revoke all on function public.seeker_audience(uuid) from public, anon, authenticated;
revoke all on function public.active_plan(uuid, uuid, public.plan_audience) from public, anon, authenticated;
revoke all on function public.consume_quota_for(uuid, text) from public, anon, authenticated;
revoke all on function public.capture_test_payment_for(uuid, public.payment_purpose, int, text) from public, anon, authenticated;
revoke all on function public.enforce_listing_limit() from public, anon, authenticated;
revoke all on function public.enforce_drive_limit() from public, anon, authenticated;
revoke all on function public.enforce_venture_limit() from public, anon, authenticated;
revoke all on function public.guard_mentor_request() from public, anon, authenticated;
revoke all on function public.refund_declined_request() from public, anon, authenticated;

revoke all on function public.consume_quota(text) from public, anon;
revoke all on function public.subscribe(text, uuid, boolean) from public, anon;
revoke all on function public.request_mentor(uuid, text, boolean) from public, anon;
revoke all on function public.complete_mentor_session(uuid) from public, anon;
revoke all on function public.dispute_mentor_session(uuid, text) from public, anon;
revoke all on function public.operator_release_due_payouts() from public, anon;
revoke all on function public.operator_resolve_payout(uuid, text) from public, anon;
revoke all on function public.my_billing() from public, anon;
grant execute on function public.consume_quota(text) to authenticated;
grant execute on function public.subscribe(text, uuid, boolean) to authenticated;
grant execute on function public.request_mentor(uuid, text, boolean) to authenticated;
grant execute on function public.complete_mentor_session(uuid) to authenticated;
grant execute on function public.dispute_mentor_session(uuid, text) to authenticated;
grant execute on function public.operator_release_due_payouts() to authenticated;
grant execute on function public.operator_resolve_payout(uuid, text) to authenticated;
grant execute on function public.my_billing() to authenticated;
