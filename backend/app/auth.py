"""Caller identity. Tokens are verified with Supabase Auth, never merely decoded.

See docs/architecture.md §7. Roles and memberships are read from server-owned tables
per request; nothing the client sends is accepted as proof of access.
"""

from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import httpx
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, ClientOptions, create_client
from supabase_auth.errors import AuthApiError, AuthRetryableError

from app.config import get_settings
from app.errors import ApiError

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    email: str | None
    access_token: str


@lru_cache
def _auth_client() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "Authentication is not configured.")
    # Only used for get_user(jwt), which does not store a session on the client.
    return create_client(
        settings.supabase_url,
        settings.supabase_publishable_key,
        ClientOptions(auto_refresh_token=False, persist_session=False),
    )


def verify_token(token: str) -> Actor:
    try:
        response = _auth_client().auth.get_user(token)
    except AuthRetryableError as exc:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "Authentication service is unavailable.") from exc
    except AuthApiError as exc:
        if exc.status and exc.status >= 500:
            raise ApiError(503, "SERVICE_UNAVAILABLE", "Authentication service is unavailable.") from exc
        raise ApiError(401, "UNAUTHENTICATED", "Your session is invalid or expired.") from exc
    except httpx.HTTPError as exc:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "Authentication service is unavailable.") from exc

    if response is None or response.user is None:
        raise ApiError(401, "UNAUTHENTICATED", "Your session is invalid or expired.")
    return Actor(user_id=UUID(response.user.id), email=response.user.email, access_token=token)


def get_actor(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Actor:
    if credentials is None or not credentials.credentials:
        raise ApiError(401, "UNAUTHENTICATED", "Login required.")
    return verify_token(credentials.credentials)
