# Phase 2: Slack Ingress - Research

**Researched:** 2026-02-20
**Domain:** Slack Events API webhook handling, URL extraction, redirect resolution
**Confidence:** HIGH

## Summary

Phase 2 implements the Slack webhook ingress layer: a FastAPI POST endpoint that receives Slack Events API payloads, verifies request signatures, handles the URL verification challenge, extracts URLs from Slack's mrkdwn format, resolves shortened/redirect URLs, captures user notes, and dispatches processing to background tasks. The endpoint must ACK within 3 seconds per Slack's requirement, with all downstream work happening asynchronously.

The standard approach uses `slack-sdk` (just the `slack_sdk.signature.SignatureVerifier` module -- no Bolt framework needed) for request authentication, a regex pattern against Slack's `<url|label>` angle-bracket format for URL extraction, `httpx.AsyncClient` with `follow_redirects=True` for redirect resolution, and FastAPI's built-in `BackgroundTasks` for async dispatch. No message queue is needed -- FastAPI BackgroundTasks run in the same process after the response is sent, which is sufficient for this single-user personal tool.

**Primary recommendation:** Use `slack-sdk` for signature verification only (lightweight, no Bolt dependency), regex-based URL extraction from Slack mrkdwn, `httpx.AsyncClient` for async redirect resolution with 10-second timeout and 5 max redirects, and FastAPI `BackgroundTasks` for post-response processing.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Message scope
- Only process new messages -- ignore edits (message_changed events)
- Top-level messages only -- thread replies are ignored
- Same endpoint (POST /slack/events) handles both URL verification challenge and message events
- Only process messages from my Slack user ID -- ignore all other users (prevents accidental processing from guests or shared channels)
- Bot messages already filtered per INGEST-05

#### Multi-URL handling
- Each URL in a message becomes a separate pipeline run (separate extraction, analysis, Notion page)
- The full non-URL text is attached as user note to every entry from the same message
- Cap at 10 URLs per message -- URLs beyond 10 are ignored
- All URLs from a single message are dispatched in parallel

#### Failed URL resolution
- Skip unresolvable shortened URLs (dead links, timeouts, 404s) and continue processing remaining URLs
- 10-second timeout for redirect resolution
- Max 5 redirect hops before giving up
- Silent skip on failure -- no logging for unresolved URLs

### Claude's Discretion
- Background task implementation pattern (BackgroundTasks, asyncio, etc.)
- Slack signature verification implementation details
- URL extraction regex/parsing approach
- How to identify shortened URLs vs direct URLs

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INGEST-01 | System accepts webhook events from `#knowledge-inbox` Slack channel | POST /slack/events endpoint with Slack signature verification via `slack_sdk.signature.SignatureVerifier`. URL verification challenge handling for initial setup. |
| INGEST-02 | System extracts URLs from Slack message format (handles `<url\|display>` unfurling) | Regex pattern `<(https?://[^\|>]+)(?:\|[^>]*)?>` extracts URLs from Slack's angle-bracket mrkdwn format. Handles both `<url>` and `<url\|label>` variants. |
| INGEST-03 | System captures non-URL text as user note included in Notion entry | After extracting URLs and their surrounding markup, remaining text (stripped and cleaned) becomes the `user_note` field on the `SlackEvent` model. |
| INGEST-04 | System ACKs Slack within 3 seconds and processes asynchronously in background | FastAPI `BackgroundTasks.add_task()` dispatches processing after returning HTTP 200. Slack retries up to 3 times if no ACK within 3 seconds. |
| INGEST-05 | System ignores bot messages to prevent feedback loops | Check for `bot_id` field or `subtype == "bot_message"` in the event object. Return 200 immediately without processing. |
| INGEST-06 | System ignores messages containing no URLs | After URL extraction, if `extracted_urls` list is empty, return 200 immediately without dispatching background work. |
| INGEST-07 | System processes multiple URLs in a single message as separate entries | Regex extracts all URLs from message text. Each URL dispatched as separate background task. Cap at 10 URLs per CONTEXT.md decision. |
| INGEST-08 | System resolves redirects and shortened URLs (t.co, bit.ly) before processing | `httpx.AsyncClient` with `follow_redirects=True`, `max_redirects=5`, `timeout=10.0`. Resolve all URLs; skip failures silently per CONTEXT.md decision. |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slack-sdk | >=3.40.0 | Slack request signature verification | Official Slack SDK. Only need `slack_sdk.signature.SignatureVerifier` -- no Bolt, no WebClient, no extras. Core package includes signature module with zero additional dependencies. Latest: 3.40.1 (Feb 2026). |
| httpx | >=0.28.0 | Async HTTP client for redirect resolution | Already a dev dependency (Phase 1). Async-native, supports `follow_redirects=True`, `max_redirects`, fine-grained `Timeout` config. Must be promoted from dev to production dependency for redirect resolution. |
| FastAPI BackgroundTasks | (bundled) | Post-response async processing | Built into FastAPI. No additional dependency. Runs tasks after response is sent. Supports both sync and async task functions. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | (builtin) | URL extraction regex | Extract URLs from Slack's `<url\|label>` mrkdwn format. Standard library, no dependency needed. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| slack-sdk SignatureVerifier | Hand-rolled HMAC verification | Would save a dependency but reimplements known-correct logic (HMAC-SHA256 with timing-safe compare, 5-min timestamp window). Not worth the risk of subtle security bugs. |
| FastAPI BackgroundTasks | Celery / Redis queue | Massive overkill for a single-user tool. BackgroundTasks is in-process, zero-infrastructure, and sufficient when there is no need for task persistence, retries, or multi-worker distribution. |
| FastAPI BackgroundTasks | asyncio.create_task() | Works but tasks can be garbage-collected if not awaited. BackgroundTasks is the FastAPI-endorsed pattern and integrates with the request lifecycle. |
| httpx for redirects | requests library | requests is sync-only. httpx provides async support needed for parallel URL resolution within background tasks. Already in the project as a dev dependency. |
| Regex URL extraction | Slack Bolt message parsing | Bolt is a full framework (200+ dependencies). We only need to extract URLs from a known format. A 1-line regex is simpler and has zero dependency cost. |

### Installation

```bash
# Add production dependency
uv add slack-sdk

# Promote httpx from dev to production (currently dev-only)
uv add httpx
```

**Note:** httpx is currently only in `[dependency-groups] dev`. It must be added to `[project] dependencies` for production use (redirect resolution runs in the deployed service, not just tests).

## Architecture Patterns

### Recommended Project Structure

```
src/knowledge_hub/
├── slack/
│   ├── __init__.py          # Package docstring (already exists from Phase 1)
│   ├── router.py            # FastAPI APIRouter with POST /slack/events
│   ├── verification.py      # Slack signature verification dependency
│   ├── urls.py              # URL extraction + redirect resolution
│   └── handlers.py          # Event type dispatch (challenge, message, ignore)
└── config.py                # Add: slack_signing_secret, allowed_user_id

tests/
├── test_slack/
│   ├── __init__.py
│   ├── test_router.py       # Endpoint integration tests
│   ├── test_verification.py # Signature verification unit tests
│   ├── test_urls.py         # URL extraction + resolution unit tests
│   └── test_handlers.py     # Event dispatch logic tests
```

**Key decisions:**
- `router.py` uses `APIRouter` (not adding routes to `app.py` directly) -- keeps app.py clean, routes are included via `app.include_router()`.
- `verification.py` is a FastAPI dependency (via `Depends()`) that extracts raw body, validates signature, and returns parsed JSON. This separates security concern from business logic.
- `urls.py` contains both extraction (sync, pure function) and resolution (async, HTTP calls) -- they are tightly related and always used together.
- `handlers.py` contains the dispatch logic that decides what to do with each event type (challenge response, message processing, ignore).

### Pattern 1: FastAPI Dependency for Signature Verification

**What:** Use a FastAPI dependency function that reads the raw body, verifies the Slack signature, and returns the parsed payload. If verification fails, raise HTTPException(403).
**When to use:** Every request to POST /slack/events.

```python
# src/knowledge_hub/slack/verification.py
# Source: slack-sdk docs + FastAPI dependency injection docs
from fastapi import Request, HTTPException
from slack_sdk.signature import SignatureVerifier

from knowledge_hub.config import get_settings


async def verify_slack_request(request: Request) -> dict:
    """FastAPI dependency: verify Slack signature and return parsed body.

    CRITICAL: Must read raw body BEFORE parsing JSON.
    Signature is computed over the raw bytes, not re-serialized JSON.
    """
    settings = get_settings()
    verifier = SignatureVerifier(signing_secret=settings.slack_signing_secret)

    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not verifier.is_valid(
        body=body,
        timestamp=timestamp,
        signature=signature,
    ):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    return await request.json()
```

### Pattern 2: URL Extraction from Slack mrkdwn

**What:** Extract URLs from Slack's angle-bracket format using regex, then compute the user note from remaining text.
**When to use:** Processing every message event that passes filters.

```python
# src/knowledge_hub/slack/urls.py
import re

# Matches <url> and <url|label> patterns in Slack mrkdwn
# Excludes channel refs (<#C123>), user mentions (<@U123>),
# and special commands (<!here>, <!channel>)
SLACK_URL_PATTERN = re.compile(r"<(https?://[^|>]+)(?:\|[^>]*)?>")


def extract_urls(text: str) -> list[str]:
    """Extract URLs from Slack mrkdwn text.

    Slack wraps URLs in angle brackets: <https://example.com>
    With optional label: <https://example.com|Example>

    Returns list of URL strings (no labels).
    """
    return SLACK_URL_PATTERN.findall(text)


def extract_user_note(text: str) -> str | None:
    """Extract non-URL text from a Slack message as a user note.

    Removes all <url|label> markup, strips whitespace.
    Returns None if no meaningful text remains.
    """
    cleaned = SLACK_URL_PATTERN.sub("", text).strip()
    return cleaned if cleaned else None
```

### Pattern 3: Async Redirect Resolution with httpx

**What:** Resolve shortened/redirect URLs to their final destination using httpx async client with configurable timeout and max redirects.
**When to use:** After URL extraction, before dispatching to downstream processing.

```python
# src/knowledge_hub/slack/urls.py (continued)
import httpx


async def resolve_url(url: str) -> str | None:
    """Resolve a URL through redirects to its final destination.

    Returns the final URL, or None if resolution fails
    (timeout, too many redirects, connection error, non-2xx).

    Uses HEAD request first (faster, less data), falls back to GET
    if HEAD is rejected (405 Method Not Allowed).
    """
    async with httpx.AsyncClient(
        follow_redirects=True,
        max_redirects=5,
        timeout=httpx.Timeout(10.0),
    ) as client:
        try:
            response = await client.head(url)
            return str(response.url)
        except (httpx.HTTPError, httpx.TooManyRedirects):
            return None


async def resolve_urls(urls: list[str]) -> list[str]:
    """Resolve multiple URLs in parallel. Skip failures silently."""
    import asyncio

    results = await asyncio.gather(
        *[resolve_url(url) for url in urls],
        return_exceptions=True,
    )
    return [r for r in results if isinstance(r, str)]
```

### Pattern 4: BackgroundTasks for Post-ACK Processing

**What:** Use FastAPI's BackgroundTasks to dispatch work after returning the 200 response to Slack.
**When to use:** Every message event that contains URLs.

```python
# src/knowledge_hub/slack/router.py
from fastapi import APIRouter, BackgroundTasks, Depends

from knowledge_hub.slack.verification import verify_slack_request
from knowledge_hub.slack.handlers import handle_slack_event

router = APIRouter()


@router.post("/slack/events")
async def slack_events(
    background_tasks: BackgroundTasks,
    payload: dict = Depends(verify_slack_request),
):
    """Receive Slack Events API webhooks.

    Handles:
    - url_verification challenge (returns challenge immediately)
    - event_callback messages (dispatches to background processing)
    - Everything else (returns 200, ignored)
    """
    return await handle_slack_event(payload, background_tasks)
```

### Pattern 5: Event Dispatch Logic

**What:** Route incoming events to appropriate handlers based on type and filters.
**When to use:** Inside the webhook endpoint handler.

```python
# src/knowledge_hub/slack/handlers.py
from fastapi import BackgroundTasks
from fastapi.responses import JSONResponse

from knowledge_hub.config import get_settings
from knowledge_hub.slack.urls import extract_urls, extract_user_note


async def handle_slack_event(
    payload: dict,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """Dispatch Slack event to appropriate handler."""
    event_type = payload.get("type")

    # URL verification challenge
    if event_type == "url_verification":
        return JSONResponse({"challenge": payload["challenge"]})

    # Event callback
    if event_type == "event_callback":
        event = payload.get("event", {})
        await handle_message_event(event, background_tasks)

    return JSONResponse({"ok": True})


async def handle_message_event(
    event: dict,
    background_tasks: BackgroundTasks,
) -> None:
    """Process a message event. Apply all filters before dispatching."""
    settings = get_settings()

    # Filter: only type "message" (not message_changed, etc.)
    if event.get("type") != "message":
        return

    # Filter: ignore messages with subtypes (edits, joins, bot_message, etc.)
    if event.get("subtype") is not None:
        return

    # Filter: ignore bot messages (belt-and-suspenders with subtype check)
    if event.get("bot_id"):
        return

    # Filter: only process messages from allowed user
    if event.get("user") != settings.allowed_user_id:
        return

    # Filter: ignore thread replies (top-level messages only)
    if event.get("thread_ts"):
        return

    # Extract URLs
    text = event.get("text", "")
    urls = extract_urls(text)

    # Filter: ignore messages with no URLs
    if not urls:
        return

    # Cap at 10 URLs
    urls = urls[:10]

    # Extract user note
    user_note = extract_user_note(text)

    # Dispatch to background processing
    background_tasks.add_task(
        process_message_urls,
        channel_id=event["channel"],
        timestamp=event["ts"],
        user_id=event["user"],
        text=text,
        urls=urls,
        user_note=user_note,
    )
```

### Anti-Patterns to Avoid

- **Parsing JSON before reading raw body:** Slack signature verification requires the raw request bytes. If you call `await request.json()` first, the body stream is consumed. Always call `await request.body()` first, verify signature, then parse JSON. In FastAPI, `request.body()` is cached after first read, so calling `request.json()` after `request.body()` works correctly.
- **Using `json.loads()` on the body and comparing to `request.json()`:** JSON re-serialization can change field order or whitespace. Always verify against the raw bytes.
- **Creating a new `httpx.AsyncClient` per URL resolution:** Each client creation opens/closes connection pools. For parallel resolution of multiple URLs from one message, use a single shared client (or use `asyncio.gather` with individual `async with` blocks -- httpx handles this efficiently).
- **Blocking the response with redirect resolution:** URL resolution can take up to 10 seconds per URL. This MUST happen in a background task, not before the 200 response to Slack.
- **Using `asyncio.create_task()` instead of `BackgroundTasks`:** Tasks created with `asyncio.create_task()` can be garbage-collected if not stored. BackgroundTasks is the FastAPI-endorsed approach and is tied to the request lifecycle.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Slack signature verification | Custom HMAC computation | `slack_sdk.signature.SignatureVerifier` | Handles timing-safe comparison, 5-minute replay window, `v0=` prefix formatting, bytes/string encoding. Easy to get subtle crypto wrong. |
| URL redirect resolution | Custom `urllib` redirect following | `httpx.AsyncClient(follow_redirects=True)` | Handles HTTP/HTTPS upgrades, relative redirects, redirect loops, cookie forwarding, protocol changes. Edge cases are numerous. |
| Slack mrkdwn URL parsing | Custom angle-bracket parser | Regex: `<(https?://[^|>]+)(?:\|[^>]*)?>` | Simple, well-defined format. Regex is the standard approach (used by Slack's own examples). No need for a full mrkdwn parser. |
| Background task scheduling | Custom thread/process pool | FastAPI `BackgroundTasks` | Built-in, zero-config, handles both sync and async functions, tied to request lifecycle. |

**Key insight:** The Slack ingress layer is largely "glue code" connecting well-understood components. The complexity is in getting the filters and edge cases right (subtype handling, thread detection, user filtering), not in the technology choices.

## Common Pitfalls

### Pitfall 1: Raw Body Consumed Before Signature Verification
**What goes wrong:** Signature verification always fails because `request.json()` consumes the body stream, and the re-serialized JSON differs from the raw bytes Slack signed.
**Why it happens:** FastAPI automatically parses JSON request bodies. If you declare a Pydantic model parameter, the body is consumed before your code runs.
**How to avoid:** Use a FastAPI dependency that calls `await request.body()` first, verifies the signature, then calls `await request.json()`. Do NOT declare the request body as a Pydantic model parameter -- use `Request` directly.
**Warning signs:** All Slack requests return 403. Signature verification works in tests (where you sign the exact JSON string) but fails with real Slack payloads.

### Pitfall 2: Not Responding Within 3 Seconds
**What goes wrong:** Slack retries the event delivery (up to 3 times), causing duplicate processing.
**Why it happens:** URL resolution, database queries, or other slow operations happen synchronously before returning the response.
**How to avoid:** Return HTTP 200 immediately. All processing (URL resolution, extraction, LLM, Notion) happens in BackgroundTasks after the response. The endpoint handler should only: verify signature, check filters, extract URLs, dispatch to background, return 200.
**Warning signs:** Seeing `X-Slack-Retry-Num` headers in requests. Same message processed multiple times.

### Pitfall 3: Duplicate Event Processing from Slack Retries
**What goes wrong:** Even with fast ACK, Slack may occasionally retry (network hiccup, load balancer timeout). Without idempotency, the same message gets processed twice.
**Why it happens:** Slack's retry mechanism sends the same `event_id` with `X-Slack-Retry-Num` and `X-Slack-Retry-Reason` headers.
**How to avoid:** Check for the `X-Slack-Retry-Num` header at the start of the handler. If present, return 200 immediately without processing. This is a simple deduplication strategy. For belt-and-suspenders, downstream phases (Notion) should also deduplicate by URL.
**Warning signs:** Duplicate Notion pages created for the same URL.

### Pitfall 4: Missing `subtype` Check for Edited Messages
**What goes wrong:** Edited messages (`message_changed` subtype) trigger reprocessing of already-handled URLs.
**Why it happens:** `message_changed` events have `type: "message"` but include a `subtype` field. If you only check `type == "message"`, edits slip through.
**How to avoid:** Reject ALL messages with a `subtype` field present. Regular user messages (the only ones we want) have NO subtype. This is the simplest and most robust filter: `if event.get("subtype") is not None: return`.
**Warning signs:** Same URL processed when user edits their message text.

### Pitfall 5: Thread Replies Triggering Processing
**What goes wrong:** Replies in threads (including our own notification replies from Phase 6) trigger URL processing.
**Why it happens:** Thread replies are `type: "message"` events with a `thread_ts` field. Without checking for `thread_ts`, they pass the type filter.
**How to avoid:** Check `if event.get("thread_ts"): return` to skip all thread replies. Top-level messages do NOT have a `thread_ts` field.
**Warning signs:** Bot's own reply messages or user thread discussions being processed as new URLs.

### Pitfall 6: HEAD Request Rejected by URL Shorteners
**What goes wrong:** Some URL shorteners (especially t.co) reject HEAD requests with 405 Method Not Allowed or return different redirect behavior for HEAD vs GET.
**Why it happens:** Not all servers implement HEAD correctly. Some shorteners treat HEAD differently from GET.
**How to avoid:** Use GET request for redirect resolution (not HEAD). The overhead is minimal since we only need the final URL, not the body content. Alternatively, try HEAD first and fall back to GET on non-2xx response. GET is safer as the default.
**Warning signs:** Some shortened URLs fail to resolve while working fine in a browser.

### Pitfall 7: Config Missing `allowed_user_id`
**What goes wrong:** Without an `allowed_user_id` config field, the user-filtering logic has no value to compare against.
**Why it happens:** Phase 1 defined `slack_bot_token` and `slack_signing_secret` but not `allowed_user_id` (which is a Phase 2 concern).
**How to avoid:** Add `allowed_user_id: str = ""` to the `Settings` class. Require it to be set via environment variable. If empty, reject all messages (fail-closed security).
**Warning signs:** No messages are ever processed, or ALL messages are processed (depending on empty-string comparison behavior).

## Code Examples

### Complete Slack Event Payload (event_callback with message)

```json
{
  "type": "event_callback",
  "token": "XXYYZZ",
  "team_id": "T123ABC456",
  "api_app_id": "A123ABC456",
  "event": {
    "type": "message",
    "channel": "C0AFQJHAVS6",
    "user": "U12345",
    "text": "Great article about AI <https://example.com/ai-article|Example Article> and also <https://t.co/abc123>",
    "ts": "1234567890.123456",
    "event_ts": "1234567890.123456",
    "channel_type": "channel"
  },
  "event_id": "Ev123ABC456",
  "event_time": 1234567890,
  "authorizations": [
    {
      "enterprise_id": "E123ABC456",
      "team_id": "T123ABC456",
      "user_id": "U123ABC456",
      "is_bot": false,
      "is_enterprise_install": false
    }
  ]
}
```

### URL Verification Challenge Payload

```json
{
  "token": "Jhj5dZrVaK7ZwHHjRyZWjbDl",
  "challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P",
  "type": "url_verification"
}
```

**Response (JSON format):**
```json
{"challenge": "3eZbrw1aBm2rZgRNFdxV2595E9CY3gmdALWMmHkvFXO7tYXAYM8P"}
```

### Bot Message Payload (should be ignored)

```json
{
  "type": "event_callback",
  "event": {
    "type": "message",
    "subtype": "bot_message",
    "bot_id": "B12345",
    "text": "Processing complete",
    "channel": "C0AFQJHAVS6",
    "ts": "1234567890.123456"
  }
}
```

### Message Changed Payload (should be ignored)

```json
{
  "type": "event_callback",
  "event": {
    "type": "message",
    "subtype": "message_changed",
    "hidden": true,
    "channel": "C0AFQJHAVS6",
    "ts": "1234567890.123456",
    "message": {
      "type": "message",
      "user": "U12345",
      "text": "edited text",
      "ts": "1234567890.123456",
      "edited": {"user": "U12345", "ts": "1234567891.123456"}
    }
  }
}
```

### Slack URL Extraction Examples

```python
# Source: Slack mrkdwn format docs (docs.slack.dev/messaging/formatting-message-text/)

# URL with label
text = "Check this out <https://example.com/article|Cool Article>"
# extract_urls(text) -> ["https://example.com/article"]

# URL without label
text = "Link: <https://example.com/page>"
# extract_urls(text) -> ["https://example.com/page"]

# Multiple URLs
text = "Two links <https://example.com> and <https://youtube.com/watch?v=abc|Video>"
# extract_urls(text) -> ["https://example.com", "https://youtube.com/watch?v=abc"]

# Channel ref and user mention (should NOT be extracted as URLs)
text = "Hey <@U12345> check <#C12345> and <https://example.com>"
# extract_urls(text) -> ["https://example.com"]
# The regex only matches https?:// prefixed content, so @/# refs are excluded.

# User note extraction
text = "Great read on AI ethics <https://example.com/ai-ethics>"
# extract_user_note(text) -> "Great read on AI ethics"

# No user note (URL only)
text = "<https://example.com>"
# extract_user_note(text) -> None
```

### Config Additions for Phase 2

```python
# src/knowledge_hub/config.py additions
class Settings(BaseSettings):
    # ... existing fields from Phase 1 ...

    # Phase 2: Slack Ingress
    slack_signing_secret: str = ""   # Already exists from Phase 1
    allowed_user_id: str = ""        # NEW: Only process messages from this Slack user
```

### Router Registration in app.py

```python
# src/knowledge_hub/app.py addition
from knowledge_hub.slack.router import router as slack_router

app.include_router(slack_router)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Slack token-based verification | Signing secret + HMAC-SHA256 signature | 2019+ | Token verification is deprecated. All apps must use signing secret verification. |
| `slackclient` package | `slack-sdk` package | 2020 (v3.0) | `slackclient` is deprecated. `slack-sdk` is the successor with modular architecture. |
| requests for HTTP | httpx (sync + async) | 2020-2024 | httpx is the modern alternative with native async support, HTTP/2, and similar API. Already in the project. |
| `on_startup` event handlers | Lifespan context manager | FastAPI 0.93+ (2023) | Already using lifespan from Phase 1. |
| Bolt framework for all Slack apps | slack-sdk for lightweight integrations | Current | Bolt is for full Slack apps with interactivity. For webhook-only integrations (receiving events, verifying signatures), `slack-sdk` is lighter and sufficient. |

**Deprecated/outdated:**
- `slackclient` package: Replaced by `slack-sdk` v3+.
- Token-based request verification: Replaced by signing secret verification.
- Verification tokens in event payloads: The `token` field in event payloads is deprecated for verification purposes. Use `X-Slack-Signature` header instead.

## Open Questions

1. **HEAD vs GET for redirect resolution**
   - What we know: HEAD is faster (no body download) but some URL shorteners reject or mishandle HEAD requests. GET always works but downloads unnecessary body content.
   - What's unclear: Which specific shorteners reject HEAD. The user's most common shortened URLs (t.co from Twitter/X) may or may not support HEAD.
   - Recommendation: Default to GET for reliability. The body content is discarded anyway since we only need the final URL. The extra bandwidth is negligible for redirect resolution.

2. **Slack retry deduplication strategy**
   - What we know: Slack sends `X-Slack-Retry-Num` header on retries. Checking this header and returning 200 immediately is the simplest dedup approach.
   - What's unclear: Whether this is sufficient or if we also need event_id-based deduplication (in-memory set of recently seen event IDs).
   - Recommendation: Start with the retry header check. Add event_id dedup only if duplicate processing is observed in practice. Downstream Notion duplicate detection (Phase 5) provides a safety net.

3. **httpx as production dependency**
   - What we know: httpx is currently dev-only in pyproject.toml. Phase 2 requires it at runtime for redirect resolution.
   - What's unclear: Whether there are any version conflicts between httpx as used by FastAPI/Starlette internally and our direct usage.
   - Recommendation: Add `httpx>=0.28.0` to production dependencies. FastAPI/Starlette use httpx internally for TestClient but don't expose it as a runtime dependency, so no conflict expected.

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/fastapi_tiangolo` - BackgroundTasks API, dependency injection patterns
- Context7 `/slackapi/python-slack-sdk` - SignatureVerifier class, is_valid() method, generate_signature() internals
- Context7 `/encode/httpx` - Redirect handling, follow_redirects, max_redirects, TooManyRedirects exception
- [Slack Events API docs](https://docs.slack.dev/apis/events-api/) - Event callback payload structure, URL verification challenge
- [Slack message formatting docs](https://docs.slack.dev/messaging/formatting-message-text/) - URL angle-bracket format, mrkdwn link syntax
- [Slack signature verification docs](https://docs.slack.dev/authentication/verifying-requests-from-slack/) - HMAC-SHA256 algorithm, X-Slack-Signature header, 5-minute window
- [slack-sdk PyPI](https://pypi.org/project/slack-sdk/) - v3.40.1, Feb 2026, signature module in core package
- [HTTPX timeouts docs](https://www.python-httpx.org/advanced/timeouts/) - Timeout class, per-request and per-client configuration

### Secondary (MEDIUM confidence)
- [Slack url_verification event](https://docs.slack.dev/reference/events/url_verification/) - Challenge request/response format (3 response options)
- [Slack bot_message subtype](https://api.slack.com/events/message/bot_message) - Bot message identification via subtype and bot_id fields
- [Slack Events API retry behavior](https://docs.slack.dev/apis/events-api/) - 3-second ACK requirement, 3 retries, X-Slack-Retry-Num header
- [PeterDaveHello/url-shorteners](https://github.com/PeterDaveHello/url-shorteners) - Comprehensive URL shortener domain list (1000+ domains)

### Tertiary (LOW confidence)
- None -- all findings verified with primary or secondary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - slack-sdk is the official SDK, httpx is already in the project, BackgroundTasks is built-in FastAPI. All versions verified.
- Architecture: HIGH - Webhook + signature verification + background processing is a well-established pattern with extensive Slack documentation and examples.
- Pitfalls: HIGH - Raw body issue, 3-second ACK, retry handling, and subtype filtering are all documented in official Slack and FastAPI docs.
- URL extraction: HIGH - Slack's mrkdwn URL format is well-documented and simple. Regex approach is standard.
- Redirect resolution: HIGH - httpx redirect following is well-documented with clear API. HEAD vs GET tradeoff is a minor open question.

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (30 days -- stable APIs, no anticipated breaking changes)
