"""Slack event model with extracted fields."""

from pydantic import BaseModel


class SlackEvent(BaseModel):
    """A Slack message event with extracted fields (no raw payload)."""

    channel_id: str
    timestamp: str  # Slack message ts, e.g., "1234567890.123456"
    user_id: str
    text: str
    extracted_urls: list[str]  # Parsed from Slack <url|label> format
    user_note: str | None = None  # Non-URL text from the message
