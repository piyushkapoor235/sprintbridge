# SprintBridge

Campus-to-career platform: students and job seekers, recruiters, universities, mentors and founders.
Hackathon build: React frontend, Python FastAPI backend, Supabase (Auth + PostgreSQL).

| Read first | |
|---|---|
| [docs/architecture.md](docs/architecture.md) | System design, roles, data model, API rules |
| [docs/api-contract.md](docs/api-contract.md) | Frozen API contract: every endpoint, payload and error code |
| [plan.md](plan.md) / [todo.md](todo.md) | Sequential build steps S01–S20 |
| [docs/threat-model.md](docs/threat-model.md), [docs/skill-intelligence.md](docs/skill-intelligence.md), [docs/business-model.md](docs/business-model.md) | Abuse cases, skill engine, pricing |

## Layout

```text
backend/            FastAPI app (Python 3.13)
  app/main.py       app factory, request-id middleware, CORS, router registration
  app/auth.py       verified caller (Supabase Auth)
  app/db.py         request-scoped DB client; narrow service client for server-owned tables
  app/errors.py     single error shape
  app/pagination.py list envelope
  app/routers/      one module per domain (all 33 contract operations implemented)
  app/schemas/      Pydantic request/response models = the contract
  app/services/     access checks, coverage, fit, skill scoring, roster CSV, CSV export, Claude extraction
  tests/            unit tests, no network needed
  tests_live/       end-to-end journeys against the live Supabase project
database/
  migrations/       0001–0011 SQL: tables, constraints, RLS, column grants, transactional RPCs
  apply_migrations.py, seed.py
  tests/            schema + row-security tests on a throwaway local Postgres
  fixtures/         synthetic sample data (students.csv)
docs/               design documents and API contract
frontend/           added in step S06
```

## Backend: run and test

```bash
cd backend
uv venv .venv --python 3.13 && uv pip install --python .venv/bin/python -r requirements-dev.txt
cp .env.example .env          # fill in Supabase URL and publishable key
.venv/bin/uvicorn app.main:app --reload    # http://localhost:8000/docs
.venv/bin/python -m pytest -q              # unit tests (no network)
.venv/bin/python -m pytest tests_live -q   # live journeys; needs backend/.env and the seed; cleans up after itself
```

`ANTHROPIC_API_KEY` in `backend/.env` enables resume and job-description analysis. Without it those endpoints return 503 and everything else works.

**Deploy:** `render.yaml` is a Render Blueprint (Free plan). In Render: New → Blueprint → this repository, then enter the secrets in the dashboard. Set `ALLOWED_ORIGINS` to the deployed frontend URL.

## Database: apply and test

Settings come from `backend/.env` (see `backend/.env.example`). `DATABASE_URL` must be the **session pooler** URI: the direct `db.<ref>` host is IPv6-only. URL-encode special characters in the password (`@` → `%40`).

```bash
set -a; . backend/.env; set +a
uv run --with 'psycopg[binary]' python database/apply_migrations.py   # applies new migrations only
uv run --with 'psycopg[binary]' python database/seed.py               # demo users + sample data, safe to re-run
```

In Supabase Auth settings, keep **email confirmation** on.

Test the schema locally without Supabase (needs `uv`; `pgserver` bundles Postgres 16):

```bash
uv run --python 3.12 --with pgserver --with 'psycopg[binary]' --with pytest pytest database/tests -q
```

`database/tests/supabase_shim.sql` only imitates Supabase's `auth` schema and roles for these tests. Never apply it to a real project.

## Secrets

`.env` files are git-ignored. The Supabase secret key is backend-only and used solely for server-owned tables (`docs/api-contract.md` §5). It never goes in the frontend, Git, screenshots or pitch material.
