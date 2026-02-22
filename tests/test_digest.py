"""Tests for weekly digest builder and daily cost alert logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_hub.digest import (
    _extract_entry_data,
    build_weekly_digest,
    check_daily_cost,
    query_recent_entries,
    send_weekly_digest,
)


def _make_notion_page(
    title: str = "Test Article",
    url: str = "https://example.com/article",
    category: str = "Article",
    tags: list[str] | None = None,
) -> dict:
    """Build a mock Notion page dict with properties in Notion API format."""
    if tags is None:
        tags = ["python", "testing"]
    return {
        "properties": {
            "Title": {
                "title": [{"plain_text": title}],
            },
            "Source": {
                "url": url,
            },
            "Category": {
                "select": {"name": category} if category else None,
            },
            "Tags": {
                "multi_select": [{"name": tag} for tag in tags],
            },
        },
    }


def test_extract_entry_data():
    """_extract_entry_data correctly parses Notion page properties."""
    page = _make_notion_page(
        title="How to Deploy",
        url="https://example.com/deploy",
        category="Article",
        tags=["devops", "cloud"],
    )

    result = _extract_entry_data(page)

    assert result["title"] == "How to Deploy"
    assert result["url"] == "https://example.com/deploy"
    assert result["category"] == "Article"
    assert result["tags"] == ["devops", "cloud"]


def test_extract_entry_data_missing_properties():
    """_extract_entry_data handles missing or empty properties gracefully."""
    page = {"properties": {}}

    result = _extract_entry_data(page)

    assert result["title"] == "Untitled"
    assert result["url"] == ""
    assert result["category"] == "Unknown"
    assert result["tags"] == []


def test_build_weekly_digest_with_entries():
    """build_weekly_digest produces a formatted message with all sections."""
    entries = [
        {"title": "Python Tips", "url": "https://example.com/python", "category": "Article", "tags": ["python", "tips"]},
        {"title": "Cloud Deploy", "url": "https://example.com/cloud", "category": "Article", "tags": ["cloud", "devops"]},
        {"title": "ML Tutorial", "url": "https://example.com/ml", "category": "Video", "tags": ["python", "ml"]},
    ]

    message = build_weekly_digest(entries, total_cost=0.003)

    assert "Weekly Knowledge Base Digest" in message
    assert "3 entries processed" in message
    assert "<https://example.com/python|Python Tips>" in message
    assert "<https://example.com/cloud|Cloud Deploy>" in message
    assert "<https://example.com/ml|ML Tutorial>" in message
    assert "articles" in message.lower()
    assert "video" in message.lower()
    assert "python (2)" in message
    assert "$0.0030" in message


def test_build_weekly_digest_zero_entries():
    """build_weekly_digest with empty list shows service running message."""
    message = build_weekly_digest([], total_cost=0.0)

    assert "No entries" in message
    assert "Service is running" in message
    assert "$0.0000" in message


@pytest.mark.asyncio
async def test_query_recent_entries():
    """query_recent_entries returns entries from Notion database query."""
    mock_client = AsyncMock()
    mock_client.data_sources.query.return_value = {
        "results": [_make_notion_page(), _make_notion_page(title="Second")],
        "has_more": False,
    }

    with (
        patch("knowledge_hub.digest.get_notion_client", return_value=mock_client),
        patch("knowledge_hub.digest.get_data_source_id", return_value="ds-123"),
    ):
        entries = await query_recent_entries(days=7)

    assert len(entries) == 2
    mock_client.data_sources.query.assert_called_once()
    call_kwargs = mock_client.data_sources.query.call_args[1]
    assert call_kwargs["data_source_id"] == "ds-123"
    assert "database_id" not in call_kwargs
    assert "on_or_after" in call_kwargs["filter"]["date"]


@pytest.mark.asyncio
async def test_query_recent_entries_pagination():
    """query_recent_entries handles pagination across multiple pages."""
    mock_client = AsyncMock()
    mock_client.data_sources.query.side_effect = [
        {
            "results": [_make_notion_page(title="Page 1")],
            "has_more": True,
            "next_cursor": "cursor-abc",
        },
        {
            "results": [_make_notion_page(title="Page 2")],
            "has_more": False,
        },
    ]

    with (
        patch("knowledge_hub.digest.get_notion_client", return_value=mock_client),
        patch("knowledge_hub.digest.get_data_source_id", return_value="ds-123"),
    ):
        entries = await query_recent_entries(days=7)

    assert len(entries) == 2
    assert mock_client.data_sources.query.call_count == 2
    # Second call should include start_cursor
    second_call_kwargs = mock_client.data_sources.query.call_args_list[1][1]
    assert second_call_kwargs["start_cursor"] == "cursor-abc"


@pytest.mark.asyncio
async def test_send_weekly_digest():
    """send_weekly_digest queries Notion, builds digest, and sends Slack DM."""
    mock_pages = [_make_notion_page(title="Test Entry")]
    mock_slack = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.allowed_user_id = "U12345"

    with (
        patch("knowledge_hub.digest.query_recent_entries", return_value=mock_pages),
        patch("knowledge_hub.digest.get_slack_client", return_value=mock_slack),
        patch("knowledge_hub.digest.get_settings", return_value=mock_settings),
        patch("knowledge_hub.digest.get_weekly_cost", return_value=0.005),
        patch("knowledge_hub.digest.reset_weekly_cost") as mock_reset,
    ):
        result = await send_weekly_digest()

    assert result == {"status": "sent", "entries": 1}
    mock_slack.chat_postMessage.assert_called_once()
    call_kwargs = mock_slack.chat_postMessage.call_args[1]
    assert call_kwargs["channel"] == "U12345"
    assert "Test Entry" in call_kwargs["text"]
    mock_reset.assert_called_once()


@pytest.mark.asyncio
async def test_check_daily_cost_under_threshold():
    """check_daily_cost returns ok when cost is under $5."""
    with patch("knowledge_hub.digest.get_daily_cost", return_value=2.0):
        result = await check_daily_cost()

    assert result == {"status": "ok", "cost": 2.0}


@pytest.mark.asyncio
async def test_check_daily_cost_over_threshold():
    """check_daily_cost sends alert when cost exceeds $5."""
    mock_slack = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.allowed_user_id = "U12345"

    with (
        patch("knowledge_hub.digest.get_daily_cost", return_value=7.0),
        patch("knowledge_hub.digest.get_slack_client", return_value=mock_slack),
        patch("knowledge_hub.digest.get_settings", return_value=mock_settings),
    ):
        result = await check_daily_cost()

    assert result == {"status": "alert_sent", "cost": 7.0}
    mock_slack.chat_postMessage.assert_called_once()
    call_kwargs = mock_slack.chat_postMessage.call_args[1]
    assert call_kwargs["channel"] == "U12345"
    assert "$7.00" in call_kwargs["text"]
    assert "exceeds $5.00" in call_kwargs["text"]


@pytest.mark.asyncio
async def test_send_weekly_digest_notion_error():
    """send_weekly_digest returns structured error when Notion query fails."""
    with (
        patch("knowledge_hub.digest.query_recent_entries", side_effect=Exception("Notion API auth failed")),
        patch("knowledge_hub.digest.get_slack_client") as mock_get_slack,
        patch("knowledge_hub.digest.get_settings") as mock_settings,
        patch("knowledge_hub.digest.reset_weekly_cost") as mock_reset,
    ):
        mock_settings.return_value.allowed_user_id = "U12345"
        result = await send_weekly_digest()

    assert result["status"] == "error"
    assert "Notion" in result["error"]
    mock_get_slack.assert_not_called()
    mock_reset.assert_not_called()


@pytest.mark.asyncio
async def test_send_weekly_digest_slack_error():
    """send_weekly_digest returns structured error when Slack send fails."""
    mock_slack = AsyncMock()
    mock_slack.chat_postMessage.side_effect = Exception("Slack token invalid")
    mock_settings = MagicMock()
    mock_settings.allowed_user_id = "U12345"

    with (
        patch("knowledge_hub.digest.query_recent_entries", return_value=[_make_notion_page()]),
        patch("knowledge_hub.digest.get_slack_client", return_value=mock_slack),
        patch("knowledge_hub.digest.get_settings", return_value=mock_settings),
        patch("knowledge_hub.digest.get_weekly_cost", return_value=0.005),
        patch("knowledge_hub.digest.reset_weekly_cost") as mock_reset,
    ):
        result = await send_weekly_digest()

    assert result["status"] == "error"
    assert "Slack" in result["error"]
    assert "entries" in result
    mock_reset.assert_not_called()


@pytest.mark.asyncio
async def test_check_daily_cost_slack_error():
    """check_daily_cost returns structured error when Slack alert send fails."""
    mock_slack = AsyncMock()
    mock_slack.chat_postMessage.side_effect = Exception("Slack error")
    mock_settings = MagicMock()
    mock_settings.allowed_user_id = "U12345"

    with (
        patch("knowledge_hub.digest.get_daily_cost", return_value=7.0),
        patch("knowledge_hub.digest.get_slack_client", return_value=mock_slack),
        patch("knowledge_hub.digest.get_settings", return_value=mock_settings),
    ):
        result = await check_daily_cost()

    assert result["status"] == "error"
    assert result["cost"] == 7.0
