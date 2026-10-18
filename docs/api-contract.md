# SprintBridge — API contract

Frozen in step S01 · 18 October 2026 · Source of truth for the frontend and backend

This document and the code describe the same API. The machine-readable version is the OpenAPI spec the backend generates at `/docs` and `/openapi.json`; its request and response shapes come from the Pydantic models in [backend/app/schemas](../backend/app/schemas). `backend/tests/test_contract.py` fails if the endpoint table below and the running app disagree. To change the contract, change both in the same step.

Background: [architecture.md](architecture.md) §8, [skill-intelligence.md](skill-intelligence.md) §12.

## 1. Conventions

| Topic | Rule |
|---|---|
| Base path | `/api` |
| Auth | `Authorization: Bearer <Supabase access token>` on every endpoint except `GET /api/health`. The backend verifies the token with Supabase Auth. |
| IDs | UUID strings |
| Times | ISO 8601 UTC, e.g. `2026-10-18T09:30:00Z` |
| Keys / enums | `snake_case` keys, lowercase enum values |
| Nullable | Optional fields are present with `null`, never omitted |
| Unknown request fields | Rejected with `422 VALIDATION_ERROR`. This is how role, owner and status fields are kept out of edit paths. |
| Skills / branches | Normalized server-side: trimmed, lowercase, de-duplicated, sorted |
| Request ID | Response header `X-Request-ID`; also in every error body |
| Workspace | Organization views send `workspace_id`. The server checks membership; the parameter is never proof of access. |

### Lists

```json
{ "items": [], "page": 1, "page_size": 20, "total": null }
```

`page` ≥ 1; `page_size` 1–100 (default 20). Ordering is stable: newest first, then by ID. `total` is filled only when it is cheap to compute.

### Errors

Every failure has one shape:

```json
{
  "detail": "You do not meet this drive's eligibility rules.",
  "code": "NOT_ELIGIBLE",
  "field_errors": {},
  "request_id": "6f1c0e9a2b7d4c8e9f0a1b2c3d4e5f60"
}
```

The frontend branches on `code`, never on `detail`.

| HTTP | `code` | When |
|---|---|---|
| 401 | `UNAUTHENTICATED` | Missing, invalid or expired token |
| 403 | `FORBIDDEN` | Signed in, but not allowed (wrong workspace, not the owner) |
| 403 | `NOT_ELIGIBLE` | Campus drive rules not met; `field_errors` is empty, reasons come from the eligibility endpoint |
| 403 | `DRIVE_REQUIRED` | Applying to a campus listing without an authorized `drive_id` |
| 404 | `NOT_FOUND` | Missing, or not visible to the caller (private rows look missing) |
| 409 | `ALREADY_APPLIED` | Duplicate application; `detail` names the existing application |
| 409 | `ALREADY_REQUESTED` | Duplicate mentor or collaboration request |
| 402 | `PAYMENT_REQUIRED` | A paid action (plan, paid mentor session, verification) needs `confirm_test_payment: true`; `detail` states the amount. Test mode: no real money |
| 402 | `QUOTA_EXCEEDED` / `PLAN_LIMIT` | Monthly free quota used up, or the plan's listing/drive/venture limit reached |
| 409 | `COOLDOWN` / `ALREADY_VERIFIED` / `NO_VERIFIER_AVAILABLE` | Verification retry inside 30 days; already verified at that level; no conflict-free verifier (nothing is charged) |
| 409 | `ALREADY_REPORTED` | The caller already reported this item |
| 409 | `ALREADY_EXISTS` | Duplicate campus drive for the same university and opportunity |
| 409 | `INVALID_TRANSITION` | Status change not allowed (e.g. `offered` → `rejected`) |
| 409 | `DEADLINE_PASSED` | Listing or drive deadline is over |
| 409 | `LISTING_CLOSED` | Listing status is `closed` |
| 413 | `PAYLOAD_TOO_LARGE` | CSV over 1 MB / 100 rows; resume over 5 MB |
| 422 | `VALIDATION_ERROR` | Bad input; `field_errors` maps field → message |
| 500 | `INTERNAL_ERROR` | Unexpected; details only in server logs |
| 501 | `NOT_IMPLEMENTED` | Reserved for contract endpoints whose step is not built (none at present) |
| 503 | `SERVICE_UNAVAILABLE` | Supabase Auth, the database or the LLM is unreachable. Retry later; this never means "wrong password". |

## 2. Endpoints

| Method | Path | Step | Who | Request | Response |
|---|---|---|---|---|---|
| GET | /api/health | S03 | Anyone | — | `{status}` |
| GET | /api/me | S06 | Signed in | — | `Me` |
| PATCH | /api/me | S07 | Signed in | `ProfilePatch` | `Me` |
| GET | /api/opportunities | S08 | Signed in | `q, type, visibility, company_id, sort=newest\|fit, page, page_size` | `Page[OpportunitySummary]` (visible listings only) |
| POST | /api/opportunities | S08 | Recruiter of `company_id` | `OpportunityCreate` | `201 OpportunityDetail` |
| GET | /api/opportunities/{opportunity_id} | S08 | Can see listing | — | `OpportunityDetail` with `skill_coverage` |
| POST | /api/opportunities/{opportunity_id}/applications | S09, S12 | Signed in | `ApplicationCreate {drive_id?}` | `201 Application` |
| GET | /api/opportunities/{opportunity_id}/fit | S17 | Can see listing | — | `FitReport` |
| GET | /api/applications | S09 | Depends on scope | `scope=student\|recruiter\|university, workspace_id?, opportunity_id?, page` | `Page[Application]` |
| PATCH | /api/applications/{application_id} | S10 | Recruiter of listing's company | `ApplicationStatusPatch {status}` | `Application` |
| GET | /api/university/roster | S11 | University admin | `workspace_id, page` | `Page[RosterRow]` |
| POST | /api/university/roster/preview | S11 | University admin | multipart: `workspace_id`, `file` (CSV) | `RosterPreview` (no writes) |
| POST | /api/university/roster/commit | S11 | University admin | multipart: `workspace_id`, `file` (CSV, fully revalidated) | `RosterCommitResult` |
| GET | /api/university/drives | S12 | Admin (with `workspace_id`) or verified student (without) | `workspace_id?, page` | `Page[Drive]` |
| POST | /api/university/drives | S12 | Admin of `university_id` | `DriveCreate` | `201 Drive` |
| GET | /api/drives/{drive_id}/eligibility | S12 | Verified student of the drive's university | — | `EligibilityResult` |
| GET | /api/university/report | S13 | University admin | `workspace_id, branch?, batch?, drive_id?` | `UniversityReport` |
| GET | /api/university/report.csv | S13 | University admin | same as report | `text/csv` (formula cells neutralized) |
| GET | /api/mentors | S14 | Signed in | `niche?, skill?, page` | `Page[MentorSummary]` |
| POST | /api/mentor-requests | S14 | Signed in, not the mentor | `MentorRequestCreate {mentor_id, note}` | `201 MentorRequest` |
| GET | /api/mentor-requests | S14 | Requester or mentor | `scope=requester\|mentor, page` | `Page[MentorRequest]` |
| PATCH | /api/mentor-requests/{request_id} | S14 | Owning mentor | `RequestDecision {status}` | `MentorRequest` |
| POST | /api/me/resume | S16 | Signed in | multipart: `file` (PDF ≤ 5 MB; scanned PDFs are OCR'd) | `201 ResumeUploadResult` (`text_source`: pdf / ocr / cached) |
| GET | /api/me/skills | S16 | Signed in | — | `SkillsResponse` (each skill has a `category`) |
| GET | /api/me/recommendations | Ext | Signed in | `limit?` (1–20) | `Recommendation[]`: open listings ranked by fit against the caller's evidence, with matching/missing skills (no LLM call) |
| GET | /api/me/role-applications | Ext | Signed in | — | `RoleApplication[]`: the caller's applications to become a recruiter, university admin or mentor, with status and decision note |
| POST | /api/me/role-applications | Ext | Signed in | `RoleApplicationCreate` (`kind`: recruiter / university_admin / mentor; `organization_name` for recruiter and university_admin, `niche` for mentor) | `201 RoleApplication` (pending). `409 ALREADY_APPLIED` / `ALREADY_GRANTED` |
| POST | /api/jds | S17 | Signed in | `JdCreate {title?, text?, source_url?}` | `201 JobDescription` |
| GET | /api/jds/{jd_id} | S17 | Owner | — | `JobDescription` |
| GET | /api/jds/{jd_id}/fit | S17 | Owner | — | `FitReport` |
| GET | /api/ventures | S18 | Signed in | `q?, skill?, page` | `Page[Venture]` |
| POST | /api/ventures | S18 | Signed in | `VentureCreate` | `201 Venture` |
| GET | /api/ventures/{venture_id} | S18 | Signed in | — | `Venture` |
| POST | /api/ventures/{venture_id}/requests | S18 | Signed in, not the founder | `CollaborationRequestCreate {note}` | `201 CollaborationRequest` |
| GET | /api/collaboration-requests | S18 | Requester or founder | `scope=requester\|founder, page` | `Page[CollaborationRequest]` |
| PATCH | /api/collaboration-requests/{request_id} | S18 | Founder | `RequestDecision {status}` | `CollaborationRequest` |
| PATCH | /api/mentors/me | Ext | Mentor | `MentorProfilePatch {niche?, experience_summary?, session_price_inr?, is_active?}` | `MentorSummary` |
| POST | /api/mentor-requests/{request_id}/complete | Ext | Owning mentor | — | `MentorRequest` (payout held 7 days) |
| POST | /api/mentor-requests/{request_id}/dispute | Ext | Requester | `DisputeCreate {reason}` | `MentorRequest` |
| POST | /api/verifications | Ext | Signed in | `VerificationCreate {skill, level, confirm_test_payment}` | `201 VerificationCreated` |
| GET | /api/verifications | Ext | Signed in | — | `Verification[]` (verifier revealed at session start) |
| GET | /api/verifications/queue | Ext | Mentor | — | `VerifierQueue` (assignments + blind audits) |
| POST | /api/verifications/{verification_id}/start | Ext | Assigned verifier | — | status `in_session` |
| POST | /api/verifications/{verification_id}/result | Ext | Assigned verifier | `VerificationResult {passed, level?, notes?}` | status `passed`/`failed` |
| POST | /api/verification-audits/{audit_id} | Ext | Assigned auditor | `AuditResult {passed, level?}` | `{agrees}` |
| GET | /api/plans | Ext | Signed in | — | `Plan[]` |
| GET | /api/billing | Ext | Signed in | — | `Billing` (plans, usage, payments, payouts) |
| POST | /api/subscriptions | Ext | Signed in / org manager | `SubscribeRequest {plan_code, organization_id?, confirm_test_payment}` | `SubscribeResult` |
| POST | /api/reports | Ext | Signed in | `ReportCreate {target_type, target_id, reason, details?}` | `201 ReportCreated` |
| GET | /api/operator/queue | Ext | Operator | — | `OperatorQueue` (reports, flagged, payouts, audit log) |
| GET | /api/operator/role-applications | Ext | Operator | — | `PendingRoleApplication[]` with applicant name/email and `existing_organization` when approval would join an existing one |
| POST | /api/operator/role-applications/{application_id} | Ext | Operator | `RoleDecision` (`approve`, `note?`) | `RoleApplication`; approval creates the organization if new, the membership or the mentor profile + grant, in one audited transaction |
| POST | /api/operator/moderate | Ext | Operator | `ModerationAction {target_type, target_id, action, note?}` | `{action}` |
| POST | /api/operator/payouts/release-due | Ext | Operator | — | `{released}` |
| POST | /api/operator/payouts/{payout_id} | Ext | Operator | `PayoutAction {action: release\|refund}` | `{action}` |

All operations are implemented (18 October 2026); rows marked **Ext** come from the threat-model and business-model extensions (migrations 0012–0016) and exercised end-to-end against the live project by `backend/tests_live/test_journeys.py`. Resume and JD analysis need `GROQ_API_KEY`; without it, or while Groq's rate limit is exhausted, they return `503 SERVICE_UNAVAILABLE` with a clear message ("switched off" or "try again in about N seconds"), and everything else works. `JobDescription` also carries `red_flags` (scam warnings).

## 3. Examples

### `GET /api/me`

```json
{
  "user_id": "0b6f2a9e-5d1c-4f7a-9a3e-1c2d3e4f5a6b",
  "email": "asha@student.test",
  "profile": {
    "user_id": "0b6f2a9e-5d1c-4f7a-9a3e-1c2d3e4f5a6b",
    "name": "Asha Rao",
    "specialization": "Data engineering",
    "education_summary": "B.Tech CSE, 2027",
    "skills": ["python", "sql"],
    "portfolio_url": "https://github.com/asha-demo",
    "is_public": true,
    "updated_at": "2026-10-18T09:30:00Z"
  },
  "capabilities": ["student", "verified_student"],
  "workspaces": []
}
```

A recruiter gets `"capabilities": ["student", "recruiter"]` and `"workspaces": [{"organization_id": "…", "name": "Acme Analytics", "type": "company", "role": "recruiter"}]`. The frontend may only offer workspaces from this list.

### `PATCH /api/me`

```json
{ "skills": ["Python", " SQL ", "python"], "portfolio_url": "https://github.com/asha-demo" }
```

Saved skills: `["python", "sql"]`. Sending `"role"`, `"user_id"` or `"cgpa"` returns `422 VALIDATION_ERROR`.

### `POST /api/opportunities`

```json
{
  "company_id": "5a0d…",
  "title": "Data Engineering Intern",
  "description": "Build ETL jobs in Python and SQL.",
  "type": "internship",
  "visibility": "campus",
  "required_skills": ["Python", "SQL", "Docker"],
  "compensation_amount": 25000,
  "currency": "INR",
  "pay_period": "month",
  "deadline": "2026-11-15T18:29:59Z"
}
```

### `GET /api/opportunities/{id}` (student caller)

```json
{
  "id": "9c1e…",
  "company_id": "5a0d…",
  "company_name": "Acme Analytics",
  "title": "Data Engineering Intern",
  "type": "internship",
  "visibility": "campus",
  "required_skills": ["docker", "python", "sql"],
  "compensation": { "amount": "25000.00", "currency": "INR", "pay_period": "month" },
  "deadline": "2026-11-15T18:29:59Z",
  "status": "open",
  "created_at": "2026-10-18T09:00:00Z",
  "description": "Build ETL jobs in Python and SQL.",
  "skill_coverage": {
    "matched_count": 2,
    "required_count": 3,
    "matching_skills": ["python", "sql"],
    "missing_skills": ["docker"],
    "coverage_percent": 67
  }
}
```

Display: `2 of 3 required skills · 67% coverage`. Each missing skill links to `/mentors?skill=docker`.

### `POST /api/opportunities/{id}/applications`

Request `{"drive_id": "d7a2…"}` (or `{}` for a public listing) → `201`:

```json
{
  "id": "a3f9…",
  "opportunity_id": "9c1e…",
  "title": "Data Engineering Intern",
  "applicant_id": "0b6f…",
  "drive_id": "d7a2…",
  "status": "applied",
  "created_at": "2026-10-18T10:00:00Z",
  "updated_at": "2026-10-18T10:00:00Z",
  "profile_snapshot": null
}
```

A second submit returns `409 ALREADY_APPLIED`. The client refetches; it does not retry in a loop.

### `GET /api/drives/{id}/eligibility`

```json
{
  "drive_id": "d7a2…",
  "eligible": false,
  "reasons": [
    { "code": "MISSING_REQUIRED_SKILL", "message": "Python is required." },
    { "code": "CGPA_MISSING", "message": "Your university record has no CGPA." }
  ],
  "matching_skills": ["sql"],
  "missing_skills": ["python"],
  "rules_version": 1
}
```

Reason codes: `NOT_ON_ROSTER`, `BRANCH_NOT_ALLOWED`, `BATCH_MISMATCH`, `CGPA_MISSING`, `CGPA_BELOW_MINIMUM`, `MISSING_REQUIRED_SKILL`, `DEADLINE_PASSED`. Thresholds are inclusive: 7.5 meets a minimum of 7.5.

### `POST /api/university/roster/preview`

CSV header (exact): `student_id,name,email,branch,batch,cgpa`. Limits: 100 rows, 1 MB. CGPA is 0–10 or blank.

```json
{
  "total_rows": 3,
  "valid_rows": [
    { "student_id": "CSE27-001", "name": "Asha Rao", "email": "asha@uni.test", "branch": "cse", "batch": 2027, "cgpa": "8.10" }
  ],
  "errors": [
    { "row": 2, "field": "cgpa", "message": "CGPA must be between 0 and 10." },
    { "row": 3, "field": "student_id", "message": "Duplicate student_id in file." }
  ]
}
```

Commit re-parses and revalidates the uploaded file. It never trusts a preview result. If any row is invalid, nothing is written.

### `PATCH /api/applications/{id}`

`{"status": "shortlisted"}`. Allowed transitions: `applied → shortlisted | offered | rejected`, `shortlisted → offered | rejected`. Repeating the current status is a no-op; anything else returns `409 INVALID_TRANSITION`.

### `GET /api/university/report`

```json
{
  "university_id": "u1…",
  "branch": "cse",
  "batch": 2027,
  "drive_id": null,
  "applications": 12,
  "shortlisted": 5,
  "offered": 2,
  "students_with_offers": 2
}
```

Only applications submitted through this university's drives are counted. An offer is not a confirmed placement.

### `GET /api/opportunities/{id}/fit` (S17)

```json
{
  "target_type": "opportunity",
  "target_id": "9c1e…",
  "fit_percent": 56,
  "required_met": 2,
  "required_total": 3,
  "items": [
    { "skill": "python", "kind": "required", "min_level": 2, "user_level": 2, "label": "system_assessed", "credit": 1.6, "bucket": "strong", "jd_quote": "Strong Python" },
    { "skill": "sql", "kind": "required", "min_level": 2, "user_level": 3, "label": "mentor_verified", "credit": 2.0, "bucket": "strong", "jd_quote": "SQL" },
    { "skill": "docker", "kind": "required", "min_level": 2, "user_level": null, "label": null, "credit": 0.0, "bucket": "missing", "jd_quote": "Docker experience" },
    { "skill": "react", "kind": "preferred", "min_level": 1, "user_level": 1, "label": "self_declared", "credit": 0.3, "bucket": "under_evidenced", "jd_quote": "React is a plus" }
  ]
}
```

This matches the worked example in [skill-intelligence.md](skill-intelligence.md) §5.2: 3.9 / 7 → 56%. Fit never replaces campus eligibility.

## 4. Database operations behind the API

Tables, constraints and row security are in [database/migrations](../database/migrations), tested by `database/tests/test_schema.py`. Most writes are plain inserts/updates that RLS and column grants already constrain. The following operations are single transactional Postgres functions (RPC), tested in `database/tests/test_operations.py`. A direct Supabase call must enforce exactly what the API enforces (architecture.md §6).

| Function (in `0010_operations.sql`) | Step | Contract |
|---|---|---|
| `submit_application(p_opportunity_id uuid, p_drive_id uuid default null) returns applications` | S09 (public), S12 (drive) | Caller from `auth.uid()`. Listing visible, `open`, before deadline. Campus listing requires an authorized drive for the same opportunity, whose university has a verified roster row for the caller, and which passes `evaluate_drive_eligibility`. Writes `profile_snapshot` (and `eligibility_snapshot` for drives). Unique violation → `ALREADY_APPLIED`. |
| `evaluate_drive_eligibility(p_drive_id uuid) returns jsonb` | S12 | The **one** authoritative predicate. Same output shape as `EligibilityResult`. Called by both the eligibility endpoint and `submit_application`. |
| `commit_roster(p_university_id uuid, p_rows jsonb) returns jsonb` | S11 | Caller must be an admin of the university. Validates every row; upserts on `(university_id, student_id)`; preserves `verified_user_id`; all-or-nothing. Returns `{inserted, updated, unchanged}`. |
| `university_report(p_university_id uuid, p_branch text, p_batch int, p_drive_id uuid) returns jsonb` | S13 | Admin only; counts drive-sourced applications only. `university_report_rows(...)` returns the same scope as rows for CSV export. |
| `list_mentors(p_niche text, p_skill text, p_limit int, p_offset int) returns jsonb` | S14 | Active mentors with a consented public projection (name, niche, skills), ordered by name then ID. |
| `display_names(p_user_ids uuid[])` | S14 | Names only for people the caller interacts with (public profiles, mentors, request counterparts, own applicants). |

Each one is `security definer` with `set search_path = ''`, checks `auth.uid()` and ownership explicitly, and grants `execute` to `authenticated` only.

**Postgres → API error mapping** (`backend/app/db.py` → `translate`). Our functions raise SQLSTATE `PTnnn` (HTTP status nnn) with the API code in `HINT`:

| Postgres / PostgREST | API |
|---|---|
| `23505` unique violation | `409 ALREADY_APPLIED` / `ALREADY_REQUESTED` (by table) |
| `PTnnn` with hint `CODE` | `nnn CODE` (e.g. `PT403`/`NOT_ELIGIBLE`, `PT409`/`INVALID_TRANSITION`) |
| `42501` / RLS violation on write | `403 FORBIDDEN` |
| `23514` check violation, `22P02` bad input | `422 VALIDATION_ERROR` |
| Zero rows returned for a by-ID read | `404 NOT_FOUND` |
| Connection error / timeout | `503 SERVICE_UNAVAILABLE` |

`applications.eligibility_snapshot` has no column `SELECT` grant. Queries on `applications` must list their columns explicitly; `select=*` fails.

## 5. Server-owned tables

`resumes`, `skill_evidence` and `job_requirements` give users no write grants, so the browser or a direct Data API call cannot fabricate evidence. The backend writes them with `db.service_client(table)`, which refuses any other table. The Supabase secret key lives only in backend configuration. It is never used for reads on a user's behalf, and never reaches the frontend. This is a deliberate, narrow exception to "caller JWT for all data access" (architecture.md §1), recorded in [skill-intelligence.md](skill-intelligence.md) §11.
