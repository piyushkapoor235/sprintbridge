-- 0016 trust & safety (docs/threat-model.md §5, §9, §11).
--   * Listings get red flags from scam phrases (charging candidates, deposits, off-platform payment).
--   * Anyone can report a listing or venture once; three distinct open reports hide a listing
--     until an operator reviews it. Hidden/removed listings stay visible to their company and operators.
--   * Operators work a review queue; every moderation decision and other key actions are audit-logged.

create type public.moderation_status as enum ('visible', 'hidden_pending_review', 'removed');
create type public.report_reason as enum ('scam', 'fake', 'abusive', 'misleading', 'other');
create type public.report_status as enum ('open', 'dismissed', 'actioned');

alter table public.opportunities
  add column moderation_status public.moderation_status not null default 'visible',
  add column red_flags text[] not null default '{}';

-- Phrases that suggest a listing charges candidates or moves payment off-platform.
create function public.detect_red_flags(p_text text)
returns text[]
language sql
immutable
set search_path = ''
as $$
  select coalesce(array_agg(label order by label), '{}')
  from (values
    ('asks candidates to pay a fee', '(registration|training|joining|processing|application|placement)\s+(fee|charge)'),
    ('asks for a deposit', 'security\s+deposit|refundable\s+deposit|deposit\s+(of|rs|inr|₹)'),
    ('asks candidates to pay', '(pay|paying)\s+(rs\.?|inr|₹|\d)|payment\s+from\s+candidates'),
    ('moves contact off-platform', 'whatsapp\s+only|telegram\s+only|contact\s+only\s+on\s+whatsapp'),
    ('promises guaranteed placement', 'guaranteed\s+(job|placement|selection)|100%\s+(placement|job)')
  ) as rules(label, pattern)
  where lower(coalesce(p_text, '')) ~ pattern
$$;

create function public.flag_opportunity()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.red_flags := public.detect_red_flags(coalesce(new.title, '') || ' ' || coalesce(new.description, ''));
  return new;
end;
$$;

create trigger opportunities_flags before insert or update of title, description on public.opportunities
  for each row execute function public.flag_opportunity();

update public.opportunities set red_flags = public.detect_red_flags(title || ' ' || description);

-- Hidden or removed listings disappear for everyone except their company and operators.
drop policy opportunities_read_public on public.opportunities;
drop policy opportunities_read_campus on public.opportunities;
create policy opportunities_read_public on public.opportunities for select to authenticated
  using (visibility = 'public' and moderation_status = 'visible');
create policy opportunities_read_campus on public.opportunities for select to authenticated
  using (visibility = 'campus' and moderation_status = 'visible' and public.can_view_campus_opportunity(id));
create policy opportunities_read_operator on public.opportunities for select to authenticated
  using (public.has_grant('operator'));

create table public.content_reports (
  id          uuid primary key default gen_random_uuid(),
  reporter_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  target_type text not null check (target_type in ('opportunity', 'venture')),
  target_id   uuid not null,
  reason      public.report_reason not null,
  details     text check (char_length(details) <= 1000),
  status      public.report_status not null default 'open',
  created_at  timestamptz not null default now(),
  resolved_at timestamptz,
  resolved_by uuid references auth.users (id),
  unique (reporter_id, target_type, target_id)
);
create index content_reports_target_idx on public.content_reports (target_type, target_id, status);

create function public.after_report()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.target_type = 'opportunity'
     and (select count(distinct reporter_id) from public.content_reports
          where target_type = 'opportunity' and target_id = new.target_id and status = 'open') >= 3 then
    update public.opportunities set moderation_status = 'hidden_pending_review'
    where id = new.target_id and moderation_status = 'visible';
    if found then
      perform public.log_event('opportunity.auto_hidden', 'opportunity', new.target_id, jsonb_build_object('reports', 3));
    end if;
  end if;
  perform public.log_event('report.created', new.target_type, new.target_id, jsonb_build_object('reason', new.reason));
  return new;
end;
$$;

create trigger content_reports_after after insert on public.content_reports
  for each row execute function public.after_report();

-- Operator review queue, grouped by target.
create function public.operator_queue()
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if not public.has_grant('operator') then
    raise exception 'Operators only.' using errcode = 'PT403', hint = 'FORBIDDEN';
  end if;
  return jsonb_build_object(
    'reports', coalesce((
      select jsonb_agg(row_to_json(q) order by q.latest desc)
      from (select r.target_type, r.target_id,
                   coalesce((select o.title from public.opportunities o where o.id = r.target_id),
                            (select v.title from public.ventures v where v.id = r.target_id), '(deleted)') as title,
                   (select o.moderation_status from public.opportunities o where o.id = r.target_id) as moderation_status,
                   (select o.red_flags from public.opportunities o where o.id = r.target_id) as red_flags,
                   count(*) as open_reports,
                   array_agg(distinct r.reason) as reasons,
                   array_agg(r.details) filter (where r.details is not null) as details,
                   max(r.created_at) as latest
            from public.content_reports r where r.status = 'open'
            group by r.target_type, r.target_id) q), '[]'::jsonb),
    'flagged', coalesce((
      select jsonb_agg(jsonb_build_object('id', o.id, 'title', o.title, 'red_flags', o.red_flags,
                                          'moderation_status', o.moderation_status,
                                          'company', (select name from public.organizations where id = o.company_id))
             order by o.created_at desc)
      from public.opportunities o where cardinality(o.red_flags) > 0 and o.moderation_status <> 'removed'), '[]'::jsonb),
    'payouts', coalesce((
      select jsonb_agg(jsonb_build_object('id', p.id, 'source', p.source, 'net_inr', p.net_inr, 'status', p.status,
                                          'release_after', p.release_after,
                                          'mentor', (select coalesce(nullif(pr.name, ''), 'Mentor') from public.mentors m
                                                     join public.profiles pr on pr.user_id = m.user_id where m.id = p.mentor_id))
             order by p.created_at desc)
      from public.payouts p where p.status in ('held', 'disputed')), '[]'::jsonb),
    'audit', coalesce((
      select jsonb_agg(jsonb_build_object('id', a.id, 'action', a.action, 'target_type', a.target_type,
                                          'target_id', a.target_id, 'details', a.details, 'created_at', a.created_at,
                                          'actor', (select coalesce(nullif(name, ''), 'System') from public.profiles where user_id = a.actor_id))
             order by a.id desc)
      from (select * from public.audit_events order by id desc limit 50) a), '[]'::jsonb));
end;
$$;

-- p_action: dismiss (no action needed), hide (pending review), remove (take down), restore (make visible).
create function public.operator_moderate(p_target_type text, p_target_id uuid, p_action text, p_note text default null)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not public.has_grant('operator') then
    raise exception 'Operators only.' using errcode = 'PT403', hint = 'FORBIDDEN';
  end if;
  if p_action not in ('dismiss', 'hide', 'remove', 'restore') then
    raise exception 'Action must be dismiss, hide, remove or restore.' using errcode = 'PT422', hint = 'VALIDATION_ERROR';
  end if;
  if p_target_type = 'opportunity' and p_action <> 'dismiss' then
    update public.opportunities
    set moderation_status = case p_action when 'hide' then 'hidden_pending_review'::public.moderation_status
                                          when 'remove' then 'removed'::public.moderation_status
                                          else 'visible'::public.moderation_status end
    where id = p_target_id;
  end if;
  update public.content_reports
  set status = case when p_action in ('dismiss', 'restore') then 'dismissed'::public.report_status
                    else 'actioned'::public.report_status end,
      resolved_at = now(), resolved_by = auth.uid()
  where target_type = p_target_type and target_id = p_target_id and status = 'open';
  perform public.log_event('moderation.' || p_action, p_target_type, p_target_id,
    jsonb_build_object('note', left(coalesce(p_note, ''), 500)));
  return jsonb_build_object('target_id', p_target_id, 'action', p_action);
end;
$$;

-- A hidden or removed listing accepts no new applications, whatever path the insert takes.
create function public.block_moderated_applications()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (select moderation_status from public.opportunities where id = new.opportunity_id) <> 'visible' then
    raise exception 'Opportunity not found.' using errcode = 'PT404', hint = 'NOT_FOUND';
  end if;
  return new;
end;
$$;
create trigger applications_moderation before insert on public.applications
  for each row execute function public.block_moderated_applications();

-- Audit trail for decisions that matter to fairness.
create function public.audit_application_status()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.status <> old.status then
    perform public.log_event('application.status', 'application', new.id,
      jsonb_build_object('from', old.status, 'to', new.status));
  end if;
  return new;
end;
$$;
create trigger applications_audit after update of status on public.applications
  for each row execute function public.audit_application_status();

create function public.audit_drive_created()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform public.log_event('drive.authorized', 'campus_drive', new.id,
    jsonb_build_object('opportunity_id', new.opportunity_id, 'min_cgpa', new.min_cgpa, 'batch', new.batch));
  return new;
end;
$$;
create trigger campus_drives_audit after insert on public.campus_drives
  for each row execute function public.audit_drive_created();

alter table public.content_reports enable row level security;
revoke all on public.content_reports from anon, authenticated;
grant select on public.content_reports to authenticated;
grant insert (target_type, target_id, reason, details) on public.content_reports to authenticated;
create policy content_reports_read on public.content_reports for select to authenticated
  using (reporter_id = (select auth.uid()) or public.has_grant('operator'));
create policy content_reports_insert on public.content_reports for insert to authenticated
  with check (reporter_id = (select auth.uid()));

revoke all on function public.flag_opportunity() from public, anon, authenticated;
revoke all on function public.block_moderated_applications() from public, anon, authenticated;
revoke all on function public.after_report() from public, anon, authenticated;
revoke all on function public.audit_application_status() from public, anon, authenticated;
revoke all on function public.audit_drive_created() from public, anon, authenticated;
revoke all on function public.operator_queue() from public, anon;
revoke all on function public.operator_moderate(text, uuid, text, text) from public, anon;
grant execute on function public.operator_queue() to authenticated;
grant execute on function public.operator_moderate(text, uuid, text, text) to authenticated;
