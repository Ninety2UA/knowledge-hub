"""Tests for Slack notification functions (success, error, duplicate, reaction).

All notifier functions must be fire-and-forget: they catch SlackApiError and log,
never allowing notification failures to propagate.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from knowledge_hub.notion.models import DuplicateResult, PageResult
from knowledge_hub.slack.notifier import (
    add_reaction,
    notify_duplicate,
    notify_error,
    notify_success,
)

CHANNEL = "C0AFQJHAVS6"
TS = "1234567890.123456"


def _make_slack_api_error(error_code: str) -> SlackApiError:
    """Build a SlackApiError with a mock response carrying the given error code."""
    resp = MagicMock()
    resp.get = MagicMock(
        side_effect=lambda key, default="": error_code if key == "error" else default,
    )
    resp.__getitem__ = MagicMock(
        side_effect=lambda key: error_code if key == "error" else None,
    )
    return SlackApiError(message=f"slack error: {error_code}", response=resp)


@pytest.fixture()
def mock_client():
    """Patch get_slack_client to return an AsyncMock Slack client."""
    client = AsyncMock()
    with patch("knowledge_hub.slack.notifier.get_slack_client", new_callable=AsyncMock) as m:
        m.return_value = client
        yield client


# -- notify_success tests --


async def test_notify_success_sends_thread_reply(mock_client: AsyncMock):
    """notify_success posts a thread reply containing the page URL and title."""
    result = PageResult(page_id="abc123", page_url="https://notion.so/abc123", title="My Page")

    await notify_success(CHANNEL, TS, result)

    mock_client.chat_postMessage.assert_called_once()
    call_kwargs = mock_client.chat_postMessage.call_args.kwargs
    assert call_kwargs["channel"] == CHANNEL
    assert call_kwargs["thread_ts"] == TS
    assert "https://notion.so/abc123" in call_kwargs["text"]
    assert "My Page" in call_kwargs["text"]


async def test_notify_success_with_cost(mock_client: AsyncMock):
    """When cost_usd is provided, message includes cost formatted to 3 decimal places."""
    result = PageResult(page_id="abc123", page_url="https://notion.so/abc123", title="My Page")

    await notify_success(CHANNEL, TS, result, cost_usd=0.003)

    text = mock_client.chat_postMessage.call_args.kwargs["text"]
    assert "(Cost: $0.003)" in text
    assert "https://notion.so/abc123" in text


async def test_notify_success_without_cost(mock_client: AsyncMock):
    """When cost_usd is not provided (None), message does NOT include cost."""
    result = PageResult(page_id="abc123", page_url="https://notion.so/abc123", title="My Page")

    await notify_success(CHANNEL, TS, result)

    text = mock_client.chat_postMessage.call_args.kwargs["text"]
    assert "Cost:" not in text


async def test_notify_success_swallows_slack_error(mock_client: AsyncMock):
    """SlackApiError from chat_postMessage does not propagate."""
    mock_client.chat_postMessage.side_effect = _make_slack_api_error("not_in_channel")
    result = PageResult(page_id="abc123", page_url="https://notion.so/abc123", title="My Page")

    # Must not raise
    await notify_success(CHANNEL, TS, result)


# -- notify_error tests --


async def test_notify_error_sends_thread_reply_with_stage(mock_client: AsyncMock):
    """notify_error posts a thread reply containing the URL, stage, and detail."""
    await notify_error(CHANNEL, TS, "https://example.com", "extraction", "timed out")

    mock_client.chat_postMessage.assert_called_once()
    text = mock_client.chat_postMessage.call_args.kwargs["text"]
    assert "https://example.com" in text
    assert "extraction" in text
    assert "timed out" in text


async def test_notify_error_swallows_slack_error(mock_client: AsyncMock):
    """SlackApiError from chat_postMessage does not propagate."""
    mock_client.chat_postMessage.side_effect = _make_slack_api_error("channel_not_found")

    await notify_error(CHANNEL, TS, "https://example.com", "extraction", "timed out")


# -- notify_duplicate tests --


async def test_notify_duplicate_sends_existing_link(mock_client: AsyncMock):
    """notify_duplicate posts the existing page URL and title."""
    dup = DuplicateResult(page_id="x", page_url="https://notion.so/x", title="Existing")

    await notify_duplicate(CHANNEL, TS, "https://example.com", dup)

    mock_client.chat_postMessage.assert_called_once()
    text = mock_client.chat_postMessage.call_args.kwargs["text"]
    assert "https://notion.so/x" in text
    assert "Existing" in text


async def test_notify_duplicate_swallows_slack_error(mock_client: AsyncMock):
    """SlackApiError from chat_postMessage does not propagate."""
    mock_client.chat_postMessage.side_effect = _make_slack_api_error("not_in_channel")
    dup = DuplicateResult(page_id="x", page_url="https://notion.so/x", title="Existing")

    await notify_duplicate(CHANNEL, TS, "https://example.com", dup)


# -- add_reaction tests --


async def test_add_reaction_calls_reactions_add(mock_client: AsyncMock):
    """add_reaction passes channel, emoji, and timestamp to reactions_add."""
    await add_reaction(CHANNEL, TS, "white_check_mark")

    mock_client.reactions_add.assert_called_once_with(
        channel=CHANNEL, name="white_check_mark", timestamp=TS
    )


async def test_add_reaction_handles_missing_scope(mock_client: AsyncMock):
    """missing_scope error is handled gracefully (no exception)."""
    mock_client.reactions_add.side_effect = _make_slack_api_error("missing_scope")

    await add_reaction(CHANNEL, TS, "white_check_mark")


async def test_add_reaction_handles_already_reacted(mock_client: AsyncMock):
    """already_reacted error is handled gracefully (no exception)."""
    mock_client.reactions_add.side_effect = _make_slack_api_error("already_reacted")

    await add_reaction(CHANNEL, TS, "white_check_mark")
