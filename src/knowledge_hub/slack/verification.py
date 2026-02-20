"""Slack request signature verification as a FastAPI dependency."""

from fastapi import HTTPException, Request
from slack_sdk.signature import SignatureVerifier

from knowledge_hub.config import get_settings


async def verify_slack_request(request: Request) -> dict:
    """Verify Slack request signature and return parsed JSON payload.

    Reads the raw body FIRST (before any JSON parsing) to ensure the
    signature verification uses the exact bytes Slack signed.

    Raises HTTPException(403) if the signature is invalid.
    """
    settings = get_settings()
    body = await request.body()

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    verifier = SignatureVerifier(signing_secret=settings.slack_signing_secret)

    if not verifier.is_valid(body=body.decode("utf-8"), timestamp=timestamp, signature=signature):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    return await request.json()
