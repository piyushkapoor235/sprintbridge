SHAPE = {"detail", "code", "field_errors", "request_id"}


def test_missing_token_is_401_with_error_shape(client):
    response = client.get("/api/me")
    assert response.status_code == 401
    body = response.json()
    assert set(body) == SHAPE
    assert body["code"] == "UNAUTHENTICATED"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_unknown_route_is_404_with_error_shape(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_validation_error_lists_fields(client, signed_in):
    response = client.patch("/api/me", json={"portfolio_url": "javascript:alert(1)", "role": "admin"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert set(body["field_errors"]) == {"portfolio_url", "role"}


def test_invalid_page_size_rejected(client, signed_in):
    response = client.get("/api/opportunities", params={"page_size": 101})
    assert response.status_code == 422
    assert "page_size" in response.json()["field_errors"]


def test_deadline_must_be_future(client, signed_in):
    response = client.post("/api/opportunities", json={
        "company_id": "5a0d0000-0000-4000-8000-000000000000", "title": "Role", "type": "job",
        "deadline": "2020-01-01T00:00:00Z"})
    assert response.status_code == 422
    assert "deadline" in response.json()["field_errors"]
