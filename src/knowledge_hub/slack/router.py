"""Slack webhook router with signature verification."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse

from knowledge_hub.slack.handlers import handle_slack_event
from knowledge_hub.slack.verification import verify_slack_request

router = APIRouter(prefix="", tags=["slack"])


@router.post("/slack/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: dict = Depends(verify_slack_request),
) -> JSONResponse:
    """Receive Slack webhook events.

    Slack retries (X-Slack-Retry-Num header) are acknowledged immediately
    to prevent duplicate processing.
    """
    # Dedup: if Slack is retrying, acknowledge immediately
    if request.headers.get("X-Slack-Retry-Num"):
        return JSONResponse({"ok": True})

    return handle_slack_event(payload, background_tasks)
