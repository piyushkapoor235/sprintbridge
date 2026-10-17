-- 0005 campus drives: a university authorizes a drive for a company opportunity.
-- Step S12. Rules are frozen once published (no UPDATE grant).
-- The authoritative eligibility predicate is added with the submit operation in S12
-- (signature in docs/api-contract.md). See docs/architecture.md §3, §6, §8.

create table public.campus_drives (
  id               uuid primary key default gen_random_uuid(),
  university_id    uuid not null references public.organizations (id) on delete cascade,
  opportunity_id   uuid not null references public.opportunities (id) on delete restrict,
  allowed_branches text[] not null default '{}' check (cardinality(allowed_branches) <= 30),
  batch            integer not null check (batch between 2000 and 2100),
  min_cgpa         numeric(4, 2) check (min_cgpa between 0 and 10),
  required_skills  text[] not null default '{}' check (cardinality(required_skills) <= 30),
  deadline         timestamptz not null,
  rules_version    integer not null default 1 check (rules_version >= 1),
  authorized_by    uuid not null default auth.uid() references auth.users (id),
  created_at       timestamptz not null default now(),
  unique (university_id, opportunity_id),
  unique (id, opportunity_id)  -- target of the applications composite FK
);

create index campus_drives_opportunity_idx on public.campus_drives (opportunity_id);

create function public.normalize_campus_drive()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if not public.org_has_type(new.university_id, 'university') then
    raise exception 'university_id must reference a university organization' using errcode = '23514';
  end if;
  new.allowed_branches := public.normalize_text_array(new.allowed_branches);
  new.required_skills := public.normalize_text_array(new.required_skills);
  return new;
end;
$$;

create trigger campus_drives_normalize before insert on public.campus_drives
  for each row execute function public.normalize_campus_drive();

-- An application's drive must belong to the same opportunity.
alter table public.applications
  add constraint applications_drive_fk
  foreign key (drive_id, opportunity_id)
  references public.campus_drives (id, opportunity_id)
  on delete restrict;

create function public.is_drive_admin(drive uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.campus_drives d
    join public.memberships m
      on m.organization_id = d.university_id and m.role = 'admin'
    where d.id = drive and m.user_id = (select auth.uid())
  )
$$;

-- Campus listing is visible to admins of a linked university and to its verified students.
create function public.can_view_campus_opportunity(opp uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.campus_drives d
    where d.opportunity_id = opp
      and (
        exists (select 1 from public.memberships m
                where m.organization_id = d.university_id and m.role = 'admin'
                  and m.user_id = (select auth.uid()))
        or exists (select 1 from public.student_roster r
                   where r.university_id = d.university_id
                     and r.verified_user_id = (select auth.uid()))
      )
  )
$$;

alter table public.campus_drives enable row level security;
revoke all on public.campus_drives from anon, authenticated;

grant select on public.campus_drives to authenticated;
grant insert (university_id, opportunity_id, allowed_branches, batch, min_cgpa,
              required_skills, deadline)
  on public.campus_drives to authenticated;

create policy campus_drives_read_admin on public.campus_drives for select to authenticated
  using (public.is_member(university_id, 'admin'));
create policy campus_drives_read_company on public.campus_drives for select to authenticated
  using (public.is_opportunity_recruiter(opportunity_id));
create policy campus_drives_read_student on public.campus_drives for select to authenticated
  using (public.is_verified_student(university_id));

create policy campus_drives_insert_admin on public.campus_drives for insert to authenticated
  with check (public.is_member(university_id, 'admin') and authorized_by = (select auth.uid()));

create policy opportunities_read_campus on public.opportunities for select to authenticated
  using (visibility = 'campus' and public.can_view_campus_opportunity(id));

create policy applications_read_drive_admin on public.applications for select to authenticated
  using (drive_id is not null and public.is_drive_admin(drive_id));

revoke all on function public.is_drive_admin(uuid) from public, anon;
revoke all on function public.can_view_campus_opportunity(uuid) from public, anon;
grant execute on function public.is_drive_admin(uuid) to authenticated;
grant execute on function public.can_view_campus_opportunity(uuid) to authenticated;
revoke all on function public.normalize_campus_drive() from public, anon, authenticated;
