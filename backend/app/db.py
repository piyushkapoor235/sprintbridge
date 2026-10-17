"""Database clients and error translation.

`get_db` gives each request its own client carrying the caller's JWT, so Postgres row-level
security applies exactly as it would to a direct Data API call. Never share one client's
session between users (docs/architecture.md §7).

`service_client` bypasses RLS. It exists only for tables that users must not be able to write
themselves (SERVER_OWNED_TABLES). Use it for those writes and nothing else: no user-scoped reads,
no business tables that have their own RLS write rules.

`run` executes a query and turns Postgres/PostgREST failures into the API error shape
(docs/api-contract.md §4).
"""

import logging

import httpx
from fastapi import Depends
from postgrest.exceptions import APIError
from supabase import Client, ClientOptions, create_client

from app.auth import Actor, get_actor
from app.config import get_settings
from app.errors import ApiError

logger = logging.getLogger("sprintbridge")

SERVER_OWNED_TABLES = frozenset({"resumes", "skill_evidence", "job_requirements"})

_VALIDATION_SQLSTATES = {"22001", "22003", "22007", "22008", "22P02", "23502", "23514"}


def user_client(actor: Actor) -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "Database is not configured.")
    return create_client(
        settings.supabase_url,
        settings.supabase_publishable_key,
        ClientOptions(
            headers={"Authorization": f"Bearer {actor.access_token}"},
            auto_refresh_token=False,
            persist_session=False,
            postgrest_client_timeout=settings.request_timeout_seconds,
        ),
    )


def get_db(actor: Actor = Depends(get_actor)) -> Client:
    return user_client(actor)


def service_client(table: str) -> Client:
    """Privileged client for one server-owned table. Raises for any other table."""
    if table not in SERVER_OWNED_TABLES:
        raise ValueError(f"{table!r} is not server-owned; use the caller's client.")
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "Server storage is not configured.")
    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key,
        ClientOptions(
            auto_refresh_token=False,
            persist_session=False,
            postgrest_client_timeout=settings.request_timeout_seconds,
        ),
    )


def translate(exc: APIError, unique_code: str = "CONFLICT") -> ApiError:
    """Map a PostgREST error to the API error contract. Never leaks SQL or table names."""
    code = exc.code or ""
    # Our own functions: SQLSTATE PTnnn -> HTTP nnn, API code in HINT, safe message in MESSAGE.
    if code.startswith("PT") and code[2:].isdigit():
        status = int(code[2:])
        return ApiError(status, exc.hint or "ERROR", exc.message or "Request failed.")
    if code == "23505":
        return ApiError(409, unique_code, "That already exists.")
    if code == "42501":
        return ApiError(403, "FORBIDDEN", "You are not allowed to do that.")
    if code == "23503":
        return ApiError(422, "VALIDATION_ERROR", "A referenced record does not exist.")
    if code in _VALIDATION_SQLSTATES:
        return ApiError(422, "VALIDATION_ERROR", "Some values are invalid.")
    logger.error("unmapped database error code=%s", code)
    return ApiError(500, "INTERNAL_ERROR", "Something went wrong.")


def run(query, unique_code: str = "CONFLICT"):
    """Execute a postgrest query builder and translate failures."""
    try:
        return query.execute()
    except APIError as exc:
        raise translate(exc, unique_code) from exc
    except httpx.HTTPError as exc:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "The database is unavailable. Try again shortly.") from exc
