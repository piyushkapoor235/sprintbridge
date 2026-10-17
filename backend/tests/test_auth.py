import httpx
import pytest
from supabase_auth.errors import AuthApiError, AuthRetryableError

from app import auth
from app.errors import ApiError


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


def _verify(monkeypatch, outcome):
    monkeypatch.setattr(auth, "_auth_client", lambda: _FakeClient(outcome))
    return auth.verify_token("token")


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
def test_token_failures_map_to_401_or_503(monkeypatch, outcome, status):
    with pytest.raises(ApiError) as caught:
        _verify(monkeypatch, outcome)
    assert caught.value.status_code == status


def test_valid_token_yields_actor(monkeypatch):
    class _User:
        id = "0b6f2a9e-5d1c-4f7a-9a3e-1c2d3e4f5a6b"
        email = "asha@student.test"

    class _Response:
        user = _User()

    actor = _verify(monkeypatch, _Response())
    assert str(actor.user_id) == _User.id
    assert actor.access_token == "token"
