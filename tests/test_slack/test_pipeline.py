"""Tests for pipeline orchestration (process_message_urls) and stage classification.

Verifies: success path, failed extraction, duplicate URL, LLM exception,
Notion exception, multi-URL success, multi-URL partial failure,
user_note propagation, and _classify_stage logic.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from knowledge_hub.models.content import ContentType, ExtractedContent, ExtractionStatus
from knowledge_hub.notion.models import DuplicateResult, PageResult
from knowledge_hub.slack.handlers import _classify_stage, process_message_urls

CHANNEL = "C0AFQJHAVS6"
TS = "1234567890.123456"
USER = "U_ALLOWED"
TEXT = "<https://example.com>"


# -- Factories --


def _make_content(url: str, status: ExtractionStatus = ExtractionStatus.FULL) -> ExtractedContent:
    """Return a minimal ExtractedContent for testing."""
    return ExtractedContent(
        url=url,
        content_type=ContentType.ARTICLE,
        title="Test",
        text="Body text " * 100,
        word_count=200,
        extraction_status=status,
    )


def _make_page_result(url: str) -> PageResult:
    """Return a PageResult for the given URL."""
    return PageResult(
        page_id="page-123",
        page_url=f"https://notion.so/{url.split('/')[-1]}",
        title="Created Page",
    )


def _make_duplicate_result(url: str) -> DuplicateResult:
    """Return a DuplicateResult for the given URL."""
    return DuplicateResult(
        page_id="dup-123",
        page_url=f"https://notion.so/dup-{url.split('/')[-1]}",
        title="Existing Page",
    )


# -- Pipeline patch targets --

_PATCH_PREFIX = "knowledge_hub.slack.handlers"


def _pipeline_patches():
    """Return a dict of all external calls to patch."""
    return {
        "resolve_urls": AsyncMock(side_effect=lambda urls: urls),
        "extract_content": AsyncMock(),
        "get_gemini_client": MagicMock(return_value=MagicMock()),
        "process_content": AsyncMock(),
        "create_notion_page": AsyncMock(),
        "notify_success": AsyncMock(),
        "notify_error": AsyncMock(),
        "notify_duplicate": AsyncMock(),
        "add_reaction": AsyncMock(),
    }


# -- Success path --


async def test_single_url_success_pipeline():
    """One URL flowing through all stages to success notification."""
    mocks = _pipeline_patches()
    url = "https://example.com/article"
    content = _make_content(url)
    page_result = _make_page_result(url)

    mocks["extract_content"].return_value = content
    mocks["process_content"].return_value = (MagicMock(), 0.001)  # (NotionPage, cost_usd)
    mocks["create_notion_page"].return_value = page_result

    with (
        patch(f"{_PATCH_PREFIX}.resolve_urls", mocks["resolve_urls"]),
        patch(f"{_PATCH_PREFIX}.extract_content", mocks["extract_content"]),
        patch(f"{_PATCH_PREFIX}.get_gemini_client", mocks["get_gemini_client"]),
        patch(f"{_PATCH_PREFIX}.process_content", mocks["process_content"]),
        patch(f"{_PATCH_PREFIX}.create_notion_page", mocks["create_notion_page"]),
        patch(f"{_PATCH_PREFIX}.notify_success", mocks["notify_success"]),
        patch(f"{_PATCH_PREFIX}.notify_error", mocks["notify_error"]),
        patch(f"{_PATCH_PREFIX}.notify_duplicate", mocks["notify_duplicate"]),
        patch(f"{_PATCH_PREFIX}.add_reaction", mocks["add_reaction"]),
    ):
        await process_message_urls(CHANNEL, TS, USER, TEXT, [url], None)

    mocks["extract_content"].assert_called_once()
    mocks["process_content"].assert_called_once()
    mocks["create_notion_page"].assert_called_once()
    mocks["notify_success"].assert_called_once_with(CHANNEL, TS, page_result, cost_usd=0.001)
    mocks["add_reaction"].assert_called_once_with(CHANNEL, TS, "white_check_mark")


# -- Failed extraction --


async def test_single_url_failed_extraction():
    """Failed extraction skips LLM/Notion stages, sends error notification."""
    mocks = _pipeline_patches()
    url = "https://example.com/broken"
    content = _make_content(url, status=ExtractionStatus.FAILED)

    mocks["extract_content"].return_value = content

    with (
        patch(f"{_PATCH_PREFIX}.resolve_urls", mocks["resolve_urls"]),
        patch(f"{_PATCH_PREFIX}.extract_content", mocks["extract_content"]),
        patch(f"{_PATCH_PREFIX}.get_gemini_client", mocks["get_gemini_client"]),
        patch(f"{_PATCH_PREFIX}.process_content", mocks["process_content"]),
        patch(f"{_PATCH_PREFIX}.create_notion_page", mocks["create_notion_page"]),
        patch(f"{_PATCH_PREFIX}.notify_success", mocks["notify_success"]),
        patch(f"{_PATCH_PREFIX}.notify_error", mocks["notify_error"]),
        patch(f"{_PATCH_PREFIX}.notify_duplicate", mocks["notify_duplicate"]),
        patch(f"{_PATCH_PREFIX}.add_reaction", mocks["add_reaction"]),
    ):
        await process_message_urls(CHANNEL, TS, USER, TEXT, [url], None)

    mocks["process_content"].assert_not_called()
    mocks["create_notion_page"].assert_not_called()
    mocks["notify_error"].assert_called_once()
    assert mocks["notify_error"].call_args.args[3] == "extraction"
    mocks["add_reaction"].assert_called_once_with(CHANNEL, TS, "x")


# -- Duplicate URL --


async def test_single_url_duplicate():
    """Duplicate URL sends duplicate notification, not error. Treated as non-failure."""
    mocks = _pipeline_patches()
    url = "https://example.com/existing"
    content = _make_content(url)
    dup = _make_duplicate_result(url)

    mocks["extract_content"].return_value = content
    mocks["process_content"].return_value = (MagicMock(), 0.001)  # (NotionPage, cost_usd)
    mocks["create_notion_page"].return_value = dup

    with (
        patch(f"{_PATCH_PREFIX}.resolve_urls", mocks["resolve_urls"]),
        patch(f"{_PATCH_PREFIX}.extract_content", mocks["extract_content"]),
        patch(f"{_PATCH_PREFIX}.get_gemini_client", mocks["get_gemini_client"]),
        patch(f"{_PATCH_PREFIX}.process_content", mocks["process_content"]),
        patch(f"{_PATCH_PREFIX}.create_notion_page", mocks["create_notion_page"]),
        patch(f"{_PATCH_PREFIX}.notify_success", mocks["notify_success"]),
        patch(f"{_PATCH_PREFIX}.notify_error", mocks["notify_error"]),
        patch(f"{_PATCH_PREFIX}.notify_duplicate", mocks["notify_duplicate"]),
        patch(f"{_PATCH_PREFIX}.add_reaction", mocks["add_reaction"]),
    ):
        await process_message_urls(CHANNEL, TS, USER, TEXT, [url], None)

    mocks["notify_duplicate"].assert_called_once_with(CHANNEL, TS, url, dup)
    mocks["notify_success"].assert_not_called()
    # Duplicate is not a failure -- checkmark reaction
    mocks["add_reaction"].assert_called_once_with(CHANNEL, TS, "white_check_mark")


# -- LLM exception --


async def test_single_url_llm_exception():
    """process_content raising sends error notification and X reaction."""
    mocks = _pipeline_patches()
    url = "https://example.com/article"
    content = _make_content(url)

    mocks["extract_content"].return_value = content
    mocks["process_content"].side_effect = RuntimeError("LLM failed")

    with (
        patch(f"{_PATCH_PREFIX}.resolve_urls", mocks["resolve_urls"]),
        patch(f"{_PATCH_PREFIX}.extract_content", mocks["extract_content"]),
        patch(f"{_PATCH_PREFIX}.get_gemini_client", mocks["get_gemini_client"]),
        patch(f"{_PATCH_PREFIX}.process_content", mocks["process_content"]),
        patch(f"{_PATCH_PREFIX}.create_notion_page", mocks["create_notion_page"]),
        patch(f"{_PATCH_PREFIX}.notify_success", mocks["notify_success"]),
        patch(f"{_PATCH_PREFIX}.notify_error", mocks["notify_error"]),
        patch(f"{_PATCH_PREFIX}.notify_duplicate", mocks["notify_duplicate"]),
        patch(f"{_PATCH_PREFIX}.add_reaction", mocks["add_reaction"]),
    ):
        await process_message_urls(CHANNEL, TS, USER, TEXT, [url], None)

    mocks["notify_error"].assert_called_once()
    mocks["add_reaction"].assert_called_once_with(CHANNEL, TS, "x")


# -- Notion exception --


async def test_single_url_notion_exception():
    """create_notion_page raising sends error notification and X reaction."""
    mocks = _pipeline_patches()
    url = "https://example.com/article"
    content = _make_content(url)

    mocks["extract_content"].return_value = content
    mocks["process_content"].return_value = (MagicMock(), 0.001)  # (NotionPage, cost_usd)
    mocks["create_notion_page"].side_effect = RuntimeError("Notion API failed")

    with (
        patch(f"{_PATCH_PREFIX}.resolve_urls", mocks["resolve_urls"]),
        patch(f"{_PATCH_PREFIX}.extract_content", mocks["extract_content"]),
        patch(f"{_PATCH_PREFIX}.get_gemini_client", mocks["get_gemini_client"]),
        patch(f"{_PATCH_PREFIX}.process_content", mocks["process_content"]),
        patch(f"{_PATCH_PREFIX}.create_notion_page", mocks["create_notion_page"]),
        patch(f"{_PATCH_PREFIX}.notify_success", mocks["notify_success"]),
        patch(f"{_PATCH_PREFIX}.notify_error", mocks["notify_error"]),
        patch(f"{_PATCH_PREFIX}.notify_duplicate", mocks["notify_duplicate"]),
        patch(f"{_PATCH_PREFIX}.add_reaction", mocks["add_reaction"]),
    ):
        await process_message_urls(CHANNEL, TS, USER, TEXT, [url], None)

    mocks["notify_error"].assert_called_once()
    mocks["add_reaction"].assert_called_once_with(CHANNEL, TS, "x")


# -- Multi-URL success --


async def test_multi_url_all_succeed():
    """Two URLs both succeed: notify_success called twice, checkmark reaction."""
    mocks = _pipeline_patches()
    urls = ["https://example.com/a", "https://example.com/b"]

    mocks["extract_content"].side_effect = [_make_content(u) for u in urls]
    mocks["process_content"].return_value = (MagicMock(), 0.001)  # (NotionPage, cost_usd)
    mocks["create_notion_page"].side_effect = [_make_page_result(u) for u in urls]

    with (
        patch(f"{_PATCH_PREFIX}.resolve_urls", mocks["resolve_urls"]),
        patch(f"{_PATCH_PREFIX}.extract_content", mocks["extract_content"]),
        patch(f"{_PATCH_PREFIX}.get_gemini_client", mocks["get_gemini_client"]),
        patch(f"{_PATCH_PREFIX}.process_content", mocks["process_content"]),
        patch(f"{_PATCH_PREFIX}.create_notion_page", mocks["create_notion_page"]),
        patch(f"{_PATCH_PREFIX}.notify_success", mocks["notify_success"]),
        patch(f"{_PATCH_PREFIX}.notify_error", mocks["notify_error"]),
        patch(f"{_PATCH_PREFIX}.notify_duplicate", mocks["notify_duplicate"]),
        patch(f"{_PATCH_PREFIX}.add_reaction", mocks["add_reaction"]),
    ):
        await process_message_urls(CHANNEL, TS, USER, TEXT, urls, None)

    assert mocks["notify_success"].call_count == 2
    mocks["add_reaction"].assert_called_once_with(CHANNEL, TS, "white_check_mark")


# -- Multi-URL partial failure --


async def test_multi_url_partial_failure():
    """First URL succeeds, second fails extraction: mixed notifications, X reaction."""
    mocks = _pipeline_patches()
    urls = ["https://example.com/good", "https://example.com/bad"]

    mocks["extract_content"].side_effect = [
        _make_content(urls[0]),
        _make_content(urls[1], status=ExtractionStatus.FAILED),
    ]
    mocks["process_content"].return_value = (MagicMock(), 0.001)  # (NotionPage, cost_usd)
    mocks["create_notion_page"].return_value = _make_page_result(urls[0])

    with (
        patch(f"{_PATCH_PREFIX}.resolve_urls", mocks["resolve_urls"]),
        patch(f"{_PATCH_PREFIX}.extract_content", mocks["extract_content"]),
        patch(f"{_PATCH_PREFIX}.get_gemini_client", mocks["get_gemini_client"]),
        patch(f"{_PATCH_PREFIX}.process_content", mocks["process_content"]),
        patch(f"{_PATCH_PREFIX}.create_notion_page", mocks["create_notion_page"]),
        patch(f"{_PATCH_PREFIX}.notify_success", mocks["notify_success"]),
        patch(f"{_PATCH_PREFIX}.notify_error", mocks["notify_error"]),
        patch(f"{_PATCH_PREFIX}.notify_duplicate", mocks["notify_duplicate"]),
        patch(f"{_PATCH_PREFIX}.add_reaction", mocks["add_reaction"]),
    ):
        await process_message_urls(CHANNEL, TS, USER, TEXT, urls, None)

    mocks["notify_success"].assert_called_once()
    mocks["notify_error"].assert_called_once()
    mocks["add_reaction"].assert_called_once_with(CHANNEL, TS, "x")


# -- user_note propagation --


async def test_user_note_passed_to_content():
    """user_note is set on ExtractedContent before process_content sees it."""
    mocks = _pipeline_patches()
    url = "https://example.com/noted"
    content = _make_content(url)

    mocks["extract_content"].return_value = content
    mocks["process_content"].return_value = (MagicMock(), 0.001)  # (NotionPage, cost_usd)
    mocks["create_notion_page"].return_value = _make_page_result(url)

    captured_content = None

    async def capture_process(client, c):  # noqa: ARG001
        nonlocal captured_content
        captured_content = c
        return (MagicMock(), 0.001)  # (NotionPage, cost_usd)

    mocks["process_content"].side_effect = capture_process

    with (
        patch(f"{_PATCH_PREFIX}.resolve_urls", mocks["resolve_urls"]),
        patch(f"{_PATCH_PREFIX}.extract_content", mocks["extract_content"]),
        patch(f"{_PATCH_PREFIX}.get_gemini_client", mocks["get_gemini_client"]),
        patch(f"{_PATCH_PREFIX}.process_content", mocks["process_content"]),
        patch(f"{_PATCH_PREFIX}.create_notion_page", mocks["create_notion_page"]),
        patch(f"{_PATCH_PREFIX}.notify_success", mocks["notify_success"]),
        patch(f"{_PATCH_PREFIX}.notify_error", mocks["notify_error"]),
        patch(f"{_PATCH_PREFIX}.notify_duplicate", mocks["notify_duplicate"]),
        patch(f"{_PATCH_PREFIX}.add_reaction", mocks["add_reaction"]),
    ):
        await process_message_urls(CHANNEL, TS, USER, TEXT, [url], "context here")

    assert captured_content is not None
    assert captured_content.user_note == "context here"


# -- _classify_stage tests --


def test_classify_stage_extraction():
    """Exception from extraction module classified as 'extraction'."""

    class ExtErr(Exception):
        pass

    ExtErr.__module__ = "knowledge_hub.extraction.client"
    assert _classify_stage(ExtErr()) == "extraction"


def test_classify_stage_llm():
    """Exception from genai module classified as 'llm'."""

    class GenaiErr(Exception):
        pass

    GenaiErr.__module__ = "google.genai.errors"
    assert _classify_stage(GenaiErr()) == "llm"


def test_classify_stage_notion():
    """Exception from notion module classified as 'notion'."""

    class NotionErr(Exception):
        pass

    NotionErr.__module__ = "knowledge_hub.notion.client"
    assert _classify_stage(NotionErr()) == "notion"


def test_classify_stage_unknown():
    """Builtin exception classified as generic 'processing'."""
    assert _classify_stage(RuntimeError("boom")) == "processing"
