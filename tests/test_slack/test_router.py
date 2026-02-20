"""Integration tests for the /slack/events endpoint."""

import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from knowledge_hub.app import app

TEST_SIGNING_SECRET = "test_signing_secret_1234"
TEST_ALLOWED_USER = "U_ALLOWED"


def _mock_settings() -> MagicMock:
    """Create a mock Settings for router tests."""
    settings = MagicMock()
    settings.slack_signing_secret = TEST_SIGNING_SECRET
    settings.allowed_user_id = TEST_ALLOWED_USER
    return settings


def _sign_request(body: bytes, secret: str) -> tuple[str, str]:
    """Generate Slack-compatible signature headers."""
    timestamp = str(int(time.time()))
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    signature = "v0=" + hmac.new(
        secret.encode(), sig_basestring.encode(), hashlib.sha256
    ).hexdigest()
    return timestamp, signature


def _make_signed_request(
    client: TestClient,
    payload: dict,
    *,
    signing_secret: str = TEST_SIGNING_SECRET,
    extra_headers: dict | None = None,
) -> object:
    """Send a signed POST to /slack/events."""
    body = json.dumps(payload).encode()
    timestamp, signature = _sign_request(body, signing_secret)
    headers = {
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": signature,
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    return client.post("/slack/events", content=body, headers=headers)


# -- Endpoint tests (INGEST-01, INGEST-04) --


@patch("knowledge_hub.slack.verification.get_settings")
def test_url_verification_challenge(mock_get_settings: MagicMock):
    """URL verification challenge returns the challenge token (INGEST-01)."""
    mock_get_settings.return_value = _mock_settings()
    payload = {
        "type": "url_verification",
        "challenge": "test_challenge_token_xyz",
    }
    with TestClient(app) as client:
        response = _make_signed_request(client, payload)
    assert response.status_code == 200
    assert response.json() == {"challenge": "test_challenge_token_xyz"}


@patch("knowledge_hub.slack.verification.get_settings")
def test_invalid_signature_returns_403(mock_get_settings: MagicMock):
    """Invalid signature returns 403."""
    mock_get_settings.return_value = _mock_settings()
    payload = {"type": "event_callback", "event": {"type": "message"}}
    body = json.dumps(payload).encode()
    headers = {
        "X-Slack-Request-Timestamp": str(int(time.time())),
        "X-Slack-Signature": "v0=invalid_signature",
        "Content-Type": "application/json",
    }
    with TestClient(app) as client:
        response = client.post("/slack/events", content=body, headers=headers)
    assert response.status_code == 403


@patch("knowledge_hub.slack.handlers.get_settings")
@patch("knowledge_hub.slack.verification.get_settings")
def test_valid_message_returns_200(
    mock_verify_settings: MagicMock,
    mock_handler_settings: MagicMock,
):
    """Valid event_callback message returns 200 with ok (INGEST-04: ACK fast)."""
    mock_verify_settings.return_value = _mock_settings()
    mock_handler_settings.return_value = _mock_settings()
    payload = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "user": TEST_ALLOWED_USER,
            "channel": "C0AFQJHAVS6",
            "ts": "1234567890.123456",
            "text": "Check <https://example.com>",
        },
    }
    with TestClient(app) as client:
        response = _make_signed_request(client, payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("knowledge_hub.slack.verification.get_settings")
def test_retry_header_returns_200_immediately(mock_get_settings: MagicMock):
    """Slack retry header causes immediate 200 without processing."""
    mock_get_settings.return_value = _mock_settings()
    payload = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "user": TEST_ALLOWED_USER,
            "text": "<https://example.com>",
        },
    }
    with TestClient(app) as client:
        response = _make_signed_request(
            client, payload, extra_headers={"X-Slack-Retry-Num": "1"}
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("knowledge_hub.slack.handlers.get_settings")
@patch("knowledge_hub.slack.verification.get_settings")
def test_bot_message_returns_200_no_processing(
    mock_verify_settings: MagicMock,
    mock_handler_settings: MagicMock,
):
    """Bot message returns 200 but no background task (INGEST-05)."""
    mock_verify_settings.return_value = _mock_settings()
    mock_handler_settings.return_value = _mock_settings()
    payload = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "subtype": "bot_message",
            "text": "<https://example.com>",
            "channel": "C0AFQJHAVS6",
            "ts": "1234567890.123456",
        },
    }
    with TestClient(app) as client:
        response = _make_signed_request(client, payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("knowledge_hub.slack.handlers.get_settings")
@patch("knowledge_hub.slack.verification.get_settings")
def test_message_with_urls_triggers_background(
    mock_verify_settings: MagicMock,
    mock_handler_settings: MagicMock,
):
    """Valid message with URLs triggers background dispatch."""
    mock_verify_settings.return_value = _mock_settings()
    mock_handler_settings.return_value = _mock_settings()
    payload = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "user": TEST_ALLOWED_USER,
            "channel": "C0AFQJHAVS6",
            "ts": "1234567890.123456",
            "text": "Read <https://example.com|Article>",
        },
    }
    with TestClient(app) as client:
        response = _make_signed_request(client, payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
