-- 0007 resumes and skill evidence (System-assessed skills).
-- Step S16 (cut-able). Evidence is server-owned: users can read and delete their own rows
-- but cannot write them, so a direct Data API call cannot fabricate evidence.
-- The backend writes through its narrow service client (backend/app/db.py).
-- See docs/skill-intelligence.md §3, §4, §11.

create type public.resume_status as enum ('uploaded', 'parsed', 'failed');
create type public.evidence_source as enum ('resume', 'github', 'proof', 'mentor');
create type public.evidence_context as enum (
  'skills_list', 'project', 'experience', 'education', 'certification', 'code'
);

create table public.resumes (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users (id) on delete cascade,
  storage_path text not null,
  sha256       char(64) not null check (sha256 ~ '^[0-9a-f]{64}$'),
  status       public.resume_status not null default 'uploaded',
  parsed_at    timestamptz,
  created_at   timestamptz not null default now(),
  unique (user_id, sha256)
);

create table public.skill_evidence (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users (id) on delete cascade,
  resume_id    uuid references public.resumes (id) on delete cascade,
  skill        text not null check (skill = lower(btrim(skill)) and char_length(skill) between 1 and 80),
  source       public.evidence_source not null,
  context_type public.evidence_context not null,
  ref          text check (char_length(ref) <= 500),
  quote        text check (char_length(quote) <= 1000),
  years        numeric(4, 1) check (years between 0 and 60),
  created_at   timestamptz not null default now()
);

create index skill_evidence_user_skill_idx on public.skill_evidence (user_id, skill);

alter table public.resumes enable row level security;
alter table public.skill_evidence enable row level security;
revoke all on public.resumes, public.skill_evidence from anon, authenticated;

grant select, delete on public.resumes, public.skill_evidence to authenticated;

create policy resumes_own on public.resumes for select to authenticated
  using (user_id = (select auth.uid()));
create policy resumes_delete_own on public.resumes for delete to authenticated
  using (user_id = (select auth.uid()));
create policy skill_evidence_own on public.skill_evidence for select to authenticated
  using (user_id = (select auth.uid()));
create policy skill_evidence_delete_own on public.skill_evidence for delete to authenticated
  using (user_id = (select auth.uid()));
