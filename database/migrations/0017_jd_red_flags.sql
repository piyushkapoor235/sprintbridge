-- 0017 pasted job descriptions keep the scam red flags found during extraction
-- (docs/threat-model.md §5), so job seekers are warned about fee-charging "jobs" they paste in.

alter table public.external_jds
  add column red_flags text[] not null default '{}' check (cardinality(red_flags) <= 10);

grant insert (source_url, title, text, red_flags) on public.external_jds to authenticated;
