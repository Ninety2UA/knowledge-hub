"""URL extraction, user note extraction, and redirect resolution for Slack messages."""

import asyncio
import logging
import re

import httpx

logger = logging.getLogger(__name__)

# Matches Slack mrkdwn URL format: <https://example.com> or <https://example.com|label>
# Does NOT match user refs <@U123>, channel refs <#C123>, or special mentions <!here>
SLACK_URL_PATTERN = re.compile(r"<(https?://[^|>]+)(?:\|[^>]*)?>")


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from Slack mrkdwn text.

    Handles both <url> and <url|label> formats. Excludes user mentions,
    channel references, and special mentions.
    """
    return SLACK_URL_PATTERN.findall(text)


def extract_user_note(text: str) -> str | None:
    """Extract non-URL text from a Slack message as the user note.

    Removes all URL markup (<url> and <url|label>) from the text,
    strips whitespace, and returns None if nothing remains.
    """
    cleaned = SLACK_URL_PATTERN.sub("", text).strip()
    return cleaned if cleaned else None


async def resolve_url(url: str) -> str | None:
    """Resolve a single URL through redirects to its final destination.

    Uses GET (not HEAD -- some shorteners reject HEAD requests).
    Returns the final URL string on success, None on any error.
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=5,
            timeout=httpx.Timeout(10.0),
        ) as client:
            response = await client.get(url)
            return str(response.url)
    except (httpx.HTTPError, httpx.TooManyRedirects):
        logger.warning("Failed to resolve URL: %s", url)
        return None


async def resolve_urls(urls: list[str]) -> list[str]:
    """Resolve all URLs in parallel, filtering out failures.

    Returns only successfully resolved URLs (skips None and exceptions).
    """
    results = await asyncio.gather(
        *[resolve_url(u) for u in urls],
        return_exceptions=True,
    )
    return [r for r in results if isinstance(r, str)]
