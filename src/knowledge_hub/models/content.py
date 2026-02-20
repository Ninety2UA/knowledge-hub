"""Extracted content model and content type enum."""

from enum import Enum

from pydantic import BaseModel


class ContentType(str, Enum):
    """Types of content that can be extracted from URLs."""

    ARTICLE = "Article"
    VIDEO = "Video"
    NEWSLETTER = "Newsletter"
    PODCAST = "Podcast"
    THREAD = "Thread"
    LINKEDIN_POST = "LinkedIn Post"
    PDF = "PDF"


class ExtractionStatus(str, Enum):
    """Extraction outcome status."""

    FULL = "full"
    PARTIAL = "partial"
    METADATA_ONLY = "metadata_only"
    FAILED = "failed"


class ExtractedContent(BaseModel):
    """Content extracted from a URL. Single model with optional fields for all content types."""

    url: str  # Original URL (always present)
    content_type: ContentType  # Detected content type (always present)
    title: str | None = None
    author: str | None = None
    source_domain: str | None = None  # e.g., "youtube.com"
    text: str | None = None  # Main body text / article content
    transcript: str | None = None  # YouTube transcript (None for articles)
    description: str | None = None  # Meta description or video description
    published_date: str | None = None  # Formats vary, kept as string
    word_count: int | None = None
    duration_seconds: int | None = None  # Video duration (None for articles)
    extraction_method: str | None = None  # e.g., "trafilatura", "youtube-transcript-api"
    extraction_status: ExtractionStatus = ExtractionStatus.FULL
