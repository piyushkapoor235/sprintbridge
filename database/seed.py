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

MENTORS = [
    ("mentor@demo.test", "Data engineering", "Sample data · 8 years building data pipelines.", ["python", "sql", "docker"]),
    ("mentor2@demo.test", "Frontend", "Sample data · 6 years of React and design systems.", ["react", "typescript"]),
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

    for email, niche, summary, skills in MENTORS:
        conn.execute(
            "insert into public.role_grants (user_id, role) values (%s, 'mentor') on conflict do nothing",
            (user_id[email],),
        )
        conn.execute(
            """insert into public.mentors (user_id, niche, experience_summary) values (%s, %s, %s)
               on conflict (user_id) do update set niche = excluded.niche,
                 experience_summary = excluded.experience_summary""",
            (user_id[email], niche, summary),
        )
        conn.execute("update public.profiles set skills = %s where user_id = %s", (skills, user_id[email]))

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
    print(f"rows   {len(ORGS)} orgs, {len(MEMBERSHIPS)} memberships, {len(MENTORS)} mentors, {len(ROSTER)} roster rows")


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
