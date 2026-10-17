def test_health_is_public_and_minimal(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_well_formed_request_id_is_echoed(client):
    response = client.get("/api/health", headers={"X-Request-ID": "abcdef12-3456"})
    assert response.headers["X-Request-ID"] == "abcdef12-3456"


def test_malformed_request_id_is_replaced(client):
    response = client.get("/api/health", headers={"X-Request-ID": "bad id\n"})
    assert response.headers["X-Request-ID"] != "bad id\n"
