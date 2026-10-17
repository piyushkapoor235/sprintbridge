-- 0008 pasted job descriptions and extracted job requirements.
-- Step S17 (cut-able). Requirements are server-written (service client) after extraction;
-- readers see requirements for opportunities they can already see, or for their own JDs.
-- See docs/skill-intelligence.md §5, §6, §11.

create type public.requirement_kind as enum ('required', 'preferred');

create table public.external_jds (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  source_url text check (source_url ~* '^https?://[^\s]+$' and char_length(source_url) <= 500),
  title      text check (char_length(title) <= 200),
  text       text not null check (char_length(text) between 1 and 20000),
  sha256     char(64) not null,  -- extraction cache key, always computed by trigger
  created_at timestamptz not null default now()
);

create index external_jds_user_idx on public.external_jds (user_id, created_at desc);

create function public.hash_external_jd()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.sha256 := encode(sha256(convert_to(new.text, 'UTF8')), 'hex');
  return new;
end;
$$;

create trigger external_jds_hash before insert on public.external_jds
  for each row execute function public.hash_external_jd();

create table public.job_requirements (
  id             uuid primary key default gen_random_uuid(),
  opportunity_id uuid references public.opportunities (id) on delete cascade,
  external_jd_id uuid references public.external_jds (id) on delete cascade,
  skill          text not null check (skill = lower(btrim(skill)) and char_length(skill) between 1 and 80),
  kind           public.requirement_kind not null,
  min_level      smallint not null default 1 check (min_level between 1 and 4),
  quote          text check (char_length(quote) <= 1000),
  confirmed_by   uuid references auth.users (id),
  created_at     timestamptz not null default now(),
  check ((opportunity_id is null) <> (external_jd_id is null))
);

create unique index job_requirements_opportunity_skill_idx
  on public.job_requirements (opportunity_id, skill) where opportunity_id is not null;
create unique index job_requirements_jd_skill_idx
  on public.job_requirements (external_jd_id, skill) where external_jd_id is not null;

alter table public.external_jds enable row level security;
alter table public.job_requirements enable row level security;
revoke all on public.external_jds, public.job_requirements from anon, authenticated;

grant select, delete on public.external_jds to authenticated;
grant insert (source_url, title, text) on public.external_jds to authenticated;
grant select on public.job_requirements to authenticated;

create policy external_jds_read_own on public.external_jds for select to authenticated
  using (user_id = (select auth.uid()));
create policy external_jds_insert_own on public.external_jds for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy external_jds_delete_own on public.external_jds for delete to authenticated
  using (user_id = (select auth.uid()));

-- Subqueries run under the caller's own RLS, so visibility follows the parent row.
create policy job_requirements_read on public.job_requirements for select to authenticated
  using (
    (opportunity_id is not null
       and exists (select 1 from public.opportunities o where o.id = opportunity_id))
    or (external_jd_id is not null
       and exists (select 1 from public.external_jds j where j.id = external_jd_id))
  );

revoke all on function public.hash_external_jd() from public, anon, authenticated;
