"""Tests for article extraction using trafilatura (mocked)."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from knowledge_hub.extraction.article import extract_article
from knowledge_hub.models.content import ContentType, ExtractionStatus


@pytest.mark.asyncio
async def test_extract_article_success():
    """Successful extraction maps trafilatura fields to ExtractedContent."""
    fake_doc = SimpleNamespace(
        text="This is the full article body text with enough words to pass.",
        title="Test Article",
        author="Jane Doe",
        date="2026-01-15",
        sitename="example.com",
        hostname="example.com",
        description="A test article description.",
    )
    with (
        patch("knowledge_hub.extraction.article.fetch_url", return_value="<html>ok</html>"),
        patch("knowledge_hub.extraction.article.bare_extraction", return_value=fake_doc),
    ):
        result = await extract_article("https://example.com/article")

    assert result.extraction_status == ExtractionStatus.FULL
    assert result.content_type == ContentType.ARTICLE
    assert result.title == "Test Article"
    assert result.author == "Jane Doe"
    assert result.published_date == "2026-01-15"
    assert result.source_domain == "example.com"
    assert result.text == fake_doc.text
    assert result.extraction_method == "trafilatura"


@pytest.mark.asyncio
async def test_extract_article_fetch_fails():
    """fetch_url returning None results in FAILED status."""
    with patch("knowledge_hub.extraction.article.fetch_url", return_value=None):
        result = await extract_article("https://example.com/broken")

    assert result.extraction_status == ExtractionStatus.FAILED
    assert result.content_type == ContentType.ARTICLE


@pytest.mark.asyncio
async def test_extract_article_extraction_fails():
    """bare_extraction returning None results in METADATA_ONLY status."""
    with (
        patch("knowledge_hub.extraction.article.fetch_url", return_value="<html>ok</html>"),
        patch("knowledge_hub.extraction.article.bare_extraction", return_value=None),
    ):
        result = await extract_article("https://example.com/empty")

    assert result.extraction_status == ExtractionStatus.METADATA_ONLY


@pytest.mark.asyncio
async def test_extract_article_word_count():
    """word_count is calculated from extracted text."""
    fake_doc = SimpleNamespace(
        text="one two three four five",
        title=None,
        author=None,
        date=None,
        sitename=None,
        hostname=None,
        description=None,
    )
    with (
        patch("knowledge_hub.extraction.article.fetch_url", return_value="<html>ok</html>"),
        patch("knowledge_hub.extraction.article.bare_extraction", return_value=fake_doc),
    ):
        result = await extract_article("https://example.com/short")

    assert result.word_count == 5


@pytest.mark.asyncio
async def test_extract_article_paywalled_domain():
    """Paywalled domain with short text results in PARTIAL status."""
    # Short text (< 200 words) on a known paywalled domain
    fake_doc = SimpleNamespace(
        text="Short paywall teaser text only.",
        title="Premium Article",
        author=None,
        date=None,
        sitename="nytimes.com",
        hostname="nytimes.com",
        description=None,
    )
    with (
        patch("knowledge_hub.extraction.article.fetch_url", return_value="<html>ok</html>"),
        patch("knowledge_hub.extraction.article.bare_extraction", return_value=fake_doc),
        patch("knowledge_hub.extraction.article.is_paywalled_domain", return_value=True),
    ):
        result = await extract_article("https://www.nytimes.com/article")

    assert result.extraction_status == ExtractionStatus.PARTIAL
