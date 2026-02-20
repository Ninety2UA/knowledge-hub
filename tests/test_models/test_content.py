"""Tests for the ExtractedContent model and ContentType enum."""

from knowledge_hub.models.content import ContentType, ExtractedContent


def test_extracted_content_minimal():
    """Create with only url and content_type (required fields), assert all optional fields are None."""
    content = ExtractedContent(url="https://example.com", content_type=ContentType.ARTICLE)
    assert content.url == "https://example.com"
    assert content.content_type == ContentType.ARTICLE
    assert content.title is None
    assert content.author is None
    assert content.source_domain is None
    assert content.text is None
    assert content.transcript is None
    assert content.description is None
    assert content.published_date is None
    assert content.word_count is None
    assert content.duration_seconds is None
    assert content.extraction_method is None


def test_extracted_content_full():
    """Create with all fields populated, assert values."""
    content = ExtractedContent(
        url="https://youtube.com/watch?v=abc",
        content_type=ContentType.VIDEO,
        title="My Video",
        author="Author Name",
        source_domain="youtube.com",
        text="Video description text",
        transcript="Hello and welcome to the video...",
        description="A great video about testing",
        published_date="2026-01-15",
        word_count=500,
        duration_seconds=600,
        extraction_method="youtube-transcript-api",
        is_partial=True,
    )
    assert content.url == "https://youtube.com/watch?v=abc"
    assert content.content_type == ContentType.VIDEO
    assert content.title == "My Video"
    assert content.author == "Author Name"
    assert content.source_domain == "youtube.com"
    assert content.transcript == "Hello and welcome to the video..."
    assert content.word_count == 500
    assert content.duration_seconds == 600
    assert content.is_partial is True


def test_content_type_enum_values():
    """Assert ContentType has exactly 7 members with correct string values."""
    members = list(ContentType)
    assert len(members) == 7
    assert ContentType.ARTICLE.value == "Article"
    assert ContentType.VIDEO.value == "Video"
    assert ContentType.NEWSLETTER.value == "Newsletter"
    assert ContentType.PODCAST.value == "Podcast"
    assert ContentType.THREAD.value == "Thread"
    assert ContentType.LINKEDIN_POST.value == "LinkedIn Post"
    assert ContentType.PDF.value == "PDF"


def test_extracted_content_is_partial_default():
    """Assert is_partial defaults to False."""
    content = ExtractedContent(url="https://example.com", content_type=ContentType.ARTICLE)
    assert content.is_partial is False


def test_extracted_content_article_no_transcript():
    """Create article type with text but no transcript, assert transcript is None."""
    content = ExtractedContent(
        url="https://example.com/article",
        content_type=ContentType.ARTICLE,
        text="Article body text goes here.",
    )
    assert content.text == "Article body text goes here."
    assert content.transcript is None
