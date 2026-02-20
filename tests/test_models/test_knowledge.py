"""Tests for the KnowledgeEntry model and related enums."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from knowledge_hub.models.content import ContentType
from knowledge_hub.models.knowledge import Category, KnowledgeEntry, Priority, Status


def test_knowledge_entry_valid():
    """Create with all required fields, assert values match."""
    now = datetime(2026, 2, 20, 12, 0, 0)
    entry = KnowledgeEntry(
        title="Test Article",
        category=Category.AI_ML,
        content_type=ContentType.ARTICLE,
        source="https://example.com/article",
        author="Jane Doe",
        date_added=now,
        priority=Priority.HIGH,
        tags=["ai", "testing"],
        summary="A test article about AI.",
    )
    assert entry.title == "Test Article"
    assert entry.category == Category.AI_ML
    assert entry.content_type == ContentType.ARTICLE
    assert entry.source == "https://example.com/article"
    assert entry.author == "Jane Doe"
    assert entry.date_added == now
    assert entry.priority == Priority.HIGH
    assert entry.tags == ["ai", "testing"]
    assert entry.summary == "A test article about AI."


def test_knowledge_entry_default_status():
    """Create entry, assert status defaults to Status.NEW."""
    entry = KnowledgeEntry(
        title="Test",
        category=Category.ENGINEERING,
        content_type=ContentType.ARTICLE,
        source="https://example.com",
        date_added=datetime(2026, 1, 1),
        priority=Priority.MEDIUM,
        summary="Test summary.",
    )
    assert entry.status == Status.NEW


def test_knowledge_entry_empty_tags():
    """Create without tags, assert defaults to empty list."""
    entry = KnowledgeEntry(
        title="Test",
        category=Category.ENGINEERING,
        content_type=ContentType.ARTICLE,
        source="https://example.com",
        date_added=datetime(2026, 1, 1),
        priority=Priority.MEDIUM,
        summary="Test summary.",
    )
    assert entry.tags == []


def test_category_enum_count():
    """Assert Category enum has exactly 11 members."""
    members = list(Category)
    assert len(members) == 11


def test_priority_enum_values():
    """Assert Priority enum has HIGH, MEDIUM, LOW."""
    assert Priority.HIGH.value == "High"
    assert Priority.MEDIUM.value == "Medium"
    assert Priority.LOW.value == "Low"
    assert len(list(Priority)) == 3


def test_status_enum_values():
    """Assert Status enum has NEW, REVIEWED, APPLIED, ARCHIVED."""
    assert Status.NEW.value == "New"
    assert Status.REVIEWED.value == "Reviewed"
    assert Status.APPLIED.value == "Applied"
    assert Status.ARCHIVED.value == "Archived"
    assert len(list(Status)) == 4


def test_knowledge_entry_invalid_category():
    """Pass invalid category string, assert ValidationError."""
    with pytest.raises(ValidationError):
        KnowledgeEntry(
            title="Test",
            category="InvalidCategory",
            content_type=ContentType.ARTICLE,
            source="https://example.com",
            date_added=datetime(2026, 1, 1),
            priority=Priority.MEDIUM,
            summary="Test summary.",
        )
