"""Tests for FastAPI app endpoints including scheduler authentication."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from knowledge_hub.app import app


@pytest.fixture
def client():
    """Create a TestClient scoped to this module (not session-scoped conftest)."""
    return TestClient(app)


def test_digest_endpoint_requires_auth(client: TestClient):
    """POST /digest without scheduler secret returns 403."""
    response = client.post("/digest")
    assert response.status_code == 403
    assert "Invalid scheduler secret" in response.json()["detail"]


def test_cost_check_endpoint_requires_auth(client: TestClient):
    """POST /cost-check without scheduler secret returns 403."""
    response = client.post("/cost-check")
    assert response.status_code == 403
    assert "Invalid scheduler secret" in response.json()["detail"]


def test_digest_endpoint_wrong_secret(client: TestClient):
    """POST /digest with wrong scheduler secret returns 403."""
    with patch("knowledge_hub.app.get_settings") as mock_settings:
        mock_settings.return_value.scheduler_secret = "correct-secret"
        response = client.post(
            "/digest",
            headers={"X-Scheduler-Secret": "wrong-secret"},
        )
    assert response.status_code == 403


def test_digest_endpoint_with_valid_auth(client: TestClient):
    """POST /digest with correct scheduler secret returns 200."""
    with (
        patch("knowledge_hub.app.get_settings") as mock_settings,
        patch("knowledge_hub.app.send_weekly_digest", new_callable=AsyncMock) as mock_digest,
    ):
        mock_settings.return_value.scheduler_secret = "test-secret"
        mock_digest.return_value = {"status": "sent", "entries": 3}
        response = client.post(
            "/digest",
            headers={"X-Scheduler-Secret": "test-secret"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "sent", "entries": 3}
    mock_digest.assert_called_once()


def test_cost_check_endpoint_with_valid_auth(client: TestClient):
    """POST /cost-check with correct scheduler secret returns 200."""
    with (
        patch("knowledge_hub.app.get_settings") as mock_settings,
        patch("knowledge_hub.app.check_daily_cost", new_callable=AsyncMock) as mock_cost,
    ):
        mock_settings.return_value.scheduler_secret = "test-secret"
        mock_cost.return_value = {"status": "ok", "cost": 1.5}
        response = client.post(
            "/cost-check",
            headers={"X-Scheduler-Secret": "test-secret"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "cost": 1.5}
    mock_cost.assert_called_once()


def test_digest_endpoint_internal_error(client: TestClient):
    """POST /digest returns 200 with error status (not 500) when digest raises."""
    with (
        patch("knowledge_hub.app.get_settings") as mock_settings,
        patch("knowledge_hub.app.send_weekly_digest", new_callable=AsyncMock) as mock_digest,
    ):
        mock_settings.return_value.scheduler_secret = "test-secret"
        mock_digest.side_effect = Exception("unexpected")
        response = client.post(
            "/digest",
            headers={"X-Scheduler-Secret": "test-secret"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert "unexpected" in body["error"]
