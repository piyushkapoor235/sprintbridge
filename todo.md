# SprintBridge — 12-hour sequential checklist

Active plan: [plan.md](plan.md). P1–P4 are the four human teammates. All steps are planned and unchecked.

## Working rule: one step at a time

1. **A step starts only after the previous step is merged to `main`.** No step runs in parallel with another.
2. **Driver** is the only person who edits the repo during the step. **Checker** reviews the diff and runs "Done when" before approving.
3. **The other two never touch the repo during the step.** They prepare the *next* step's inputs outside the repo (column "Prepare next"). The next Driver commits them.
4. **Git flow:** branch `step/NN-slug` from the latest `main` → one PR → Checker approves after the check passes → squash-merge → everyone pulls → the next step starts. Only one branch is open at a time, so there are no merge conflicts.
5. **Timebox:** at 150% of budget, decide whether to ship a minimal version or move the step to the cut list. A half-done step is never merged.
6. **`main` stays deployable.** From S04 on, every merge redeploys, and "Done when" is re-run on the deployed URL.
7. **"P2 then P1"** means two commits in order inside the same step and PR: backend first, then frontend.

## Progress (18 October 2026)

Direction: **the backend is completed first**, starting from the scaffold below.

| Step | State |
|---|---|
| S01 | Repo structure, [docs/api-contract.md](docs/api-contract.md), `.gitignore`, `backend/.env.example` and README are done. **Pending:** sign-off from all four teammates. |
| S02 | **Done, live.** Supabase project `bigckdvgoispnogelzai` (Mumbai, Postgres 17). All nine migrations applied with `database/apply_migrations.py`; all 17 tables have RLS; `anon` has no table grants; email confirmation is on. 20 local schema tests pass, plus live Data API checks. |
| S03 | **Done, live.** FastAPI skeleton: health, verified-token dependency, request-scoped client, error shape, pagination, all 33 contract routes (unbuilt ones return 501 with their step), 23 tests. Against live Supabase: no token → 401, bad token → 401, real token → verified. |
| S05 | **Done, live.** `database/seed.py` (safe to re-run): 8 demo users (pre-confirmed, password in `backend/.env`), 4 orgs, 4 memberships, 2 mentors, 4 roster rows labelled sample data. |
| Backend S06–S18 | **Done, live (backend half).** All 33 contract operations implemented: `/me`, listings, applications and status, roster preview/commit, drives and eligibility, report + CSV, mentors, ventures, resume → System-assessed skills, pasted JD → fit and gap. Transactional RPCs in `0010_operations.sql`. |
| Tests | 49 backend unit tests; 43 local Postgres tests (schema, RLS, RPCs); 9 live end-to-end journeys against Supabase, passing on two consecutive runs and cleaning up after themselves; 30 earlier direct Data API attack checks. |
| Frontend redesign | **Done.** Stripe-inspired design system, University workspace, sample data; 11 browser tests pass. |
| Doc extensions (0012–0016) | **Done, live.**<br>• **Ventures:** public teaser, private plan only for accepted collaborators, NDA, compensation type.<br>• **Plans & billing:** 13 plans, quotas and listing/drive/venture limits enforced in the database, simulated payments, mentor escrow → 20%/10% commission → payout held 7 days → dispute / operator settle.<br>• **Mentor skill verification:** random conflict-checked assignment (same organization, prior contact, reciprocity, per-institution cap), reveal at session start, same fee pass/fail, 30-day cooldown with a new verifier, 20% blind second review that can suspend a badge and lower the verifier's quality score, 18-month expiry; Mentor-verified skills feed fit scores and verified experts rank first.<br>• **Trust & safety:** scam-phrase red flags, reports, auto-hide after 3, operator console, audit log.<br>**Tests:** 57 DB, 49 backend, 9 live journeys; each feature was walked through in the live UI as real demo users. |
| Not done | **Deploy:** `render.yaml` is ready but needs your Render account; set the frontend service's `branch:` to `main`. **Claude key:** resume/JD analysis returns 503 until `ANTHROPIC_API_KEY` is set. **Needs outside services:** real payment provider (Razorpay), KYC / liveness, DigiLocker/NAD academic verification, GitHub OAuth analysis, 48-hour proof plans, recruiter outreach drafts, video sessions. |

## Steps

| Done | Step | Driver → Checker | Budget | Ends at | Task | Done when | Prepare next (idle pair) | Likely files |
|---|---|---|---|---|---|---|---|---|
| [ ] | S01 | P1 → P2 | 0:30 | 0:30 | Agree scope, names for P1–P4, demo story. Write `docs/api-contract.md` with frozen JSON examples for every hackathon endpoint. Create repo folders, `.gitignore`, `.env.example`, README. | All four sign off on the contract; repo is clean | P3, P4: core table columns + RLS rules for S02 | `docs/api-contract.md`, `README.md`, `.env.example` |
| [x] | S02 | P2 → P3 | 0:30 | 1:00 | Supabase Free project. Auth with **email confirmation on**. Tables `profiles`, `organizations`, `memberships`, `role_grants` + grants + RLS. | A direct Data API write to `role_grants` is denied; free tier confirmed | P1, P4: auth/error test cases for S03 | `database/migrations/0001_core.sql` |
| [x] | S03 | P2 → P1 | 0:45 | 1:45 | FastAPI skeleton: `/api/health`, verified-token dependency, request-scoped DB client, error shape `{detail, code, field_errors, request_id}`, pagination helper, pytest | Invalid/expired token → 401; tests pass | P3, P4: Render settings + CORS origins for S04 | `backend/app/{main,auth,db,errors}.py`, `backend/tests/` |
| [ ] | S04 | P2 → P4 | 0:15 | 2:00 | Deploy backend to Render Free; precise CORS allowlist | Public `/api/health` responds | P1, P3: seed data list (2 universities, 2 companies, users) for S05 | Render config, `requirements.txt` |
| [x] | S05 | P3 → P2 | 0:20 | 2:20 | `database/seed.py`: orgs, demo users, memberships, role grants. Data labelled `Sample data`; passwords outside Git. | Seed reruns with no duplicates; user of org B cannot read org A | P1, P4: wireframe + shared component list for S06 | `database/seed.py` |
| [ ] | S06 | P1 → P2 | 0:45 | 3:05 | Frontend shell: Vite + Tailwind, routes, AuthProvider, `api.ts`, shared components, login, dashboard via `/api/me`; deploy static site | **Checkpoint A:** deployed login → `/me` shows the seeded user | P3, P4: profile field allowlist + validation cases for S07 | `frontend/src/{App.tsx,auth/,lib/api.ts,components/,pages/Login.tsx}` |
| [ ] | S07 | P2 then P1 → P3 | 0:30 | 3:35 | `PATCH /api/me` allowlist + Profile page (skills labelled `Self-declared`, portfolio URL) | Edit persists after refresh; role/verification fields rejected | P3, P4: opportunity fixtures + visibility cases for S08 | `routers/profiles.py`, `pages/Profile.tsx` |
| [ ] | S08 | P2 then P1 → P3 | 0:45 | 4:20 | `opportunities` table + list/detail/create APIs + listing pages + recruiter create form | Own-company recruiter creates; other company and students are denied | P3, P4: application duplicate/deadline cases for S09 | `migrations/002_opportunities.sql`, `routers/opportunities.py`, `pages/Opportunities*.tsx`, `pages/Recruiter.tsx` |
| [ ] | S09 | P2 then P1 → P4 | 0:45 | 5:05 | `applications` table + transactional submit RPC (public listings) + role-scoped list + Applications page | Double/concurrent submit → one row + 409 `ALREADY_APPLIED`; direct insert denied | P3, P4: status transition table for S10 | `migrations/003_applications.sql`, `routers/applications.py`, `pages/Applications.tsx` |
| [ ] | S10 | P2 then P1 → P3 | 0:30 | 5:35 | Recruiter status transitions + applicant tab + student tracker | **Checkpoint B:** public journey (create → apply → shortlist → tracker) on the deployed URL | P1, P4: sample roster CSV + invalid CSV cases for S11 | `routers/applications.py`, `pages/Recruiter.tsx` |
| [ ] | S11 | P3 → P2 | 0:45 | 6:20 | `student_roster` + CSV preview/commit (atomic, revalidated) + University roster tab labelled `University-claimed · Sample data` | Bad CSV → no writes; reimport → no duplicates; existing links preserved | P1, P4: eligibility fixture cases (7.5 threshold, missing CGPA, branch/batch/skill, expired) for S12 | `migrations/004_roster.sql`, `routers/university.py`, `pages/University.tsx` |
| [ ] | S12 | P3 then P2 → P1 | 0:45 | 7:05 | `campus_drives` + **one eligibility DB predicate** + `GET /api/drives/{id}/eligibility` + drive-linked submit + eligibility card | All fixture cases pass; omitting `drive_id` cannot bypass a campus listing | P1, P4: expected report counts from fixtures for S13 | `migrations/005_drives.sql`, `services/eligibility.py`, `routers/applications.py` |
| [ ] | S13 | P3 → P4 | 0:30 | 7:35 | University report counts + CSV export (formula cells neutralized) | **Checkpoint C:** campus journey works; counts match fixtures; other university denied | P1, P2: mentor fixtures + request cases for S14 | `routers/university.py` (report), `pages/University.tsx` |
| [ ] | S14 | P4 → P2 | 0:45 | 8:20 | `mentors`, `mentor_requests` + list/filter/request/accept/decline + pages | Unrelated mentor cannot accept or read the note; requester sees the saved status | P1, P3: coverage cases (none / all / duplicates / case) for S15 | `migrations/006_mentors.sql`, `routers/mentors.py`, `pages/Mentors*.tsx` |
| [ ] | S15 | P2 then P1 → P4 | 0:20 | 8:40 | Count-based `skill_coverage` on listing detail + missing skill → `/mentors?skill=` link | **Checkpoint D (core complete):** gap → matching mentor or honest empty state | P3, P4: 2 sample resumes (one with an injection line) + expected skills for S16 | `routers/opportunities.py`, `pages/OpportunityDetail.tsx` |
| [ ] | S16 | P2 → P3 | 0:45 | 9:25 | *Cut-able.* `services/llm.py` (Claude, structured output), `resumes` + `skill_evidence`, `POST /api/me/resume`, quote check, `GET /api/me/skills`, upload page + "why" panel | Sample resume → skills with valid quotes; the injection line has no effect; LLM outage → manual skills still work | P1, P4: JD fixture + the §5.2 worked example for S17 | `services/llm.py`, `migrations/007_skills.sql`, `routers/skills.py`, `pages/Skills.tsx` |
| [ ] | S17 | P2 then P1 → P4 | 0:45 | 10:10 | *Cut-able.* `job_requirements`, `external_jds`, fit formula, `GET /api/opportunities/{id}/fit`, `POST /api/jds`, `GET /api/jds/{id}/fit`, paste-JD page + gap report | [skill-intelligence.md](docs/skill-intelligence.md) §5.2 example returns 56%; eligibility still separate | P1, P3: hardening test list for S19 | `services/fit.py`, `routers/jds.py`, `pages/{PasteJd,GapReport}.tsx` |
| [ ] | S18 | P4 → P1 | 0:30 | 10:40 | *Stretch.* Ventures + collaboration request/accept | Only the founder can accept; otherwise deferred honestly | P2, P3: hardening test list for S19 | `routers/ventures.py`, `pages/Ventures*.tsx` |
| [ ] | S19 | P2 → P3 | 0:30 | 11:10 | **Feature freeze.** Cross-org access, duplicate, deadline, invalid-token tests; hide or remove unfinished UI | All tests pass on the deployed build | P1, P4: demo script + browser profiles for S20 | `backend/tests/` |
| [ ] | S20 | P4 → All | 0:30 | 11:40 | Reset demo data, timed rehearsal, backup recording, submit | The four-minute script runs with no database edits; submission receipt | — | `demo/` |

**Buffer: 0:20.**

Checkpoint fallbacks:
- If Checkpoint A slips past 3:30, all four help on that step until it merges.
- If Checkpoint B slips past 6:00, drop S18 immediately.

## Cut order when behind

1. S18 ventures → describe as future scope.
2. S17 fit + pasted JD → show as design.
3. S16 resume engine → show as a labelled design or recording.
4. Simplify S13 to counts only.

S01–S15, S19 and S20 are never cut.

Deferred product work lives in [threat-model.md](docs/threat-model.md), [business-model.md](docs/business-model.md), [skill-intelligence.md](docs/skill-intelligence.md) and [architecture.md](docs/architecture.md) §14. The earlier `full-mvp-backlog.md` is not in this repo. Deferred tasks are not completed tasks.
