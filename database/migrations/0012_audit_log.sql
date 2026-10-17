-- 0012 append-only audit log of sensitive actions (docs/threat-model.md §10, §11).
-- Written only by SECURITY DEFINER functions and triggers; readable by operators only.

create table public.audit_events (
  id          bigint generated always as identity primary key,
  actor_id    uuid references auth.users (id) on delete set null,
  action      text not null check (char_length(action) between 1 and 80),
  target_type text not null check (char_length(target_type) between 1 and 40),
  target_id   uuid,
  details     jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);

create index audit_events_created_idx on public.audit_events (created_at desc);
create index audit_events_target_idx on public.audit_events (target_type, target_id);

create function public.log_event(p_action text, p_target_type text, p_target_id uuid, p_details jsonb default '{}'::jsonb)
returns void
language sql
security definer
set search_path = ''
as $$
  insert into public.audit_events (actor_id, action, target_type, target_id, details)
  values ((select auth.uid()), p_action, p_target_type, p_target_id, coalesce(p_details, '{}'::jsonb))
$$;

alter table public.audit_events enable row level security;
revoke all on public.audit_events from anon, authenticated;
grant select on public.audit_events to authenticated;

create policy audit_events_read_operator on public.audit_events for select to authenticated
  using (public.has_grant('operator'));

-- Callable only from other definer functions and triggers, never directly by users.
revoke all on function public.log_event(text, text, uuid, jsonb) from public, anon, authenticated;
