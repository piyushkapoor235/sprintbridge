-- 0011 recency input for the System-assessed score (docs/skill-intelligence.md §4).
-- Step S16. The year the resume says the skill was last used, as extracted; null when unknown.

alter table public.skill_evidence
  add column last_used_year smallint check (last_used_year between 1950 and 2100);
