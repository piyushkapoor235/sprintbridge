"""Shared fixtures: a throwaway Postgres with the Supabase shim and all migrations applied."""

from __future__ import annotations

import contextlib
import tempfile
import uuid
from pathlib import Path

import pgserver
import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = sorted((ROOT / "migrations").glob("*.sql"))
SHIM = ROOT / "tests" / "supabase_shim.sql"


@pytest.fixture(scope="session")
def dsn():
    server = pgserver.get_server(tempfile.mkdtemp(), cleanup_mode="stop")
    with psycopg.connect(server.get_uri(), autocommit=True) as conn:
        conn.execute(SHIM.read_text())
        for path in MIGRATIONS:
            conn.execute(path.read_text())
    yield server.get_uri()


@pytest.fixture
def db(dsn):
    with psycopg.connect(dsn) as conn:
        yield Db(conn)
        conn.rollback()


class Db:
    """Runs statements as the superuser (setup) or as an authenticated user (under RLS)."""

    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def admin(self, sql: str, params=None):
        self.conn.execute("reset role")
        # Owner/setup context: no signed-in user (plan limits and quotas do not apply).
        self.conn.execute("select set_config('request.jwt.claim.sub', '', true)")
        return self.conn.execute(sql, params)

    def user(self, user_id: uuid.UUID, sql: str, params=None):
        self.conn.execute("set local role authenticated")
        self.conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(user_id),))
        # On error the transaction is aborted; `fails` rolls back to its savepoint,
        # which also undoes the SET LOCAL role above.
        cur = self.conn.execute(sql, params)
        self.conn.execute("reset role")
        return cur

    @contextlib.contextmanager
    def fails(self, exc=psycopg.Error, sqlstate: str | None = None):
        """Assert the block raises `exc` (optionally with `sqlstate`), keeping the transaction usable."""
        self.conn.execute("savepoint expect_failure")
        with pytest.raises(exc) as caught:
            yield
        self.conn.execute("rollback to savepoint expect_failure")
        if sqlstate:
            assert caught.value.sqlstate == sqlstate, caught.value

    def new_user(self, name: str = "") -> uuid.UUID:
        return self.admin(
            "insert into auth.users (email, raw_user_meta_data) values (%s, %s) returning id",
            (f"{uuid.uuid4().hex[:8]}@example.test", psycopg.types.json.Jsonb({"name": name})),
        ).fetchone()[0]

    def new_org(self, kind: str) -> uuid.UUID:
        return self.admin(
            "insert into public.organizations (name, type) values (%s, %s) returning id",
            (f"{kind}-{uuid.uuid4().hex[:6]}", kind),
        ).fetchone()[0]

    def member(self, user_id, org_id, role):
        self.admin(
            "insert into public.memberships (user_id, organization_id, role) values (%s, %s, %s)",
            (user_id, org_id, role),
        )

    def new_opportunity(self, company_id, created_by, visibility="public", skills=("Python",)):
        return self.admin(
            """insert into public.opportunities
                 (company_id, title, type, visibility, required_skills, deadline, created_by)
               values (%s, 'Backend intern', 'internship', %s, %s, now() + interval '7 days', %s)
               returning id""",
            (company_id, visibility, list(skills), created_by),
        ).fetchone()[0]
