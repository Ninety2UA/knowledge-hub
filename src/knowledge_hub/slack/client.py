"""Async Slack client singleton.

Creates a cached AsyncWebClient instance configured with the bot token from
application settings. Follows the established lazy-init pattern from
notion/client.py and llm/client.py.
"""

from slack_sdk.web.async_client import AsyncWebClient

from knowledge_hub.config import get_settings

_client: AsyncWebClient | None = None


async def get_slack_client() -> AsyncWebClient:
    """Return a cached async Slack client instance.

    Creates the client on first call using slack_bot_token from settings.
    Subsequent calls return the cached instance.
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncWebClient(token=settings.slack_bot_token)
    return _client


def reset_client() -> None:
    """Reset the cached client instance. Used for testing."""
    global _client
    _client = None
