import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import Actor, get_actor
from app.main import app


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def signed_in(client):
    """Bypass Supabase token verification with a fixed caller."""
    actor = Actor(user_id=uuid.uuid4(), email="tester@example.test", access_token="test-token")
    app.dependency_overrides[get_actor] = lambda: actor
    return actor
