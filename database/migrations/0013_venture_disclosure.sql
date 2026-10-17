-- 0013 ventures: tiered disclosure, compensation type, NDA acceptance (docs/threat-model.md §8).
-- Everyone sees the public teaser; the full problem statement is visible only to the founder and
-- accepted collaborators, through venture_private_details().

create type public.compensation_type as enum ('paid', 'stipend', 'equity', 'unpaid', 'to_discuss');

alter table public.ventures
  add column teaser text,
  add column compensation_type public.compensation_type not null default 'to_discuss';
update public.ventures set teaser = left(problem, 280) where teaser is null;
alter table public.ventures
  alter column teaser set not null,
  add constraint ventures_teaser_check check (char_length(teaser) between 1 and 280);

-- Column-level read grant: `problem` is no longer selectable directly.
revoke select on public.ventures from authenticated;
grant select (id, founder_id, title, teaser, industry, stage, needed_skills, compensation_type, created_at, updated_at)
  on public.ventures to authenticated;
grant insert (title, teaser, problem, industry, stage, needed_skills, compensation_type) on public.ventures to authenticated;
grant update (title, teaser, problem, industry, stage, needed_skills, compensation_type) on public.ventures to authenticated;

-- Requesters must accept the confidentiality terms before they can see details.
alter table public.collaboration_requests
  add column nda_accepted boolean not null default true,
  add constraint collaboration_requests_nda_check check (nda_accepted);
alter table public.collaboration_requests alter column nda_accepted drop default;
grant insert (venture_id, note, nda_accepted) on public.collaboration_requests to authenticated;

create function public.can_view_venture_details(p_venture_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (select 1 from public.ventures v where v.id = p_venture_id and v.founder_id = (select auth.uid()))
      or exists (select 1 from public.collaboration_requests c
                 where c.venture_id = p_venture_id and c.requester_id = (select auth.uid()) and c.status = 'accepted')
$$;

create function public.venture_private_details(p_venture_id uuid)
returns text
language sql
stable
security definer
set search_path = ''
as $$
  select case when public.can_view_venture_details(p_venture_id)
              then (select v.problem from public.ventures v where v.id = p_venture_id) end
$$;

revoke all on function public.can_view_venture_details(uuid) from public, anon;
revoke all on function public.venture_private_details(uuid) from public, anon;
grant execute on function public.can_view_venture_details(uuid) to authenticated;
grant execute on function public.venture_private_details(uuid) to authenticated;
