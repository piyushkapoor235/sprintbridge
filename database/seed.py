"""Seed the demo dataset. Safe to re-run: existing users and rows are reused, not duplicated.

Reads backend/.env (or the environment): SUPABASE_URL, SUPABASE_SECRET_KEY, DATABASE_URL, DEMO_PASSWORD.

    uv run --with 'psycopg[binary]' python database/seed.py

Everything here is synthetic "Sample data". Real people's data never goes in this file.
Users are created through the Supabase Auth admin API (pre-confirmed); the rest is inserted
as the database owner, which is why this script must never run in request handling.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import psycopg

ENV_FILE = Path(__file__).resolve().parents[1] / "backend" / ".env"

USERS = {
    "student@demo.test": "Asha Rao",
    "student2@demo.test": "Vikram Shah",
    "recruiter@demo.test": "Ravi Menon",
    "recruiter2@demo.test": "Lena Park",
    "admin.a@demo.test": "Dr. Kavya Nair",
    "admin.b@demo.test": "Prof. Imran Qureshi",
    "mentor@demo.test": "Arjun Mehta",
    "mentor2@demo.test": "Sara Thomas",
    "mentor3@demo.test": "Neha Kulkarni",
    "founder@demo.test": "Kabir Malhotra",
    "operator@demo.test": "Priya Operator",
}

ORGS = [
    ("Demo University A", "university"),
    ("Demo University B", "university"),
    ("Acme Analytics", "company"),
    ("Globex Labs", "company"),
]

MEMBERSHIPS = [
    ("recruiter@demo.test", "Acme Analytics", "recruiter"),
    ("recruiter2@demo.test", "Globex Labs", "recruiter"),
    ("admin.a@demo.test", "Demo University A", "admin"),
    ("admin.b@demo.test", "Demo University B", "admin"),
]

# (email, niche, summary, profile skills, session price INR or None for free, calibrated expertise {skill: level})
MENTORS = [
    ("mentor@demo.test", "Data engineering", "Sample data · 8 years building data pipelines.",
     ["python", "sql", "docker"], 500, {"python": 3, "sql": 3, "docker": 2}),
    ("mentor2@demo.test", "Frontend", "Sample data · 6 years of React and design systems.",
     ["react", "typescript"], None, {"react": 3, "typescript": 3}),
    ("mentor3@demo.test", "Backend & data", "Sample data · Staff engineer, 11 years in Python services.",
     ["python", "sql", "java"], 800, {"python": 4, "sql": 3, "java": 3}),
]

# Plans for organizations (subject, plan). Individuals start on free plans.
SUBSCRIPTIONS = [
    ("Acme Analytics", "recruiter_growth"),
    ("Globex Labs", "recruiter_starter"),
    ("Demo University A", "university_campus"),
]

# (founder email, title, teaser, private problem statement, industry, stage, needed skills, compensation)
VENTURES = [
    ("founder@demo.test", "CampusEats", "Cutting hostel food waste with pre-booked meals.",
     "Sample data · Hostels waste ~30% of cooked food. Students pre-book meals in an app; the mess cooks to demand. "
     "Pilot agreed with two hostels. Need a mobile engineer and a data person for demand forecasting.",
     "Food tech", "prototype", ["react", "python", "sql"], "equity"),
    ("founder@demo.test", "SkillSwap", "Peer-to-peer skill exchange for first-year students.",
     "Sample data · Students trade an hour of what they know for an hour of what they need, tracked with credits.",
     "Edtech", "idea", ["typescript", "figma"], "to_discuss"),
]

PROFILES = {
    "student@demo.test": ("Data engineering", "B.Tech CSE, 2027", ["python", "sql"]),
    "student2@demo.test": ("Backend", "B.Tech CSE, 2027", ["java", "sql"]),
}

# University-claimed roster rows (sample data). Student 1 and 2 are linked to accounts.
ROSTER = [
    ("Demo University A", "CSE27-001", "Asha Rao", "student@demo.test", "CSE", 2027, "8.10", True),
    ("Demo University A", "CSE27-002", "Vikram Shah", "student2@demo.test", "CSE", 2027, "7.50", True),
    ("Demo University A", "IT27-003", "Meera Iyer", "meera.iyer@uni-a.test", "IT", 2027, "7.49", False),
    ("Demo University A", "CSE27-006", "Rohan Das", "rohan.das@uni-a.test", "CSE", 2027, None, False),
]

# Sample listings so every screen has real rows to show. Matched by (company, title) on re-run.
# (company, recruiter, title, type, visibility, skills, monthly stipend INR or None, days to deadline, description)
OPPORTUNITIES = [
    ("Acme Analytics", "recruiter@demo.test", "Data Engineering Intern", "internship", "campus",
     ["python", "sql", "docker"], 30000, 21,
     "Sample data · Build and monitor the ETL pipelines behind Acme's campus analytics product. "
     "You will write Python jobs, model data in PostgreSQL and ship with Docker."),
    ("Acme Analytics", "recruiter@demo.test", "Junior Analytics Engineer", "job", "public",
     ["sql", "python", "dbt"], 75000, 30,
     "Sample data · Own reporting models end to end: SQL transformations in dbt, data quality checks "
     "and dashboards used by 40+ partner colleges."),
    ("Acme Analytics", "recruiter@demo.test", "Product Design Intern", "internship", "public",
     ["figma", "user research"], 25000, 14,
     "Sample data · Work with the design lead on onboarding flows for students and recruiters."),
    ("Globex Labs", "recruiter2@demo.test", "Frontend Developer", "job", "public",
     ["react", "typescript", "css"], 90000, 25,
     "Sample data · Build fast, accessible React interfaces for Globex's developer platform."),
    ("Globex Labs", "recruiter2@demo.test", "Backend Developer Intern", "internship", "public",
     ["java", "sql", "rest apis"], 28000, 18,
     "Sample data · Ship REST services in Java and SQL alongside a senior engineer."),
]

# (university, company, opportunity title, branches, batch, min CGPA, required skills, days to deadline)
DRIVES = [
    ("Demo University A", "Acme Analytics", "Data Engineering Intern", ["cse", "it"], 2027, "7.50", ["python"], 14),
]


def load_env() -> None:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip())


def ensure_user(url: str, key: str, email: str, name: str, password: str) -> None:
    body = json.dumps(
        {"email": email, "password": password, "email_confirm": True, "user_metadata": {"name": name}}
    ).encode()
    request = urllib.request.Request(
        f"{url}/auth/v1/admin/users",
        data=body,
        method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20):
            print(f"user   created {email}")
    except urllib.error.HTTPError as exc:
        if exc.code == 422:  # already registered
            print(f"user   exists  {email}")
        else:
            raise


def seed_rows(conn: psycopg.Connection) -> None:
    user_id = dict(conn.execute("select email, id from auth.users where email like '%%@demo.test'").fetchall())

    org_id = {}
    for name, kind in ORGS:
        row = conn.execute("select id from public.organizations where name = %s", (name,)).fetchone()
        if row is None:
            row = conn.execute(
                "insert into public.organizations (name, type) values (%s, %s) returning id", (name, kind)
            ).fetchone()
        org_id[name] = row[0]

    for email, org, role in MEMBERSHIPS:
        conn.execute(
            """insert into public.memberships (user_id, organization_id, role) values (%s, %s, %s)
               on conflict (user_id, organization_id, role) do nothing""",
            (user_id[email], org_id[org], role),
        )

    for email, (specialization, education, skills) in PROFILES.items():
        conn.execute(
            """update public.profiles set specialization = %s, education_summary = %s, skills = %s
               where user_id = %s""",
            (specialization, education, skills, user_id[email]),
        )

    for email, niche, summary, skills, price, expertise in MENTORS:
        conn.execute(
            "insert into public.role_grants (user_id, role) values (%s, 'mentor') on conflict do nothing",
            (user_id[email],),
        )
        mentor_id = conn.execute(
            """insert into public.mentors (user_id, niche, experience_summary, session_price_inr) values (%s, %s, %s, %s)
               on conflict (user_id) do update set niche = excluded.niche,
                 experience_summary = excluded.experience_summary, session_price_inr = excluded.session_price_inr
               returning id""",
            (user_id[email], niche, summary, price),
        ).fetchone()[0]
        for skill, level in expertise.items():
            conn.execute(
                """insert into public.mentor_expertise (mentor_id, skill, level) values (%s, %s, %s)
                   on conflict (mentor_id, skill) do update set level = excluded.level""",
                (mentor_id, skill, level),
            )
        conn.execute("update public.profiles set skills = %s where user_id = %s", (skills, user_id[email]))

    conn.execute(
        "insert into public.role_grants (user_id, role) values (%s, 'operator') on conflict do nothing",
        (user_id["operator@demo.test"],),
    )
    for org, plan in SUBSCRIPTIONS:
        conn.execute(
            """insert into public.subscriptions (organization_id, audience, plan_code, renews_at)
               select %s, audience, code, now() + interval '1 year' from public.plans where code = %s
               on conflict (organization_id, audience) where organization_id is not null
               do update set plan_code = excluded.plan_code, status = 'active'""",
            (org_id[org], plan),
        )
    for email, title, teaser, problem, industry, stage, skills, pay in VENTURES:
        if not conn.execute("select 1 from public.ventures where founder_id = %s and title = %s",
                            (user_id[email], title)).fetchone():
            conn.execute(
                """insert into public.ventures (founder_id, title, teaser, problem, industry, stage, needed_skills, compensation_type)
                   values (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_id[email], title, teaser, problem, industry, stage, skills, pay),
            )

    for uni, student_id, name, email, branch, batch, cgpa, linked in ROSTER:
        conn.execute(
            """insert into public.student_roster
                 (university_id, student_id, name, email, verified_user_id, branch, batch, cgpa)
               values (%s, %s, %s, %s, %s, %s, %s, %s)
               on conflict (university_id, student_id) do update set
                 name = excluded.name, email = excluded.email, branch = excluded.branch,
                 batch = excluded.batch, cgpa = excluded.cgpa""",
            (org_id[uni], student_id, name, email, user_id[email] if linked else None, branch, batch, cgpa),
        )
    opportunity_id = {}
    for company, recruiter, title, kind, visibility, skills, stipend, days, description in OPPORTUNITIES:
        row = conn.execute(
            "select id from public.opportunities where company_id = %s and title = %s", (org_id[company], title)
        ).fetchone()
        if row is None:
            row = conn.execute(
                """insert into public.opportunities
                     (company_id, title, description, type, visibility, required_skills,
                      compensation_amount, currency, pay_period, deadline, created_by)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, now() + make_interval(days => %s), %s)
                   returning id""",
                (org_id[company], title, description, kind, visibility, skills, stipend,
                 "INR" if stipend else None, "month" if stipend else None, days, user_id[recruiter]),
            ).fetchone()
        opportunity_id[(company, title)] = row[0]

    for uni, company, title, branches, batch, min_cgpa, skills, days in DRIVES:
        conn.execute(
            """insert into public.campus_drives
                 (university_id, opportunity_id, allowed_branches, batch, min_cgpa, required_skills, deadline, authorized_by)
               select %s, %s, %s, %s, %s, %s, now() + make_interval(days => %s), m.user_id
               from public.memberships m where m.organization_id = %s and m.role = 'admin' limit 1
               on conflict (university_id, opportunity_id) do nothing""",
            (org_id[uni], opportunity_id[(company, title)], branches, batch, min_cgpa, skills, days, org_id[uni]),
        )
    print(f"rows   {len(ORGS)} orgs, {len(MEMBERSHIPS)} memberships, {len(MENTORS)} mentors, {len(ROSTER)} roster rows, "
          f"{len(OPPORTUNITIES)} listings, {len(DRIVES)} drives, {len(VENTURES)} ventures, {len(SUBSCRIPTIONS)} org plans")


def main() -> int:
    load_env()
    missing = [n for n in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "DATABASE_URL", "DEMO_PASSWORD") if not os.environ.get(n)]
    if missing:
        print(f"Missing settings: {', '.join(missing)}", file=sys.stderr)
        return 2

    for email, name in USERS.items():
        ensure_user(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"], email, name, os.environ["DEMO_PASSWORD"])

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        seed_rows(conn)  # one transaction: all rows or none
    return 0


if __name__ == "__main__":
    sys.exit(main())
