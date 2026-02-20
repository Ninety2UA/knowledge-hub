"""Pipeline integration tests with mocked extractors."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from youtube_transcript_api._errors import TranscriptsDisabled

from knowledge_hub.extraction.timeout import extract_with_timeout
from knowledge_hub.models.content import ContentType, ExtractedContent, ExtractionStatus


def _ok_result(url: str, content_type: ContentType) -> ExtractedContent:
    """Build a successful ExtractedContent for test assertions."""
    return ExtractedContent(
        url=url,
        content_type=content_type,
        extraction_status=ExtractionStatus.FULL,
        extraction_method="test",
    )


@pytest.mark.asyncio
async def test_pipeline_routes_youtube():
    """YouTube URL dispatches to extract_youtube."""
    url = "https://www.youtube.com/watch?v=abc123abc12"
    mock_yt = AsyncMock(return_value=_ok_result(url, ContentType.VIDEO))

    with patch("knowledge_hub.extraction.timeout.extract_youtube", mock_yt):
        result = await extract_with_timeout(url)

    mock_yt.assert_awaited_once_with(url)
    assert result.content_type == ContentType.VIDEO


@pytest.mark.asyncio
async def test_pipeline_routes_pdf():
    """PDF URL dispatches to extract_pdf."""
    url = "https://example.com/doc.pdf"
    mock_pdf = AsyncMock(return_value=_ok_result(url, ContentType.PDF))

    with patch("knowledge_hub.extraction.timeout.extract_pdf", mock_pdf):
        result = await extract_with_timeout(url)

    mock_pdf.assert_awaited_once_with(url)
    assert result.content_type == ContentType.PDF


@pytest.mark.asyncio
async def test_pipeline_routes_article():
    """Generic URL dispatches to extract_article."""
    url = "https://example.com/blog-post"
    mock_article = AsyncMock(return_value=_ok_result(url, ContentType.ARTICLE))

    with patch("knowledge_hub.extraction.timeout.extract_article", mock_article):
        result = await extract_with_timeout(url)

    mock_article.assert_awaited_once_with(url)
    assert result.content_type == ContentType.ARTICLE


@pytest.mark.asyncio
async def test_pipeline_timeout():
    """Extractor exceeding timeout returns FAILED with method='timeout'."""

    async def slow_extractor(url):
        await asyncio.sleep(10)
        return _ok_result(url, ContentType.ARTICLE)

    url = "https://example.com/slow"
    with patch("knowledge_hub.extraction.timeout.extract_article", side_effect=slow_extractor):
        result = await extract_with_timeout(url, timeout_seconds=0.1)

    assert result.extraction_status == ExtractionStatus.FAILED
    assert result.extraction_method == "timeout"


@pytest.mark.asyncio
async def test_pipeline_retry_on_transient_error():
    """Transient error on first attempt triggers retry, second attempt succeeds."""
    url = "https://example.com/flaky"
    ok = _ok_result(url, ContentType.ARTICLE)
    mock_article = AsyncMock(side_effect=[httpx.HTTPError("network glitch"), ok])

    with patch("knowledge_hub.extraction.timeout.extract_article", mock_article):
        result = await extract_with_timeout(url, timeout_seconds=30.0)

    assert result.extraction_status == ExtractionStatus.FULL
    assert mock_article.await_count == 2


@pytest.mark.asyncio
async def test_pipeline_no_retry_on_permanent_error():
    """Permanent error (TranscriptsDisabled) is not retried -- extractor handles it."""
    url = "https://www.youtube.com/watch?v=abc123abc12"
    # TranscriptsDisabled is caught inside extract_youtube, not in the pipeline.
    # The pipeline only sees the returned ExtractedContent.
    metadata_result = ExtractedContent(
        url=url,
        content_type=ContentType.VIDEO,
        extraction_status=ExtractionStatus.METADATA_ONLY,
        extraction_method="youtube-transcript-api",
    )
    mock_yt = AsyncMock(return_value=metadata_result)

    with patch("knowledge_hub.extraction.timeout.extract_youtube", mock_yt):
        result = await extract_with_timeout(url)

    assert result.extraction_status == ExtractionStatus.METADATA_ONLY
    # Only called once -- no retry since extractor returned normally
    mock_yt.assert_awaited_once_with(url)
