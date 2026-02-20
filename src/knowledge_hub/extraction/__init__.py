"""Content extraction: article, video, and PDF content retrieval.

Public API:
    extract_content(url) -> ExtractedContent
        Single entry point that detects content type, dispatches to the
        appropriate extractor, and enforces a 30-second timeout.
"""

from knowledge_hub.extraction.router import detect_content_type
from knowledge_hub.extraction.timeout import extract_with_timeout
from knowledge_hub.models.content import ExtractionStatus

# Public alias -- callers import extract_content, not extract_with_timeout
extract_content = extract_with_timeout

__all__ = [
    "extract_content",
    "detect_content_type",
    "ExtractionStatus",
]
