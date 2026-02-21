"""Slack notification functions for pipeline outcomes.

All functions are fire-and-forget: they catch and log errors but never raise,
ensuring notification failures cannot crash the pipeline or prevent other URLs
from processing.
"""

import logging

from slack_sdk.errors import SlackApiError

from knowledge_hub.notion.models import DuplicateResult, PageResult
from knowledge_hub.slack.client import get_slack_client

logger = logging.getLogger(__name__)


async def notify_success(channel_id: str, timestamp: str, result: PageResult) -> None:
    """Post a thread reply with a link to the newly created Notion page.

    Args:
        channel_id: Slack channel ID.
        timestamp: Original message timestamp (thread parent).
        result: Successful page creation result with URL and title.
    """
    try:
        client = await get_slack_client()
        await client.chat_postMessage(
            channel=channel_id,
            thread_ts=timestamp,
            text=f"Saved to Notion: <{result.page_url}|{result.title}>",
        )
    except SlackApiError:
        logger.warning(
            "Failed to send success notification for %s", result.page_url, exc_info=True
        )


async def notify_error(
    channel_id: str, timestamp: str, url: str, stage: str, detail: str
) -> None:
    """Post a thread reply describing the failure stage and error.

    Args:
        channel_id: Slack channel ID.
        timestamp: Original message timestamp (thread parent).
        url: The URL that failed processing.
        stage: Pipeline stage where the error occurred (extraction, llm, notion, processing).
        detail: Human-readable error description.
    """
    try:
        client = await get_slack_client()
        await client.chat_postMessage(
            channel=channel_id,
            thread_ts=timestamp,
            text=f"Failed to process <{url}>: {stage} \u2014 {detail}",
        )
    except SlackApiError:
        logger.warning(
            "Failed to send error notification for %s", url, exc_info=True
        )


async def notify_duplicate(
    channel_id: str, timestamp: str, url: str, duplicate: DuplicateResult
) -> None:
    """Post a thread reply linking to the existing Notion page.

    Args:
        channel_id: Slack channel ID.
        timestamp: Original message timestamp (thread parent).
        url: The duplicate URL.
        duplicate: Duplicate detection result with existing page URL and title.
    """
    try:
        client = await get_slack_client()
        await client.chat_postMessage(
            channel=channel_id,
            thread_ts=timestamp,
            text=f"Already saved: <{duplicate.page_url}|{duplicate.title}>",
        )
    except SlackApiError:
        logger.warning(
            "Failed to send duplicate notification for %s", url, exc_info=True
        )


async def add_reaction(channel_id: str, timestamp: str, emoji: str) -> None:
    """Add an emoji reaction to the original message.

    Handles common non-error conditions gracefully:
    - missing_scope: bot lacks reactions:write permission
    - already_reacted: reaction already exists on the message
    - no_item_specified: message not found (deleted or invalid timestamp)

    Args:
        channel_id: Slack channel ID.
        timestamp: Original message timestamp.
        emoji: Emoji name without colons (e.g., "white_check_mark").
    """
    try:
        client = await get_slack_client()
        await client.reactions_add(
            channel=channel_id,
            name=emoji,
            timestamp=timestamp,
        )
    except SlackApiError as exc:
        error_code = exc.response.get("error", "") if exc.response else ""
        if error_code in ("missing_scope", "already_reacted", "no_item_specified"):
            logger.warning(
                "Reaction '%s' not added (%s): %s", emoji, error_code, timestamp
            )
        else:
            logger.error(
                "Failed to add reaction '%s' to %s: %s",
                emoji,
                timestamp,
                error_code,
                exc_info=True,
            )
