# Phase 2: Slack Ingress - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Webhook handler that receives Slack events from #knowledge-inbox, validates them, extracts clean URLs from messages, resolves shortened URLs, captures user notes, and dispatches to background processing. Notifications (thread replies, reactions) and downstream processing (extraction, LLM, Notion) are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Message scope
- Only process new messages — ignore edits (message_changed events)
- Top-level messages only — thread replies are ignored
- Same endpoint (POST /slack/events) handles both URL verification challenge and message events
- Only process messages from my Slack user ID — ignore all other users (prevents accidental processing from guests or shared channels)
- Bot messages already filtered per INGEST-05

### Multi-URL handling
- Each URL in a message becomes a separate pipeline run (separate extraction, analysis, Notion page)
- The full non-URL text is attached as user note to every entry from the same message
- Cap at 10 URLs per message — URLs beyond 10 are ignored
- All URLs from a single message are dispatched in parallel

### Failed URL resolution
- Skip unresolvable shortened URLs (dead links, timeouts, 404s) and continue processing remaining URLs
- 10-second timeout for redirect resolution
- Max 5 redirect hops before giving up
- Silent skip on failure — no logging for unresolved URLs

### Claude's Discretion
- Background task implementation pattern (BackgroundTasks, asyncio, etc.)
- Slack signature verification implementation details
- URL extraction regex/parsing approach
- How to identify shortened URLs vs direct URLs

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-slack-ingress*
*Context gathered: 2026-02-20*
