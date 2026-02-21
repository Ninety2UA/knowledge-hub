"""Tests for the Notion property builder."""

from datetime import datetime

from knowledge_hub.models.content import ContentType
from knowledge_hub.models.knowledge import Category, KnowledgeEntry, Priority, Status
from knowledge_hub.models.notion import KeyLearning, NotionPage
from knowledge_hub.notion.properties import build_properties


def _make_page(**overrides) -> NotionPage:
    """Create a valid NotionPage with sensible defaults."""
    entry_defaults = {
        "title": "Test Article",
        "category": Category.AI_ML,
        "content_type": ContentType.ARTICLE,
        "source": "https://example.com/test",
        "author": "Test Author",
        "date_added": datetime(2026, 2, 20),
        "priority": Priority.HIGH,
        "tags": ["AI", "Python"],
        "summary": "A test summary for the article.",
    }
    entry_defaults.update(overrides.pop("entry_overrides", {}))
    entry = KnowledgeEntry(**entry_defaults)
    page_defaults = {
        "entry": entry,
        "summary_section": "Executive summary of the article.",
        "key_points": ["Point 1", "Point 2", "Point 3"],
        "key_learnings": [
            KeyLearning(
                what="Testing matters",
                why_it_matters="Catches bugs early",
                how_to_apply=["Write tests", "Run in CI"],
            )
        ],
        "detailed_notes": "Detailed notes about the article.",
    }
    page_defaults.update(overrides)
    return NotionPage(**page_defaults)


def test_build_properties_all_10_keys():
    """All 10 Notion property keys are present."""
    page = _make_page()
    props = build_properties(page)
    expected_keys = {
        "Title",
        "Category",
        "Content Type",
        "Source",
        "Author/Creator",
        "Date Added",
        "Status",
        "Priority",
        "Tags",
        "Summary",
    }
    assert set(props.keys()) == expected_keys


def test_build_properties_title_format():
    """Title uses Notion title rich_text format."""
    page = _make_page()
    props = build_properties(page)
    title = props["Title"]
    assert "title" in title
    assert title["title"][0]["type"] == "text"
    assert title["title"][0]["text"]["content"] == "Test Article"


def test_build_properties_select_fields():
    """Category, Content Type, Status, Priority use select format."""
    page = _make_page()
    props = build_properties(page)
    for key in ["Category", "Content Type", "Status", "Priority"]:
        assert "select" in props[key], f"{key} missing select"
        assert "name" in props[key]["select"], f"{key} missing select.name"


def test_build_properties_status_always_new():
    """Status is always 'New' regardless of input."""
    page = _make_page()
    props = build_properties(page)
    assert props["Status"]["select"]["name"] == "New"


def test_build_properties_url_field():
    """Source uses Notion URL format."""
    page = _make_page()
    props = build_properties(page)
    assert props["Source"] == {"url": "https://example.com/test"}


def test_build_properties_date_field():
    """Date Added uses Notion date format with ISO string."""
    page = _make_page()
    props = build_properties(page)
    date_prop = props["Date Added"]
    assert "date" in date_prop
    assert "start" in date_prop["date"]
    # Verify it's a valid ISO format string
    assert "2026-02-20" in date_prop["date"]["start"]


def test_build_properties_tags_multi_select():
    """Tags use multi_select format with name objects."""
    page = _make_page()
    props = build_properties(page)
    tags_prop = props["Tags"]
    assert "multi_select" in tags_prop
    tag_names = [t["name"] for t in tags_prop["multi_select"]]
    assert tag_names == ["AI", "Python"]


def test_build_properties_long_summary_split():
    """Summary longer than 2000 chars is split into multiple rich_text chunks."""
    long_summary = "x" * 4500
    page = _make_page(entry_overrides={"summary": long_summary})
    props = build_properties(page)
    chunks = props["Summary"]["rich_text"]
    assert len(chunks) == 3  # 2000 + 2000 + 500
    for chunk in chunks:
        assert len(chunk["text"]["content"]) <= 2000


def test_build_properties_author_none():
    """Author=None produces empty string in rich_text."""
    page = _make_page(entry_overrides={"author": None})
    props = build_properties(page)
    author_text = props["Author/Creator"]["rich_text"][0]["text"]["content"]
    assert author_text == ""
