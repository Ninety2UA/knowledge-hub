"""Prompt template tests for build_system_prompt and build_user_content."""

from knowledge_hub.llm.prompts import build_system_prompt, build_user_content
from knowledge_hub.models.content import ContentType, ExtractedContent, ExtractionStatus


def _make_content(**kwargs) -> ExtractedContent:
    """Return a valid ExtractedContent with sensible defaults, override via kwargs."""
    defaults = {
        "url": "https://example.com/article",
        "content_type": ContentType.ARTICLE,
        "title": "Test Article Title",
        "author": "Jane Doe",
        "source_domain": "example.com",
        "text": "This is a comprehensive article about software engineering. " * 100,
        "word_count": 1000,
        "extraction_status": ExtractionStatus.FULL,
    }
    defaults.update(kwargs)
    return ExtractedContent(**defaults)


def test_build_system_prompt_contains_categories():
    """Output contains all 11 Category enum values."""
    content = _make_content()
    prompt = build_system_prompt(content)
    categories = [
        "AI & Machine Learning",
        "Marketing",
        "Product",
        "Growth",
        "Analytics",
        "Engineering",
        "Design",
        "Business",
        "Career",
        "Productivity",
        "Other",
    ]
    for cat in categories:
        assert cat in prompt, f"Category '{cat}' not found in system prompt"


def test_build_system_prompt_contains_seeded_tags():
    """Output contains representative seeded tags (spot-check 6)."""
    content = _make_content()
    prompt = build_system_prompt(content)
    spot_check_tags = ["ai", "marketing", "engineering", "productivity", "growth", "career"]
    for tag in spot_check_tags:
        assert tag in prompt, f"Seeded tag '{tag}' not found in system prompt"


def test_build_system_prompt_contains_priority_criteria():
    """Output mentions High, Medium, Low with criteria."""
    content = _make_content()
    prompt = build_system_prompt(content)
    assert "High" in prompt
    assert "Medium" in prompt
    assert "Low" in prompt
    assert "actionable" in prompt.lower()


def test_build_system_prompt_contains_key_learning_structure():
    """Output mentions what, why_it_matters, how_to_apply (LLM-07)."""
    content = _make_content()
    prompt = build_system_prompt(content)
    assert "what" in prompt.lower()
    assert "why_it_matters" in prompt
    assert "how_to_apply" in prompt


def test_build_system_prompt_contains_importance_ordering():
    """Output mentions ordering by importance, not source order (LLM-08)."""
    content = _make_content()
    prompt = build_system_prompt(content)
    assert "importance" in prompt.lower()
    assert "source" in prompt.lower() or "appearance" in prompt.lower()


def test_build_system_prompt_video_addendum():
    """Video content type triggers timestamp/duration instructions."""
    content = _make_content(content_type=ContentType.VIDEO, word_count=5000)
    prompt = build_system_prompt(content)
    assert "timestamp" in prompt.lower()
    assert "duration" in prompt.lower()


def test_build_system_prompt_short_content_addendum():
    """Content with word_count=200 triggers short content instructions."""
    content = _make_content(word_count=200)
    prompt = build_system_prompt(content)
    assert "500 words" in prompt.lower() or "under 500" in prompt.lower()
    assert "proportionally shorter" in prompt.lower()


def test_build_system_prompt_article_no_addendum():
    """Article with 2000 words gets base prompt only (no addendums)."""
    content = _make_content(word_count=2000)
    prompt = build_system_prompt(content)
    # Should NOT contain video or short content addendums
    assert "timestamp" not in prompt.lower()
    assert "proportionally shorter" not in prompt.lower()


def test_build_user_content_article():
    """Article with title, author, text produces correct format."""
    content = _make_content(
        title="My Article",
        author="John Smith",
        source_domain="blog.example.com",
        text="Full article body text here.",
    )
    result = build_user_content(content)
    assert "Title: My Article" in result
    assert "Author: John Smith" in result
    assert "Source: blog.example.com" in result
    assert "Full article body text here." in result


def test_build_user_content_video():
    """Video with transcript uses transcript as body (not text)."""
    content = _make_content(
        content_type=ContentType.VIDEO,
        text=None,
        transcript="Hello and welcome to this video about machine learning...",
        word_count=5000,
    )
    result = build_user_content(content)
    assert "Hello and welcome to this video" in result


def test_build_user_content_fallback_description():
    """Content with only description falls back to description as body."""
    content = _make_content(
        text=None,
        transcript=None,
        description="A brief description of the content.",
    )
    result = build_user_content(content)
    assert "A brief description of the content." in result


def test_build_user_content_omits_none_fields():
    """None title/author not included in output."""
    content = _make_content(title=None, author=None)
    result = build_user_content(content)
    assert "Title:" not in result
    assert "Author:" not in result


def test_build_user_content_with_user_note():
    """User note is included in output when present."""
    content = _make_content(user_note="Check this for Q3")
    result = build_user_content(content)
    assert "User Note: Check this for Q3" in result


def test_build_user_content_without_user_note():
    """User Note line is absent when user_note is None."""
    content = _make_content(user_note=None)
    result = build_user_content(content)
    assert "User Note" not in result
