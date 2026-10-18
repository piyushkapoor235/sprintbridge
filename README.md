<div align="center">

<img src="docs/readme/intro.gif" alt="Animated introduction: the SprintBridge mark builds, then the stack appears by layer — interface, API, data, AI, delivery — beside the flow from a resume to evidence, fit and an opportunity." width="100%">

<h3>Careers built on evidence, not claims.</h3>

<p>Upload a resume, see every skill with the line that proves it, find where you fit, and close the gap with someone you can trust.</p>

<a href="https://sprintbridge-frontend.onrender.com"><img src="docs/readme/cta-explore.svg" alt="Explore SprintBridge → https://sprintbridge-frontend.onrender.com" height="52"></a>

<p><sub>Live hackathon build with sample data · Demo accounts shared on request · Payments run in labelled test mode</sub></p>

<img src="docs/readme/badges/react-19.svg" alt="React 19" height="28"> <img src="docs/readme/badges/typescript.svg" alt="TypeScript" height="28"> <img src="docs/readme/badges/vite-7.svg" alt="Vite 7" height="28"> <img src="docs/readme/badges/tailwind-4.svg" alt="Tailwind CSS 4" height="28"> <img src="docs/readme/badges/fastapi.svg" alt="FastAPI" height="28"><br>
<img src="docs/readme/badges/python-3-13.svg" alt="Python 3.13" height="28"> <img src="docs/readme/badges/pydantic-2.svg" alt="Pydantic v2" height="28"> <img src="docs/readme/badges/supabase.svg" alt="Supabase Auth" height="28"> <img src="docs/readme/badges/postgres-rls.svg" alt="PostgreSQL with row-level security" height="28"> <img src="docs/readme/badges/groq.svg" alt="Groq gpt-oss-120b" height="28"><br>
<img src="docs/readme/badges/rapidocr.svg" alt="RapidOCR" height="28"> <img src="docs/readme/badges/render.svg" alt="Render" height="28"> <img src="docs/readme/badges/playwright.svg" alt="Playwright" height="28"> <img src="docs/readme/badges/pytest.svg" alt="pytest, 178 tests" height="28">

<p><a href="#the-experience">Experience</a> · <a href="#the-product-as-a-skeleton">Skeleton</a> · <a href="#the-pipeline">Pipeline</a> · <a href="#behind-the-product">Pitch</a> · <a href="#engineering-map">Engineering</a> · <a href="#local-development">Development</a></p>

</div>

---

## The experience

SprintBridge puts students and job seekers, recruiters, universities, mentors, founders and operators on one platform. A resume becomes skills backed by exact quotes; fit against any opening is computed by a formula you can read; campus eligibility is enforced by the database; and the gap to a job leads to a mentor whose expertise, not price, decides their rank.

<img src="docs/readme/film-resume.gif" alt="Product film excerpt: a two-column resume is uploaded on the live site, analysed in seconds, skills appear grouped by category with levels, the evidence quotes open, and openings are ranked by fit." width="100%">

<a href="https://sprintbridge-frontend.onrender.com">
  <img src="docs/readme/screens/skills.jpg" alt="SprintBridge skill evidence page: skills grouped by category, each with a level, an evidence score and the resume quotes behind it" width="100%">
</a>

*Live-site screenshot. Click to open the app. Sample data illustrates the workflow.*

| Prove what you know | Find where you fit | Grow with people you can trust |
| :--- | :--- | :--- |
| Upload a text or scanned resume; every skill comes back with the line that proves it. | Openings are ranked by fit, showing what you have and what to build. Paste any job for a fit report with scam warnings. | A missing skill links to mentors ranked by verified expertise. Sessions are paid into escrow. |
| Labels stay honest: *Self-declared*, *System-assessed*, *Mentor-verified*. | Campus drives say exactly why you are or aren't eligible. | Independent, randomly assigned verifiers award badges that expire after 18 months. |

### Seven ways in

**Everyone signs up the same way** and chooses what they're joining as. What differs is who vouches for them:

| Who | Access | Approved by |
| :--- | :--- | :--- |
| Job seeker | Sign up | Nobody: the default |
| Student | Confirmed email on the university's roster | The university, by importing its roster; the account links automatically |
| Founder | Post a venture | Nobody |
| Recruiter · University admin · Mentor | Apply on **Roles & access** | A platform operator, in one audited step |
| Operator | Platform owner only | — |

Nobody can give themselves a role: the database creates memberships and mentor grants only inside the operator's approval function.

### Trust is part of the interface

- **Quotes, not keywords:** a skill is kept only if its quote is found in the resume text (case-, whitespace- and typography-insensitive). Invented quotes are dropped and counted.
- **Scores you can read:** the model only extracts; Python turns evidence into levels (evidence ≥ 75 → L3) and fit (required × 2, preferred × 1, scaled by confidence: mentor-verified 1.0, system-assessed 0.8, self-declared 0.3). Only a mentor can certify level 4.
- **Eligibility, explained:** branch, batch, CGPA, mandatory skills and deadline are one database check. A failed check shows the reason (*“Python is required.”*) and disables apply; fit never overrides it.
- **One transaction per application:** apply re-checks everything, blocks duplicates and stores a snapshot of the profile and eligibility the recruiter sees.
- **Money held fairly:** paid mentor sessions sit in escrow, are refunded on decline, and payouts are held 7 days for disputes. Verification costs the same whether you pass or fail.
- **Scams flagged early:** fee requests and “WhatsApp only” are detected in listings and pasted job descriptions; three reports from different users hide a listing until an operator reviews it.

---

## The product, as a skeleton

One loop through the student workspace, stripped to its structure.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme/product-skeleton-dark.svg">
  <img src="docs/readme/product-skeleton-light.svg" alt="Animated skeleton of the SprintBridge student loop: a resume is uploaded, skills appear with a quote, openings are ranked by fit, campus eligibility is explained for two students, and a mentor session leads to a verified badge." width="100%">
</picture>

| | Step | What the interface does |
| :---: | :--- | :--- |
| **1** | Upload a resume | A text PDF is read directly; a scanned one goes through OCR. Identical files are served from cache. |
| **2** | See the evidence | Skills are grouped by category, each with a level, a score out of 100 and *Why this assessment?* quotes. |
| **3** | Find where you fit | *Opportunities that fit your resume* ranks open listings, with *You have* / *To build*. |
| **4** | Check eligibility | A campus drive answers *Eligible* or names the missing rule before anyone applies. |
| **5** | Close the gap | The missing skill opens mentors with verified expertise; a passed verification upgrades the label. |

---

## The pipeline

Reading a resume and computing fit are separate paths. The stored evidence connects them.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme/pipeline-skeleton-dark.svg">
  <img src="docs/readme/pipeline-skeleton-light.svg" alt="Animated pipeline: a resume moves through upload, read, extract, verify, coverage and score into the skill_evidence table; a job description then meets that evidence in fit and explain, ending on a ranked opening with the exact resume line." width="100%">
</picture>

**Open any stage** to see what happens inside it.

<details>
<summary><b>01 · Upload</b> — validated intake with a content-hash cache</summary>
<br>
<img src="docs/readme/stages/01-upload.svg" alt="Upload stage" width="100%">

- **What happens:** the PDF (≤ 5 MB, checked by its magic bytes) is hashed; the same file with current evidence returns instantly, so re-uploads cost no quota or rate limit.
- **Carries forward:** owner, file hash, resume record.
- **Where to look:** `backend/app/routers/skills.py` (`upload_resume`)
</details>

<details>
<summary><b>02 · Read</b> — text layer first, OCR for scans</summary>
<br>
<img src="docs/readme/stages/02-read.svg" alt="Read stage" width="100%">

- **What happens:** pypdf's text layer is used when it has enough real words; otherwise pages are rendered and read by RapidOCR in a short-lived child process. Two-column layouts are read column by column by finding the gutter.
- **Carries forward:** resume text and `text_source` (`pdf` / `ocr` / `cached`).
- **Where to look:** `backend/app/services/documents.py`, `backend/app/services/ocr_worker.py`
</details>

<details>
<summary><b>03 · Extract</b> — structured skills with verbatim quotes</summary>
<br>
<img src="docs/readme/stages/03-extract.svg" alt="Extract stage" width="100%">

- **What happens:** Groq (`openai/gpt-oss-120b`, fallback `gpt-oss-20b`) returns strict JSON: skill, context (experience, project, education, certification, skills list), quote, years, last used. The resume is wrapped as untrusted data; embedded instructions are ignored. A local per-model budget respects Groq's rate limits.
- **Carries forward:** candidate skills with quotes.
- **Where to look:** `backend/app/services/llm.py`
</details>

<details>
<summary><b>04 · Verify</b> — no quote, no skill</summary>
<br>
<img src="docs/readme/stages/04-verify.svg" alt="Verify stage" width="100%">

- **What happens:** every quote must appear in the resume text after normalising case, whitespace, curly quotes, dashes and PDF ligatures; anything else is dropped and reported as `skills_rejected`. Aliases map spellings to one name (`Postgres` → `postgresql`).
- **Carries forward:** only evidence that exists in the document.
- **Where to look:** `backend/app/services/documents.py` (`squash`, `quote_in_source`), `backend/app/services/normalize.py`
</details>

<details>
<summary><b>05 · Coverage</b> — the same skills on every run</summary>
<br>
<img src="docs/readme/stages/05-coverage.svg" alt="Coverage stage" width="100%">

- **What happens:** a deterministic pass finds every known skill named in the resume, with the section it sits in (Experience, Projects, …) and the role's dates, and fills what the model skipped. Ambiguous words (“go”, “excel”) are left to the model; certifications count as the vendor skill.
- **Carries forward:** complete, dated evidence rows.
- **Where to look:** `backend/app/services/normalize.py` (`mentioned_skills`)
</details>

<details>
<summary><b>06 · Score</b> — evidence points to levels</summary>
<br>
<img src="docs/readme/stages/06-score.svg" alt="Score stage" width="100%">

- **What happens:** in-context mentions (20, then +10, up to 35), depth (experience 15 / project 10, +5 per year, up to 40) and recency (25 / 15 / 5) add up to a score; bands give levels 1–3. Mentor verification outranks everything.
- **Carries forward:** each skill's level, score, label and category.
- **Where to look:** `backend/app/services/skill_profile.py`
</details>

<details>
<summary><b>07 · Fit</b> — a formula, not a guess</summary>
<br>
<img src="docs/readme/stages/07-fit.svg" alt="Fit stage" width="100%">

- **What happens:** a listing's requirements (or a pasted job, extracted by Groq with red flags) are weighed: required × 2, preferred × 1, each × min(level / needed, 1) × confidence. Eligibility is reported separately and never overridden.
- **Carries forward:** fit %, required skills met, strengths, gaps.
- **Where to look:** `backend/app/services/fit.py`, `backend/app/routers/skills.py` (`/me/recommendations`, `/jds`)
</details>

<details>
<summary><b>08 · Explain</b> — quotes, gaps and the next step</summary>
<br>
<img src="docs/readme/stages/08-explain.svg" alt="Explain stage" width="100%">

- **What happens:** the interface shows *Why this assessment?* quotes, ranked openings with *You have* / *To build*, and a *Find a mentor* link for every gap.
- **Carries forward:** a decision the student can check and act on.
- **Where to look:** `frontend/src/pages/Skills.tsx`, `frontend/src/pages/JobFit.tsx`, `frontend/src/pages/Mentors.tsx`
</details>

<details>
<summary><b>Full system diagram</b> — every service and store, in one view</summary>
<br>

```mermaid
flowchart TD
    WEB["Browser · React static site on Render"] -->|login| AUTH["Supabase Auth · email confirmation"]
    WEB -->|JWT on every call| API["FastAPI on Render · ES256 token check"]
    API -->|caller's own token| DB[("Supabase Postgres · RLS on every table")]
    DB --- RPC["SQL functions · apply · drives · payments · verification · role approval"]
    API --> READ["Resume → text layer or OCR child process"]
    READ --> LLM["Groq gpt-oss · strict JSON · quotes"]
    LLM --> CHECK["Quote check · coverage pass"]
    CHECK --> EVID[("skill_evidence")]
    EVID --> SCORE["Python scoring · levels · fit"]
    SCORE --> WEB
    API --> AUDIT[("Audit log · operator console")]
```

</details>

Groq extracts; it never scores. The quote check and the deterministic coverage pass make results checkable and repeatable, but a resume can still overstate experience: that is why *System-assessed* is labelled as such, and only an independent mentor can make a skill *Mentor-verified*.

---

## Behind the product

Slides from the SprintBridge pitch deck. They explain the mechanisms with the demo's sample data; the pipeline above describes the implementation.

<table>
<tr>
<td width="33%"><img src="docs/readme/slides/06-engine.jpg" alt="The skill engine: the AI reads, Python scores. Four steps: read the PDF, extract with quotes, check every mention, score in Python." width="100%"></td>
<td width="33%"><img src="docs/readme/slides/04-roles.jpg" alt="Who gets which role: anyone can sign up, nobody can make themselves a recruiter." width="100%"></td>
<td width="33%"><img src="docs/readme/slides/11-security.jpg" alt="Security by design: every rule lives in the database. 178 tests, 55 API operations, 18 migrations." width="100%"></td>
</tr>
<tr><td align="center"><b>The AI reads, Python scores</b></td><td align="center"><b>Roles are approved, not claimed</b></td><td align="center"><b>Rules live in the database</b></td></tr>
</table>

<details>
<summary><b>See the full deck</b> — fourteen slides · <a href="docs/pitch/SprintBridge.pdf">PDF</a> · <a href="docs/pitch/SprintBridge.pptx">PowerPoint</a></summary>
<br>

| Why | | | |
| :---: | :---: | :---: | :---: |
| <img src="docs/readme/slides/01-cover.jpg" alt="SprintBridge: careers built on evidence, not claims." width="200"> | <img src="docs/readme/slides/02-problem.jpg" alt="Every step from campus to career runs on unverified claims." width="200"> | <img src="docs/readme/slides/03-solution.jpg" alt="One platform, seven users, every connection live." width="200"> | <img src="docs/readme/slides/04-roles.jpg" alt="Anyone can sign up. Nobody can make themselves a recruiter." width="200"> |

| How it works | | | |
| :---: | :---: | :---: | :---: |
| <img src="docs/readme/slides/05-student.jpg" alt="The student journey: from sign-up to a verified badge." width="200"> | <img src="docs/readme/slides/06-engine.jpg" alt="The AI reads. Python scores." width="200"> | <img src="docs/readme/slides/07-live.jpg" alt="Measured on the live app: 12 skills, 80% top fit, 53% fit to a pasted job." width="200"> | <img src="docs/readme/slides/08-campus.jpg" alt="Recruiter and university, connected by one drive." width="200"> |

| Trust and business | | | |
| :---: | :---: | :---: | :---: |
| <img src="docs/readme/slides/09-mentors.jpg" alt="A badge you can’t get from a friend." width="200"> | <img src="docs/readme/slides/10-safety.jpg" alt="Scams are flagged before a student applies." width="200"> | <img src="docs/readme/slides/11-security.jpg" alt="Every rule lives in the database, not the screen." width="200"> | <img src="docs/readme/slides/12-business.jpg" alt="Free to start, paid for scale. Trust is never for sale." width="200"> |

| Today and next | |
| :---: | :---: |
| <img src="docs/readme/slides/13-real.jpg" alt="What’s real, and what comes next." width="200"> | <img src="docs/readme/slides/14-demo.jpg" alt="See it run." width="200"> |

</details>

<details>
<summary><b>See campus eligibility and role onboarding in motion</b></summary>
<br>

<img src="docs/readme/film-eligibility.gif" alt="Live site: the same campus drive tells Vikram 'Python is required' with apply disabled, while Asha is eligible." width="100%">

<img src="docs/readme/film-onboarding.gif" alt="Live site: a new user applies as a mentor on Roles & access, the operator approves the application, and the Verifier desk appears in the new mentor's menu." width="100%">

</details>

<details>
<summary><b>See more of the live app</b></summary>

![Openings ranked by fit with matching and missing skills](docs/readme/screens/recommendations.jpg)

![Job-fit report for a pasted job description](docs/readme/screens/job-fit.jpg)

![Campus drive: not eligible, Python is required](docs/readme/screens/eligibility-blocked.jpg)

![Mentor directory ranked by verified expertise](docs/readme/screens/mentors.jpg)

![University workspace: authorised campus drives](docs/readme/screens/university.jpg)

![Operator console: role applications, reports, payouts and audit log](docs/readme/screens/operator.jpg)

![Venture with a public teaser and NDA request](docs/readme/screens/ventures.jpg)

![Sign-up with the joining-as choice](docs/readme/screens/signup.jpg)

</details>

---

## Engineering map

| Layer | Implementation |
| :--- | :--- |
| Interface | `frontend/` — React 19, TypeScript, Vite, Tailwind CSS 4; one page per screen, Supabase JS for sign-in only. |
| API and access | FastAPI with Pydantic models as the contract; Supabase JWTs verified locally (ES256 via JWKS) on every request; 55 operations in [`docs/api-contract.md`](docs/api-contract.md), checked by a test. |
| Data and rules | Supabase PostgreSQL: 18 migrations, row-level security on every table, column grants, and SQL functions for every multi-step action (apply, drives, payments, verification, role approval). |
| Skill engine | Groq extraction with strict JSON, quote verification, deterministic coverage pass, Python scoring and fit; RapidOCR for scanned resumes. |
| Trust and money | Escrowed test-mode payments, held payouts, disputes, conflict-free random verifier assignment, scam flags, reports and an audit log. |
| Delivery | Render Blueprint (`render.yaml`): API web service plus static site, auto-deployed from `main`. |
| Verification | 85 backend unit tests, 9 live journeys, 66 database security tests, 7 frontend unit tests, 11 Playwright journeys. |

<details>
<summary><b>Repository layout</b></summary>

```text
backend/
  app/main.py            App factory: request IDs, CORS, error handlers, routers
  app/auth.py            Token verification (local ES256, remote fallback)
  app/db.py              Request-scoped client with the caller's token; narrow service client
  app/routers/           me, opportunities, applications, university, drives, mentors, skills,
                         ventures, verification, billing, trust, onboarding
  app/schemas/           Pydantic models = the API contract
  app/services/          llm (Groq), documents + ocr_worker (PDF, OCR), normalize (aliases,
                         categories, mentions), skill_profile, fit, coverage, roster CSV, CSV export
  tests/  tests_live/    Unit tests (no network) and end-to-end journeys
database/
  migrations/            0001–0018: tables, RLS, grants, SQL functions
  seed.py  reset_demo.py Demo organisations, users and data; clean reset
  tests/                 Schema and row-security tests on a throwaway Postgres
frontend/
  src/pages/  src/lib/   Screens, API client and types
  tests/                 Vitest and Playwright
docs/                    Architecture, API contract, threat model, skill engine, business model,
                         showcase workflow, diagrams, pitch deck
render.yaml              Render Blueprint
```

</details>

### Boundaries that matter

The backend calls the database with the signed-in user's own token, so row-level security applies to every request: one company never sees another's applicants, and one university never sees another's roster. Direct database calls that skip the app are refused for granting a role, posting for another company, editing CGPA, faking skill evidence or reading a founder's private plan. Resumes and job descriptions are treated as untrusted input. These are implementation safeguards with tests, not a security certification.

The live build uses sample data and a labelled test mode for payments. OCR of scanned resumes works locally but needs more memory than the free 512 MB Render instance has; text PDFs work everywhere. The free instance sleeps after 15 idle minutes, so the first request can take about 30–50 seconds.

---

## Local development

You need Python 3.13 with [`uv`](https://docs.astral.sh/uv/), Node 24 and a Supabase project.

```bash
# Database: settings come from backend/.env (DATABASE_URL = Supabase session pooler URI)
cp backend/.env.example backend/.env
set -a; . backend/.env; set +a
uv run --with 'psycopg[binary]' python database/apply_migrations.py
uv run --with 'psycopg[binary]' python database/seed.py

# Backend: http://localhost:8000/docs
cd backend
uv venv .venv --python 3.13 && uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload

# Frontend: http://127.0.0.1:5173  (VITE_API_BASE_URL is the API origin, without /api)
cd frontend && npm ci && cp .env.example .env.local && npm run dev
```

Without `GROQ_API_KEY`, resume and job-description analysis return a clear 503 and everything else works. Keep **email confirmation** on in Supabase Auth and set the Site URL to where the frontend runs. Deploy with [`render.yaml`](render.yaml) (New → Blueprint), entering secrets in the dashboard. `database/reset_demo.py --yes` restores the demo data, including undoing role approvals.

<details>
<summary><b>Checks</b> — backend, database and frontend</summary>

```bash
# Backend — inside backend/
.venv/bin/python -m pytest -q              # 85 unit tests, no network
.venv/bin/python -m pytest tests_live -q   # 9 live journeys against Supabase; cleans up

# Database — from the repository root (pgserver bundles Postgres)
uv run --python 3.12 --with pgserver --with 'psycopg[binary]' --with pytest pytest database/tests -q   # 66

# Frontend — inside frontend/
npm test                 # 7 unit tests
npm run build            # type check + production build
npx playwright test      # 11 browser journeys
```

</details>

For deeper context: [showcase workflow](docs/showcase-workflow.md) (every flow, step by step), [architecture](docs/architecture.md), [skill engine](docs/skill-intelligence.md), [threat model](docs/threat-model.md), [business model](docs/business-model.md) and [API contract](docs/api-contract.md).

---

<div align="center">

<p><strong>Built by Daksh · Yatin Gogia · Daksh Kumar · Piyush Kapoor</strong></p>

Careers built on evidence, not claims.

<a href="https://sprintbridge-frontend.onrender.com"><img src="docs/readme/cta-explore.svg" alt="Open the live app → https://sprintbridge-frontend.onrender.com" height="52"></a>

<sub>© 2026 SprintBridge. Screenshots and animations show the live hackathon build with sample data.</sub>

</div>
