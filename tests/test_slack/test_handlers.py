"""Tests for Slack message filtering and dispatch logic."""

from unittest.mock import MagicMock, patch

from knowledge_hub.slack.handlers import handle_message_event


def _make_event(**overrides: object) -> dict:
    """Build a valid Slack message event dict with overrides."""
    base = {
        "type": "message",
        "user": "U_ALLOWED",
        "channel": "C0AFQJHAVS6",
        "ts": "1234567890.123456",
        "text": "Check <https://example.com>",
    }
    base.update(overrides)
    return base


def _mock_settings() -> MagicMock:
    """Create a mock Settings with allowed_user_id."""
    settings = MagicMock()
    settings.allowed_user_id = "U_ALLOWED"
    return settings


# -- Filter tests (INGEST-05, INGEST-06) --


@patch("knowledge_hub.slack.handlers.get_settings")
def test_ignores_non_message_type(mock_get_settings: MagicMock):
    """Events with type != 'message' are not dispatched."""
    mock_get_settings.return_value = _mock_settings()
    bg = MagicMock()
    handle_message_event({"type": "app_mention", "text": "<https://example.com>"}, bg)
    bg.add_task.assert_not_called()


@patch("knowledge_hub.slack.handlers.get_settings")
def test_ignores_subtype_bot_message(mock_get_settings: MagicMock):
    """Bot messages (subtype: bot_message) are filtered out (INGEST-05)."""
    mock_get_settings.return_value = _mock_settings()
    bg = MagicMock()
    event = _make_event(subtype="bot_message")
    handle_message_event(event, bg)
    bg.add_task.assert_not_called()


@patch("knowledge_hub.slack.handlers.get_settings")
def test_ignores_subtype_message_changed(mock_get_settings: MagicMock):
    """Edited messages (subtype: message_changed) are filtered out."""
    mock_get_settings.return_value = _mock_settings()
    bg = MagicMock()
    event = _make_event(subtype="message_changed")
    handle_message_event(event, bg)
    bg.add_task.assert_not_called()


@patch("knowledge_hub.slack.handlers.get_settings")
def test_ignores_bot_id(mock_get_settings: MagicMock):
    """Messages with bot_id are filtered out (belt-and-suspenders)."""
    mock_get_settings.return_value = _mock_settings()
    bg = MagicMock()
    event = _make_event(bot_id="B123")
    handle_message_event(event, bg)
    bg.add_task.assert_not_called()


@patch("knowledge_hub.slack.handlers.get_settings")
def test_ignores_wrong_user(mock_get_settings: MagicMock):
    """Messages from non-allowed users are filtered out."""
    mock_get_settings.return_value = _mock_settings()
    bg = MagicMock()
    event = _make_event(user="U_OTHER")
    handle_message_event(event, bg)
    bg.add_task.assert_not_called()


@patch("knowledge_hub.slack.handlers.get_settings")
def test_ignores_thread_reply(mock_get_settings: MagicMock):
    """Thread replies (thread_ts present) are filtered out."""
    mock_get_settings.return_value = _mock_settings()
    bg = MagicMock()
    event = _make_event(thread_ts="123.456")
    handle_message_event(event, bg)
    bg.add_task.assert_not_called()


@patch("knowledge_hub.slack.handlers.get_settings")
def test_ignores_no_urls(mock_get_settings: MagicMock):
    """Messages with no URLs are filtered out (INGEST-06)."""
    mock_get_settings.return_value = _mock_settings()
    bg = MagicMock()
    event = _make_event(text="just a regular message, no links")
    handle_message_event(event, bg)
    bg.add_task.assert_not_called()


@patch("knowledge_hub.slack.handlers.get_settings")
def test_processes_valid_message(mock_get_settings: MagicMock):
    """Valid message from allowed user with URL triggers dispatch."""
    mock_get_settings.return_value = _mock_settings()
    bg = MagicMock()
    event = _make_event()
    handle_message_event(event, bg)
    bg.add_task.assert_called_once()


# -- Multi-URL tests (INGEST-07) --


@patch("knowledge_hub.slack.handlers.get_settings")
def test_multiple_urls_dispatched(mock_get_settings: MagicMock):
    """Message with 3 URLs dispatches all 3 to background."""
    mock_get_settings.return_value = _mock_settings()
    bg = MagicMock()
    text = "<https://a.com> <https://b.com> <https://c.com>"
    event = _make_event(text=text)
    handle_message_event(event, bg)
    bg.add_task.assert_called_once()
    call_kwargs = bg.add_task.call_args
    # The urls kwarg should have 3 URLs
    assert len(call_kwargs.kwargs["urls"]) == 3


@patch("knowledge_hub.slack.handlers.get_settings")
def test_urls_capped_at_10(mock_get_settings: MagicMock):
    """Message with 12 URLs only dispatches first 10."""
    mock_get_settings.return_value = _mock_settings()
    bg = MagicMock()
    urls = " ".join(f"<https://example{i}.com>" for i in range(12))
    event = _make_event(text=urls)
    handle_message_event(event, bg)
    bg.add_task.assert_called_once()
    call_kwargs = bg.add_task.call_args
    assert len(call_kwargs.kwargs["urls"]) == 10
