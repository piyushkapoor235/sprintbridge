"""Reset the demo to a clean starting point, then re-seed. For rehearsals and live demos.

Deletes ALL activity (applications, drives, requests, payments, payouts, verifications, ventures,
reports, usage, audit log, analyses, listings, non-seed roster rows) and re-runs database/seed.py.
Demo user accounts are kept. Accounts created through sign-up are kept unless --remove-signups.

    uv run --with 'psycopg[binary]' python database/reset_demo.py --yes
    uv run --with 'psycopg[binary]' python database/reset_demo.py --yes --remove-signups

Never run this against a database with real users.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from seed import ROSTER, load_env  # noqa: E402

# Children before parents.
TABLES = [
    "verification_audits",
    "verification_requests",
    "payouts",
    "mentor_requests",
    "collaboration_requests",
    "applications",
    "campus_drives",
    "content_reports",
    "usage_events",
    "payments",
    "job_requirements",
    "external_jds",
    "skill_evidence",
    "resumes",
    "audit_events",
    "opportunities",
    "ventures",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="confirm: delete all demo activity")
    parser.add_argument("--remove-signups", action="store_true", help="also delete accounts not ending in @demo.test")
    args = parser.parse_args()
    if not args.yes:
        print("Refusing to run without --yes (this deletes all activity).", file=sys.stderr)
        return 2
    load_env()

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        for table in TABLES:
            deleted = conn.execute(f"delete from public.{table}").rowcount
            print(f"clear  {table:<24} {deleted}")
        seed_ids = [row[1] for row in ROSTER]
        deleted = conn.execute("delete from public.student_roster where not (student_id = any(%s))", (seed_ids,)).rowcount
        print(f"clear  {'student_roster (non-seed)':<24} {deleted}")
        deleted = conn.execute("delete from public.subscriptions where user_id is not null").rowcount
        print(f"clear  {'personal subscriptions':<24} {deleted}")
        if args.remove_signups:
            deleted = conn.execute("delete from auth.users where email not like '%%@demo.test'").rowcount
            print(f"clear  {'sign-up accounts':<24} {deleted}")

    return subprocess.call([sys.executable, str(HERE / "seed.py")])


if __name__ == "__main__":
    sys.exit(main())
