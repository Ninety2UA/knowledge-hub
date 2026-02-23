"""Tests for the NotionPage and KeyLearning models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from knowledge_hub.models.content import ContentType
from knowledge_hub.models.knowledge import Category, KnowledgeEntry, Priority
from knowledge_hub.models.notion import KeyLearning, NotionPage


def _make_entry(**overrides) -> KnowledgeEntry:
    """Helper to create a valid KnowledgeEntry with defaults."""
    defaults = {
        "title": "Test Article",
        "category": Category.AI_ML,
        "content_type": ContentType.ARTICLE,
        "source": "https://example.com",
        "date_added": datetime(2026, 2, 20),
        "priority": Priority.HIGH,
        "summary": "A test summary.",
    }
    defaults.update(overrides)
    return KnowledgeEntry(**defaults)


def test_notion_page_valid():
    """Create NotionPage with valid KnowledgeEntry and all 4 sections, assert fields."""
    entry = _make_entry()
    learning = KeyLearning(
        title="Testing Best Practices",
        what="Testing is important",
        why_it_matters="Catches bugs early",
        how_to_apply=["Write tests first", "Run tests in CI"],
        resources_needed="pytest, CI pipeline",
        estimated_time="30 minutes",
    )
    page = NotionPage(
        entry=entry,
        summary_section="This is a 3-5 sentence executive summary.",
        key_points=["Point 1", "Point 2", "Point 3"],
        key_learnings=[learning],
        detailed_notes="Detailed breakdown of the content.",
    )
    assert page.entry.title == "Test Article"
    assert page.summary_section == "This is a 3-5 sentence executive summary."
    assert len(page.key_points) == 3
    assert len(page.key_learnings) == 1
    assert page.detailed_notes == "Detailed breakdown of the content."


def test_key_learning_structure():
    """Create KeyLearning with what, why_it_matters, how_to_apply list, assert all fields."""
    learning = KeyLearning(
        title="Use Pydantic for Runtime Validation",
        what="Pydantic validates data at runtime",
        why_it_matters="Catches invalid data before it reaches business logic",
        how_to_apply=["Define BaseModel subclasses", "Use type hints", "Let Pydantic raise ValidationError"],
        resources_needed="Pydantic v2",
        estimated_time="10-15 minutes",
    )
    assert learning.title == "Use Pydantic for Runtime Validation"
    assert learning.what == "Pydantic validates data at runtime"
    assert learning.why_it_matters == "Catches invalid data before it reaches business logic"
    assert len(learning.how_to_apply) == 3
    assert learning.how_to_apply[0] == "Define BaseModel subclasses"


def test_notion_page_key_learnings_list():
    """Create with multiple KeyLearning entries, assert list length."""
    entry = _make_entry()
    learnings = [
        KeyLearning(
            title=f"Learning Title {i}",
            what=f"Learning {i}",
            why_it_matters=f"Reason {i}",
            how_to_apply=[f"Step {i}"],
            resources_needed=f"Tool {i}",
            estimated_time=f"{i * 10} minutes",
        )
        for i in range(5)
    ]
    page = NotionPage(
        entry=entry,
        summary_section="Summary.",
        key_points=["Point 1"],
        key_learnings=learnings,
        detailed_notes="Notes.",
    )
    assert len(page.key_learnings) == 5


def test_notion_page_requires_entry():
    """Omit entry field, assert ValidationError."""
    with pytest.raises(ValidationError):
        NotionPage(
            summary_section="Summary.",
            key_points=["Point 1"],
            key_learnings=[],
            detailed_notes="Notes.",
        )
