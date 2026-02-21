"""Weekly digest builder and daily cost alert logic.

Queries Notion for recent entries, builds a formatted Slack message summarizing
the week's knowledge base activity, and checks daily Gemini spend against a threshold.
"""

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

from knowledge_hub.config import get_settings
from knowledge_hub.cost import get_daily_cost, get_weekly_cost, reset_weekly_cost
from knowledge_hub.notion.client import get_notion_client, get_data_source_id
from knowledge_hub.slack.client import get_slack_client

logger = logging.getLogger(__name__)


async def query_recent_entries(days: int = 7) -> list[dict]:
    """Query Notion database for entries added in the last N days.

    Handles pagination to return all matching entries.

    Args:
        days: Number of days to look back from now (default 7).

    Returns:
        Flat list of Notion page objects.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    client = await get_notion_client()
    data_source_id = await get_data_source_id()

    all_entries: list[dict] = []
    start_cursor: str | None = None

    while True:
        kwargs: dict = {
            "database_id": data_source_id,
            "filter": {
                "property": "Date Added",
                "date": {"on_or_after": cutoff},
            },
        }
        if start_cursor:
            kwargs["start_cursor"] = start_cursor

        result = await client.databases.query(**kwargs)
        all_entries.extend(result.get("results", []))

        if result.get("has_more"):
            start_cursor = result.get("next_cursor")
        else:
            break

    return all_entries


def _extract_entry_data(page: dict) -> dict:
    """Extract structured data from a Notion page object.

    Args:
        page: A Notion page object with properties.

    Returns:
        Dict with keys: title, url, category, tags.
    """
    props = page.get("properties", {})

    # Title (title type)
    title_prop = props.get("Title", {})
    title_items = title_prop.get("title", [])
    title = title_items[0].get("plain_text", "Untitled") if title_items else "Untitled"

    # Source URL (url type)
    source_prop = props.get("Source", {})
    url = source_prop.get("url", "")

    # Category (select type)
    category_prop = props.get("Category", {})
    category_select = category_prop.get("select")
    category = category_select.get("name", "Unknown") if category_select else "Unknown"

    # Tags (multi_select type)
    tags_prop = props.get("Tags", {})
    tags_items = tags_prop.get("multi_select", [])
    tags = [tag.get("name", "") for tag in tags_items]

    return {
        "title": title,
        "url": url,
        "category": category,
        "tags": tags,
    }


def build_weekly_digest(entries: list[dict], total_cost: float = 0.0) -> str:
    """Build a formatted Slack message summarizing the week's entries.

    Args:
        entries: List of extracted entry data dicts (from _extract_entry_data).
        total_cost: Total Gemini API cost for the period.

    Returns:
        Formatted Slack message string.
    """
    if not entries:
        return (
            "No entries processed this week. Service is running.\n"
            f"*Total Gemini cost:* ${total_cost:.4f}"
        )

    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=7)).strftime("%b %d")
    end_date = now.strftime("%b %d, %Y")

    lines: list[str] = []

    # Header
    lines.append(f"*Weekly Knowledge Base Digest*\n_{start_date} to {end_date}_\n")

    # Entry count
    lines.append(f"*{len(entries)} entries processed*\n")

    # Entry list
    for entry in entries:
        url = entry.get("url", "")
        title = entry.get("title", "Untitled")
        if url:
            lines.append(f"- <{url}|{title}>")
        else:
            lines.append(f"- {title}")

    lines.append("")

    # Category breakdown
    categories = Counter(entry.get("category", "Unknown") for entry in entries)
    category_parts = [f"{count} {cat.lower()}s" if count > 1 else f"{count} {cat.lower()}"
                      for cat, count in categories.most_common()]
    lines.append(f"*Categories:* {', '.join(category_parts)}\n")

    # Top tags
    all_tags: list[str] = []
    for entry in entries:
        all_tags.extend(entry.get("tags", []))
    if all_tags:
        tag_counts = Counter(all_tags)
        top_tags = [f"{tag} ({count})" for tag, count in tag_counts.most_common(5)]
        lines.append(f"*Top tags:* {', '.join(top_tags)}\n")

    # Total cost
    lines.append(f"*Total Gemini cost:* ${total_cost:.4f}")

    return "\n".join(lines)


async def send_weekly_digest() -> dict:
    """Query recent entries, build digest, and send as Slack DM.

    Returns:
        Dict with status and entry count.
    """
    settings = get_settings()

    # Query Notion for recent entries
    try:
        pages = await query_recent_entries(days=7)
        entries = [_extract_entry_data(page) for page in pages]
    except Exception as e:
        logger.error("Failed to query Notion for digest", extra={"error": str(e)})
        return {"status": "error", "error": f"Failed to query Notion: {e}"}

    # Get accumulated cost
    total_cost = get_weekly_cost()

    # Build message
    message = build_weekly_digest(entries, total_cost=total_cost)

    # Send DM
    try:
        client = await get_slack_client()
        await client.chat_postMessage(
            channel=settings.allowed_user_id,
            text=message,
        )
    except Exception as e:
        logger.error("Failed to send digest via Slack", extra={"error": str(e), "entries": len(entries)})
        return {"status": "error", "error": f"Failed to send Slack message: {e}", "entries": len(entries)}

    # Reset weekly accumulator only after successful send
    reset_weekly_cost()

    logger.info(
        "Weekly digest sent",
        extra={"entries": len(entries), "total_cost": round(total_cost, 6)},
    )

    return {"status": "sent", "entries": len(entries)}


async def check_daily_cost() -> dict:
    """Check daily Gemini cost and alert if over threshold.

    Returns:
        Dict with status and current cost.
    """
    settings = get_settings()
    cost = get_daily_cost()

    if cost > 5.0:
        try:
            client = await get_slack_client()
            await client.chat_postMessage(
                channel=settings.allowed_user_id,
                text=f"Daily Gemini cost alert: ${cost:.2f} exceeds $5.00 threshold",
            )
        except Exception as e:
            logger.error("Failed to send cost alert via Slack", extra={"error": str(e), "cost_usd": round(cost, 6)})
            return {"status": "error", "error": f"Failed to send cost alert: {e}", "cost": cost}
        logger.warning(
            "Daily cost alert triggered",
            extra={"cost_usd": round(cost, 6)},
        )
        return {"status": "alert_sent", "cost": cost}

    logger.info(
        "Daily cost check OK",
        extra={"cost_usd": round(cost, 6)},
    )
    return {"status": "ok", "cost": cost}
