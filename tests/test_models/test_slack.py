"""Tests for the SlackEvent model."""

import pytest
from pydantic import ValidationError

from knowledge_hub.models.slack import SlackEvent


def test_slack_event_valid():
    """Create SlackEvent with all required fields, assert all fields match."""
    event = SlackEvent(
        channel_id="C0AFQJHAVS6",
        timestamp="1234567890.123456",
        user_id="U12345",
        text="Check out https://example.com",
        extracted_urls=["https://example.com"],
    )
    assert event.channel_id == "C0AFQJHAVS6"
    assert event.timestamp == "1234567890.123456"
    assert event.user_id == "U12345"
    assert event.text == "Check out https://example.com"
    assert event.extracted_urls == ["https://example.com"]


def test_slack_event_with_user_note():
    """Create with optional user_note, assert it is set."""
    event = SlackEvent(
        channel_id="C0AFQJHAVS6",
        timestamp="1234567890.123456",
        user_id="U12345",
        text="Great article https://example.com",
        extracted_urls=["https://example.com"],
        user_note="Great article",
    )
    assert event.user_note == "Great article"


def test_slack_event_without_user_note():
    """Create without user_note, assert it defaults to None."""
    event = SlackEvent(
        channel_id="C0AFQJHAVS6",
        timestamp="1234567890.123456",
        user_id="U12345",
        text="https://example.com",
        extracted_urls=["https://example.com"],
    )
    assert event.user_note is None


def test_slack_event_multiple_urls():
    """Create with multiple URLs in extracted_urls list, assert length."""
    urls = [
        "https://example.com/article1",
        "https://example.com/article2",
        "https://youtube.com/watch?v=abc",
    ]
    event = SlackEvent(
        channel_id="C0AFQJHAVS6",
        timestamp="1234567890.123456",
        user_id="U12345",
        text="Links: " + " ".join(urls),
        extracted_urls=urls,
    )
    assert len(event.extracted_urls) == 3


def test_slack_event_missing_required_field():
    """Omit channel_id, assert ValidationError is raised."""
    with pytest.raises(ValidationError):
        SlackEvent(
            timestamp="1234567890.123456",
            user_id="U12345",
            text="https://example.com",
            extracted_urls=["https://example.com"],
        )
