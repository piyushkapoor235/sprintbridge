-- 0009 ventures and collaboration requests (stretch).
-- Step S18. Acceptance means visible collaboration only, not equity or employment.
-- See docs/architecture.md §9 Venture Launchpad.

create type public.venture_stage as enum ('idea', 'prototype', 'mvp', 'revenue');

create table public.ventures (
  id            uuid primary key default gen_random_uuid(),
  founder_id    uuid not null default auth.uid() references auth.users (id) on delete cascade,
  title         text not null check (char_length(title) between 1 and 200),
  problem       text not null check (char_length(problem) between 1 and 4000),
  industry      text not null check (char_length(industry) between 1 and 120),
  stage         public.venture_stage not null default 'idea',
  needed_skills text[] not null default '{}' check (cardinality(needed_skills) <= 30),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create function public.normalize_venture()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.needed_skills := public.normalize_text_array(new.needed_skills);
  return new;
end;
$$;

create trigger ventures_normalize before insert or update on public.ventures
  for each row execute function public.normalize_venture();
create trigger ventures_updated_at before update on public.ventures
  for each row execute function public.set_updated_at();

create table public.collaboration_requests (
  id           uuid primary key default gen_random_uuid(),
  venture_id   uuid not null references public.ventures (id) on delete cascade,
  requester_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  note         text not null check (char_length(note) between 1 and 1000),
  status       public.request_status not null default 'pending',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (requester_id, venture_id)
);

create index collaboration_requests_venture_idx on public.collaboration_requests (venture_id);

create trigger collaboration_requests_transition before update of status on public.collaboration_requests
  for each row execute function public.check_request_transition();
create trigger collaboration_requests_updated_at before update on public.collaboration_requests
  for each row execute function public.set_updated_at();

create function public.is_venture_founder(venture uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.ventures v where v.id = venture and v.founder_id = (select auth.uid())
  )
$$;

alter table public.ventures enable row level security;
alter table public.collaboration_requests enable row level security;
revoke all on public.ventures, public.collaboration_requests from anon, authenticated;

grant select on public.ventures to authenticated;
grant insert (title, problem, industry, stage, needed_skills) on public.ventures to authenticated;
grant update (title, problem, industry, stage, needed_skills) on public.ventures to authenticated;

grant select on public.collaboration_requests to authenticated;
grant insert (venture_id, note) on public.collaboration_requests to authenticated;
grant update (status) on public.collaboration_requests to authenticated;

create policy ventures_read on public.ventures for select to authenticated using (true);
create policy ventures_insert_own on public.ventures for insert to authenticated
  with check (founder_id = (select auth.uid()));
create policy ventures_update_own on public.ventures for update to authenticated
  using (founder_id = (select auth.uid()))
  with check (founder_id = (select auth.uid()));

create policy collaboration_requests_read on public.collaboration_requests for select to authenticated
  using (requester_id = (select auth.uid()) or public.is_venture_founder(venture_id));
create policy collaboration_requests_insert on public.collaboration_requests for insert to authenticated
  with check (requester_id = (select auth.uid()) and not public.is_venture_founder(venture_id));
create policy collaboration_requests_decide on public.collaboration_requests for update to authenticated
  using (public.is_venture_founder(venture_id))
  with check (public.is_venture_founder(venture_id));

revoke all on function public.is_venture_founder(uuid) from public, anon;
grant execute on function public.is_venture_founder(uuid) to authenticated;
revoke all on function public.normalize_venture() from public, anon, authenticated;
