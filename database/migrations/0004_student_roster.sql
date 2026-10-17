-- 0004 student roster: university-claimed records (never "verified").
-- Step S11. Rows are written only by the transactional roster commit operation
-- (docs/api-contract.md); there is no direct INSERT/UPDATE grant.
-- See docs/architecture.md §6 rule 5 and docs/threat-model.md §2.

create table public.student_roster (
  id               uuid primary key default gen_random_uuid(),
  university_id    uuid not null references public.organizations (id) on delete cascade,
  student_id       text not null check (char_length(student_id) between 1 and 64),
  name             text not null check (char_length(name) between 1 and 200),
  email            text not null check (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  verified_user_id uuid references auth.users (id) on delete set null,
  branch           text not null check (char_length(branch) between 1 and 64),
  batch            integer not null check (batch between 2000 and 2100),
  cgpa             numeric(4, 2) check (cgpa between 0 and 10),  -- fixed 10-point demo scale
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  unique (university_id, student_id),
  unique (university_id, verified_user_id)
);

create function public.normalize_roster_row()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if not public.org_has_type(new.university_id, 'university') then
    raise exception 'university_id must reference a university organization' using errcode = '23514';
  end if;
  new.branch := lower(btrim(new.branch));
  new.email := lower(btrim(new.email));
  new.student_id := btrim(new.student_id);
  -- A re-import must never move an existing account link.
  if tg_op = 'UPDATE' and old.verified_user_id is not null
     and new.verified_user_id is distinct from old.verified_user_id then
    raise exception 'verified_user_id is preserved on re-import' using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger student_roster_normalize before insert or update on public.student_roster
  for each row execute function public.normalize_roster_row();
create trigger student_roster_updated_at before update on public.student_roster
  for each row execute function public.set_updated_at();

-- Caller has a linked roster row at this university.
create function public.is_verified_student(university uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.student_roster r
    where r.university_id = university and r.verified_user_id = (select auth.uid())
  )
$$;

alter table public.student_roster enable row level security;
revoke all on public.student_roster from anon, authenticated;
grant select on public.student_roster to authenticated;

create policy student_roster_read_admin on public.student_roster for select to authenticated
  using (public.is_member(university_id, 'admin'));
create policy student_roster_read_self on public.student_roster for select to authenticated
  using (verified_user_id = (select auth.uid()));

revoke all on function public.is_verified_student(uuid) from public, anon;
grant execute on function public.is_verified_student(uuid) to authenticated;
revoke all on function public.normalize_roster_row() from public, anon, authenticated;
