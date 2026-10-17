# Person 1 frontend checklist

Source: [plan.md](plan.md), fetched backend `d62300b`. See the implementation update for local completion; unchecked acceptance gates still require live or teammate verification. P2 checks P1's foundation/API integration; P3/P4 check their respective joined journeys. Dependencies below refer to these F tasks.

## Implementation update — 18 October 2026

The original acceptance gates below include live/backend/hosted checks, so they are not automatically checked off by local UI work.

| Area | Current state |
|---|---|
| F01–F10 | Frontend implementation present: shell, client, auth, profile, listing/create, application/tracker, recruiter decisions and campus eligibility. Production build and focused unit/browser checks run locally. Real seeded-account acceptance awaits P2 configuration. |
| F11 | P3 university admin page is not present; shared auth/client/controls and student drive flow are ready for integration. |
| F12 | Minimal real-API mentor discovery/request/inbox pages implemented so gap links work; P4 can extend. Live request/decision acceptance remains pending. |
| F13–F14 | Resume evidence and pasted-JD/opportunity fit views implemented. Extraction outage is browser-tested; real provider success awaits backend configuration. |
| F15 | P4 ventures deferred; no unfinished venture navigation shown. |
| F16 | Render static configuration and local startup instructions prepared. No deployment performed. |
| F17 | Automated isolated-browser journeys and responsive screenshots checked. Outsider trials, real cross-tenant tests and hosted smoke checks remain pending. |

Browser fixtures live only in tests; production screens always use configured auth/API. See `frontend/README.md` for exact startup and verification commands.

| Task | Depends | Deliverable / likely files | Done when / verification |
|---|---|---|---|
| [ ] F01 Scaffold | — | `frontend/package.json`, Vite/TS configuration, entry point, base CSS, `.env.example` | Dev page loads; production build/type check passes; browser env contains only public configuration. |
| [ ] F02 API contract client | F01 | `src/lib/api.ts`, `src/lib/types.ts`, focused client test | Auth header, structured/non-JSON errors, abort, multipart and blob responses handled; no automatic mutation replay. Focused error/auth tests pass. |
| [ ] F03 Seeded login | F02 | `src/auth/AuthProvider.tsx`, Supabase client, `pages/Login.tsx`, protected route | Real login → `/me`; logout clears private state; expired/invalid token and service outage differ. Requires P2 configuration; browser reload preserves valid session. |
| [ ] F04 Shared shell | F03 | `App.tsx`, `AppLayout`, shared controls and dashboard | Keyboard-usable navigation; only server-authorized workspaces; workspace changes ignore old responses; dashboard shows no fabricated counts. Verify two seeded roles. |
| [ ] Checkpoint A | F04 | Authenticated foundation (S06) | Build/type check and focused tests pass; real login/context works. Hosted acceptance additionally requires backend/static deployment. |
| [ ] F05 Profile | F04 | `pages/Profile.tsx`, profile tests | PATCH `/me` persists allowed edits after refresh; field errors render; manual skills and portfolio have correct evidence labels; no academic/role editing. |
| [ ] F06 Recruiter listing creation | F05 | `pages/Recruiter.tsx`, listing form | Company selected from recruiter workspaces; compensation fields supplied together; deadline includes timezone. Real POST then company list shows the saved listing. |
| [ ] F07 Opportunity discovery | F06 | `pages/Opportunities.tsx`, `OpportunityDetail.tsx` | Search/type/visibility filters, pagination and empty/error states work; detail shows coverage counts and null states correctly. Refresh/deep links work. |
| [ ] F08 Public application and tracker | F07 | detail apply action, `pages/Applications.tsx`, submit test | Submit once; pending button blocks double-click; 409 shows existing application guidance; unknown network outcome checks saved state. Student list persists after refresh. |
| [ ] F09 Recruiter applicant decisions | F08 | recruiter applicant tab, transition test | Correct scope/workspace; returned snapshot visible; only allowed transitions offered; successful shortlist appears in student's tracker. Test other-company denial and stale workspace response. |
| [ ] Checkpoint B | F09 | Public end-to-end flow (S07–S10) | Create → discover → apply → shortlist → refresh tracker passes with real backend in separate student/recruiter browser profiles. |
| [ ] F10 Student campus context | F09 | campus drive selector/list, eligibility card, detail integration | Paginated drives matched to listing; selected drive survives URL refresh; reasons shown independently of coverage; campus submission includes drive_id. Verify eligible/ineligible/no-drive cases. |
| [ ] F11 University integration | F10; P3 pages | route registration, shared controls/API interfaces | P3 roster/drive/report pages reuse auth/layout; university switch clears rows; CSV downloads work; sample roster labelled University-claimed. P3 checks scoped counts and denial. |
| [ ] F12 Mentor integration | F10; P4 pages | mentor routes, detail missing-skill links | Encoded skill opens P4 filter; editable note requires explicit submit; honest empty state; requester sees saved decision. No invented booking/chat features. |
| [ ] Checkpoint C/D | F11,F12 | Core complete (S11–S15) | Campus apply and gap-to-mentor journeys pass; fit or coverage never overrides failed eligibility; no misleading verified badges. |
| [ ] F13 Optional skills page | Core checkpoint; extraction enabled | `pages/Skills.tsx`, upload and evidence components | PDF ≤5 MB upload; returned quotes/levels/scores displayed; success refetches skills; 413/422/503 and manual-skills fallback tested. P2 checks real provider separately. |
| [ ] F14 Optional JD/fit view | F13 | `pages/PasteJd.tsx`, `GapReport.tsx`, detail fit panel | Pasted text saved and fit loaded; strong/under-evidenced/missing groups and null score correct; required/preferred shown; results never described as hiring probability. |
| [ ] F15 Optional venture registration | Core checkpoint; P4 pages | app routes/navigation | Register only P4's functional pages; persisted request/acceptance verified; otherwise omit navigation and mark deferred. |
| [ ] F16 Hosted frontend | F04 minimum; final check after core | static deployment config, README startup notes | Production build published with SPA fallback; frontend origin allowed by API; direct route refresh, real login and authenticated fetch succeed. No secret keys in bundle. |
| [ ] F17 Final Person 1 checks | Core checkpoint,F16; optional tasks if included | focused tests, demo checklist | Mobile layout, keyboard/focus, loading/error/empty states, slow/failed requests and cross-workspace clearing checked; two outsiders complete student journey; unfinished optional features hidden. |

Cut order: ventures, then JD/fit UI, then resume UI. Core S06–S15 frontend work remains required. No frontend implementation or deployment is performed by this planning change.
