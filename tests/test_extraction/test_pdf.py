"""Tests for PDF extraction (mocked httpx + pypdf)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from knowledge_hub.extraction.pdf import MAX_PDF_SIZE_BYTES, extract_pdf
from knowledge_hub.models.content import ContentType, ExtractionStatus


def _mock_client(head_headers=None, get_content=b"", head_error=False):
    """Build a mocked httpx.AsyncClient context manager."""
    client = AsyncMock()

    if head_error:
        client.head.side_effect = httpx.HTTPError("HEAD failed")
    else:
        head_resp = MagicMock()
        head_resp.headers = head_headers or {}
        client.head.return_value = head_resp

    get_resp = MagicMock()
    get_resp.content = get_content
    get_resp.raise_for_status = MagicMock()
    client.get.return_value = get_resp

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, client


@pytest.mark.asyncio
async def test_extract_pdf_success():
    """Successful PDF extraction returns FULL with text and metadata."""
    mock_ctx, mock_client = _mock_client(
        head_headers={"content-length": "1000"},
        get_content=b"%PDF-fake-content",
    )

    # Mock PdfReader
    page = MagicMock()
    page.extract_text.return_value = "Page one text content here."
    reader = MagicMock()
    reader.pages = [page]
    reader.metadata = SimpleNamespace(title="Test PDF", author="Test Author")

    with (
        patch("knowledge_hub.extraction.pdf.httpx.AsyncClient", return_value=mock_ctx),
        patch("knowledge_hub.extraction.pdf.PdfReader", return_value=reader),
    ):
        result = await extract_pdf("https://example.com/doc.pdf")

    assert result.extraction_status == ExtractionStatus.FULL
    assert result.content_type == ContentType.PDF
    assert result.text == "Page one text content here."
    assert result.title == "Test PDF"
    assert result.author == "Test Author"
    assert result.word_count == 5
    assert result.extraction_method == "pypdf"


@pytest.mark.asyncio
async def test_extract_pdf_too_large_head():
    """HEAD Content-Length exceeding 20MB returns METADATA_ONLY without GET."""
    big_size = str(MAX_PDF_SIZE_BYTES + 1)
    mock_ctx, mock_client = _mock_client(
        head_headers={"content-length": big_size},
    )

    with patch("knowledge_hub.extraction.pdf.httpx.AsyncClient", return_value=mock_ctx):
        result = await extract_pdf("https://example.com/huge.pdf")

    assert result.extraction_status == ExtractionStatus.METADATA_ONLY
    assert "too large" in (result.description or "").lower()
    # GET should not have been called
    mock_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_extract_pdf_too_large_body():
    """GET body exceeding 20MB returns METADATA_ONLY."""
    oversized_body = b"x" * (MAX_PDF_SIZE_BYTES + 1)
    mock_ctx, _ = _mock_client(
        head_error=True,  # HEAD fails, falls through to GET
        get_content=oversized_body,
    )

    with patch("knowledge_hub.extraction.pdf.httpx.AsyncClient", return_value=mock_ctx):
        result = await extract_pdf("https://example.com/big.pdf")

    assert result.extraction_status == ExtractionStatus.METADATA_ONLY


@pytest.mark.asyncio
async def test_extract_pdf_no_text():
    """PDF with empty pages (scanned/image) returns METADATA_ONLY."""
    mock_ctx, _ = _mock_client(
        head_headers={"content-length": "1000"},
        get_content=b"%PDF-fake",
    )

    page = MagicMock()
    page.extract_text.return_value = ""
    reader = MagicMock()
    reader.pages = [page]
    reader.metadata = None

    with (
        patch("knowledge_hub.extraction.pdf.httpx.AsyncClient", return_value=mock_ctx),
        patch("knowledge_hub.extraction.pdf.PdfReader", return_value=reader),
    ):
        result = await extract_pdf("https://example.com/scanned.pdf")

    assert result.extraction_status == ExtractionStatus.METADATA_ONLY
    assert result.text is None


@pytest.mark.asyncio
async def test_extract_pdf_metadata():
    """PDF metadata (title, author) maps to ExtractedContent fields."""
    mock_ctx, _ = _mock_client(
        head_headers={"content-length": "500"},
        get_content=b"%PDF-data",
    )

    page = MagicMock()
    page.extract_text.return_value = "Some text."
    reader = MagicMock()
    reader.pages = [page]
    reader.metadata = SimpleNamespace(title="My Paper", author="Dr. Smith")

    with (
        patch("knowledge_hub.extraction.pdf.httpx.AsyncClient", return_value=mock_ctx),
        patch("knowledge_hub.extraction.pdf.PdfReader", return_value=reader),
    ):
        result = await extract_pdf("https://example.com/paper.pdf")

    assert result.title == "My Paper"
    assert result.author == "Dr. Smith"


@pytest.mark.asyncio
async def test_extract_pdf_download_error():
    """httpx error during download results in FAILED."""
    mock_ctx, mock_client = _mock_client(head_error=True)
    mock_client.get.side_effect = httpx.HTTPError("Connection refused")

    with patch("knowledge_hub.extraction.pdf.httpx.AsyncClient", return_value=mock_ctx):
        result = await extract_pdf("https://example.com/broken.pdf")

    assert result.extraction_status == ExtractionStatus.FAILED
