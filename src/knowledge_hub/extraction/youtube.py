"""YouTube transcript extraction using youtube-transcript-api."""

import asyncio
import re

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    InvalidVideoId,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from knowledge_hub.models.content import ContentType, ExtractedContent, ExtractionStatus

# Comprehensive regex for all YouTube URL formats
VIDEO_ID_PATTERN = re.compile(
    r"(?:youtube\.com/(?:watch\?.*v=|shorts/|embed/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)


def extract_video_id(url: str) -> str | None:
    """Extract the 11-character video ID from a YouTube URL.

    Handles: youtube.com/watch?v=, youtu.be/, youtube.com/shorts/, youtube.com/embed/
    Also handles URLs with additional query params (e.g., &t=123, &list=PLxxx).
    """
    match = VIDEO_ID_PATTERN.search(url)
    return match.group(1) if match else None


async def extract_youtube(url: str) -> ExtractedContent:
    """Extract YouTube transcript and metadata.

    Uses YouTubeTranscriptApi instance fetch() method (not deprecated static methods).
    All sync calls wrapped in asyncio.to_thread().

    Returns ExtractedContent with:
    - FULL: transcript extracted successfully
    - METADATA_ONLY: captions disabled or not found (TranscriptsDisabled, NoTranscriptFound)
    - FAILED: video unavailable, invalid ID, or no video ID in URL
    """
    video_id = extract_video_id(url)
    if video_id is None:
        return ExtractedContent(
            url=url,
            content_type=ContentType.VIDEO,
            source_domain="youtube.com",
            extraction_status=ExtractionStatus.FAILED,
            extraction_method="youtube-transcript-api",
        )

    ytt_api = YouTubeTranscriptApi()
    try:
        # Sync call wrapped in to_thread
        transcript = await asyncio.to_thread(
            ytt_api.fetch, video_id, languages=["en"]
        )
        text = " ".join(snippet.text for snippet in transcript)
        word_count = len(text.split()) if text else None

        return ExtractedContent(
            url=url,
            content_type=ContentType.VIDEO,
            transcript=text,
            source_domain="youtube.com",
            word_count=word_count,
            extraction_method="youtube-transcript-api",
            extraction_status=ExtractionStatus.FULL,
        )
    except (TranscriptsDisabled, NoTranscriptFound):
        # Fallback: metadata-only (captions unavailable)
        return ExtractedContent(
            url=url,
            content_type=ContentType.VIDEO,
            transcript=None,
            source_domain="youtube.com",
            extraction_method="youtube-transcript-api",
            extraction_status=ExtractionStatus.METADATA_ONLY,
        )
    except (VideoUnavailable, InvalidVideoId):
        return ExtractedContent(
            url=url,
            content_type=ContentType.VIDEO,
            source_domain="youtube.com",
            extraction_method="youtube-transcript-api",
            extraction_status=ExtractionStatus.FAILED,
        )
