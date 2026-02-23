"""Tests for the Notion block builder."""

from datetime import datetime

from knowledge_hub.models.content import ContentType
from knowledge_hub.models.knowledge import Category, KnowledgeEntry, Priority
from knowledge_hub.models.notion import KeyLearning, NotionPage
from knowledge_hub.notion.blocks import build_body_blocks


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
        "tags": ["AI"],
        "summary": "A test summary.",
    }
    entry_defaults.update(overrides.pop("entry_overrides", {}))
    entry = KnowledgeEntry(**entry_defaults)
    page_defaults = {
        "entry": entry,
        "summary_section": "Executive summary of the article.",
        "key_points": ["Point 1", "Point 2"],
        "key_learnings": [
            KeyLearning(
                title="Testing Best Practices",
                what="Testing matters",
                why_it_matters="Catches bugs early",
                how_to_apply=["Write tests", "Run in CI"],
                resources_needed="pytest, CI pipeline",
                estimated_time="30 minutes",
            )
        ],
        "detailed_notes": "Detailed notes about the article.",
    }
    page_defaults.update(overrides)
    return NotionPage(**page_defaults)


def test_build_body_blocks_has_4_sections():
    """4 heading_2 blocks with correct section names."""
    page = _make_page()
    blocks = build_body_blocks(page)
    headings = [
        b for b in blocks
        if b["type"] == "heading_2"
    ]
    heading_texts = [
        h["heading_2"]["rich_text"][0]["text"]["content"]
        for h in headings
    ]
    assert heading_texts == [
        "Summary",
        "Key Points",
        "Key Learnings & Actionable Steps",
        "Detailed Notes / Full Breakdown",
    ]


def test_build_body_blocks_summary_section():
    """Paragraph block follows Summary heading."""
    page = _make_page()
    blocks = build_body_blocks(page)
    # blocks[0] = Summary heading, blocks[1] = summary paragraph
    assert blocks[1]["type"] == "paragraph"
    assert blocks[1]["paragraph"]["rich_text"][0]["text"]["content"] == (
        "Executive summary of the article."
    )


def test_build_body_blocks_key_points_numbered():
    """numbered_list_item blocks for each key point."""
    page = _make_page(key_points=["Point A", "Point B", "Point C"])
    blocks = build_body_blocks(page)
    numbered = [b for b in blocks if b["type"] == "numbered_list_item"]
    # Key points + how_to_apply steps (2 steps in default key_learnings)
    point_texts = [
        b["numbered_list_item"]["rich_text"][0]["text"]["content"]
        for b in numbered
    ]
    assert "Point A" in point_texts
    assert "Point B" in point_texts
    assert "Point C" in point_texts


def test_build_body_blocks_key_learnings_structure():
    """Key Learnings has bold 'what', paragraph 'why', numbered 'how to apply'."""
    learning = KeyLearning(
        title="AI is Transformative",
        what="AI is transformative",
        why_it_matters="Changes every industry",
        how_to_apply=["Learn ML basics", "Build a project"],
        resources_needed="Python, TensorFlow",
        estimated_time="2-3 months",
    )
    page = _make_page(key_learnings=[learning])
    blocks = build_body_blocks(page)

    # Find the Key Learnings heading index
    kl_idx = None
    for i, b in enumerate(blocks):
        if (
            b["type"] == "heading_2"
            and b["heading_2"]["rich_text"][0]["text"]["content"]
            == "Key Learnings & Actionable Steps"
        ):
            kl_idx = i
            break
    assert kl_idx is not None

    # Next block: heading_3 "Learning 1: AI is Transformative"
    learning_heading = blocks[kl_idx + 1]
    assert learning_heading["type"] == "heading_3"
    assert learning_heading["heading_3"]["rich_text"][0]["text"]["content"] == (
        "Learning 1: AI is Transformative"
    )

    # Next: "What:" labeled paragraph
    what_block = blocks[kl_idx + 2]
    assert what_block["type"] == "paragraph"
    assert what_block["paragraph"]["rich_text"][0]["annotations"]["bold"] is True
    assert what_block["paragraph"]["rich_text"][0]["text"]["content"] == "What: "
    assert what_block["paragraph"]["rich_text"][1]["text"]["content"] == "AI is transformative"

    # Next: "Why it matters:" labeled paragraph
    why_block = blocks[kl_idx + 3]
    assert why_block["type"] == "paragraph"
    assert why_block["paragraph"]["rich_text"][0]["annotations"]["bold"] is True
    assert why_block["paragraph"]["rich_text"][0]["text"]["content"] == "Why it matters: "

    # Next: "How to apply" bold label
    how_label = blocks[kl_idx + 4]
    assert how_label["type"] == "paragraph"
    assert how_label["paragraph"]["rich_text"][0]["annotations"]["bold"] is True

    # Next: numbered items for steps
    step1 = blocks[kl_idx + 5]
    step2 = blocks[kl_idx + 6]
    assert step1["type"] == "numbered_list_item"
    assert step1["numbered_list_item"]["rich_text"][0]["text"]["content"] == "Learn ML basics"
    assert step2["type"] == "numbered_list_item"
    assert step2["numbered_list_item"]["rich_text"][0]["text"]["content"] == "Build a project"

    # Next: resources and time
    resources_block = blocks[kl_idx + 7]
    assert resources_block["paragraph"]["rich_text"][0]["text"]["content"] == "Resources/tools needed: "
    time_block = blocks[kl_idx + 8]
    assert time_block["paragraph"]["rich_text"][0]["text"]["content"] == "Estimated total time: "


def test_build_body_blocks_detailed_notes_paragraphs():
    """Regular text in detailed_notes renders as paragraphs."""
    page = _make_page(detailed_notes="First paragraph.\n\nSecond paragraph.")
    blocks = build_body_blocks(page)
    detail_idx = None
    for i, b in enumerate(blocks):
        if b["type"] == "heading_2" and "Detailed Notes / Full Breakdown" in (
            b["heading_2"]["rich_text"][0]["text"]["content"]
        ):
            detail_idx = i
            break
    assert detail_idx is not None
    # After heading: two paragraphs
    assert blocks[detail_idx + 1]["type"] == "paragraph"
    assert blocks[detail_idx + 1]["paragraph"]["rich_text"][0]["text"]["content"] == (
        "First paragraph."
    )
    assert blocks[detail_idx + 2]["type"] == "paragraph"
    assert blocks[detail_idx + 2]["paragraph"]["rich_text"][0]["text"]["content"] == (
        "Second paragraph."
    )


def test_build_body_blocks_detailed_notes_subheadings():
    """'## Sub' in detailed_notes renders as heading_3."""
    page = _make_page(detailed_notes="## My Subheading\n\nSome text.")
    blocks = build_body_blocks(page)
    # Find heading_3 blocks after the Detailed Notes heading
    detail_idx = None
    for i, b in enumerate(blocks):
        if b["type"] == "heading_2" and "Detailed Notes / Full Breakdown" in (
            b["heading_2"]["rich_text"][0]["text"]["content"]
        ):
            detail_idx = i
            break
    assert detail_idx is not None
    h3_after_detail = [
        b for b in blocks[detail_idx:] if b["type"] == "heading_3"
    ]
    assert len(h3_after_detail) == 1
    assert h3_after_detail[0]["heading_3"]["rich_text"][0]["text"]["content"] == "My Subheading"


def test_build_body_blocks_detailed_notes_bullet_lists():
    """'- item' in detailed_notes renders as bulleted_list_item."""
    page = _make_page(detailed_notes="- Item one\n- Item two\n- Item three")
    blocks = build_body_blocks(page)
    bullet_blocks = [b for b in blocks if b["type"] == "bulleted_list_item"]
    texts = [
        b["bulleted_list_item"]["rich_text"][0]["text"]["content"]
        for b in bullet_blocks
    ]
    assert "Item one" in texts
    assert "Item two" in texts
    assert "Item three" in texts


def test_build_body_blocks_has_dividers():
    """Divider blocks separate sections."""
    page = _make_page()
    blocks = build_body_blocks(page)
    dividers = [b for b in blocks if b["type"] == "divider"]
    # 3 dividers: after Summary, after Key Points, after Key Learnings
    assert len(dividers) == 3


def test_build_body_blocks_long_text_split():
    """Paragraph with >2000 chars has multiple rich_text chunks."""
    long_text = "a" * 4500
    page = _make_page(summary_section=long_text)
    blocks = build_body_blocks(page)
    # blocks[1] = summary paragraph (after heading)
    para = blocks[1]
    chunks = para["paragraph"]["rich_text"]
    assert len(chunks) == 3  # 2000 + 2000 + 500
    for chunk in chunks:
        assert len(chunk["text"]["content"]) <= 2000
