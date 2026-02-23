"""YouTube transcript extraction using youtube-transcript-api."""

import asyncio
import logging
import re

import httpx

logger = logging.getLogger(__name__)

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    InvalidVideoId,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)
from youtube_transcript_api.proxies import GenericProxyConfig

from knowledge_hub.config import get_settings
from knowledge_hub.models.content import ContentType, ExtractedContent, ExtractionStatus

# Comprehensive regex for all YouTube URL formats
VIDEO_ID_PATTERN = re.compile(
    r"(?:youtube\.com/(?:watch\?.*v=|shorts/|embed/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)


def extract_video_id(url: str) -> str | None:
    """Extract the 11-character video ID from a YouTube URL.

    Handles: youtube.com/watch?v=, youtu.be/, youtube.com/shorts/, youtube.com/embed/
    Also handles URLs with additional query params (e.g., &t=123, &list=PLxxx).
    """
    match = VIDEO_ID_PATTERN.search(url)
    return match.group(1) if match else None


async def extract_youtube(url: str) -> ExtractedContent:
    """Extract YouTube transcript and metadata.

    Uses YouTubeTranscriptApi instance fetch() method (not deprecated static methods).
    All sync calls wrapped in asyncio.to_thread().

    Returns ExtractedContent with:
    - FULL: transcript extracted successfully
    - METADATA_ONLY: captions disabled or not found (TranscriptsDisabled, NoTranscriptFound)
    - FAILED: video unavailable, invalid ID, or no video ID in URL
    """
    video_id = extract_video_id(url)
    if video_id is None:
        return ExtractedContent(
            url=url,
            content_type=ContentType.VIDEO,
            source_domain="youtube.com",
            extraction_status=ExtractionStatus.FAILED,
            extraction_method="youtube-transcript-api",
        )

    # Always fetch page metadata (title, author, description)
    title, author, description = await _fetch_youtube_metadata(url)

    proxy_url = get_settings().youtube_proxy_url
    proxy_config = GenericProxyConfig(https_url=proxy_url) if proxy_url else None
    ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)
    try:
        # Sync call wrapped in to_thread
        transcript = await asyncio.to_thread(
            ytt_api.fetch, video_id, languages=["en"]
        )
        text = " ".join(snippet.text for snippet in transcript)
        word_count = len(text.split()) if text else None

        return ExtractedContent(
            url=url,
            content_type=ContentType.VIDEO,
            title=title,
            author=author,
            description=description,
            transcript=text,
            source_domain="youtube.com",
            word_count=word_count,
            extraction_method="youtube-transcript-api",
            extraction_status=ExtractionStatus.FULL,
        )
    except (TranscriptsDisabled, NoTranscriptFound):
        # Fallback: metadata-only (captions unavailable)
        return ExtractedContent(
            url=url,
            content_type=ContentType.VIDEO,
            title=title,
            author=author,
            description=description,
            transcript=None,
            source_domain="youtube.com",
            extraction_method="youtube-transcript-api",
            extraction_status=ExtractionStatus.METADATA_ONLY,
        )
    except (VideoUnavailable, InvalidVideoId):
        return ExtractedContent(
            url=url,
            content_type=ContentType.VIDEO,
            source_domain="youtube.com",
            extraction_method="youtube-transcript-api",
            extraction_status=ExtractionStatus.FAILED,
        )
    except Exception as exc:
        # Catch-all for IP blocks, request errors, etc.
        logger.warning("Transcript extraction failed (will use Gemini fallback): %s (%s)", url, exc)
        return ExtractedContent(
            url=url,
            content_type=ContentType.VIDEO,
            title=title,
            author=author,
            description=description,
            transcript=None,
            source_domain="youtube.com",
            extraction_method="youtube-transcript-api-fallback",
            extraction_status=ExtractionStatus.METADATA_ONLY,
        )


async def _fetch_youtube_metadata(url: str) -> tuple[str | None, str | None, str | None]:
    """Fetch title, author, and description from YouTube page HTML.

    Tries multiple selectors for each field since YouTube's HTML changes frequently.

    Returns:
        Tuple of (title, author, description). Any field may be None.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

        title = None
        author = None
        description = None

        # Title: og:title is most reliable
        m = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        if m:
            title = m.group(1)

        # Author: try multiple patterns (YouTube HTML changes frequently)
        # JSON patterns first — unambiguously refer to the channel.
        # itemprop="name" is last resort since first match is often the video title.
        author_patterns = [
            r'"ownerChannelName":"([^"]*)"',
            r'"author":"([^"]*)"',
            r'"channelName":"([^"]*)"',
            r'<meta name="author" content="([^"]*)"',
            r'<link itemprop="name" content="([^"]*)"',
        ]
        for pattern in author_patterns:
            m = re.search(pattern, html)
            if m and m.group(1):
                author = m.group(1)
                break

        # Description: og:description
        m = re.search(r'<meta property="og:description" content="([^"]*)"', html)
        if m:
            description = m.group(1)

        return title, author, description
    except Exception:
        logger.debug("Failed to fetch YouTube page metadata for %s", url, exc_info=True)
        return None, None, None
