# SprintBridge — Round 2 showcase workflow

How every flow works from start to end, who is involved, and what the system does behind each step. Every flow below was run in the app against the real database (18 October 2026); the "Result" lines are what we observed. Flows A2 and H were re-run after the onboarding and resume-engine changes the same day.

**Live app:** https://sprintbridge-frontend.onrender.com · **API:** https://sprintbridge-api.onrender.com/api/health

**Contents**
1. [The system in one picture](#1-the-system-in-one-picture)
2. [Before the demo](#2-before-the-demo)
3. [Accounts](#3-accounts)
4. [How each user gets their role](#4-how-each-user-gets-their-role)
5. [Flow A — Create an account](#flow-a--create-an-account-and-sign-in)
6. [Flow A2 — Become a recruiter, university or mentor](#flow-a2--become-a-recruiter-university-or-mentor)
7. [Flow B — Campus placement, end to end](#flow-b--campus-placement-end-to-end-the-core-connectivity-story)
8. [Flow C — Skill gap → mentor → paid session](#flow-c--skill-gap--mentor--paid-session)
9. [Flow D — Independent skill verification](#flow-d--independent-skill-verification)
10. [Flow E — Venture Launchpad](#flow-e--venture-launchpad-entrepreneurs)
11. [Flow F — Plans, quotas and payments](#flow-f--plans-quotas-and-payments-test-mode)
12. [Flow G — Trust & safety](#flow-g--trust--safety)
13. [Flow H — Resume → skills → job fit → recommendations](#flow-h--resume--skills--job-fit--recommendations)
14. [Flow diagrams per user type (for slides)](#14-flow-diagrams-per-user-type-for-slides)
15. [Security points to show](#15-security-points-to-show)
16. [Suggested 12-minute demo order](#16-suggested-12-minute-demo-order)
17. [What is real and what is simulated](#17-what-is-real-and-what-is-simulated)

---

## 1. The system in one picture

Seven kinds of user share one platform (student and job seeker differ only in pricing and campus access). Every arrow below is a live connection we demo.

```mermaid
flowchart LR
    S[Student / job seeker]
    R[Recruiter]
    U[University admin]
    M[Mentor / verifier]
    F[Founder]
    O[Operator]

    R -- posts listing, shares campus ID --> U
    U -- imports roster, authorizes drive --> S
    S -- applies through drive --> R
    R -- shortlist / offer --> S
    R -- decision appears in --> U
    S -- skill gap: request + escrow payment --> M
    M -- accepts, completes session --> S
    S -- requests verification --> X{System assigns<br/>conflict-free mentor}
    X --> M
    M -- Mentor-verified badge --> S
    F -- venture teaser --> S
    S -- NDA request --> F
    S -- reports scam listing --> O
    O -- removes listing, settles payouts --> R
    O -- refunds disputed session --> S
    O -- approves recruiter / university / mentor applications --> R
```

| Layer | What it is |
|---|---|
| Frontend | React app, deployed at https://sprintbridge-frontend.onrender.com (locally `http://127.0.0.1:5173`); works on phones |
| Backend | Python FastAPI, deployed at https://sprintbridge-api.onrender.com/api (locally `http://127.0.0.1:8000/api`); verifies every login token (ES256 signature) |
| AI engine | Groq (`gpt-oss-120b`, fallback `gpt-oss-20b`) extracts skills and job requirements with verbatim quotes; Python computes every score |
| Database | Supabase PostgreSQL with row-level security on every table, plus database functions for every multi-step action, so rules hold even if someone calls the database directly |
| Auth | Supabase Auth with email confirmation |

---

## 2. Before the demo

1. **Wake the deployed backend** a minute before you start: open https://sprintbridge-api.onrender.com/api/health. Render's free plan sleeps after 15 idle minutes and the first request then takes 30–50 seconds.
2. **Use the live app** at https://sprintbridge-frontend.onrender.com. To run locally instead: `cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000` and `cd frontend && npm run dev`, then open `http://127.0.0.1:5173`.
3. **Reset to a clean state** (deletes all activity, keeps demo accounts, re-seeds sample data):
   `uv run --with 'psycopg[binary]' python database/reset_demo.py --yes`
4. **Use separate browser profiles** (or one normal + one private window) per role, so two people stay logged in at once. Sign out between roles otherwise.
5. **For live sign-ups (Flow A), configure email first** — see the note in Flow A. Without it, Supabase allows only ~2 emails per hour.
6. **Upload text PDFs in the demo.** Scanned (image-only) resumes are read with OCR, which works locally, but OCR needs more memory than Render's free 512 MB instance has, so a scanned upload fails there.
7. Resume and job-description analysis runs on Groq (`GROQ_API_KEY` in `backend/.env`). Groq's free limits are tight (about 30 requests and 8,000 tokens per minute per model), so space out analyses during the demo; the same resume or job description pasted twice is served from cache instantly. If the limit is hit the page says how many seconds to wait.

---

## 3. Accounts

Password for every demo account: shared privately with the team.

| Account | Role | Starting state |
|---|---|---|
| `student@demo.test` | Asha Rao — student, Demo University A | CSE 2027, CGPA 8.10, skills python + sql — **eligible** for the campus drive |
| `student2@demo.test` | Vikram Shah — student, Demo University A | CSE 2027, CGPA 7.50, skills java + sql — **not eligible** (no Python) |
| `recruiter@demo.test` | Ravi Menon — Acme Analytics | Recruiter Growth plan (unlimited listings) |
| `recruiter2@demo.test` | Lena Park — Globex Labs | Recruiter Starter plan; cannot see Acme's data |
| `admin.a@demo.test` | Dr. Kavya Nair — Demo University A | University Campus plan, 4 roster students, 1 drive |
| `admin.b@demo.test` | Prof. Imran Qureshi — Demo University B | Cannot see University A's data |
| `mentor@demo.test` | Arjun Mehta — Data engineering | ₹500/session; verified expert in python L3, sql L3, docker L2 |
| `mentor2@demo.test` | Sara Thomas — Frontend | Free; expert in react L3, typescript L3 |
| `mentor3@demo.test` | Neha Kulkarni — Backend & data | ₹800/session; expert in python L4, sql L3, java L3 |
| `founder@demo.test` | Kabir Malhotra — entrepreneur | Ventures: CampusEats (equity), SkillSwap |
| `operator@demo.test` | Priya — platform operator | Moderation, payouts, role approvals, audit log |
| `newrecruiter@demo.test` | Meera Iyer — signed up as "Recruiter / company" | No role yet after a reset: use her to show onboarding (Flow A2) |
| `newstudent@demo.test` | Rohan Das — signed up as "Student" | Not on any roster after a reset: University A imports him live (Flow A2) |

---

## 4. How each user gets their role

Everyone signs up the same way. What differs is who has to vouch for them.

| User | How they get access | Who approves | What opens up |
|---|---|---|---|
| **Job seeker** | Sign up | Nobody (default) | Public listings, job fit, mentors, ventures; Job Seeker pricing |
| **Student** | Sign up with the same email the university has on its roster | The **university**, by importing its roster; the account links automatically once the email is confirmed | Campus drives of their university; Student pricing |
| **Founder** | Sign up and post a venture | Nobody | Ventures, collaborator requests under NDA |
| **Recruiter** | Sign up, choose "Recruiter / company", then **apply** on *Roles & access* with the company name | A platform **operator** checks the person really works there | Recruiter workspace for that company; joining an existing company is flagged for extra care |
| **University admin** | Same, choosing "University placement office" | **Operator** | University workspace: roster, drives, placement report |
| **Mentor** | Same, choosing "Mentor", with area of expertise | **Operator** | Mentor profile, inbox, earnings. Being a *verifier* also needs calibrated expertise, which the platform records separately |
| **Operator** | Granted by the platform owner only | Platform owner | Operator console |

```mermaid
flowchart LR
    V[Visitor] --> SU[Sign up · choose 'joining as'] --> C[Confirm email] --> JS[Job seeker access]
    JS -->|university imports this email| ST[Student: campus drives]
    JS -->|posts a venture| FO[Founder]
    JS -->|applies on Roles & access| AP[Application: pending]
    AP -->|operator approves| RO[Recruiter / University admin / Mentor workspace]
    AP -->|operator rejects, with reason| JS
```

Nobody can give themselves a role: the database only creates memberships and mentor grants inside the operator's approval function, and every approval is written to the audit log.

---

## Flow A — Create an account and sign in

**Who:** a new visitor. **Shows:** self-service onboarding with email confirmation.

| # | Where | Action | What the system does |
|---|---|---|---|
| 1 | `/login` | Click **Create account** | The URL becomes `/login?mode=signup`, so it can be shared. |
| 2 | Sign-up form | Enter name, choose **I'm joining as** (Student, Job seeker, Founder, Recruiter / company, University placement office, Mentor), a real email, password twice | Each choice explains what happens next. Checks the passwords match and are ≥ 8 characters. |
| 3 | Submit | **Create account** | Supabase creates the account (unconfirmed) and emails a confirmation link. A database trigger immediately creates the user's empty profile with their name. Screen: **"Check your inbox."** with **Resend link**. |
| 4 | Sign in before confirming | Enter email + password | Blocked: **"Your email isn't confirmed yet. Resend the confirmation link."** |
| 5 | Email | Open the confirmation link | Account is confirmed. |
| 6 | `/login` | Sign in | Lands on **Overview — "Hello, ‹name›."** with the *Your path* card (0 skills, 0 applications). |
| 7 | Menu | — | A new user sees the student/job-seeker menu. Someone who chose Recruiter, University or Mentor sees a prompt: **"Finish your recruiter application"** (Flow A2). Workspaces appear only after approval. |
| 8 | `/profile` | Add specialization and skills, save | Skills are cleaned up (lowercase, de-duplicated) and labelled **Self-declared**. |
| 9 | `/billing` | — | Not on a university roster → **Job Seeker** plans (₹299 Pro). Roster-linked users get **Student** pricing (₹149 Pro). |

**Error messages users see:** wrong password → "That email and password don't match"; existing email → "An account with this email already exists. Sign in instead"; invalid address → "Use a real email address you can open"; email limit → "We've sent too many emails in the last hour".

**Result (live):** a new account was created, blocked before confirmation, confirmed, signed in to its own dashboard, saved a profile, and was correctly placed on job-seeker pricing.

> **Before round 2:** Supabase's built-in email sender allows about 2 emails per hour. That limit is what stopped our second live sign-up test ("We've sent too many emails…"). In Supabase → **Authentication → Emails → SMTP Settings**, connect a provider (e.g. Resend, Brevo or Gmail SMTP) and raise the rate limit. Also set **Authentication → URL Configuration → Site URL** to the address the app runs on (e.g. `http://127.0.0.1:5173`), so confirmation links open the app.

---

## Flow A2 — Become a recruiter, university or mentor

**Who:** a new recruiter, the operator; a university and a new student. **Shows:** open sign-up without letting anyone pose as a company or college.

| # | Role | Where | Action | What the system does |
|---|---|---|---|---|
| 1 | New recruiter (Meera) | `/dashboard` | — | Notice: **"You signed up as a recruiter. Finish your recruiter application…"** |
| 2 | Meera | `/join` (**Roles & access**) | Choose **Recruiter**, company **Initech Labs**, title, website → **Send application** | Application saved as **Under review**. No workspace yet. One open application per role; applying for a role you already have is refused. |
| 3 | Operator (Priya) | `/operator` → **Role applications** | Review name, email, company, website → **Approve** (or **Reject** with a reason) | One database transaction: creates the company if it's new (or flags **"Approving adds them to the existing organization …"**), adds the recruiter membership, records who approved, writes the audit log. |
| 4 | Meera | Menu | — | **Recruiter workspace** appears; `/join` shows **"You have this role"** and the application as **Approved**. She can post listings for Initech Labs only. |
| 5 | University (Dr. Nair) | `/university` → **Roster** | Import a CSV row with `newstudent@demo.test` | Saved as **University-claimed**. |
| 6 | New student (Rohan) | Sign in | — | His confirmed email matches the roster row, so his account is **linked automatically**: **Student** pricing, and University A's campus listings appear in **Opportunities**. Only a confirmed email can claim a row, and a claimed row is never re-assigned. |

Universities and mentors follow steps 1–4 the same way (a mentor gives an area of expertise instead of a company).

**Result (live):** Meera applied → Priya approved → Initech Labs was created with Meera as recruiter and her Recruiter workspace opened. University A imported Rohan → on sign-in he had Student pricing and saw the campus ML Engineering Intern listing.

---

## Flow B — Campus placement, end to end (the core connectivity story)

**Who:** recruiter → university → two students → recruiter → student → university. **Shows:** every party connected, with each one seeing only what they're allowed to.

| # | Role | Where | Action | What the system does |
|---|---|---|---|---|
| 1 | Recruiter (Ravi) | `/recruiter` → **Create opportunity** | Title, description, **Visibility: Campus**, required skills, deadline, stipend | Listing is saved for Acme only (the company plan's listing limit is checked). Campus listings are **invisible to students** until a university authorizes a drive. |
| 2 | Recruiter | **Your listings** | Click **Copy ID** under the campus listing | Gives the ID to share with a university (the company↔university link). |
| 3 | University (Dr. Nair) | `/university` → **Roster** | Upload CSV → **Preview** | Every row is validated; problems are listed by row and field (e.g. "CGPA must be between 0 and 10", "Duplicate student_id"). **Import is disabled while any row is invalid.** |
| 4 | University | Roster | **Import roster** | All rows or none are saved ("Imported: 2 added, 0 updated, 0 unchanged"). Re-importing updates instead of duplicating. Records are labelled **University-claimed**, never "verified". |
| 5 | University | **Campus drives** | Paste the ID, branches (CSE), batch 2027, min CGPA, mandatory skill (python), deadline → **Authorize drive** | Drive rules are frozen once published. The listing is now visible to this university's roster students only. |
| 6 | Student (Asha) | `/opportunities` → the listing | Choose **Application route: Demo University A · 2027** | Eligibility is checked against her university record and skills: **"Eligible for this drive"**. Skill coverage (e.g. 67%, 2 of 3 skills) is shown separately: coverage never overrides eligibility. |
| 7 | Student | Same page | **Apply for this opportunity** | One database transaction re-checks everything (deadline, drive, eligibility), saves a snapshot of her profile and eligibility, and blocks duplicates → **"Application received."** |
| 8 | Student (Vikram) | Same listing | Choose the drive | **"Not eligible — Python is required."** Apply is disabled. The missing skills show **Find a mentor** links (into Flow C). |
| 9 | Recruiter | `/recruiter` → **Applicants** | **Shortlist**, then **Mark offered** | Only the hiring company can change status, and only forwards (applied → shortlisted → offered/rejected). Every change is written to the audit log. |
| 10 | Student (Asha) | `/applications` | — | Tracker shows **Offered**, via **Campus drive**. |
| 11 | University | **Campus applicants** | — | Shows Asha · Data Engineering Intern · **Offered**. Only applications made through *this university's drives* appear. |
| 12 | University | **Overview** | **Export CSV** | KPIs: campus applications, shortlisted, offers, students with offers. CSV downloads with spreadsheet-formula protection. An offer is not counted as a placement. |

**Result (live):** listing created → 2 students imported → drive authorized → Asha eligible and applied → Vikram blocked with the reason → shortlisted → offered → Asha's tracker showed Offered → university saw it in applicants, KPIs (1 application, 1 offer, 1 student with an offer) and the CSV row.

**Isolation to point out:** Globex's recruiter cannot see Acme's applicants; University B cannot see University A's roster, drives or report; students never see other students' applications.

---

## Flow C — Skill gap → mentor → paid session

**Who:** student, mentor. **Shows:** gap analysis feeds mentor matching; escrow payments.

| # | Role | Where | Action | What the system does |
|---|---|---|---|---|
| 1 | Student | Listing → **Room to grow** | **Find a mentor** next to a missing skill | Opens `/mentors?skill=python`. |
| 2 | Student | `/mentors` | — | Mentors with **calibrated expertise** in that skill come first (**Verified expert** badge, levels like *python · L3*), then mentors who only self-declare it. **Price never changes the order.** |
| 3 | Student | Arjun's card | **Request mentorship** → note → **Continue · ₹500** | Paid mentor → a clearly labelled **Test mode** payment step ("no card is charged"). |
| 4 | Student | Same | **Confirm test payment & send** | One transaction: monthly quota check (free plan: 2 requests/month) + test payment + request. "₹500 is held in escrow and refunded if they decline." |
| 5 | Mentor (Arjun) | `/mentor-requests` → **Mentor inbox** | **Accept** | Only this mentor can decide. |
| 6 | Mentor | Same | **Mark session completed** | Payout created: **₹500 gross − ₹100 commission (20%) = ₹400**, **held 7 days** for disputes. (Mentor Pro: 10% commission.) |
| 7 | Mentor | `/billing` → **Earnings** | — | "Mentor session ₹500 ₹100 ₹400 — Held until ‹date›". |
| 8 | Mentor | `/billing` → **Your session price** | Change price | Takes effect for new requests. |

**If the mentor declines** → the payment is refunded automatically; both sides see **Refunded** (verified live: Vikram's ₹800 to Neha).
**If the student disputes** a completed session → see Flow F.

**Result (live):** Arjun and Neha ranked as verified Python experts with prices → ₹500 escrow → accepted → completed → ₹400 held in earnings.

---

## Flow D — Independent skill verification

**Who:** student, a system-chosen mentor, optionally a second mentor. **Shows:** the anti-fraud design. Students can't pick friends, and verifiers are paid the same for pass or fail.

| # | Role | Where | Action | What the system does |
|---|---|---|---|---|
| 1 | Student (Asha) | `/skills` → **Get mentor-verified** | Skill *python*, level *2 · Working* → **Request verification** | Before charging, the system checks a conflict-free verifier exists. If none: "No independent verifier is available… You have not been charged." |
| 2 | Student | Same | **Confirm test payment** (₹499 student / ₹999 job seeker) | The system **randomly assigns** a verifier who: has calibrated expertise ≥ the level; has a quality score ≥ 60%; **shares no organization** with her (college or employer); has **never had contact** with her (mentor requests, ventures); has never verified her; is not in a reciprocal pair with her; and hasn't hit the per-college monthly cap. |
| 3 | Student | Status table | — | "Verifier assigned — **Revealed when the session starts**." She cannot find or pressure the verifier in advance. |
| 4 | Verifier (Neha) | `/verify` (**Verifier desk**) | **Start session** | Her name now appears to the student. |
| 5 | Verifier | Same | Outcome **Pass**, level **2**, notes → **Record result** | She cannot certify above her own level. Her 60% share (₹299) is **held**. In 20% of cases a **blind second review** is sent to another independent mentor, who doesn't see the first result. |
| 6 | Student | `/skills` | — | Python shows **Mentor-verified · Level 2 · Verified until ‹+18 months›** with the verifier's notes. Fit scores now treat it as the strongest evidence. |

**Rules also in force (tested in the database):** a fail starts a **30-day cooldown**, and a retry always gets a **different** verifier. If a second reviewer disagrees, the badge goes **Under review**, the verifier's payout is **clawed back**, and their quality score drops.

**Result (live):** Asha had just had a session with Arjun, so the system assigned **Neha, not Arjun** (conflict rule). Neha was revealed at session start, passed Asha at L2, and Asha's Python became **Mentor-verified until Apr 2028**.

---

## Flow E — Venture Launchpad (entrepreneurs)

**Who:** founder, student. **Shows:** protecting founders' ideas while letting talent join.

| # | Role | Where | Action | What the system does |
|---|---|---|---|---|
| 1 | Founder (Kabir) | `/ventures` → **Post a venture** | Name, **public teaser**, **private full plan**, industry, stage, compensation type (paid / stipend / equity / unpaid / to discuss), skills needed | Founder Free allows 1 venture, Founder Pro 3 (posting beyond the limit shows "Founder Free includes 1 venture(s). Upgrade to post more."). |
| 2 | Student | `/ventures` | Browse, filter by a skill they can bring | Cards show stage, compensation and teaser. **The private plan is never sent to non-members** (the database blocks that column). |
| 3 | Student | Venture page | Write what they'd bring, tick **"I'll keep the founder's plan confidential"**, send | The request requires NDA acceptance (enforced in the database too). |
| 4 | Founder | Venture page → **Requests to join** | **Accept** | "‹name› joined." Collaborator count increases. |
| 5 | Student | Venture page | — | **The full plan is now visible.** Status: Accepted. |

**Result (live):** the founder saw the private plan; the student saw only the teaser; NDA request sent; founder accepted; the student then saw the full plan; a third venture was blocked by the free plan.

---

## Flow F — Plans, quotas and payments (test mode)

**Who:** everyone. **Shows:** a sustainable business model that never sells trust.

| # | Role | Where | What to show |
|---|---|---|---|
| 1 | Any user | `/billing` | **This month's usage** meters (job-fit reports, mentor requests, resume analyses) against plan limits; counted only when an action succeeds. |
| 2 | Student | `/billing` → **Upgrade to Student Pro** | Test-mode step: "This plan costs ₹149. Confirming records a simulated payment — no card is charged." → **Confirm test payment** → "You're now on Student Pro", limits become **∞**. |
| 3 | Recruiter / University | `/billing` | Organization plans: listing limits (Recruiter Free 1 / Starter 5 / Growth unlimited), university Campus plan priced per enrolled student per year. |
| 4 | Mentor | `/billing` | Mentor plans (commission 20% → 10%), session price, earnings with hold dates. |
| 5 | **Decline → refund** | Mentor declines a paid request | Payment flips to **Refunded** automatically, for both sides. |
| 6 | **Dispute → operator → refund** | Student: `/mentor-requests` → completed paid session → **Report a problem** → **Open dispute** | Session becomes **Disputed**; the held payout is frozen. |
| 7 | Operator | `/operator` → **Payouts to settle** | The disputed payout appears → **Refund** (or **Release**). The student's payment shows **Refunded**. **Release all due** pays out holds past their 7-day window. |

**Principles to say out loud:** paid plans never change search ranking or verification outcomes; verification costs the same whether you pass or fail; employers can never charge candidates.

**Result (live):** Student Free → Pro upgrade; Vikram's ₹800 refunded on decline; Asha's disputed ₹500 session refunded by the operator; all payments listed in each user's billing.

---

## Flow G — Trust & safety

**Who:** recruiter (bad actor), three students, operator. **Shows:** the platform protects candidates from scams automatically.

| # | Role | Where | Action | What the system does |
|---|---|---|---|---|
| 1 | Recruiter | `/recruiter` → Create | Description: "Pay a registration fee of Rs 1500… Contact WhatsApp only." | Scam-phrase detection flags it: *asks candidates to pay a fee*, *moves contact off-platform*. |
| 2 | Student | Listing page | — | Amber warning: **"Be careful with this listing… Genuine employers never charge candidates."** |
| 3 | 3 different users | Listing → **Report** → reason *Asks for money / scam* | Each user can report once. After **3 distinct reports** the listing is **hidden automatically** pending review; students now get "not found" and can't apply. The company still sees it. |
| 4 | Operator (Priya) | `/operator` | Report card: 3 reports, flags, "Hidden pending review" → **Remove listing** | Listing taken down. **Automatically flagged listings** and **Payouts to settle** are in the same console. |
| 5 | Operator | **Audit log** | — | Every sensitive action with who and when: payments, refunds, verification requests/sessions/results, reports, auto-hide, moderation, application status changes, drive authorizations. |

**Result (live):** warning shown → 3 reports → auto-hidden → operator removed it → audit log showed the full trail with real names.

---

## Flow H — Resume → skills → job fit → recommendations

**Who:** a student. **Shows:** the AI engine extracts evidence; the score is deterministic and explainable.

| # | Where | Action | What the system does |
|---|---|---|---|
| 1 | `/skills` | Upload a PDF resume | The server reads the PDF's text (or OCRs a scanned one). Groq extracts each skill with an **exact quote** from the resume; quotes not found in the resume are dropped. A deterministic pass also finds every known skill named in the resume and its section (Experience, Projects…) and dates, so results don't vary between runs. |
| 2 | Same | — | Skills grouped by category (Languages, Frameworks, Databases, Cloud & DevOps…), each with a level 1–3, an evidence score out of 100, and **"Why this assessment?"** listing the quotes. Labelled **System-assessed**; only a mentor can certify level 4. |
| 3 | Same → **Opportunities that fit your resume** | — | Open listings ranked by fit (e.g. Backend Developer Intern 80%, 3 of 3 required skills), with **You have** / **To build** skills and a link to apply. |
| 4 | `/job-fit` | Paste any job description | Groq extracts required and preferred skills (with quotes) and any **scam red flags**; the fit report splits skills into **Your strengths**, **More evidence needed** and **Skills to build** (each linked to mentors). A JD pasted twice is served from cache. |

**Result (live):** Vikram's two-column resume → 18 skills in 6 categories (e.g. java L3, spring boot L2, postgresql L2) → Backend Developer Intern and Data Engineering Intern at 80% fit → Data Engineer JD 57% fit, missing airflow, dbt, spark. The same resume as a scanned image gave the same 18 skills (run locally).

---

## 14. Flow diagrams per user type (for slides)

One diagram per kind of user, showing their journey through the product. Rendered PNGs are in `docs/diagrams/`.

Each diagram reads top to bottom in stages; inside a stage, left to right.

### Student
```mermaid
flowchart TB
    subgraph S1["1 · Get started"]
        direction LR
        A[Sign up as Student] --> B[University imports roster] --> C[Account links<br/>by confirmed email]
    end
    subgraph S2["2 · Know your skills"]
        direction LR
        D[Upload resume] --> E[Skills with quotes,<br/>levels, categories] --> F[Openings ranked<br/>by fit]
    end
    subgraph S3["3 · Apply"]
        direction LR
        G[Campus drive:<br/>eligibility check] -->|eligible| H[Apply in one<br/>transaction] --> I[Track: applied →<br/>shortlisted → offered]
    end
    subgraph S4["4 · Grow"]
        direction LR
        J[Missing skill:<br/>find a mentor] --> K[Paid session<br/>in escrow] --> L[Independent<br/>verification] --> M[Mentor-verified<br/>badge]
    end
    S1 --> S2 --> S3 --> S4
```

### Job seeker
```mermaid
flowchart TB
    subgraph S1["1 · Get started"]
        direction LR
        A[Sign up as Job seeker] --> B[Upload resume] --> C[Skills with evidence]
    end
    subgraph S2["2 · Check the fit"]
        direction LR
        D[Paste any job<br/>description] --> E[Fit report +<br/>scam warnings] --> F[Apply to public<br/>listings]
    end
    subgraph S3["3 · Close the gap"]
        direction LR
        G[Mentor for a<br/>missing skill] --> H[Verification] --> I[Mentor-verified<br/>badge raises fit]
    end
    S1 --> S2 --> S3
```

### Recruiter
```mermaid
flowchart TB
    subgraph S1["1 · Get verified"]
        direction LR
        A[Sign up as Recruiter] --> B[Apply with<br/>company name] --> C[Operator approves] --> D[Recruiter workspace]
    end
    subgraph S2["2 · Post"]
        direction LR
        E[Public listing] ~~~ F[Campus listing:<br/>share ID with university] --> G[University<br/>authorizes drive]
    end
    subgraph S3["3 · Hire"]
        direction LR
        H[Applicants with profile +<br/>eligibility snapshot] --> I[Shortlist] --> J[Offer / Reject<br/>audited]
    end
    S1 --> S2 --> S3
```

### University placement office
```mermaid
flowchart TB
    subgraph S1["1 · Get verified"]
        direction LR
        A[Sign up as University] --> B[Apply with<br/>college name] --> C[Operator approves]
    end
    subgraph S2["2 · Students"]
        direction LR
        D[Import roster CSV:<br/>preview, all-or-nothing] --> E[Students link<br/>by confirmed email]
    end
    subgraph S3["3 · Drives"]
        direction LR
        F[Authorize drive for a<br/>recruiter's campus listing] --> G[Only eligible roster<br/>students can apply]
    end
    subgraph S4["4 · Outcomes"]
        direction LR
        H[Campus applicants<br/>and decisions] --> I[Placement report<br/>+ safe CSV export]
    end
    S1 --> S2 --> S3 --> S4
```

### Mentor
```mermaid
flowchart TB
    subgraph S1["1 · Get verified"]
        direction LR
        A[Sign up as Mentor] --> B[Apply with<br/>area of expertise] --> C[Operator approves]
    end
    subgraph S2["2 · Mentor"]
        direction LR
        D[Listed in directory:<br/>price never affects rank] --> E[Request arrives:<br/>payment in escrow]
        E -->|accept| F[Session done:<br/>payout held 7 days]
        E -->|decline| G[Student refunded]
    end
    subgraph S3["3 · Verify (calibrated mentors)"]
        direction LR
        H[Randomly assigned,<br/>conflict-free] --> I[Live session] --> J[Pass / fail:<br/>same fee]
    end
    S1 --> S2 --> S3
```

### Founder
```mermaid
flowchart TB
    subgraph S1["1 · Pitch"]
        direction LR
        A[Sign up as Founder] --> B[Post venture: public<br/>teaser + private plan]
    end
    subgraph S2["2 · Build the team"]
        direction LR
        C[Students request to join<br/>and accept NDA] --> D[Founder accepts] --> E[Collaborator sees<br/>the full plan]
    end
    S1 --> S2
```

### Operator
```mermaid
flowchart TB
    A[Operator console] --> B[Approve recruiter /<br/>university / mentor]
    A --> C[Scam reports and flags:<br/>auto-hidden after 3 reports]
    A --> D[Disputed payouts:<br/>refund or release]
    A --> E[Audit log of every<br/>sensitive action]
```

---

## 15. Security points to show

- **Roles can't be self-assigned.** Anyone can sign up, but recruiter, university and mentor access is granted only when an operator approves an application, inside one audited database function. Students are linked to a university only when their confirmed email is on that university's roster.
- **Every rule lives in the database**, not just the UI. In testing, direct database calls that bypass the app were refused for: granting yourself a role, posting for another company, inserting an application directly, editing CGPA, faking skill evidence, reading a founder's private plan, or reading the audit log.
- **Login tokens are verified on every request** (ES256 signature + expiry + issuer). A forged token gets `401`.
- **Organizations are isolated.** Companies and universities see only their own data.
- **Honest labels:** Self-declared → System-assessed → **Mentor-verified**; university data is "University-claimed".

---

## 16. Suggested 12-minute demo order

| Time | Flow | Accounts (separate browser profiles) |
|---|---|---|
| 0:00–1:00 | **A** — Create account (choose "joining as"), "check your inbox", sign in to a fresh dashboard | new email |
| 1:00–2:00 | **A2** — Meera applies as recruiter → operator approves → workspace opens | newrecruiter, operator |
| 2:00–5:00 | **B** — Recruiter campus listing → university drive → Asha eligible + applies → Vikram blocked → recruiter offers → tracker + university report | recruiter, admin.a, student, student2 |
| 5:00–6:00 | **H** — Upload a resume → skills by category → recommended openings → paste a JD → fit report | student2 |
| 6:00–7:30 | **C** — Vikram's gap → Find a mentor → verified experts first → paid request (test payment) → mentor accepts & completes → earnings held | student, mentor |
| 7:30–9:00 | **D** — Request verification → system assigns a conflict-free mentor → verifier desk → Mentor-verified badge | student, mentor3 |
| 9:00–10:00 | **E** — Founder's teaser → NDA request → accept → plan unlocked | student, founder |
| 10:00–11:30 | **G + F** — Scam listing warning → reports → auto-hidden → operator removes; dispute → operator refunds | recruiter2, students, operator |
| 11:30–12:00 | Security points + business model one-liner | — |

Reset before each rehearsal: `database/reset_demo.py --yes`.

---

## 17. What is real and what is simulated

| Real (working end to end) | Simulated / not built |
|---|---|
| Accounts, email confirmation, login, role applications and operator approval, roster linking, organization isolation | **Payments** use a clearly labelled *Test mode*; no card is charged. A real provider (e.g. Razorpay) can replace one database function later. |
| Listings, campus drives, eligibility, applications, decisions, reports, CSV | Live video for verification sessions: sessions happen outside the app; the result is recorded in it. |
| Mentor matching, escrow logic, commission, holds, refunds, disputes | ID / liveness checks (KYC) |
| Independent verification: conflict checks, random assignment, audits, expiry | DigiLocker / NAD academic record verification |
| Ventures with confidentiality | GitHub analysis, 48-hour proof plans, recruiter outreach drafts |
| Reports, scam flags, auto-hide, operator console, audit log | Scanned-resume OCR works locally but not on the free 512 MB server |
| Resume and job-description analysis on Groq (rate-limited; identical inputs cached), fit scores, recommendations | |
