-- 0001 core identity: profiles, organizations, memberships, role grants.
-- Step S02. See docs/architecture.md §3, §6.
--
-- Conventions for every migration:
--   * RLS on every table; revoke Supabase's default grants, then grant only what each role needs.
--   * Column-level INSERT/UPDATE grants stop generic edit paths from touching ids, owners or status.
--   * SECURITY DEFINER helpers pin search_path to '' and fully qualify every relation.

-- ---------------------------------------------------------------------------
-- Shared enums and helpers
-- ---------------------------------------------------------------------------

create type public.org_type as enum ('company', 'university');
create type public.membership_role as enum ('recruiter', 'admin');
create type public.grant_role as enum ('mentor', 'operator');

-- Lower-case, trim, drop blanks and duplicates, sort. Used for every skill/branch array.
create function public.normalize_text_array(input text[])
returns text[]
language sql
immutable
set search_path = ''
as $$
  select coalesce(
    array(
      select distinct lower(btrim(v)) as x
      from unnest(input) as v
      where btrim(v) <> ''
      order by x
    ),
    '{}'::text[]
  )
$$;

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- profiles: one per auth user, created by trigger. Self-declared fields only.
-- ---------------------------------------------------------------------------

create table public.profiles (
  user_id           uuid primary key references auth.users (id) on delete cascade,
  name              text not null default '' check (char_length(name) <= 120),
  specialization    text check (char_length(specialization) <= 120),
  education_summary text check (char_length(education_summary) <= 1000),
  skills            text[] not null default '{}' check (cardinality(skills) <= 50),
  portfolio_url     text check (
                      portfolio_url ~* '^https?://[^\s]+$' and char_length(portfolio_url) <= 500
                    ),
  is_public         boolean not null default true,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create function public.normalize_profile()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.skills := public.normalize_text_array(new.skills);
  new.name := btrim(new.name);
  return new;
end;
$$;

create trigger profiles_normalize before insert or update on public.profiles
  for each row execute function public.normalize_profile();
create trigger profiles_updated_at before update on public.profiles
  for each row execute function public.set_updated_at();

-- New auth user -> empty profile. Name comes from sign-up metadata when present.
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (user_id, name)
  values (new.id, coalesce(left(new.raw_user_meta_data ->> 'name', 120), ''));
  return new;
end;
$$;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- organizations, memberships, role_grants: setup-owned, read-only to users.
-- ---------------------------------------------------------------------------

create table public.organizations (
  id         uuid primary key default gen_random_uuid(),
  name       text not null check (char_length(name) between 1 and 200),
  type       public.org_type not null,
  created_at timestamptz not null default now()
);

create table public.memberships (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users (id) on delete cascade,
  organization_id uuid not null references public.organizations (id) on delete cascade,
  role            public.membership_role not null,
  created_at      timestamptz not null default now(),
  unique (user_id, organization_id, role)
);

create index memberships_org_idx on public.memberships (organization_id);

-- recruiter -> company, admin -> university.
create function public.check_membership_org_type()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  org_kind public.org_type;
begin
  select o.type into org_kind from public.organizations o where o.id = new.organization_id;
  if (new.role = 'recruiter' and org_kind <> 'company')
     or (new.role = 'admin' and org_kind <> 'university') then
    raise exception 'membership role % does not match organization type %', new.role, org_kind
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger memberships_org_type before insert or update on public.memberships
  for each row execute function public.check_membership_org_type();

create table public.role_grants (
  user_id    uuid not null references auth.users (id) on delete cascade,
  role       public.grant_role not null,
  granted_at timestamptz not null default now(),
  primary key (user_id, role)
);

-- Reusable check that a referenced organization has the expected type.
create function public.org_has_type(org uuid, expected public.org_type)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from public.organizations o where o.id = org and o.type = expected)
$$;

-- Membership check for RLS. SECURITY DEFINER avoids recursive RLS on memberships.
create function public.is_member(org uuid, wanted public.membership_role)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.memberships m
    where m.user_id = (select auth.uid())
      and m.organization_id = org
      and m.role = wanted
  )
$$;

create function public.has_grant(wanted public.grant_role)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.role_grants g
    where g.user_id = (select auth.uid()) and g.role = wanted
  )
$$;

-- ---------------------------------------------------------------------------
-- Privileges and row-level security
-- ---------------------------------------------------------------------------

alter table public.profiles      enable row level security;
alter table public.organizations enable row level security;
alter table public.memberships   enable row level security;
alter table public.role_grants   enable row level security;

revoke all on public.profiles, public.organizations, public.memberships, public.role_grants
  from anon, authenticated;

grant select on public.profiles to authenticated;
grant update (name, specialization, education_summary, skills, portfolio_url, is_public)
  on public.profiles to authenticated;
grant select on public.organizations, public.memberships, public.role_grants to authenticated;

create policy profiles_read on public.profiles for select to authenticated
  using (user_id = (select auth.uid()) or is_public);
create policy profiles_update_own on public.profiles for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy organizations_read on public.organizations for select to authenticated
  using (true);

create policy memberships_read_own on public.memberships for select to authenticated
  using (user_id = (select auth.uid()));

create policy role_grants_read_own on public.role_grants for select to authenticated
  using (user_id = (select auth.uid()));

-- Helpers callable by signed-in users only (RLS policies run as the caller).
revoke all on function public.org_has_type(uuid, public.org_type) from public, anon;
revoke all on function public.is_member(uuid, public.membership_role) from public, anon;
revoke all on function public.has_grant(public.grant_role) from public, anon;
grant execute on function public.org_has_type(uuid, public.org_type) to authenticated;
grant execute on function public.is_member(uuid, public.membership_role) to authenticated;
grant execute on function public.has_grant(public.grant_role) to authenticated;

-- Trigger functions are never called directly.
revoke all on function public.handle_new_user() from public, anon, authenticated;
revoke all on function public.check_membership_org_type() from public, anon, authenticated;
revoke all on function public.normalize_profile() from public, anon, authenticated;
revoke all on function public.set_updated_at() from public, anon, authenticated;
