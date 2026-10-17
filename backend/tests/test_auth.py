import time
import uuid

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from supabase_auth.errors import AuthApiError, AuthRetryableError

from app import auth
from app.config import get_settings
from app.errors import ApiError

# --- remote fallback (Supabase Auth get_user) -------------------------------------------


class _FakeAuth:
    def __init__(self, outcome):
        self.outcome = outcome

    def get_user(self, token):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class _FakeClient:
    def __init__(self, outcome):
        self.auth = _FakeAuth(outcome)


def _remote(monkeypatch, outcome):
    monkeypatch.setattr(auth, "_auth_client", lambda: _FakeClient(outcome))
    return auth._verify_remotely("token")


@pytest.mark.parametrize(
    ("outcome", "status"),
    [
        (AuthApiError("invalid JWT", 401, None), 401),
        (AuthApiError("upstream", 500, None), 503),
        (AuthRetryableError("timeout", 0), 503),
        (httpx.ConnectError("down"), 503),
        (None, 401),
    ],
)
def test_remote_failures_map_to_401_or_503(monkeypatch, outcome, status):
    with pytest.raises(ApiError) as caught:
        _remote(monkeypatch, outcome)
    assert caught.value.status_code == status


def test_remote_valid_token_yields_actor(monkeypatch):
    class _User:
        id = "0b6f2a9e-5d1c-4f7a-9a3e-1c2d3e4f5a6b"
        email = "asha@student.test"

    class _Response:
        user = _User()

    actor = _remote(monkeypatch, _Response())
    assert str(actor.user_id) == _User.id and actor.access_token == "token"


# --- local ES256 verification against the project's JWKS ---------------------------------

KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())


class _SigningKey:
    def __init__(self, key):
        self.key = key


class _FakeJwks:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return _SigningKey(self.public_key)


@pytest.fixture
def local(monkeypatch):
    monkeypatch.setattr(auth, "_jwks_client", lambda: _FakeJwks(KEY.public_key()))
    monkeypatch.setattr(auth, "_auth_client", lambda: (_ for _ in ()).throw(AssertionError("remote should not be called")))
    return f"{get_settings().supabase_url.rstrip('/')}/auth/v1"


def _token(issuer, *, key=KEY, exp_offset=3600, aud="authenticated", alg="ES256"):
    claims = {"sub": str(uuid.uuid4()), "email": "a@b.test", "aud": aud, "iss": issuer,
              "exp": int(time.time()) + exp_offset}
    return jwt.encode(claims, key, algorithm=alg)


def test_local_valid_token(local):
    token = _token(local)
    actor = auth.verify_token(token)
    assert actor.email == "a@b.test" and actor.access_token == token


@pytest.mark.parametrize(
    "kwargs",
    [
        {"exp_offset": -10},  # expired
        {"aud": "anon"},  # wrong audience
        {"key": OTHER_KEY},  # signed by someone else
    ],
)
def test_local_rejects_bad_tokens(local, kwargs):
    with pytest.raises(ApiError) as caught:
        auth.verify_token(_token(local, **kwargs))
    assert caught.value.status_code == 401


def test_local_rejects_wrong_issuer(local):
    with pytest.raises(ApiError):
        auth.verify_token(_token("https://evil.example/auth/v1"))


def test_garbage_is_401_without_network(local):
    with pytest.raises(ApiError) as caught:
        auth.verify_token("not-a-jwt")
    assert caught.value.status_code == 401


def test_shared_secret_tokens_fall_back_to_remote(monkeypatch):
    called = {}

    def remote(token):
        called["yes"] = True
        return auth.Actor(user_id=uuid.uuid4(), email=None, access_token=token)

    monkeypatch.setattr(auth, "_verify_remotely", remote)
    token = jwt.encode({"sub": "x"}, "secret", algorithm="HS256")
    auth.verify_token(token)
    assert called
