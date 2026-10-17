# SprintBridge frontend

Person 1 implementation on `frontend`, built against the API on `yatin` at `d62300b`. React, TypeScript, Vite, Tailwind and Supabase Auth; all business operations go through FastAPI.

## Start locally (PowerShell)

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
# Fill the three public values in .env.local, then:
npm run dev
```

Open http://127.0.0.1:5173. Without configuration, the login page explains that sign-in is unavailable. There is no fake-login or production demo-data mode.

`VITE_API_BASE_URL` is the backend origin, for example `http://localhost:8000`, without `/api`. The helper adds `/api` once. `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` come from P2. These values are embedded in the browser bundle. Never place a database password, Supabase secret/service-role key or Anthropic key in a VITE variable.

P2 must allow both development origins actually used (e.g. `http://127.0.0.1:5173,http://localhost:5173`) in backend `ALLOWED_ORIGINS`, configure Supabase, apply migrations and provide seeded account credentials privately. No secrets or seed passwords are included here.

## Screens and handoff

- `/login`, `/dashboard`: authenticated session, server capabilities, organization selection and real counts.
- `/profile`: editable allowlist; manual skills are self-declared.
- `/opportunities`, `/opportunities/:id`: search, filters, pagination, detail, count-based coverage, campus drive selection and authoritative eligibility; submit with duplicate/unknown-outcome handling.
- `/applications`: student tracker with refresh and pagination.
- `/recruiter`: company listings/create form, applicant snapshots and allowed status decisions. Company changes clear page state.
- `/skills`: PDF upload, server evidence labels, scores/levels and quotes; manual profile remains available during extraction outage.
- `/job-fit`: pasted JD analysis, persisted `jd_id` URL, or `opportunity_id` report. Fit and eligibility remain separate.
- `/mentors`, `/mentor-requests`: minimal integrated gap-to-mentor flow, explicit note submission, requester tracking and mentor decisions. P4 can extend these existing pages.

P3's university admin screens and P4's ventures are not fabricated or exposed as empty navigation. P3 can add a `University` page to `src/pages` and register it under the protected Layout in `src/App.tsx`, gated by server capability/workspace. Use `useAuth().api`, `workspace`, shared UI, and the existing multipart/blob support. Business data must never be fetched directly from Supabase. Student campus eligibility is already integrated.

The shell uses navy/blue, a restrained teal accent, compact rows and shared spacing. Mobile navigation hides from keyboard focus while closed. Read, empty, error, pending and saved states are explicit. There are no fabricated metrics or verified academic badges.

## Verification

```powershell
npm test
npm run build
npm run test:e2e
```

Unit tests cover the HTTP boundary, safe links and status decisions. Playwright uses an isolated installed Chrome (`channel: chrome`), starts Vite on port 5174, and intercepts Supabase/API requests with synthetic fixtures. Its test-only public configuration is in `playwright.config.ts`; it does not connect to the real backend. Chrome must be installed to run this suite. Screenshots and traces go to ignored `test-results/`.

Browser tests exercise profile persistence, public/campus application, recruiter decisions, workspace clearing, mentor filtering, unavailable analysis, protected navigation, and responsive overview layouts at 320/768/1024/1440px. Passing these checks does **not** verify real login, database writes, Claude output, hosting or CORS.

Local verification on 18 October 2026: 7 unit tests passed, 11 browser tests passed, production TypeScript/build passed. npm reported zero known dependency vulnerabilities after updating the test runner. Desktop/mobile overview, login and ineligible-campus detail screenshots were visually inspected.

Before claiming live completion, run with seeded student/recruiter accounts in separate browser profiles: create a listing → update profile → apply → shortlist → refresh student tracker; repeat with a real eligible/ineligible campus drive; then check mentor request/decision and enabled analysis. Verify another organization cannot see applicants. P2 owns the backend configuration and the previously observed offline backend test failures.

## Deployment

The root `render.yaml` includes a static frontend service using branch `frontend`, root `frontend`, `npm ci && npm run build`, publish directory `dist`, and a `/*` rewrite to `/index.html`. This is configuration only; no hosting resource was created. Set the three public VITE values before building and put the deployed frontend origin in backend CORS. Rebuild after changing VITE values. Check `/profile` and `/opportunities/<id>` on direct refresh after deployment.

References: [Vite setup](https://vite.dev/guide/), [Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite), [Supabase auth events](https://supabase.com/docs/reference/javascript/auth-onauthstatechange), [Render Blueprint fields](https://render.com/docs/blueprint-spec).
