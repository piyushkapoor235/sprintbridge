-- 0002 opportunities owned by company organizations.
-- Step S08. See docs/architecture.md §3 (visibility), §6.

create type public.opportunity_type as enum ('job', 'internship');
create type public.opportunity_visibility as enum ('public', 'campus');
create type public.opportunity_status as enum ('open', 'closed');
create type public.pay_period as enum ('hour', 'month', 'year', 'one_time');

create table public.opportunities (
  id                  uuid primary key default gen_random_uuid(),
  company_id          uuid not null references public.organizations (id) on delete restrict,
  title               text not null check (char_length(title) between 1 and 200),
  description         text not null default '' check (char_length(description) <= 10000),
  type                public.opportunity_type not null,
  visibility          public.opportunity_visibility not null default 'public',
  required_skills     text[] not null default '{}' check (cardinality(required_skills) <= 30),
  compensation_amount numeric(12, 2) check (compensation_amount >= 0),
  currency            char(3) check (currency ~ '^[A-Z]{3}$'),
  pay_period          public.pay_period,
  deadline            timestamptz not null,
  status              public.opportunity_status not null default 'open',
  created_by          uuid not null default auth.uid() references auth.users (id),
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  -- Compensation is all-or-nothing.
  check ((compensation_amount is null) = (currency is null)
         and (compensation_amount is null) = (pay_period is null))
);

create index opportunities_company_idx on public.opportunities (company_id);
create index opportunities_listing_idx on public.opportunities (created_at desc, id desc);

create function public.normalize_opportunity()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if not public.org_has_type(new.company_id, 'company') then
    raise exception 'company_id must reference a company organization' using errcode = '23514';
  end if;
  new.required_skills := public.normalize_text_array(new.required_skills);
  return new;
end;
$$;

create trigger opportunities_normalize before insert or update on public.opportunities
  for each row execute function public.normalize_opportunity();
create trigger opportunities_updated_at before update on public.opportunities
  for each row execute function public.set_updated_at();

-- Recruiter of the opportunity's company. Used by later tables' policies.
create function public.is_opportunity_recruiter(opp uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.opportunities o
    join public.memberships m
      on m.organization_id = o.company_id and m.role = 'recruiter'
    where o.id = opp and m.user_id = (select auth.uid())
  )
$$;

alter table public.opportunities enable row level security;
revoke all on public.opportunities from anon, authenticated;

grant select on public.opportunities to authenticated;
grant insert (company_id, title, description, type, visibility, required_skills,
              compensation_amount, currency, pay_period, deadline)
  on public.opportunities to authenticated;
grant update (title, description, type, visibility, required_skills,
              compensation_amount, currency, pay_period, deadline, status)
  on public.opportunities to authenticated;

-- Public listings are discoverable by every signed-in user; the owning company sees all of its own.
-- Campus visibility is added in 0005 once campus_drives exists.
create policy opportunities_read_public on public.opportunities for select to authenticated
  using (visibility = 'public');
create policy opportunities_read_company on public.opportunities for select to authenticated
  using (public.is_member(company_id, 'recruiter'));

create policy opportunities_insert_company on public.opportunities for insert to authenticated
  with check (public.is_member(company_id, 'recruiter') and created_by = (select auth.uid()));

create policy opportunities_update_company on public.opportunities for update to authenticated
  using (public.is_member(company_id, 'recruiter'))
  with check (public.is_member(company_id, 'recruiter'));

revoke all on function public.is_opportunity_recruiter(uuid) from public, anon;
grant execute on function public.is_opportunity_recruiter(uuid) to authenticated;
revoke all on function public.normalize_opportunity() from public, anon, authenticated;
