# Phase 6: Pipeline Integration & Notifications - Research

**Researched:** 2026-02-21
**Domain:** End-to-end pipeline wiring + Slack notification APIs (thread replies, emoji reactions)
**Confidence:** HIGH

## Summary

Phase 6 has two distinct responsibilities: (1) wiring the four existing isolated modules (Slack ingress, content extraction, LLM processing, Notion output) into a single working pipeline, and (2) adding Slack notifications (thread replies and emoji reactions) to confirm every outcome to the user. The v1.0 milestone audit identified exactly what is broken: `process_message_urls()` in `handlers.py` calls `extract_content(url)` but discards the result -- `process_content()` from `knowledge_hub.llm` and `create_notion_page()` from `knowledge_hub.notion` are never called. Additionally, `user_note` extracted from Slack messages is silently dropped because `ExtractedContent` has no field for it.

For Slack notifications, the project already has `slack-sdk>=3.40.1` installed and `slack_bot_token` configured in `Settings`. The `AsyncWebClient` from `slack_sdk.web.async_client` provides `chat_postMessage` (with `thread_ts` for thread replies) and `reactions_add` (for emoji reactions). These are straightforward API calls with well-documented error patterns. The bot must have `chat:write` scope (for thread replies) and `reactions:write` scope (for emoji reactions) -- if `reactions:write` is missing, the reaction call will fail with a `missing_scope` error that must be handled gracefully.

The pipeline orchestration is the critical new code. It sits in the existing `process_message_urls()` function (or a new pipeline module) and chains: extract -> LLM process -> Notion create -> notify. Each stage can fail independently, and the notification must reflect the specific failure stage. The Slack client singleton follows the same cached-singleton pattern established by `get_notion_client()` and `get_gemini_client()`.

**Primary recommendation:** Create a `slack/client.py` for the AsyncWebClient singleton and a `slack/notifier.py` for notification functions. Extend `process_message_urls()` in `handlers.py` to call `process_content()`, `create_notion_page()`, and the notifier. Handle each stage's errors with try/except, sending stage-specific error messages to the user via thread reply. Add `user_note` to `ExtractedContent` as an optional field to close the data-loss gap.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None -- user delegated all implementation decisions for this phase.

### Claude's Discretion
- **Notification messages** -- Format, tone, and content of Slack thread replies for success, failure, and duplicate outcomes
- **Multi-URL reporting** -- Whether to use one reply per URL or consolidated replies when a message contains multiple URLs; how to handle partial success (some URLs succeed, some fail)
- **Error detail level** -- How specific error messages are to the user; whether to vary detail by failure stage (extraction vs LLM vs Notion)
- **Reaction emoji behavior** -- Which emojis for which outcomes; handling of processing-in-progress state; graceful fallback if reaction scope is missing

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| NOTIFY-01 | System replies in Slack thread with Notion page link on successful processing | `AsyncWebClient.chat_postMessage(channel=channel_id, thread_ts=message_ts, text=...)`. Thread reply is created by passing the original message's `ts` as `thread_ts`. Format message with Notion page URL and title. Bot needs `chat:write` scope. |
| NOTIFY-02 | System replies in Slack thread with error details if processing fails | Same `chat_postMessage` with `thread_ts`. Catch exceptions from extraction, LLM, and Notion stages independently. Include stage name and error class in the message so user knows WHERE it failed, not just that it failed. |
| NOTIFY-03 | System replies in Slack thread if duplicate URL detected (includes link to existing entry) | `create_notion_page()` returns `DuplicateResult` (with `page_id`, `page_url`, `title`) when duplicate found. Thread reply includes existing page URL and title. No error -- this is a success-path notification. |
| NOTIFY-04 | System adds reaction emoji to original Slack message (checkmark on success, X on failure) | `AsyncWebClient.reactions_add(channel=channel_id, name="white_check_mark", timestamp=message_ts)`. Requires `reactions:write` scope. If scope missing, `SlackApiError` with `missing_scope` error -- catch and log, do not fail the pipeline. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| slack-sdk | >=3.40.1 | Slack API client (thread replies, reactions) | Already installed. Official Python SDK. `AsyncWebClient` for async operations. Context7 confirms `chat_postMessage` with `thread_ts` and `reactions_add` APIs. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (no new libraries) | -- | -- | All required libraries already in pyproject.toml |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AsyncWebClient | httpx direct calls to Slack API | Loses automatic token handling, error parsing, rate limit management. No benefit. |
| Per-URL thread replies | Single consolidated reply | Per-URL is simpler, gives immediate feedback, and avoids complex message assembly. Consolidated reply would batch but delay feedback. |

**Installation:**
```bash
# No new packages needed -- slack-sdk already in pyproject.toml
```

## Architecture Patterns

### Recommended Project Structure
```
src/knowledge_hub/
├── slack/
│   ├── __init__.py       # (update exports)
│   ├── client.py         # NEW: AsyncWebClient singleton (get_slack_client)
│   ├── notifier.py       # NEW: notify_success, notify_error, notify_duplicate, add_reaction
│   ├── router.py         # (unchanged)
│   ├── handlers.py       # (MODIFY: wire full pipeline in process_message_urls)
│   ├── urls.py           # (unchanged)
│   └── verification.py   # (unchanged)
├── models/
│   └── content.py        # (MODIFY: add user_note field to ExtractedContent)
├── extraction/           # (unchanged)
├── llm/                  # (unchanged)
└── notion/               # (unchanged)
```

### Pattern 1: Cached Async Client Singleton
**What:** Same pattern used by `get_notion_client()` and `get_gemini_client()` -- module-level `_client` variable, lazy initialization on first call, `reset_client()` for testing.
**When to use:** For the Slack `AsyncWebClient` initialization.
**Example:**
```python
# Source: verified pattern from knowledge_hub/notion/client.py + Context7 AsyncWebClient docs
from slack_sdk.web.async_client import AsyncWebClient
from knowledge_hub.config import get_settings

_client: AsyncWebClient | None = None

async def get_slack_client() -> AsyncWebClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncWebClient(token=settings.slack_bot_token)
    return _client

def reset_client() -> None:
    global _client
    _client = None
```

### Pattern 2: Stage-Specific Error Handling in Pipeline
**What:** Each pipeline stage (extract, LLM, Notion) is wrapped in its own try/except. On failure, the error is caught, a stage-specific error message is sent to the user, and processing for that URL stops. The pipeline does NOT abort all remaining URLs.
**When to use:** In `process_message_urls()` when iterating over resolved URLs.
**Example:**
```python
# Source: derived from existing codebase patterns (handlers.py, service.py)
for url in resolved:
    try:
        content = await extract_content(url)
        if content.extraction_status == ExtractionStatus.FAILED:
            await notify_error(channel_id, timestamp, url, "extraction", "Content extraction failed")
            await add_reaction(channel_id, timestamp, "x")
            continue

        notion_page = await process_content(gemini_client, content)
        result = await create_notion_page(notion_page)

        if isinstance(result, DuplicateResult):
            await notify_duplicate(channel_id, timestamp, url, result)
            # Duplicate is not a failure -- use checkmark or specific emoji
            continue

        # PageResult -- success
        await notify_success(channel_id, timestamp, result)
        await add_reaction(channel_id, timestamp, "white_check_mark")

    except Exception as exc:
        await notify_error(channel_id, timestamp, url, stage, str(exc))
        await add_reaction(channel_id, timestamp, "x")
```

### Pattern 3: Fire-and-Forget Notifications
**What:** Notification failures (thread reply or reaction) must NEVER crash the pipeline or prevent other URLs from processing. All notification calls are wrapped in try/except with logging only.
**When to use:** Every call to `chat_postMessage` and `reactions_add`.
**Example:**
```python
# Source: Context7 SlackApiError + project error handling patterns
from slack_sdk.errors import SlackApiError

async def add_reaction(channel_id: str, timestamp: str, emoji: str) -> None:
    try:
        client = await get_slack_client()
        await client.reactions_add(channel=channel_id, name=emoji, timestamp=timestamp)
    except SlackApiError as e:
        # Graceful degradation: missing_scope, already_reacted, etc.
        logger.warning("Failed to add reaction %s: %s", emoji, e.response["error"])
```

### Pattern 4: One Thread Reply Per URL
**What:** For messages with multiple URLs, send one thread reply per URL rather than consolidating into a single reply. This provides immediate incremental feedback and avoids complexity of building multi-result messages.
**When to use:** When a Slack message contains 2+ URLs.
**Why:** Simpler implementation, immediate per-URL feedback, easier to scan in Slack thread. A message with 3 URLs gets 3 thread replies (each with its own status).

### Anti-Patterns to Avoid
- **Aborting all URLs on first failure:** Each URL must be processed independently. One failure must not prevent other URLs in the same message from being processed.
- **Generic error messages:** "Processing failed" is useless. Include the URL, the stage that failed, and the error type. User needs to know if it was a network issue (retry later) vs content issue (URL is broken).
- **Letting notification errors propagate:** A `SlackApiError` from `chat_postMessage` or `reactions_add` must never crash the pipeline. Log and continue.
- **Adding reaction per-URL for multi-URL messages:** Reactions are per-message, not per-URL. For multi-URL messages, use a single reaction on the original message: checkmark only if ALL URLs succeeded, X if ANY failed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Slack API authentication | Manual HTTP headers with Bearer token | `AsyncWebClient(token=...)` | Handles auth, rate limiting, retries, error parsing |
| Thread reply assembly | Raw HTTP POST to chat.postMessage | `client.chat_postMessage(thread_ts=...)` | SDK handles serialization, error codes, response validation |
| Emoji reaction | Raw HTTP POST to reactions.add | `client.reactions_add(...)` | SDK handles the three required params (channel, name, timestamp) |
| Slack message formatting | Plain string concatenation | Slack mrkdwn format strings | Slack auto-links URLs in `<url>` format; bold with `*text*` |

**Key insight:** The `slack-sdk` `AsyncWebClient` handles all Slack API complexity. The notification code should be thin wrappers around SDK calls with error handling.

## Common Pitfalls

### Pitfall 1: Reaction Added Multiple Times for Multi-URL Messages
**What goes wrong:** If processing 3 URLs in one message, adding a checkmark reaction after each successful URL results in `already_reacted` error on the 2nd and 3rd calls.
**Why it happens:** Reactions are per-message, not per-URL. You can only add each emoji once per message.
**How to avoid:** Track per-message outcome across all URLs. Add reaction ONCE after all URLs are processed. Use checkmark if all succeeded, X if any failed.
**Warning signs:** `already_reacted` errors in logs; or worse, mixing checkmark and X on the same message (both are valid but confusing).

### Pitfall 2: Bot Not In Channel
**What goes wrong:** `chat_postMessage` fails with `not_in_channel` error because the bot user hasn't been invited to `#knowledge-inbox`.
**Why it happens:** Bot tokens require the bot to be a member of the channel to post messages. Creating the app and adding scopes doesn't auto-join channels.
**How to avoid:** Document that the bot must be invited to `#knowledge-inbox` (`/invite @botname`). Handle `not_in_channel` gracefully in error logging. Alternatively, add `chat:write.public` scope which allows posting to public channels without joining.
**Warning signs:** `not_in_channel` or `channel_not_found` errors in first deployment.

### Pitfall 3: Missing reactions:write Scope
**What goes wrong:** `reactions_add` fails with `missing_scope` error because the Slack app wasn't configured with the `reactions:write` OAuth scope.
**Why it happens:** Developers add `chat:write` for messaging but forget `reactions:write` for emoji reactions. These are separate scopes.
**How to avoid:** Verify both scopes are present in the Slack app configuration. In code, catch `SlackApiError` from `reactions_add` and handle `missing_scope` gracefully -- log a warning and skip reactions rather than crashing. The CONTEXT.md explicitly calls out "graceful fallback if reaction scope is missing."
**Warning signs:** `missing_scope` error on first `reactions_add` call.

### Pitfall 4: user_note Silently Dropped
**What goes wrong:** User adds a note alongside the URL in Slack (e.g., "Check this out for our Q3 strategy <https://example.com>"). The note "Check this out for our Q3 strategy" is extracted in Phase 2 but never reaches the LLM prompt because `ExtractedContent` has no `user_note` field.
**Why it happens:** The milestone audit identified this: `user_note` is captured by `extract_user_note()` and passed to `process_message_urls()`, but `ExtractedContent` has no field for it. The note is dropped at the extraction boundary.
**How to avoid:** Add `user_note: str | None = None` field to `ExtractedContent`. Pass it through extraction, then into the LLM prompt via `build_user_content()`. This closes the INGEST-03 data-loss gap.
**Warning signs:** User notes never appearing in Notion pages.

### Pitfall 5: ExtractionStatus.FAILED Sent to LLM
**What goes wrong:** If extraction returns `FAILED` status (e.g., timeout, network error), the pipeline sends empty/null content to the LLM. Gemini either fails with validation error or generates garbage output.
**Why it happens:** No guard checking `extraction_status` before calling `process_content()`.
**How to avoid:** After `extract_content()`, check `content.extraction_status == ExtractionStatus.FAILED`. If failed, skip LLM + Notion and go directly to error notification. Only proceed to LLM for `FULL`, `PARTIAL`, or `METADATA_ONLY` statuses.
**Warning signs:** Gemini API errors for URLs that failed extraction; Notion pages with nonsensical content.

## Code Examples

Verified patterns from official sources and existing codebase:

### AsyncWebClient Thread Reply
```python
# Source: Context7 /slackapi/python-slack-sdk - chat_postMessage with thread_ts
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

client = AsyncWebClient(token="xoxb-...")

# Success notification (NOTIFY-01)
await client.chat_postMessage(
    channel="C0AFQJHAVS6",
    thread_ts="1234567890.123456",
    text="Saved to Notion: <https://notion.so/page-id|Article Title>"
)

# Error notification (NOTIFY-02)
await client.chat_postMessage(
    channel="C0AFQJHAVS6",
    thread_ts="1234567890.123456",
    text="Failed to process <https://example.com>: Content extraction timed out after 30s"
)

# Duplicate notification (NOTIFY-03)
await client.chat_postMessage(
    channel="C0AFQJHAVS6",
    thread_ts="1234567890.123456",
    text="Already saved: <https://notion.so/page-id|Existing Article Title>"
)
```

### Emoji Reaction
```python
# Source: Context7 /slackapi/python-slack-sdk - reactions_add
# Success reaction (NOTIFY-04)
await client.reactions_add(
    channel="C0AFQJHAVS6",
    name="white_check_mark",  # checkmark emoji
    timestamp="1234567890.123456"
)

# Failure reaction
await client.reactions_add(
    channel="C0AFQJHAVS6",
    name="x",  # X emoji
    timestamp="1234567890.123456"
)
```

### Graceful Reaction Fallback
```python
# Source: Context7 SlackApiError + CONTEXT.md requirement for graceful fallback
async def add_reaction(channel_id: str, timestamp: str, emoji: str) -> None:
    """Add reaction to a message. Silently fails on missing scope or already_reacted."""
    try:
        client = await get_slack_client()
        await client.reactions_add(channel=channel_id, name=emoji, timestamp=timestamp)
    except SlackApiError as e:
        error_code = e.response.get("error", "unknown")
        if error_code in ("missing_scope", "already_reacted", "no_item_specified"):
            logger.warning("Reaction skipped (%s): %s on %s", error_code, emoji, timestamp)
        else:
            logger.error("Unexpected reaction error: %s", e)
```

### Full Pipeline Flow (process_message_urls replacement)
```python
# Source: derived from existing handlers.py + all phase public APIs
from knowledge_hub.extraction import extract_content
from knowledge_hub.llm import get_gemini_client, process_content
from knowledge_hub.models.content import ExtractionStatus
from knowledge_hub.notion import create_notion_page
from knowledge_hub.notion.models import DuplicateResult, PageResult
from knowledge_hub.slack.notifier import add_reaction, notify_duplicate, notify_error, notify_success

async def process_message_urls(
    channel_id: str,
    timestamp: str,
    user_id: str,
    text: str,
    urls: list[str],
    user_note: str | None,
) -> None:
    resolved = await resolve_urls(urls)
    gemini_client = get_gemini_client()  # Sync singleton
    all_succeeded = True

    for url in resolved:
        try:
            # Stage 1: Extract content
            content = await extract_content(url)
            if content.extraction_status == ExtractionStatus.FAILED:
                await notify_error(channel_id, timestamp, url, "extraction",
                                   "Content could not be extracted")
                all_succeeded = False
                continue

            # Pass user_note through to content
            content.user_note = user_note

            # Stage 2: LLM processing
            notion_page = await process_content(gemini_client, content)

            # Stage 3: Notion page creation
            result = await create_notion_page(notion_page)

            if isinstance(result, DuplicateResult):
                await notify_duplicate(channel_id, timestamp, url, result)
                continue  # Duplicate is not failure

            # Stage 4: Success notification
            await notify_success(channel_id, timestamp, result)

        except Exception as exc:
            logger.error("Pipeline failed for %s: %s", url, exc, exc_info=True)
            await notify_error(channel_id, timestamp, url, _classify_stage(exc), str(exc))
            all_succeeded = False

    # One reaction per message (not per URL)
    emoji = "white_check_mark" if all_succeeded else "x"
    await add_reaction(channel_id, timestamp, emoji)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Slack `chat_postMessage` sync only | `AsyncWebClient` with native async/await | slack-sdk 3.x (2023+) | Can use `await` directly in async handlers without `run_in_executor` |
| Manual webhook HTTP calls | `AsyncWebClient` with built-in error handling | slack-sdk 3.x | Automatic rate limit handling, retry, response validation |

**Deprecated/outdated:**
- `slack.WebClient` (old import path) -> use `slack_sdk.web.async_client.AsyncWebClient`
- `SlackClient` (very old) -> removed in slack-sdk 3.x

## Open Questions

1. **Slack bot OAuth scopes**
   - What we know: Bot needs `chat:write` (for thread replies) and `reactions:write` (for emoji reactions). The project's config has `slack_bot_token` but no documentation of which scopes were configured during app setup.
   - What's unclear: Whether the current Slack app has `reactions:write` scope. The CONTEXT.md explicitly mentions "graceful fallback if reaction scope is missing" which suggests this may not be configured.
   - Recommendation: Code `add_reaction` with graceful fallback (catch `missing_scope` error). Document required scopes. Test both with and without `reactions:write`.

2. **user_note forwarding into LLM prompt**
   - What we know: `user_note` is captured in Phase 2 but dropped before LLM processing (milestone audit confirmed). Adding `user_note` to `ExtractedContent` closes the gap. But `build_user_content()` in `llm/prompts.py` also needs modification to include the note.
   - What's unclear: Whether modifying `ExtractedContent` and `build_user_content()` is strictly Phase 6 scope or should be tracked separately.
   - Recommendation: Include in Phase 6 as a pipeline integration fix -- it is exactly the kind of cross-module wiring this phase is for. Minimal change: add field to model, pass through extraction, include in LLM prompt.

3. **Processing-in-progress indicator**
   - What we know: CONTEXT.md mentions "handling of processing-in-progress state" for reaction emoji behavior. An "eyes" or "hourglass_flowing_sand" reaction could indicate processing has started, replaced by checkmark/X when done.
   - What's unclear: Whether adding an intermediate reaction provides value given the 10-60 second processing time.
   - Recommendation: Add "eyes" reaction at start of processing, then remove it and add final reaction. Simple pattern: `reactions_add("eyes")` at start, `reactions_remove("eyes")` + `reactions_add("white_check_mark")` at end. If scope is missing, skip gracefully.

## Sources

### Primary (HIGH confidence)
- Context7 `/slackapi/python-slack-sdk` -- AsyncWebClient initialization, chat_postMessage with thread_ts, reactions_add API, SlackApiError handling
- Existing codebase: `handlers.py`, `service.py`, `client.py` (Notion), `client.py` (Gemini), `config.py` -- established singleton patterns, error handling conventions, pipeline structure
- v1.0 Milestone Audit (`v1.0-MILESTONE-AUDIT.md`) -- integration gaps, broken connections, orphaned exports

### Secondary (MEDIUM confidence)
- Context7 `/slackapi/python-slack-sdk` -- retry handler internals, error response structure (verified against SDK source)

### Tertiary (LOW confidence)
- None -- all findings verified against Context7 or existing codebase patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- slack-sdk already installed, AsyncWebClient API verified via Context7 with code examples
- Architecture: HIGH -- extends established patterns from Phases 1-5 (cached singletons, background task processing, stage-specific error handling)
- Pitfalls: HIGH -- derived from verified Slack API behaviors (documented error codes) and milestone audit findings (integration gaps confirmed by code inspection)

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (stable domain -- Slack SDK and project patterns unlikely to change)
