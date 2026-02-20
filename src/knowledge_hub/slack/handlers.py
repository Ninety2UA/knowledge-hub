"""Slack event dispatch and message filtering logic."""

import logging

from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse

from knowledge_hub.config import get_settings
from knowledge_hub.extraction import extract_content
from knowledge_hub.models.slack import SlackEvent
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
    """Resolve URLs and create SlackEvent models.

    This is the background task handoff point for Phase 3+.
    Currently resolves URLs and creates model instances for future processing.
    """
    resolved = await resolve_urls(urls)

    logger.info(
        "Resolved %d/%d URLs for message %s",
        len(resolved),
        len(urls),
        timestamp,
    )

    for url in resolved:
        event = SlackEvent(
            channel_id=channel_id,
            timestamp=timestamp,
            user_id=user_id,
            text=text,
            extracted_urls=[url],
            user_note=user_note,
        )
        # Phase 3: extract content from each URL
        result = await extract_content(url)
        logger.info(
            "Extraction %s for %s (method=%s)",
            result.extraction_status.value,
            url,
            result.extraction_method,
        )
        # Phase 4+ will consume the ExtractedContent result for LLM processing
        logger.debug("Created SlackEvent for URL: %s", event.extracted_urls[0])
