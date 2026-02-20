"""PDF download and text extraction using pypdf."""

import asyncio
from io import BytesIO
from urllib.parse import urlparse

import httpx
from pypdf import PdfReader

from knowledge_hub.models.content import ContentType, ExtractedContent, ExtractionStatus

MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024  # 20MB


async def extract_pdf(url: str) -> ExtractedContent:
    """Download and extract text content from a PDF URL.

    Checks Content-Length before download (HEAD request) and enforces 20MB cap.
    Uses pypdf PdfReader with BytesIO for in-memory processing.
    All sync pypdf calls wrapped in asyncio.to_thread().

    Returns ExtractedContent with:
    - FULL: text extracted from PDF pages
    - METADATA_ONLY: no text extracted (scanned/image PDF) or PDF exceeds size cap
    - FAILED: download failed or PDF parsing error
    """
    source_domain = urlparse(url).hostname

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(25.0), follow_redirects=True
        ) as client:
            # Optimization: check Content-Length header first
            try:
                head_resp = await client.head(url)
                content_length_str = head_resp.headers.get("content-length", "0")
                content_length = int(content_length_str)
                if content_length > MAX_PDF_SIZE_BYTES:
                    return ExtractedContent(
                        url=url,
                        content_type=ContentType.PDF,
                        source_domain=source_domain,
                        extraction_method="pypdf",
                        extraction_status=ExtractionStatus.METADATA_ONLY,
                        description=f"PDF too large: {content_length} bytes (limit: {MAX_PDF_SIZE_BYTES})",
                    )
            except (httpx.HTTPError, ValueError):
                pass  # HEAD failed or no Content-Length -- proceed with GET

            response = await client.get(url)
            response.raise_for_status()

        # Check actual download size
        if len(response.content) > MAX_PDF_SIZE_BYTES:
            return ExtractedContent(
                url=url,
                content_type=ContentType.PDF,
                source_domain=source_domain,
                extraction_method="pypdf",
                extraction_status=ExtractionStatus.METADATA_ONLY,
                description=f"PDF too large: {len(response.content)} bytes (limit: {MAX_PDF_SIZE_BYTES})",
            )

        # pypdf is synchronous -- run in thread
        reader = await asyncio.to_thread(PdfReader, BytesIO(response.content))

        # Extract text from all pages
        pages_text = []
        for page in reader.pages:
            page_text = await asyncio.to_thread(page.extract_text)
            if page_text:
                pages_text.append(page_text)
        text = "\n".join(pages_text).strip() or None

        # Extract metadata
        meta = reader.metadata
        title = meta.title if meta else None
        author = meta.author if meta else None
        word_count = len(text.split()) if text else None

        extraction_status = ExtractionStatus.FULL if text else ExtractionStatus.METADATA_ONLY

        return ExtractedContent(
            url=url,
            content_type=ContentType.PDF,
            title=title,
            author=author,
            source_domain=source_domain,
            text=text,
            word_count=word_count,
            extraction_method="pypdf",
            extraction_status=extraction_status,
        )

    except httpx.HTTPError:
        return ExtractedContent(
            url=url,
            content_type=ContentType.PDF,
            source_domain=source_domain,
            extraction_method="pypdf",
            extraction_status=ExtractionStatus.FAILED,
        )
    except Exception:
        # Catch pypdf parsing errors and other unexpected errors
        return ExtractedContent(
            url=url,
            content_type=ContentType.PDF,
            source_domain=source_domain,
            extraction_method="pypdf",
            extraction_status=ExtractionStatus.FAILED,
        )
