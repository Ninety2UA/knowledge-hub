"""Gemini client singleton with async support.

Creates a cached genai.Client instance configured with the API key from
application settings. Uses a 60-second HTTP timeout. Does NOT configure
HttpRetryOptions -- tenacity handles retries at the application level
to avoid double-retry behavior.
"""

from google import genai
from google.genai import types

from knowledge_hub.config import get_settings

_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    """Return a cached Gemini client instance.

    Creates the client on first call using gemini_api_key from settings.
    Subsequent calls return the cached instance.
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=60_000),
        )
    return _client


def reset_client() -> None:
    """Reset the cached client instance. Used for testing."""
    global _client
    _client = None
