"""Pure function converting NotionPage body into Notion block objects.

Builds the 4-section page body (Summary, Key Points, Key Learnings,
Detailed Notes) as a list of Notion block dicts. Handles the 2000-char
rich_text limit. The caller handles the 100-block batch limit.
"""

import re

from knowledge_hub.models.notion import NotionPage


def _split_rich_text(text: str, limit: int = 2000) -> list[dict]:
    """Split text into multiple rich_text objects respecting Notion's 2000-char limit."""
    if not text:
        return [{"type": "text", "text": {"content": ""}}]
    chunks = []
    for i in range(0, len(text), limit):
        chunks.append({"type": "text", "text": {"content": text[i : i + limit]}})
    return chunks


_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")


def _parse_inline_formatting(text: str) -> list[dict]:
    """Parse inline **bold** markdown into Notion rich_text with annotations.

    Returns a list of rich_text objects with bold annotations where appropriate.
    Falls back to plain _split_rich_text for text without formatting.
    """
    if "**" not in text:
        return _split_rich_text(text)

    parts: list[dict] = []
    pos = 0
    for m in _BOLD_PATTERN.finditer(text):
        # Text before the bold
        if m.start() > pos:
            parts.append({"type": "text", "text": {"content": text[pos : m.start()]}})
        # The bold text
        parts.append(
            {
                "type": "text",
                "text": {"content": m.group(1)},
                "annotations": {"bold": True},
            }
        )
        pos = m.end()
    # Remaining text after last bold
    if pos < len(text):
        parts.append({"type": "text", "text": {"content": text[pos:]}})

    return parts or _split_rich_text(text)


def _heading_block(text: str, level: int = 2) -> dict:
    """Create a heading block (heading_2 or heading_3). Truncates to 2000 chars."""
    key = f"heading_{level}"
    return {
        "object": "block",
        "type": key,
        key: {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]},
    }


def _paragraph_block(text: str) -> dict:
    """Create a paragraph block with rich_text splitting and inline bold."""
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _parse_inline_formatting(text)},
    }


def _bold_paragraph_block(text: str) -> dict:
    """Create a paragraph block with bold annotations.

    Uses Notion rich_text annotations instead of markdown syntax,
    since markdown **text** renders as literal asterisks in Notion.
    """
    if not text:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": ""},
                        "annotations": {"bold": True},
                    }
                ]
            },
        }
    chunks = []
    for i in range(0, len(text), 2000):
        chunks.append(
            {
                "type": "text",
                "text": {"content": text[i : i + 2000]},
                "annotations": {"bold": True},
            }
        )
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": chunks},
    }


def _labeled_paragraph_block(label: str, text: str) -> dict:
    """Create a paragraph with bold label followed by plain text.

    Example: **What:** Some description text here.
    """
    rich_text: list[dict] = [
        {
            "type": "text",
            "text": {"content": f"{label} "},
            "annotations": {"bold": True},
        }
    ]
    # Split remaining text into 2000-char chunks
    for i in range(0, max(len(text), 1), 2000):
        rich_text.append({"type": "text", "text": {"content": text[i : i + 2000]}})
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": rich_text},
    }


def _numbered_item_block(text: str) -> dict:
    """Create a numbered_list_item block."""
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": _split_rich_text(text)},
    }


def _bulleted_item_block(text: str) -> dict:
    """Create a bulleted_list_item block."""
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _parse_inline_formatting(text)},
    }


def _divider_block() -> dict:
    """Create a divider block."""
    return {"object": "block", "type": "divider", "divider": {}}


def build_body_blocks(page: NotionPage) -> list[dict]:
    """Build the 4-section page body as a list of Notion block dicts.

    Sections:
    1. Summary - heading + paragraph + divider
    2. Key Points - heading + numbered list items + divider
    3. Key Learnings & Actionable Steps - heading + structured blocks + divider
    4. Detailed Notes - heading + parsed paragraphs/subheadings/bullets

    Returns list[dict]. Caller handles the 100-block batch limit.
    """
    blocks: list[dict] = []

    # Section 1: Summary
    blocks.append(_heading_block("Summary"))
    blocks.append(_paragraph_block(page.summary_section))
    blocks.append(_divider_block())

    # Section 2: Key Points (numbered list)
    blocks.append(_heading_block("Key Points"))
    for point in page.key_points:
        blocks.append(_numbered_item_block(point))
    blocks.append(_divider_block())

    # Section 3: Key Learnings & Actionable Steps
    blocks.append(_heading_block("Key Learnings & Actionable Steps"))
    for i, kl in enumerate(page.key_learnings):
        # Heading: "Learning N: Title"
        blocks.append(_heading_block(f"Learning {i + 1}: {kl.title}", level=3))
        # Labeled paragraphs
        blocks.append(_labeled_paragraph_block("What:", kl.what))
        blocks.append(_labeled_paragraph_block("Why it matters:", kl.why_it_matters))
        # "How to apply" label + numbered sub-steps
        blocks.append(_bold_paragraph_block("How to apply — Step-by-step:"))
        for step in kl.how_to_apply:
            blocks.append(_numbered_item_block(step))
        # Resources and time estimate
        blocks.append(_labeled_paragraph_block("Resources/tools needed:", kl.resources_needed))
        blocks.append(_labeled_paragraph_block("Estimated total time:", kl.estimated_time))
        # Divider between learnings (not after last one)
        if i < len(page.key_learnings) - 1:
            blocks.append(_divider_block())
    blocks.append(_divider_block())

    # Section 4: Detailed Notes / Full Breakdown (line-by-line parsing for proper Notion blocks)
    blocks.append(_heading_block("Detailed Notes / Full Breakdown"))
    for line in page.detailed_notes.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("### "):
            blocks.append(_heading_block(line[4:], level=3))
        elif line.startswith("## "):
            blocks.append(_heading_block(line[3:], level=3))
        elif line.startswith("# "):
            blocks.append(_heading_block(line[2:], level=2))
        elif line.startswith("- "):
            blocks.append(_bulleted_item_block(line[2:].strip()))
        elif line.startswith("* "):
            blocks.append(_bulleted_item_block(line[2:].strip()))
        else:
            blocks.append(_paragraph_block(line))

    return blocks
