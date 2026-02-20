"""Article content extraction using trafilatura."""

import asyncio

from trafilatura import bare_extraction, fetch_url

from knowledge_hub.extraction.paywall import is_paywalled_domain
from knowledge_hub.models.content import ContentType, ExtractedContent, ExtractionStatus


async def extract_article(url: str) -> ExtractedContent:
    """Extract article content via trafilatura.

    All sync trafilatura calls are wrapped in asyncio.to_thread() to avoid
    blocking the event loop.

    Returns ExtractedContent with appropriate ExtractionStatus:
    - FULL: body text extracted successfully
    - PARTIAL: paywalled domain with short/empty body text
    - METADATA_ONLY: bare_extraction returned no body text but metadata exists
    - FAILED: fetch_url returned None (could not download)
    """
    # Download page (sync, runs in thread pool)
    downloaded = await asyncio.to_thread(fetch_url, url)
    if downloaded is None:
        return ExtractedContent(
            url=url,
            content_type=ContentType.ARTICLE,
            extraction_status=ExtractionStatus.FAILED,
            extraction_method="trafilatura",
        )

    # Extract content (sync, runs in thread pool)
    doc = await asyncio.to_thread(bare_extraction, downloaded, url=url)
    if doc is None:
        return ExtractedContent(
            url=url,
            content_type=ContentType.ARTICLE,
            extraction_status=ExtractionStatus.METADATA_ONLY,
            extraction_method="trafilatura",
        )

    # Map trafilatura Document fields to ExtractedContent
    text = doc.text or None
    title = doc.title or None
    author = doc.author or None
    published_date = doc.date or None
    source_domain = doc.sitename or doc.hostname or None
    description = doc.description or None
    word_count = len(text.split()) if text else None

    # Determine extraction status
    if text:
        extraction_status = ExtractionStatus.FULL
        # Check if paywalled with short content (likely truncated)
        if is_paywalled_domain(url) and word_count and word_count < 200:
            extraction_status = ExtractionStatus.PARTIAL
    else:
        extraction_status = ExtractionStatus.METADATA_ONLY

    return ExtractedContent(
        url=url,
        content_type=ContentType.ARTICLE,
        title=title,
        author=author,
        source_domain=source_domain,
        text=text,
        description=description,
        published_date=published_date,
        word_count=word_count,
        extraction_method="trafilatura",
        extraction_status=extraction_status,
    )
