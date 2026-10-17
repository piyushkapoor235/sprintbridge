# Person 1 frontend plan

Updated 18 October 2026 against `origin/yatin` at `d62300b`. Work branch: `frontend` (explicitly requested by the user); do not work on or push to `main`. This branch starts from the fetched backend commit. This plan supplements the team-wide `plan.md` and `todo.md`; it does not mark their frontend steps complete.

## Backend readiness and changed architecture

Implementation note: Person 1's frontend is now present in `frontend/`; see its README and the implementation update in `tasks/todo.md`. Read the initial readiness notes below as the baseline from before this implementation. Live backend/hosted acceptance still requires configuration.

- React + TypeScript + Vite + Tailwind + React Router remains the frontend stack. Supabase is used directly only for authentication; all business data goes through FastAPI.
- Implementations exist for all 33 contract operations, including profiles, listings, applications, campus, mentors, resume skills, external JDs, fit and ventures. Source: `backend/app/routers`, `backend/app/schemas`, `docs/api-contract.md`.
- No frontend exists yet. Render configuration currently deploys only the backend; the team checklist says deployment is pending.
- Fresh offline test run: `uv run --python 3.13 --with-requirements requirements-dev.txt python -m pytest tests -q` from `backend` returned **46 passed, 3 failed**. The contract-route/auth-security checks passed. Three validation tests in `tests/test_errors.py` expected 422 but received 503: their `signed_in` fixture overrides auth, not `get_db`, and `user_client` rejects missing Supabase settings before validation completes. P2 should make these offline tests independent of local credentials and rerun. Backend completion is therefore implementation coverage, not a clean fresh-checkout verification result.
- The repository reports live/database checks passed previously. Those are historical results, not verification of today's hosted service. No local `backend/.env` is present. Real login and database journeys require configuration from P2.
- Resume/JD extraction uses Claude in FastAPI; deterministic backend code calculates evidence scores and fit. Existing live tests replace Claude with a fake. Actual extraction needs the backend key and a real-provider smoke check by P2.
- Academic UI says `University-claimed`, with `Sample data` for demo data. Never translate the internal `verified_student` capability into an academic verified badge. Skills display `Self-declared`, `System-assessed`, or the returned `Mentor-verified` label; do not invent a verification workflow.

## Scope and ownership

P1 owns the app shell, shared controls, auth/workspace context, API helper, login/dashboard, profile, opportunities/detail, applications, recruiter screens, student campus eligibility integration and missing-skill mentor navigation. Plan P1's optional skills and JD screens after the core journey. P3 retains university roster/drive/report pages; P4 retains mentor/request pages and optional ventures. P1 registers their exported pages and checks integration.

The team checklist describes sequential work and PR review. Follow that coordination, but use the user's explicitly requested non-main branch for this work. Do not merge/push main as part of frontend implementation.

## Frontend/API decisions

1. Use one `AuthProvider` with the Supabase SDK session lifecycle and server context from `GET /api/me`. Workspaces come from `workspaces[].organization_id`, type and role. Keep active workspace and auth global; forms and fetched page data local.
2. Use one typed fetch helper for bearer auth, JSON, multipart and blob responses. Branch on error `code`; show `field_errors` and request ID. Let the browser set multipart boundaries. Clear stale private data on logout/workspace switch, cancel obsolete reads, and refetch lists after writes. Do not automatically retry mutations with unknown outcomes.
3. Match Pydantic wire types: snake_case, UUID strings, nullable fields, paginated `{items,page,page_size,total}`. Handle nullable total. Preserve the API's compensation amount representation; do not assume every money value arrives as a JSON number.
4. Edit profiles with `PATCH /api/me`, not `/api/profiles`. Send only editable fields, omit unchanged fields, and send concrete booleans/arrays for `is_public`/`skills`; reserve null for nullable text/link fields.
5. Opportunity detail does not embed campus drives. Load student-visible `GET /api/university/drives` without workspace_id, paginate, and match `opportunity_id`. Preserve selected drive in the detail URL, validate against returned drives, then call `/api/drives/{id}/eligibility`. Public applications may omit a drive; campus applications require one. Server decisions remain authoritative.
6. Keep count-based skill coverage, deterministic evidence-weighted fit, and campus eligibility visibly separate. Null coverage/fit means unavailable/no requirements, never zero percent. Missing skill links use encoded `/mentors?skill=...` parameters.
7. Start listing sort with `newest`. If exposing `sort=fit`, explain it ranks only the newest 100 matching listings; ranking currently uses required_skills at level 1 while detail fit can use extracted requirements. Do not promise a global ranking or exact consistency between the two.
8. Recruiter listing queries use `company_id`; applicant queries use `scope=recruiter&workspace_id=...`. Applicant detail comes from the returned profile snapshot. Allowed transitions: applied → shortlisted/offered/rejected; shortlisted → offered/rejected; offered/rejected terminal. Refetch after 409 conflicts.
9. No API exists for editing/deleting/closing listings, fetching arbitrary private profiles, or granting roles. Do not add UI controls that promise those operations.
10. Optional resume upload is a synchronous multipart PDF request, max 5 MB; it is not an async job/polling API. On success refetch `/api/me/skills`. Show evidence quotes, levels and scores as returned. On 503 keep manual profile editing usable.
11. Optional JD creation starts with pasted text (`POST /api/jds`), followed by detail and fit GETs. URL input is supported by the backend but not needed for the first UI. Display missing/under_evidenced/strong buckets and required/preferred distinctions; never call fit a hiring probability.

## Configuration and integration prerequisites

P2 supplies the API base URL, Supabase URL, browser-safe publishable key and seeded account access privately. Proposed frontend names: `VITE_API_BASE_URL` (server origin, helper adds `/api`), `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`. Keep Anthropic, database and Supabase secret keys backend-only.

P2 configures CORS for localhost:5173 and the hosted frontend. P1 adds static-site build/publish configuration and SPA fallback when deployment is ready. Seeded login is the first milestone; no signup, password recovery, custom auth storage, state-management library or dashboard analytics service is needed.

## Build sequence and completion gates

Detailed tasks and acceptance checks are in `tasks/todo.md`.

1. Foundation → real seeded login and `/me` context.
2. Profile → recruiter creates listing → student discovers/applies → recruiter shortlists → tracker survives refresh.
3. Student campus discovery/eligibility → P3 university and P4 mentor page integration → gap-to-mentor flow.
4. Optional resume skills and pasted-JD fit after the core works. Ventures remain P4's stretch work.
5. Responsive/keyboard/error-state checks → hosted smoke tests in separate role browser profiles.

Use build/type checks for every slice and focused frontend tests for auth failure handling, stale workspace responses, permitted status actions and critical submission behavior. Verify actual UI journeys against the backend; fixtures alone do not count as completion. Do not change backend contracts silently to make a screen easier.

## Risks and dependencies

- Real backend deployment, credentials and CORS are unverified here; local UI scaffolding can begin, authenticated acceptance cannot pass until they are supplied.
- Root checklist timing and some historical file/migration names are stale. Prefer actual routers/schemas and the API contract over suggested filenames.
- A profile PATCH schema permits null on fields whose stored value may be non-null; explicit field handling above avoids relying on that ambiguity, and P2 should verify server validation.
- The original 12-hour timeline includes backend work already done. Track frontend milestones rather than claiming the old timeboxes still estimate remaining effort.
- No full security audit is implied by checking frontend readiness. Do not treat reported live test results as a production-readiness guarantee.
