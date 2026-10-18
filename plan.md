# SprintBridge — four-person, 12-hour hackathon plan

Updated 17 October 2026. Active plan; replaces the original 14–18-week implementation schedule. Python is the backend language. Database must be free. All times are elapsed from hackathon kickoff, not clock times.

The original product vision was in `full-mvp-roadmap.md`, which is not in this repo. Post-hackathon scope now lives in [architecture.md](docs/architecture.md) §14, [threat-model.md](docs/threat-model.md), [business-model.md](docs/business-model.md) and [skill-intelligence.md](docs/skill-intelligence.md). The active checklist is [todo.md](todo.md). This document plans the work; it does not claim anything is built or deployed.

**Build mode: strict sequential steps (S01–S20).** Only one step is in progress at a time. It is merged to `main` before the next step starts, so parallel branches cannot conflict. See §4.

## 1. Define the demo (step S01)

Four people have 48 person-hours, but dependencies and integration reduce usable implementation time. Target a reliable demonstrable prototype of SprintBridge's central promise. A production-ready five-pillar ecosystem is beyond this window.

**Main demonstration:** a university imports synthetic student records; a student sees an eligible campus opportunity and its matching/missing skills; the student applies; a recruiter shortlists the application; the university sees that campus outcome. A job seeker can also apply to an independent public opportunity without university membership.

**Second demonstration:** a student discovers a niche mentor, sends a request, and the mentor accepts it.

**Stretch demonstration:** a founder lists an idea; another user requests to join; the founder accepts. Build only after the main application journey passes Checkpoint B (S10), and only as step S18 after the core is complete. If unfinished, describe Venture Launchpad honestly as planned work in the pitch.

### Scope commitment

| Pillar | Hackathon version | Deferred |
|---|---|---|
| Skill Proof | Editable `Self-declared` skills, education summary, portfolio URL; matching and missing skill chips. *Cut-able (S16–S17):* resume upload → Claude extraction with cited evidence → `System-assessed` skills; fit score + gap report for listings and pasted JDs | GitHub OAuth analysis, 48-hour proof plans, recruiter outreach, mentor verification (`Mentor-verified`) |
| Opportunity Hub | Public listing, recruiter create form, apply once, applicant list, Applied/Shortlisted/Offered/Rejected status | Talent search, messaging, advanced pipelines, notifications by email |
| University Portal | Small CSV import, branch/batch/CGPA eligibility, campus drive linked to listing, campus applications, simple counts and CSV export | Bulk invitations, ERP, complex grading conversion, accreditation reports, multi-campus targeting automation |
| Mentor Connect | Niche filter, seeded mentor profiles, request note, accept/decline | Booking calendars, video, payment, sponsored programs, reminders |
| Venture Launchpad | Stretch: idea list/create, request, accept/decline | Investor matching, equity, chat, legal team agreements |

Public launch, real institutional onboarding, paid subscriptions, automated email flows, and real student data are outside the hackathon deliverable. Use seeded, real authenticated demo accounts with synthetic content. Do not use a role dropdown that grants privileges. A demo account selector may choose an account to log into, but server-side authorization must still verify its identity.

## 2. Design (prepared off-repo by the idle pair during S02–S05, committed in S06)

P1 and P4 sketch the shared layout while S02–S05 run; nobody commits UI code until S06. Reuse one navigation/sidebar, card, table, button, form, and status badge style. Use navy/blue as suggested by the reference image. Prioritize readable, functional screens over custom animation.

Required routes: `/login`, `/dashboard`, `/profile`, `/opportunities`, `/opportunities/:id`, `/applications`, `/recruiter`, `/university`, `/mentors`, `/mentor-requests`. Optional: `/ventures` and `/ventures/:id`.

The university page can use tabs for roster, drives, and reports; the recruiter page can use tabs for listings and applicants. Avoid creating a separate dashboard framework for each role. Show clear loading/error/empty states and disable duplicate submissions while requests are pending.

## 3. Stack and shared contract: frozen in S01

| Layer | Decision | Owner |
|---|---|---|
| Frontend | React + Vite + Tailwind; standard React state and one API helper | Person 1 |
| Backend | Python + FastAPI + Pydantic + Uvicorn | Person 2 |
| Database | Supabase Free PostgreSQL | Person 2 provisions; Person 3 owns schema/seed files |
| Authentication | Supabase Auth; pre-created email/password demo users | Person 2 |
| Data client | Supabase Python client, request-scoped user credentials | Person 2 supplies shared helper |
| Eligibility and CSV | One authoritative eligibility database predicate called by both the eligibility endpoint and atomic submission ([architecture.md](docs/architecture.md) §6). Standard-library `csv` for parsing; focused pytest cases. | Person 3 |
| Skill extraction (cut-able) | Groq API (gpt-oss-120b) inside FastAPI; the LLM extracts with quotes, Python computes scores | Person 2 |
| Hosting | Render Free static frontend + Render Free Python web service | Person 2; Person 1 frontend setup |
| Fallback demonstration | Frontend and FastAPI run locally, using the same hosted Supabase project | Entire team rehearses |

React/Vite is proposed because Python owns the backend; there is no need for an additional Next.js server in this demo. Assumption: at least one teammate knows React and two can work in Python. Assign the strongest UI developer to Person 1, strongest backend developer to Person 2, and remaining full-stack work to Persons 3 and 4. Do not learn unfamiliar state-management or ORM frameworks during the event.

Supabase currently lists a $0 Free plan with a 500 MB database and 50,000 monthly active users. Free projects may pause after one week of inactivity; automated backups are not included. A small synthetic dataset fits comfortably. Keep schema and seed files in Git so demo data is reproducible. Source: [Supabase pricing](https://supabase.com/pricing), checked 17 October 2026.

FastAPI provides Python APIs, validation integration, and generated API documentation useful for team integration. See [FastAPI documentation](https://fastapi.tiangolo.com/). Supabase documents a [Python client](https://supabase.com/docs/reference/python/introduction). Use those supported APIs, with versions pinned once the initial smoke test passes.

Render offers free static sites and Python web services. Its free web service sleeps after 15 minutes idle and may take about a minute to wake; its local filesystem is ephemeral. Store data in Supabase, and open the backend before judging. Confirm account eligibility and remaining quotas during hour 1; do not assume paid resources are free. Source: [Render Free documentation](https://render.com/docs/free).

### Authentication and database boundary

Browser authenticates with Supabase → sends access token to FastAPI → backend verifies token through Supabase Auth → obtains server-controlled role/membership → executes authorized operation with the caller's database credentials and row-level policies. Never accept role, company, university, or user ownership from unchecked client fields. Token decoding alone is not verification; follow [Supabase JWT guidance](https://supabase.com/docs/guides/auth/jwts).

Browser uses Supabase only for authentication. Business operations go through FastAPI. Use one request-scoped database client per caller; do not mutate a shared global client's session between users. Enable row-level policies; restrict access to identity, ownership, and organization scope. Person 2 defines these helpers/policies early, and module owners supply their domain-specific checks. Privileged credentials are only for controlled seed/setup operations and never go into frontend code or source control.

Turn on Supabase email confirmation for new sign-ups ([threat-model.md](docs/threat-model.md) §13). Seed two university identities and two employer identities for negative access testing, even though the presentation uses one of each. Public mentor/listing/venture data excludes private academic fields. Prelink synthetic roster records to authenticated demo users; arbitrary CSV email/student IDs must not create account privileges. Real membership-claim onboarding is deferred.

### Minimal schema

Use UUIDs, UTC ISO timestamps, and snake_case JSON. Person 3 is the only editor of the shared schema/seed files. All members agree column names before coding.

| Table | Minimal contents |
|---|---|
| `profiles` | auth user ID, name, skills, portfolio URL; private role grants cannot be edited through profile form |
| `organizations` | ID, name, type: company/university |
| `memberships` | user ID, organization ID, fixed admin/recruiter role |
| `student_roster` | university ID, student identifier, optional seeded user link, branch, batch, CGPA on a fixed 10-point demo scale. Shown as `University-claimed · Sample data`, never "verified". |
| `opportunities` | company ID, title, type, description, required skills, compensation/currency/period, deadline, status |
| `campus_drives` | university ID, opportunity ID, minimum CGPA, allowed branches, batch, required skills, deadline |
| `applications` | opportunity ID, applicant ID, optional drive ID, status, submitted eligibility snapshot, timestamps; unique applicant/opportunity |
| `mentors` | user ID, name, niche, experience summary |
| `mentor_requests` | mentor ID, requester ID, note, status; unique active requester/mentor pair |
| `ventures` (stretch) | founder ID, title, problem, stage, needed skills |
| `collaboration_requests` (stretch) | venture ID, requester ID, status; unique requester/venture |

For the demo, campus drives are explicitly authorized by a university admin and linked to a real seeded recruiter-owned opportunity. This permits campus operations without inventing a university–company commercial tie-up. Recruiters control application decisions; university accounts only view their own drive applications. General public applications are never included in campus reporting automatically.

### Shared API agreement

Prefix all business endpoints with `/api`. IDs and ownership are derived/validated server-side. List responses use `{items: [...], page, page_size}`; mutations return the saved object. Errors use `{detail, code, field_errors, request_id}` as in [architecture.md](docs/architecture.md) §8. Use 401 for missing/invalid login, 403 for denied access, 409 for duplicate/conflict, and 422 for invalid input. Keep generated `/docs` usable for integration.

| Owner | Endpoints | Frontend consumer |
|---|---|---|
| P2 | `GET /api/health`; `GET/PATCH /api/me` | P1 |
| P2 | `GET/POST /api/opportunities`; `GET /api/opportunities/{id}` | P1 |
| P2 | `POST /api/opportunities/{id}/applications`; `GET /api/applications`; `PATCH /api/applications/{id}` | P1, P3 |
| P3 | `POST /api/university/roster/preview`; `POST /api/university/roster/commit`; `GET /api/university/roster` | P3 |
| P3 | `GET/POST /api/university/drives`; `GET /api/drives/{id}/eligibility` | P3 |
| P3 | `GET /api/university/report`; `GET /api/university/report.csv` | P3 |
| P4 | `GET /api/mentors`; `POST/GET /api/mentor-requests`; `PATCH /api/mentor-requests/{id}` | P4 |
| P4 stretch | `GET/POST /api/ventures`; `POST /api/ventures/{id}/requests`; `GET/PATCH /api/collaboration-requests[/{id}]` | P4 |

`GET /api/applications` returns own applications for students, own company applicants for recruiters, and own-drive applicants for university admins. Role behavior is explicit, not caller-supplied arbitrary filters. Student drive discovery can return a sanitized eligible-drive list from `GET /api/university/drives`; only university admins can create drives. Missing required academic values produce ineligibility/verification-needed reasons. Apply calls with `drive_id` invoke P3's eligibility predicate inside the transactional submission operation and persist the evaluated rule/profile snapshot. UI-only eligibility checks are insufficient.

CSV import: fixed header `student_id,name,email,branch,batch,cgpa`; demo limit 100 rows/1 MB; reject bad headers, invalid numbers, CGPA outside 0–10, and duplicate identifiers. Preview is read-only; commit revalidates the submitted data, uses an atomic database function, and creates no duplicate records on retry. Never trust a client assertion that preview succeeded. Existing verified user links stay unchanged. Export neutralizes spreadsheet formula cells.

Eligibility example: branch CSE/IT, batch 2027, CGPA at least 7.5, mandatory Python skill. Exact threshold passes; missing CGPA fails with an explanation. Normalize skill/branch case. Public opportunities require no university membership. Use transparent matching/missing skill lists. If S16–S17 ship, Claude only extracts skills with quotes. Fit is a deterministic, displayed formula ([skill-intelligence.md](docs/skill-intelligence.md) §5.2), never an AI prediction.

## 4. How the four people work: one step at a time

Work runs as **one ordered sequence of steps (S01–S20)**. Only one step is in progress at a time, so no two people edit the repo at once and branches cannot conflict.

1. **A step starts only after the previous step is merged to `main`.**
2. **Driver** is the only person editing the repo in that step. **Checker** reviews the diff and runs the step's "Done when" check before approving.
3. **The idle pair never touches the repo.** They prepare the next step's inputs outside the repo: payload examples, test cases, fixtures, UI copy, demo script. The next Driver commits them. This keeps each step short and keeps all four people busy.
4. **Git flow:** `step/NN-slug` branch from the latest `main` → one PR → Checker approves → squash-merge → everyone pulls → next step. One open branch at a time.
5. **Timebox:** at 150% of budget, decide whether to ship a minimal version or cut the step. Never merge a half-done step.
6. **`main` stays deployable.** From S04, every merge redeploys and the check is re-run on the deployed URL.
7. **Cross-stack steps** ("P2 then P1") are two ordered commits in the same PR: backend first, then frontend.

Ownership by expertise is unchanged, but it now determines **who drives which step**, not parallel lanes. Assign the strongest UI developer to P1, the strongest backend developer to P2, and the other two full-stack developers to P3 and P4.

| Person | Drives | Checks |
|---|---|---|
| **P1 — frontend/integration** | S01, S06, frontend half of S07–S10, S15, S17 | S03, S12, S18 |
| **P2 — Python/backend + deploy** | S02, S03, S04, backend half of S07–S10, S12 submit integration, S15, S16, S17, S19 | S01, S05, S06, S11, S14 |
| **P3 — data/university** | S05, S11, S12, S13 | S02, S07, S08, S10, S16, S19 |
| **P4 — mentors/demo** | S14, S18, S20 | S04, S09, S13, S15, S17 |

Only P2 handles deployment secrets. Each member gets local configuration through an approved private channel, never the repository. Temporary fixtures may unblock a UI step, but they must be replaced with real API calls within that same step before it merges.

## 5. Step sequence and checkpoints

The full checklist with Driver, Checker, files and "prepare next" items is in [todo.md](todo.md). Summary:

| Step | Ends at | Result |
|---|---|---|
| S01–S05 | 2:20 | Contract frozen; Supabase + core tables/RLS + email confirmation; FastAPI auth skeleton deployed; seed data |
| S06 | 3:05 | **Checkpoint A:** deployed login → `/me` |
| S07–S10 | 5:35 | **Checkpoint B:** public journey: profile → listing → apply once → recruiter shortlist → tracker |
| S11–S13 | 7:35 | **Checkpoint C:** roster CSV → drive eligibility → campus apply → university report |
| S14–S15 | 8:40 | **Checkpoint D (core complete):** mentor request/accept; missing skill → mentor link |
| S16–S17 | 10:10 | *Cut-able:* resume → System-assessed skills; fit + gap report for listings and pasted JDs |
| S18 | 10:40 | *Stretch:* ventures |
| S19 | 11:10 | Feature freeze + hardening tests |
| S20 | 11:40 | Demo reset, rehearsal, backup recording, submission (0:20 buffer) |

Fallbacks:
- **Checkpoint A late (after 3:30):** all four people help on that step until it merges.
- **Checkpoint B late (after 6:00):** cut S18 immediately.
- **Checkpoint D late (after 9:15):** cut S17, then S16. Show the skill engine as a labelled design or recording, never as faked output.
- **CSV import still broken at S13:** use clearly labelled preloaded roster data and disclose import as incomplete.

**Cut order:** S18 → S17 → S16 → simplify S13 to counts. S01–S15, S19 and S20 are never cut. After S19 no new features; the remaining time belongs to deployment, rehearsal and submission.

Sequential work trades parallel speed for zero conflicts. The idle pair's preparation is what makes this fit in 12 hours. If a step's inputs are not ready when it starts, the Driver uses the simplest valid version and records the gap.

## 6. Release and demonstrate

### Minimum passing checks

1. (S06–S07) Student logs in, edits skills/portfolio, refreshes, and sees persistence.
2. (S08–S10) Public opportunity works without university membership.
3. (S12) Eligible campus student can apply; wrong branch, low/missing CGPA, wrong batch, missing required skill, and expired drive fail clearly.
4. (S09–S10) Repeated/concurrent application creates one row; student cannot patch their hiring status.
5. (S10) Recruiter shortlists their applicant; another company cannot read or change it.
6. (S12–S13) University sees only its authorized campus applicants; another university cannot read its roster/report.
7. (S11, S13) CSV preview catches invalid input; commit preserves unique identifiers; report counts match stored records.
8. (S14) Mentor receives a real request and can accept; unrelated mentor cannot modify it.
9. (S19) Frontend build succeeds; backend imports/starts; focused eligibility and permission tests pass; deployed navigation/API calls work.
10. (S20) All demo actions use synthetic data. No service credential appears in frontend bundles, Git, screenshots, or pitch materials.

Acceptance concerns actual saved data, not toast notifications alone. Each check is the "Done when" of the listed step in [todo.md](todo.md) and is re-run in S19.

If S16–S17 ship, also check:
- a sample resume yields skills whose quotes exist in the source
- an injection line in the resume has no effect
- the worked fit example returns 56% If venture is included, prove request acceptance persists and only the founder can accept.

Deployment starts in S04 (backend) and S06 (frontend), and every later merge redeploys. Frontend and Python service can be separate Render Free services; configure the API URL and a precise CORS allowlist for the deployed frontend and local development. Test browser refresh on frontend routes. Keep secrets backend-only and use Supabase as persistent storage. Local fallback still needs internet for Supabase; the prerecorded demo is the contingency for connectivity loss. Do not introduce a second SQLite backend during the final hour.

### Seed dataset

Use 8 synthetic students with deliberately varied branch/batch/CGPA/skills; 2 universities; 2 employers; 5 opportunities including a public one; 1–2 campus drives; 4 mentors. Add 3 ventures only for the stretch feature. Store seed setup as repeatable scripts; keep passwords outside source control. Preserve a dedicated student account with no application before the presentation so the apply action is repeatable.

### Four-minute presentation

- 0:00–0:30: State the problem and SprintBridge's campus-to-career proposition.
- 0:30–1:10: University previews a small roster CSV and shows an eligibility rule.
- 1:10–2:00: Student views matching/missing skills (and, if S16–S17 shipped, a resume-derived fit + gap report) and applies to an eligible opportunity.
- 2:00–2:40: Recruiter shortlists; student's tracker and university campus count reflect the update.
- 2:40–3:20: Student requests a mentor; mentor accepts.
- 3:20–4:00: Show venture collaboration if working; otherwise explain it as future scope. Close with the Python architecture, independent B2B model, and what the prototype demonstrates.

Use separate browser profiles for student/recruiter/university/mentor sessions to avoid logout confusion. Open the sleeping backend before presenting and verify a database read. Keep a 2–3-minute backup video and startup instructions. Adapt the script length to the actual judging slot and submission rules when supplied.

## 7. Measure and learn during the hackathon

Use lightweight evidence: number of submitted applications, shortlisted students, mentorship requests accepted, and elapsed time to complete the main journey. Counts are demo activity, not customer traction. Distinguish multiple offers from unique students and do not label an offer as a confirmed placement.

Ask two people outside the team to try the student journey during S19. Record one major point of confusion and fix it if safe. After submission, list incomplete parts against the original roadmap and identify the next genuine pilot requirement. No commercial/production readiness claims are implied by the hackathon build.

The first team action is to assign names to P1–P4, agree the example API payloads, and start the shared repository/database setup. Team assignments are based on strengths, not seniority; if experience differs, swap the people while keeping the step Driver/Checker assignments in §4.
