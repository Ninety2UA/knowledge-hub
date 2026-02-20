"""Tests for URL extraction, user note extraction, and redirect resolution."""

from unittest.mock import AsyncMock, patch

import httpx

from knowledge_hub.slack.urls import extract_urls, extract_user_note, resolve_url, resolve_urls

# -- extract_urls tests (INGEST-02) --


def test_extract_url_with_label():
    """Slack mrkdwn <url|label> format extracts the URL only."""
    result = extract_urls("Check <https://example.com|Cool Article>")
    assert result == ["https://example.com"]


def test_extract_url_without_label():
    """Slack mrkdwn <url> format extracts the URL."""
    result = extract_urls("Link: <https://example.com/page>")
    assert result == ["https://example.com/page"]


def test_extract_multiple_urls():
    """Multiple URLs in one message are all extracted."""
    text = "Read <https://a.com|A> and <https://b.com>"
    result = extract_urls(text)
    assert result == ["https://a.com", "https://b.com"]


def test_extract_no_urls():
    """Plain text with no URLs returns empty list."""
    result = extract_urls("just text no links")
    assert result == []


def test_extract_ignores_user_mention():
    """User mentions <@U12345> are not extracted as URLs."""
    result = extract_urls("Hey <@U12345> check <https://example.com>")
    assert result == ["https://example.com"]


def test_extract_ignores_channel_ref():
    """Channel refs <#C12345> are not extracted as URLs."""
    result = extract_urls("See <#C12345> and <https://example.com>")
    assert result == ["https://example.com"]


def test_extract_ignores_special_commands():
    """Special mentions <!here> are not extracted as URLs."""
    result = extract_urls("<!here> <https://example.com>")
    assert result == ["https://example.com"]


def test_extract_url_with_query_params():
    """Query parameters are preserved in extracted URLs."""
    result = extract_urls("<https://youtube.com/watch?v=abc&t=120>")
    assert result == ["https://youtube.com/watch?v=abc&t=120"]


def test_extract_url_with_pipe_in_label():
    """Pipe in label portion does not break extraction."""
    # Slack encodes: <url|label> -- the URL part cannot contain pipes,
    # but the label can theoretically have any text. Verify the URL is clean.
    result = extract_urls("<https://example.com|Click here>")
    assert result == ["https://example.com"]


def test_extract_http_url():
    """HTTP (not just HTTPS) URLs are also extracted."""
    result = extract_urls("<http://example.com>")
    assert result == ["http://example.com"]


# -- extract_user_note tests (INGEST-03) --


def test_user_note_with_text_and_url():
    """Text surrounding a URL is returned as the user note."""
    result = extract_user_note("Great read on AI <https://example.com>")
    assert result == "Great read on AI"


def test_user_note_url_only():
    """A message containing only a URL returns None."""
    result = extract_user_note("<https://example.com>")
    assert result is None


def test_user_note_multiple_urls_with_text():
    """Text around multiple URLs is captured, URL markup stripped."""
    result = extract_user_note(
        "Check these <https://a.com> and <https://b.com> for reference"
    )
    assert result is not None
    assert "Check these" in result
    assert "for reference" in result
    assert "https://" not in result


def test_user_note_empty_string():
    """Empty string returns None."""
    result = extract_user_note("")
    assert result is None


def test_user_note_whitespace_only_after_removal():
    """Whitespace-only after URL removal returns None."""
    result = extract_user_note("  <https://example.com>  ")
    assert result is None


# -- resolve_url tests (INGEST-08) --


async def test_resolve_url_follows_redirect():
    """resolve_url follows redirects and returns the final URL."""
    mock_response = AsyncMock()
    mock_response.url = httpx.URL("https://example.com/article")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("knowledge_hub.slack.urls.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_url("https://t.co/abc")

    assert result == "https://example.com/article"


async def test_resolve_url_timeout_returns_none():
    """resolve_url returns None on timeout."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("knowledge_hub.slack.urls.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_url("https://t.co/abc")

    assert result is None


async def test_resolve_url_too_many_redirects_returns_none():
    """resolve_url returns None on too many redirects."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TooManyRedirects("too many"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("knowledge_hub.slack.urls.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_url("https://t.co/abc")

    assert result is None


async def test_resolve_url_http_error_returns_none():
    """resolve_url returns None on HTTP errors."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=httpx.HTTPError("connection failed")
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("knowledge_hub.slack.urls.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_url("https://t.co/abc")

    assert result is None


# -- resolve_urls tests (INGEST-08) --


async def test_resolve_urls_returns_successful_only():
    """resolve_urls filters out None results from failed resolutions."""

    async def mock_resolve(url: str) -> str | None:
        if url == "https://fail.com":
            return None
        return f"https://resolved-{url.split('//')[1]}"

    with patch("knowledge_hub.slack.urls.resolve_url", side_effect=mock_resolve):
        result = await resolve_urls(
            ["https://a.com", "https://fail.com", "https://b.com"]
        )

    assert result == ["https://resolved-a.com", "https://resolved-b.com"]


async def test_resolve_urls_skips_failures():
    """resolve_urls returns empty list when all URLs fail."""

    async def mock_resolve(url: str) -> str | None:
        return None

    with patch("knowledge_hub.slack.urls.resolve_url", side_effect=mock_resolve):
        result = await resolve_urls(["https://a.com", "https://b.com"])

    assert result == []


async def test_resolve_urls_empty_input():
    """resolve_urls with empty input returns empty list."""
    result = await resolve_urls([])
    assert result == []
