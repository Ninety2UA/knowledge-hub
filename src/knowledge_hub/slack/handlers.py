"""Slack event dispatch and message filtering logic."""

import logging

from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse

from knowledge_hub.config import get_settings
from knowledge_hub.extraction import extract_content
from knowledge_hub.llm import get_gemini_client, process_content
from knowledge_hub.models.content import ExtractionStatus
from knowledge_hub.notion import create_notion_page
from knowledge_hub.notion.models import DuplicateResult
from knowledge_hub.slack.notifier import (
    add_reaction,
    notify_duplicate,
    notify_error,
    notify_success,
)
from knowledge_hub.slack.urls import extract_urls, extract_user_note, resolve_urls

logger = logging.getLogger(__name__)


def handle_slack_event(payload: dict, background_tasks: BackgroundTasks) -> JSONResponse:
    """Dispatch a Slack event based on its type.

    - url_verification: return the challenge token
    - event_callback: process the contained event
    - anything else: acknowledge with 200
    """
    if payload.get("type") == "url_verification":
        return JSONResponse({"challenge": payload["challenge"]})

    if payload.get("type") == "event_callback":
        event = payload.get("event", {})
        handle_message_event(event, background_tasks)
        return JSONResponse({"ok": True})

    return JSONResponse({"ok": True})


def handle_message_event(event: dict, background_tasks: BackgroundTasks) -> None:
    """Apply message filters and dispatch URL processing to background.

    Filters are applied in order (most common rejections first):
    1. Not a message event -> skip
    2. Has subtype (edits, bot_message, joins, etc.) -> skip
    3. Has bot_id -> skip (belt-and-suspenders bot filter)
    4. Wrong user -> skip
    5. Thread reply -> skip
    6. No URLs -> skip
    """
    settings = get_settings()

    # Filter 1: Not a message
    if event.get("type") != "message":
        return

    # Filter 2: Has subtype (edits, bot_message, channel_join, etc.)
    if event.get("subtype") is not None:
        return

    # Filter 3: Bot messages (belt-and-suspenders)
    if event.get("bot_id"):
        return

    # Filter 4: Wrong user
    if event.get("user") != settings.allowed_user_id:
        return

    # Filter 5: Thread replies (not top-level messages)
    if event.get("thread_ts"):
        return

    text = event.get("text", "")

    # Filter 6: No URLs in message
    urls = extract_urls(text)
    if not urls:
        return

    # Cap URLs at 10 per message
    urls = urls[:10]

    user_note = extract_user_note(text)

    logger.info(
        "Dispatching %d URL(s) from user %s in channel %s",
        len(urls),
        event.get("user"),
        event.get("channel"),
    )

    background_tasks.add_task(
        process_message_urls,
        channel_id=event["channel"],
        timestamp=event["ts"],
        user_id=event["user"],
        text=text,
        urls=urls,
        user_note=user_note,
    )


async def process_message_urls(
    channel_id: str,
    timestamp: str,
    user_id: str,
    text: str,
    urls: list[str],
    user_note: str | None,
) -> None:
    """Resolve URLs and process each through the full pipeline.

    For each URL: extract content -> LLM analysis -> Notion page creation -> Slack notification.
    Each URL is processed independently -- one failure does not abort others.
    A single emoji reaction is added to the original message after all URLs are processed.
    """
    resolved = await resolve_urls(urls)

    logger.info(
        "Resolved %d/%d URLs for message %s",
        len(resolved),
        len(urls),
        timestamp,
    )

    gemini_client = get_gemini_client()
    all_succeeded = True

    for url in resolved:
        try:
            # Stage 1: Extract content
            content = await extract_content(url)
            if content.extraction_status == ExtractionStatus.FAILED:
                await notify_error(
                    channel_id, timestamp, url, "extraction",
                    "Content could not be extracted",
                )
                all_succeeded = False
                continue

            # Pass user_note through to content for LLM prompt
            content.user_note = user_note

            # Stage 2: LLM processing
            notion_page, cost_usd = await process_content(gemini_client, content)

            # Stage 3: Notion page creation
            result = await create_notion_page(notion_page)

            if isinstance(result, DuplicateResult):
                await notify_duplicate(channel_id, timestamp, url, result)
                continue  # Duplicate is not a failure

            # Success
            await notify_success(channel_id, timestamp, result, cost_usd=cost_usd)
            logger.info("Pipeline complete for %s -> %s", url, result.page_url)

        except Exception as exc:
            logger.error("Pipeline failed for %s: %s", url, exc, exc_info=True)
            stage = _classify_stage(exc)
            await notify_error(channel_id, timestamp, url, stage, str(exc))
            all_succeeded = False

    # One reaction per message (not per URL) -- checkmark if all succeeded, X if any failed
    emoji = "white_check_mark" if all_succeeded else "x"
    await add_reaction(channel_id, timestamp, emoji)


def _classify_stage(exc: Exception) -> str:
    """Classify which pipeline stage an exception originated from.

    Uses exception module path to identify the stage. Falls back to 'processing'
    for unclassifiable exceptions.
    """
    module = type(exc).__module__ or ""
    if "extraction" in module:
        return "extraction"
    if "llm" in module or "genai" in module or "google" in module:
        return "llm"
    if "notion" in module:
        return "notion"
    return "processing"
