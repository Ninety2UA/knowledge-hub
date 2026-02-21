"""Pure function converting NotionPage body into Notion block objects.

Builds the 4-section page body (Summary, Key Points, Key Learnings,
Detailed Notes) as a list of Notion block dicts. Handles the 2000-char
rich_text limit. The caller handles the 100-block batch limit.
"""

from knowledge_hub.models.notion import NotionPage


def _split_rich_text(text: str, limit: int = 2000) -> list[dict]:
    """Split text into multiple rich_text objects respecting Notion's 2000-char limit."""
    if not text:
        return [{"type": "text", "text": {"content": ""}}]
    chunks = []
    for i in range(0, len(text), limit):
        chunks.append({"type": "text", "text": {"content": text[i : i + limit]}})
    return chunks


def _heading_block(text: str, level: int = 2) -> dict:
    """Create a heading block (heading_2 or heading_3)."""
    key = f"heading_{level}"
    return {
        "object": "block",
        "type": key,
        key: {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _paragraph_block(text: str) -> dict:
    """Create a paragraph block with rich_text splitting."""
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _split_rich_text(text)},
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
        "bulleted_list_item": {"rich_text": _split_rich_text(text)},
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
        # "What" as bold paragraph
        blocks.append(_bold_paragraph_block(kl.what))
        # "Why it matters" as paragraph
        blocks.append(_paragraph_block(f"Why it matters: {kl.why_it_matters}"))
        # "How to apply" as numbered sub-steps
        for step in kl.how_to_apply:
            blocks.append(_numbered_item_block(step))
    blocks.append(_divider_block())

    # Section 4: Detailed Notes
    blocks.append(_heading_block("Detailed Notes"))
    for para in page.detailed_notes.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if para.startswith("## "):
            blocks.append(_heading_block(para[3:], level=3))
        elif para.startswith("- "):
            for line in para.split("\n"):
                line = line.lstrip("- ").strip()
                if line:
                    blocks.append(_bulleted_item_block(line))
        else:
            blocks.append(_paragraph_block(para))

    return blocks
