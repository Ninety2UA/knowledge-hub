"""Tests for the health endpoint."""

from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient):
    """GET /health returns 200 status code."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_body(client: TestClient):
    """GET /health returns expected JSON body."""
    response = client.get("/health")
    assert response.json() == {
        "status": "ok",
        "service": "knowledge-hub",
        "version": "0.1.0",
    }
