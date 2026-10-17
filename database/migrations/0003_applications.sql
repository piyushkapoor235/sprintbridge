-- 0003 applications: one per applicant per opportunity.
-- Step S09 (table, read rules, status transitions). Creation goes only through the
-- transactional submit operation described in docs/api-contract.md (no direct INSERT grant).
-- See docs/architecture.md §6 rules 3, 4, 6 and §8 transition rules.

create type public.application_status as enum ('applied', 'shortlisted', 'offered', 'rejected');

create table public.applications (
  id                   uuid primary key default gen_random_uuid(),
  opportunity_id       uuid not null references public.opportunities (id) on delete restrict,
  applicant_id         uuid not null references auth.users (id) on delete cascade,
  drive_id             uuid,  -- FK to campus_drives added in 0005
  status               public.application_status not null default 'applied',
  eligibility_snapshot jsonb, -- private: read only through a scoped function
  profile_snapshot     jsonb not null,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  unique (applicant_id, opportunity_id)
);

create index applications_opportunity_idx on public.applications (opportunity_id);
create index applications_drive_idx on public.applications (drive_id) where drive_id is not null;

-- applied -> shortlisted | offered | rejected; shortlisted -> offered | rejected.
-- Repeating the current status is a no-op. SQLSTATE PT409 makes PostgREST answer HTTP 409.
create function public.check_application_transition()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.status = old.status then
    return new;
  end if;
  if (old.status = 'applied' and new.status in ('shortlisted', 'offered', 'rejected'))
     or (old.status = 'shortlisted' and new.status in ('offered', 'rejected')) then
    return new;
  end if;
  raise exception 'INVALID_TRANSITION: % -> %', old.status, new.status
    using errcode = 'PT409', hint = 'INVALID_TRANSITION';
end;
$$;

create trigger applications_transition before update of status on public.applications
  for each row execute function public.check_application_transition();
create trigger applications_updated_at before update on public.applications
  for each row execute function public.set_updated_at();

alter table public.applications enable row level security;
revoke all on public.applications from anon, authenticated;

-- eligibility_snapshot is deliberately excluded from the column grant.
grant select (id, opportunity_id, applicant_id, drive_id, status, profile_snapshot,
              created_at, updated_at)
  on public.applications to authenticated;
grant update (status) on public.applications to authenticated;

create policy applications_read_own on public.applications for select to authenticated
  using (applicant_id = (select auth.uid()));
create policy applications_read_recruiter on public.applications for select to authenticated
  using (public.is_opportunity_recruiter(opportunity_id));

-- Only the owning company's recruiters change status; applicants cannot.
create policy applications_update_recruiter on public.applications for update to authenticated
  using (public.is_opportunity_recruiter(opportunity_id))
  with check (public.is_opportunity_recruiter(opportunity_id));

revoke all on function public.check_application_transition() from public, anon, authenticated;
