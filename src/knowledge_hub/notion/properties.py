"""Pure function mapping NotionPage to Notion API properties dict.

Maps all 10 KnowledgeEntry fields to the Notion API property format
required by pages.create(). Handles the 2000-character rich_text limit
by splitting long text into multiple rich_text objects.
"""

from knowledge_hub.models.notion import NotionPage


def _split_rich_text(text: str, limit: int = 2000) -> list[dict]:
    """Split text into multiple rich_text objects respecting Notion's 2000-char limit.

    Every text field MUST go through this to avoid 400 errors on long content.
    """
    if not text:
        return [{"type": "text", "text": {"content": ""}}]
    chunks = []
    for i in range(0, len(text), limit):
        chunks.append({"type": "text", "text": {"content": text[i : i + limit]}})
    return chunks


def build_properties(page: NotionPage) -> dict:
    """Map all 10 KnowledgeEntry fields to Notion API property dict.

    Pure function -- no API calls, no async. The caller is responsible for
    setting entry.source to the normalized URL before calling this function.

    Returns a dict suitable for pages.create(properties=...).
    """
    entry = page.entry
    return {
        "Title": {"title": _split_rich_text(entry.title)},
        "Category": {"select": {"name": entry.category.value}},
        "Content Type": {"select": {"name": entry.content_type.value}},
        "Source": {"url": entry.source},
        "Author/Creator": {"rich_text": _split_rich_text(entry.author or "")},
        "Date Added": {"date": {"start": entry.date_added.isoformat()}},
        "Status": {"select": {"name": entry.status.value}},
        "Priority": {"select": {"name": entry.priority.value}},
        "Tags": {"multi_select": [{"name": t} for t in entry.tags]},
        "Summary": {"rich_text": _split_rich_text(entry.summary)},
    }
