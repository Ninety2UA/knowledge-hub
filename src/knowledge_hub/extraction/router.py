"""URL pattern matching and content type detection."""

import re

from knowledge_hub.models.content import ContentType

# Patterns ordered by specificity
YOUTUBE_PATTERN = re.compile(
    r"(?:youtube\.com/(?:watch\?.*v=|shorts/|embed/)|youtu\.be/)"
)
PDF_PATTERN = re.compile(r"\.pdf(?:\?.*)?$", re.IGNORECASE)
SUBSTACK_PATTERN = re.compile(r"\.substack\.com/")
MEDIUM_PATTERN = re.compile(r"(?:^https?://medium\.com/|\.medium\.com/)")


def detect_content_type(url: str) -> ContentType:
    """Detect content type from URL patterns. Unknown URLs default to ARTICLE."""
    if YOUTUBE_PATTERN.search(url):
        return ContentType.VIDEO
    if PDF_PATTERN.search(url):
        return ContentType.PDF
    if SUBSTACK_PATTERN.search(url):
        return ContentType.NEWSLETTER
    if MEDIUM_PATTERN.search(url):
        return ContentType.ARTICLE  # Medium uses trafilatura like articles
    return ContentType.ARTICLE  # Default fallback
