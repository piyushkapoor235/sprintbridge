-- 0006 mentors and mentor requests.
-- Step S14. Mentor rows are setup-owned (a 'mentor' role grant plus a mentors row).
-- See docs/architecture.md §6, §8 transition rules, §9 Mentor Connect.

create type public.request_status as enum ('pending', 'accepted', 'declined');

create table public.mentors (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null unique references auth.users (id) on delete cascade,
  niche              text not null check (char_length(niche) between 1 and 120),
  experience_summary text not null default '' check (char_length(experience_summary) <= 2000),
  is_active          boolean not null default true,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create trigger mentors_updated_at before update on public.mentors
  for each row execute function public.set_updated_at();

create table public.mentor_requests (
  id           uuid primary key default gen_random_uuid(),
  mentor_id    uuid not null references public.mentors (id) on delete cascade,
  requester_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  note         text not null check (char_length(note) between 1 and 1000),
  status       public.request_status not null default 'pending',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  unique (requester_id, mentor_id)
);

create index mentor_requests_mentor_idx on public.mentor_requests (mentor_id);

-- pending -> accepted | declined. Repeating the final status is a no-op; reversing is not allowed.
-- Shared with collaboration_requests (0009).
create function public.check_request_transition()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.status = old.status then
    return new;
  end if;
  if old.status = 'pending' and new.status in ('accepted', 'declined') then
    return new;
  end if;
  raise exception 'INVALID_TRANSITION: % -> %', old.status, new.status
    using errcode = 'PT409', hint = 'INVALID_TRANSITION';
end;
$$;

create trigger mentor_requests_transition before update of status on public.mentor_requests
  for each row execute function public.check_request_transition();
create trigger mentor_requests_updated_at before update on public.mentor_requests
  for each row execute function public.set_updated_at();

create function public.is_mentor_owner(mentor uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.mentors t where t.id = mentor and t.user_id = (select auth.uid())
  )
$$;

-- Requestable: active, and not the caller's own mentor profile.
create function public.can_request_mentor(mentor uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.mentors t
    where t.id = mentor and t.is_active and t.user_id <> (select auth.uid())
  )
$$;

alter table public.mentors enable row level security;
alter table public.mentor_requests enable row level security;
revoke all on public.mentors, public.mentor_requests from anon, authenticated;

grant select on public.mentors to authenticated;
grant update (niche, experience_summary, is_active) on public.mentors to authenticated;

grant select on public.mentor_requests to authenticated;
grant insert (mentor_id, note) on public.mentor_requests to authenticated;
grant update (status) on public.mentor_requests to authenticated;

create policy mentors_read on public.mentors for select to authenticated
  using (is_active or user_id = (select auth.uid()));
create policy mentors_update_own on public.mentors for update to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy mentor_requests_read on public.mentor_requests for select to authenticated
  using (requester_id = (select auth.uid()) or public.is_mentor_owner(mentor_id));
create policy mentor_requests_insert on public.mentor_requests for insert to authenticated
  with check (requester_id = (select auth.uid()) and public.can_request_mentor(mentor_id));
create policy mentor_requests_decide on public.mentor_requests for update to authenticated
  using (public.is_mentor_owner(mentor_id))
  with check (public.is_mentor_owner(mentor_id));

revoke all on function public.is_mentor_owner(uuid) from public, anon;
revoke all on function public.can_request_mentor(uuid) from public, anon;
grant execute on function public.is_mentor_owner(uuid) to authenticated;
grant execute on function public.can_request_mentor(uuid) to authenticated;
revoke all on function public.check_request_transition() from public, anon, authenticated;
