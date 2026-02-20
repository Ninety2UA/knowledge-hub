"""Tests for URL content type routing."""

from knowledge_hub.extraction.router import detect_content_type
from knowledge_hub.models.content import ContentType


def test_youtube_watch_url():
    assert detect_content_type("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == ContentType.VIDEO


def test_youtube_short_url():
    assert detect_content_type("https://youtu.be/dQw4w9WgXcQ") == ContentType.VIDEO


def test_youtube_shorts_url():
    assert detect_content_type("https://www.youtube.com/shorts/dQw4w9WgXcQ") == ContentType.VIDEO


def test_youtube_embed_url():
    assert detect_content_type("https://www.youtube.com/embed/dQw4w9WgXcQ") == ContentType.VIDEO


def test_youtube_with_extra_params():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120&list=PLxxx"
    assert detect_content_type(url) == ContentType.VIDEO


def test_pdf_url():
    assert detect_content_type("https://example.com/paper.pdf") == ContentType.PDF


def test_pdf_url_with_query():
    assert detect_content_type("https://example.com/paper.pdf?dl=1") == ContentType.PDF


def test_pdf_url_case_insensitive():
    assert detect_content_type("https://example.com/DOCUMENT.PDF") == ContentType.PDF


def test_substack_url():
    assert detect_content_type("https://newsletter.substack.com/p/hello") == ContentType.NEWSLETTER


def test_medium_url():
    assert detect_content_type("https://medium.com/@user/article-title") == ContentType.ARTICLE


def test_medium_custom_domain():
    assert detect_content_type("https://blog.medium.com/article-slug") == ContentType.ARTICLE


def test_unknown_url():
    assert detect_content_type("https://example.com/page") == ContentType.ARTICLE


def test_bare_domain():
    assert detect_content_type("https://nytimes.com") == ContentType.ARTICLE
