"""Processor tests with mocked Gemini client."""

from unittest.mock import AsyncMock, patch

import pytest

from google.genai.errors import ClientError, ServerError

from knowledge_hub.llm.processor import _is_retryable, build_notion_page, process_content
from knowledge_hub.llm.schemas import LLMKeyLearning, LLMResponse
from knowledge_hub.models.content import ContentType, ExtractedContent, ExtractionStatus
from knowledge_hub.models.knowledge import Category, Priority, Status
from knowledge_hub.models.notion import NotionPage


def _make_mock_llm_response() -> LLMResponse:
    """Return a valid LLMResponse instance for processor tests."""
    return LLMResponse(
        title="Understanding RAG Pipelines",
        summary="A comprehensive guide to building RAG pipelines.",
        category=Category.ENGINEERING,
        priority=Priority.HIGH,
        tags=["engineering", "llms", "architecture"],
        summary_section="This article covers RAG pipeline design fundamentals.",
        key_points=[
            "RAG reduces hallucinations",
            "Chunk size affects quality",
            "Embedding model choice matters",
            "Hybrid search is effective",
            "Re-ranking improves precision",
        ],
        key_learnings=[
            LLMKeyLearning(
                what="Chunk overlap improves context",
                why_it_matters="Prevents context loss at boundaries",
                how_to_apply=["Set overlap to 10-20%"],
            ),
            LLMKeyLearning(
                what="Hybrid search outperforms dense-only",
                why_it_matters="Keyword matching catches exact terms",
                how_to_apply=["Combine BM25 with vector search"],
            ),
            LLMKeyLearning(
                what="Re-ranking is worth the latency",
                why_it_matters="Cross-encoder improves precision by 15-20%",
                how_to_apply=["Add re-ranker after retrieval"],
            ),
        ],
        detailed_notes="## RAG Architecture\n\nDetailed breakdown...",
    )


def _make_content(**kwargs) -> ExtractedContent:
    """Return a valid ExtractedContent with sensible defaults, override via kwargs."""
    defaults = {
        "url": "https://example.com/rag-guide",
        "content_type": ContentType.ARTICLE,
        "title": "RAG Pipelines Guide",
        "author": "Jane Doe",
        "source_domain": "example.com",
        "text": "Full article body about RAG pipelines. " * 50,
        "word_count": 1000,
        "extraction_status": ExtractionStatus.FULL,
    }
    defaults.update(kwargs)
    return ExtractedContent(**defaults)


# --- process_content tests ---


@pytest.mark.asyncio
async def test_process_content_returns_notion_page():
    """Mock _call_gemini, verify NotionPage has correct entry fields."""
    mock_response = _make_mock_llm_response()
    content = _make_content()

    with patch(
        "knowledge_hub.llm.processor._call_gemini",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await process_content(AsyncMock(), content)

    assert isinstance(result, NotionPage)
    assert result.entry.title == "Understanding RAG Pipelines"
    assert result.entry.category == Category.ENGINEERING
    assert result.entry.source == "https://example.com/rag-guide"
    assert result.entry.status == Status.NEW
    assert result.entry.content_type == ContentType.ARTICLE


@pytest.mark.asyncio
async def test_process_content_maps_key_learnings():
    """Verify LLMKeyLearning objects are mapped to KeyLearning in NotionPage."""
    mock_response = _make_mock_llm_response()
    content = _make_content()

    with patch(
        "knowledge_hub.llm.processor._call_gemini",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await process_content(AsyncMock(), content)

    assert len(result.key_learnings) == 3
    assert result.key_learnings[0].what == "Chunk overlap improves context"
    assert result.key_learnings[0].why_it_matters == "Prevents context loss at boundaries"
    assert result.key_learnings[0].how_to_apply == ["Set overlap to 10-20%"]


@pytest.mark.asyncio
async def test_process_content_partial_extraction_overrides_priority():
    """Content with ExtractionStatus.PARTIAL gets Priority.LOW."""
    mock_response = _make_mock_llm_response()
    assert mock_response.priority == Priority.HIGH  # LLM assigns HIGH

    content = _make_content(extraction_status=ExtractionStatus.PARTIAL)

    with patch(
        "knowledge_hub.llm.processor._call_gemini",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await process_content(AsyncMock(), content)

    assert result.entry.priority == Priority.LOW


@pytest.mark.asyncio
async def test_process_content_metadata_only_overrides_priority():
    """Content with ExtractionStatus.METADATA_ONLY gets Priority.LOW."""
    mock_response = _make_mock_llm_response()
    content = _make_content(extraction_status=ExtractionStatus.METADATA_ONLY)

    with patch(
        "knowledge_hub.llm.processor._call_gemini",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await process_content(AsyncMock(), content)

    assert result.entry.priority == Priority.LOW


@pytest.mark.asyncio
async def test_process_content_full_extraction_preserves_priority():
    """Content with ExtractionStatus.FULL keeps LLM-assigned priority."""
    mock_response = _make_mock_llm_response()
    content = _make_content(extraction_status=ExtractionStatus.FULL)

    with patch(
        "knowledge_hub.llm.processor._call_gemini",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await process_content(AsyncMock(), content)

    assert result.entry.priority == Priority.HIGH


@pytest.mark.asyncio
async def test_process_content_uses_video_prompt():
    """Mock build_system_prompt, verify it's called with video content."""
    mock_response = _make_mock_llm_response()
    content = _make_content(content_type=ContentType.VIDEO, word_count=5000)

    with (
        patch(
            "knowledge_hub.llm.processor._call_gemini",
            new_callable=AsyncMock,
            return_value=mock_response,
        ),
        patch("knowledge_hub.llm.processor.build_system_prompt") as mock_prompt,
    ):
        mock_prompt.return_value = "system prompt"
        await process_content(AsyncMock(), content)
        mock_prompt.assert_called_once_with(content)
        assert mock_prompt.call_args[0][0].content_type == ContentType.VIDEO


# --- build_notion_page tests ---


def test_build_notion_page_sets_status_new():
    """Verify entry.status is always Status.NEW."""
    llm_result = _make_mock_llm_response()
    content = _make_content()
    page = build_notion_page(llm_result, content)
    assert page.entry.status == Status.NEW


def test_build_notion_page_uses_extraction_source():
    """Verify entry.source == content.url (not LLM-generated)."""
    llm_result = _make_mock_llm_response()
    content = _make_content(url="https://custom-source.com/article")
    page = build_notion_page(llm_result, content)
    assert page.entry.source == "https://custom-source.com/article"


def test_build_notion_page_uses_extraction_content_type():
    """Verify entry.content_type == content.content_type."""
    llm_result = _make_mock_llm_response()
    content = _make_content(content_type=ContentType.VIDEO)
    page = build_notion_page(llm_result, content)
    assert page.entry.content_type == ContentType.VIDEO


# --- _is_retryable tests ---


def test_is_retryable_server_error():
    """ServerError returns True."""
    error = ServerError(500, "internal server error")
    assert _is_retryable(error) is True


def test_is_retryable_rate_limit():
    """ClientError(429) returns True."""
    error = ClientError(429, "rate limit exceeded")
    assert _is_retryable(error) is True


def test_is_retryable_bad_request():
    """ClientError(400) returns False."""
    error = ClientError(400, "bad request")
    assert _is_retryable(error) is False


def test_is_retryable_auth_error():
    """ClientError(401) returns False."""
    error = ClientError(401, "unauthorized")
    assert _is_retryable(error) is False
