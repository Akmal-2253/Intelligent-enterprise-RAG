"""
Minimal smoke test. Run with: pytest
Requires a reachable Postgres (see README) since app startup creates tables.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
