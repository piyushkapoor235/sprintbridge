"""Caller identity.

Tokens are verified, never merely decoded (docs/architecture.md §7):
  1. Locally: the token's ES256 signature is checked against the project's published JSON Web Key
     Set (cached), together with expiry, audience and issuer. This is Supabase's recommended
     verification and saves a network round-trip on every request.
  2. Fallback: if the key set cannot be fetched or the token uses a key/algorithm we don't hold,
     the token is checked remotely with Supabase Auth (get_user).
Trade-off of (1): a token stays valid until it expires (about 1 hour) even after sign-out.
Roles and memberships are read from server-owned tables per request; nothing the client sends is
accepted as proof of access.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import httpx
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, ClientOptions, create_client
from supabase_auth.errors import AuthApiError, AuthRetryableError

from app.config import get_settings
from app.errors import ApiError

logger = logging.getLogger("sprintbridge")
_bearer = HTTPBearer(auto_error=False)
_ASYMMETRIC = {"ES256", "RS256", "EdDSA"}


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


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    url = f"{get_settings().supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=5)


def _verify_locally(token: str) -> Actor | None:
    """Return the actor for a valid token, raise 401 for an invalid one, or None to fall back."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise ApiError(401, "UNAUTHENTICATED", "Your session is invalid or expired.") from exc
    if header.get("alg") not in _ASYMMETRIC:
        return None  # legacy shared-secret tokens: let Supabase Auth decide
    try:
        key = _jwks_client().get_signing_key_from_jwt(token)
    except (jwt.PyJWKClientError, jwt.PyJWKClientConnectionError) as exc:
        logger.warning("jwks unavailable, falling back to remote verification: %s", type(exc).__name__)
        return None
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            key.key,
            algorithms=[header["alg"]],
            audience="authenticated",
            issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise ApiError(401, "UNAUTHENTICATED", "Your session is invalid or expired.") from exc
    return Actor(user_id=UUID(claims["sub"]), email=claims.get("email"), access_token=token)


def _verify_remotely(token: str) -> Actor:
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


def verify_token(token: str) -> Actor:
    return _verify_locally(token) or _verify_remotely(token)


def get_actor(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Actor:
    if credentials is None or not credentials.credentials:
        raise ApiError(401, "UNAUTHENTICATED", "Login required.")
    return verify_token(credentials.credentials)
