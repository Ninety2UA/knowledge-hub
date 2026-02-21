"""Tests for Slack client singleton (init, caching, reset)."""

from unittest.mock import MagicMock, patch

import pytest

from knowledge_hub.slack.client import get_slack_client, reset_client


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure clean singleton state for every test."""
    reset_client()
    yield
    reset_client()


@patch("knowledge_hub.slack.client.get_settings")
async def test_get_slack_client_creates_client(mock_get_settings: MagicMock):
    """get_slack_client returns an AsyncWebClient initialised from settings."""
    settings = MagicMock()
    settings.slack_bot_token = "xoxb-test"
    mock_get_settings.return_value = settings

    client = await get_slack_client()

    from slack_sdk.web.async_client import AsyncWebClient

    assert isinstance(client, AsyncWebClient)


@patch("knowledge_hub.slack.client.get_settings")
async def test_get_slack_client_returns_cached(mock_get_settings: MagicMock):
    """Second call returns the same object (singleton)."""
    settings = MagicMock()
    settings.slack_bot_token = "xoxb-test"
    mock_get_settings.return_value = settings

    first = await get_slack_client()
    second = await get_slack_client()

    assert first is second


@patch("knowledge_hub.slack.client.get_settings")
async def test_reset_client_clears_cache(mock_get_settings: MagicMock):
    """After reset_client(), a new instance is created."""
    settings = MagicMock()
    settings.slack_bot_token = "xoxb-test"
    mock_get_settings.return_value = settings

    first = await get_slack_client()
    reset_client()
    second = await get_slack_client()

    assert first is not second
