"""Timeout-guarded extraction pipeline with retry logic."""

import asyncio
import logging
import time

import httpx

from knowledge_hub.extraction.article import extract_article
from knowledge_hub.extraction.pdf import extract_pdf
from knowledge_hub.extraction.router import detect_content_type
from knowledge_hub.extraction.youtube import extract_youtube
from knowledge_hub.models.content import ContentType, ExtractedContent, ExtractionStatus

logger = logging.getLogger(__name__)

# Minimum remaining time (seconds) to attempt a retry
_RETRY_MIN_REMAINING = 3.0


async def extract_with_timeout(
    url: str, timeout_seconds: float = 30.0
) -> ExtractedContent:
    """Extract content from a URL within a wall-clock timeout budget.

    Wraps the full extraction pipeline in asyncio.timeout(). If the pipeline
    exceeds the budget, returns ExtractedContent with FAILED status instead
    of raising an exception.
    """
    try:
        async with asyncio.timeout(timeout_seconds):
            return await _extract_pipeline(url, timeout_seconds)
    except TimeoutError:
        logger.warning("Extraction timed out after %.1fs: %s", timeout_seconds, url)
        return ExtractedContent(
            url=url,
            content_type=detect_content_type(url),
            extraction_status=ExtractionStatus.FAILED,
            extraction_method="timeout",
        )


async def _extract_pipeline(url: str, timeout_seconds: float) -> ExtractedContent:
    """Route URL to the appropriate extractor with one retry on transient failures.

    Retry logic:
    - One retry on transient failures (network errors, connection issues).
    - Permanent failures (TranscriptsDisabled, VideoUnavailable, etc.) are NOT retried.
    - Retry only attempted if >= 3 seconds remain in the timeout budget.
    """
    content_type = detect_content_type(url)
    deadline = time.monotonic() + timeout_seconds

    try:
        return await _dispatch(url, content_type)
    except _TRANSIENT_ERRORS as exc:
        remaining = deadline - time.monotonic()
        if remaining < _RETRY_MIN_REMAINING:
            logger.warning(
                "Transient error with <%.1fs remaining, skipping retry: %s (%s)",
                _RETRY_MIN_REMAINING,
                url,
                exc,
            )
            return ExtractedContent(
                url=url,
                content_type=content_type,
                extraction_status=ExtractionStatus.FAILED,
                extraction_method="retry-exhausted",
            )

        logger.info(
            "Transient error, retrying (%.1fs remaining): %s (%s)",
            remaining,
            url,
            exc,
        )
        try:
            return await _dispatch(url, content_type)
        except _TRANSIENT_ERRORS as retry_exc:
            logger.warning("Retry also failed: %s (%s)", url, retry_exc)
            return ExtractedContent(
                url=url,
                content_type=content_type,
                extraction_status=ExtractionStatus.FAILED,
                extraction_method="retry-exhausted",
            )


async def _dispatch(url: str, content_type: ContentType) -> ExtractedContent:
    """Dispatch to the correct extractor based on content type."""
    if content_type == ContentType.VIDEO:
        return await extract_youtube(url)
    if content_type == ContentType.PDF:
        return await extract_pdf(url)
    # ARTICLE, NEWSLETTER, and any other type use the article extractor
    return await extract_article(url)


# Transient (retryable) error types
_TRANSIENT_ERRORS = (httpx.HTTPError, ConnectionError, OSError)
