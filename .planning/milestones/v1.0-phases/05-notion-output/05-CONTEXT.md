# Phase 5: Notion Output - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Create fully populated Notion knowledge base pages with all 10 properties and 4-section body. Detect duplicate URLs before creation and manage the tag schema. This phase builds the Notion output service — pipeline orchestration and Slack notifications are separate phases (6).

</domain>

<decisions>
## Implementation Decisions

### Duplicate handling
- Match duplicates using **normalized URLs** — strip tracking params (utm_*), normalize protocol to https, remove trailing slashes before comparing
- When a duplicate is found: **skip creation, return existing page info** (page ID, URL, and title) so Phase 6 can tell the user "Already saved: [Title]" with a link
- Always skip — no option to refresh/update existing pages. User must delete the old page manually if they want re-processing
- No staleness tracking or age reporting on duplicates

### Tag management policy
- **Notion database is the source of truth** for valid tags — not the hardcoded SEEDED_TAGS list in code
- Fetch available tags from Notion's Tags multi_select property and **cache with TTL** (refresh periodically, not per-link)
- **Only use existing Notion tags** — if the LLM suggests a tag not in the Notion schema, drop it. No auto-adding new tags to the schema
- If a cached tag becomes stale (removed from Notion between cache refresh and page creation), **drop silently** — page gets created with fewer tags

### Claude's Discretion
- Page body formatting (how 4 sections render as Notion blocks — heading levels, list styles, dividers)
- Cache TTL duration for tags
- Error handling on Notion API failures

</decisions>

<specifics>
## Specific Ideas

- The `/kb` command is NOT part of this solution — this is the hosted FastAPI pipeline processing Slack webhooks
- Tag validation should feed the current Notion tags into the LLM prompt so Gemini only sees tags that actually exist

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-notion-output*
*Context gathered: 2026-02-21*
