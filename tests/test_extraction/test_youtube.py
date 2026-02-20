"""Tests for YouTube transcript extraction (mocked youtube-transcript-api)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from knowledge_hub.extraction.youtube import extract_video_id, extract_youtube
from knowledge_hub.models.content import ContentType, ExtractionStatus


# --- Video ID extraction tests (sync) ---


def test_extract_video_id_watch():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_short():
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_shorts():
    assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_embed():
    assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_with_params():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120&list=PLxxx"
    assert extract_video_id(url) == "dQw4w9WgXcQ"


def test_extract_video_id_invalid():
    assert extract_video_id("https://example.com/page") is None


# --- YouTube extractor tests (async) ---


@pytest.mark.asyncio
async def test_extract_youtube_success():
    """Successful transcript fetch returns FULL status with joined text."""
    snippets = [
        SimpleNamespace(text="Hello world"),
        SimpleNamespace(text="this is a test"),
    ]
    mock_api = MagicMock()
    mock_api.fetch.return_value = snippets

    with patch("knowledge_hub.extraction.youtube.YouTubeTranscriptApi", return_value=mock_api):
        result = await extract_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert result.extraction_status == ExtractionStatus.FULL
    assert result.content_type == ContentType.VIDEO
    assert result.transcript == "Hello world this is a test"
    assert result.word_count == 6
    assert result.source_domain == "youtube.com"
    assert result.extraction_method == "youtube-transcript-api"


@pytest.mark.asyncio
async def test_extract_youtube_transcripts_disabled():
    """TranscriptsDisabled results in METADATA_ONLY."""
    from youtube_transcript_api._errors import TranscriptsDisabled

    mock_api = MagicMock()
    mock_api.fetch.side_effect = TranscriptsDisabled("abc123abc12")

    with patch("knowledge_hub.extraction.youtube.YouTubeTranscriptApi", return_value=mock_api):
        result = await extract_youtube("https://www.youtube.com/watch?v=abc123abc12")

    assert result.extraction_status == ExtractionStatus.METADATA_ONLY
    assert result.transcript is None


@pytest.mark.asyncio
async def test_extract_youtube_no_transcript():
    """NoTranscriptFound results in METADATA_ONLY."""
    from youtube_transcript_api._errors import NoTranscriptFound

    mock_api = MagicMock()
    mock_api.fetch.side_effect = NoTranscriptFound(
        "abc123abc12", ["de"], "No transcript found"
    )

    with patch("knowledge_hub.extraction.youtube.YouTubeTranscriptApi", return_value=mock_api):
        result = await extract_youtube("https://www.youtube.com/watch?v=abc123abc12")

    assert result.extraction_status == ExtractionStatus.METADATA_ONLY


@pytest.mark.asyncio
async def test_extract_youtube_video_unavailable():
    """VideoUnavailable results in FAILED."""
    from youtube_transcript_api._errors import VideoUnavailable

    mock_api = MagicMock()
    mock_api.fetch.side_effect = VideoUnavailable("abc123abc12")

    with patch("knowledge_hub.extraction.youtube.YouTubeTranscriptApi", return_value=mock_api):
        result = await extract_youtube("https://www.youtube.com/watch?v=abc123abc12")

    assert result.extraction_status == ExtractionStatus.FAILED


@pytest.mark.asyncio
async def test_extract_youtube_invalid_id():
    """Non-YouTube URL (no video ID) results in FAILED."""
    result = await extract_youtube("https://example.com/not-youtube")

    assert result.extraction_status == ExtractionStatus.FAILED
    assert result.content_type == ContentType.VIDEO
