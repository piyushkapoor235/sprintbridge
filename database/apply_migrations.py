"""Apply database/migrations/*.sql in order, each once, recording what ran.

Usage (from the repo root; DATABASE_URL is the Supabase session-pooler connection string):

    DATABASE_URL='postgresql://postgres.<ref>:<password>@<host>:5432/postgres' \
      uv run --with 'psycopg[binary]' python database/apply_migrations.py

Each migration runs in its own transaction. Applied file names are stored in
public.schema_migrations, so re-running skips what is already applied.
"""

import os
import sys
from pathlib import Path

import psycopg

MIGRATIONS = sorted((Path(__file__).parent / "migrations").glob("*.sql"))


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("Set DATABASE_URL to the Supabase connection string.", file=sys.stderr)
        return 2

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            """create table if not exists public.schema_migrations (
                 name text primary key,
                 applied_at timestamptz not null default now())"""
        )
        # Bookkeeping only; keep it out of the Data API.
        conn.execute("alter table public.schema_migrations enable row level security")
        conn.execute("revoke all on public.schema_migrations from anon, authenticated")
        applied = {row[0] for row in conn.execute("select name from public.schema_migrations")}

        for path in MIGRATIONS:
            if path.name in applied:
                print(f"skip   {path.name}")
                continue
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute("insert into public.schema_migrations (name) values (%s)", (path.name,))
            print(f"apply  {path.name}")
        # Ask PostgREST to pick up the new tables immediately.
        conn.execute("notify pgrst, 'reload schema'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
