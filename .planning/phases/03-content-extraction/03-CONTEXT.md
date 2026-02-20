# Phase 3: Content Extraction - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract meaningful text and metadata from article URLs, YouTube videos, and PDFs. Route by content type, enforce timeouts, handle failures gracefully. Content is extracted and structured — LLM analysis and Notion output are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Content type routing
- URL pattern matching (regex) to detect content type — no HTTP header checks
- Four extractor types: YouTube (transcript), PDF (text extraction), platform-specific (Substack, Medium — better metadata only, same body extraction via trafilatura), and general article (trafilatura for everything else)
- Unknown URL types fall through to the general article extractor
- Platform-specific extractors enhance metadata only (newsletter name, author bio, series info) — body text still uses trafilatura

### Failure & fallback chain
- When body text extraction fails but metadata is available, proceed with metadata-only — mark as partial extraction
- 30-second hard cap on total wall-clock time per URL (not per extractor step)
- One retry on transient failures (network timeouts, 5xx responses), still within the 30s budget
- Accept any extraction result regardless of text length — no minimum threshold

### PDF extraction depth
- Extract full text from entire PDF (LLM phase handles summarization downstream)
- No OCR for scanned/image-based PDFs — fall back to metadata-only
- 20MB file size cap — skip extraction for larger PDFs, flag as metadata-only
- Extract author/title from PDF document properties (embedded metadata) when available

### Paywall handling
- Known paywalled domain list stored in config (not hardcoded) for easy updates
- Still attempt extraction on paywalled domains — some give partial content (first paragraphs)
- Flag extraction result using a status enum: `full | partial | metadata_only | failed`
- The extraction status enum captures all failure modes (paywall, timeout, empty, error) in one field

### Claude's Discretion
- Choice of PDF extraction library
- Exact regex patterns for content type detection
- Which domains to include in the initial paywalled domain list
- Platform-specific metadata field mapping for Substack/Medium

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

*Phase: 03-content-extraction*
*Context gathered: 2026-02-20*
