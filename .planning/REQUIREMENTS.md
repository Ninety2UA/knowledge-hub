# Requirements: Knowledge Base Automation

**Defined:** 2026-02-19
**Core Value:** Every link shared in Slack becomes a structured, searchable, actionable Notion entry — automatically, reliably, within 60 seconds.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Input & Ingestion

- [x] **INGEST-01**: System accepts webhook events from `#knowledge-inbox` Slack channel
- [x] **INGEST-02**: System extracts URLs from Slack message format (handles `<url|display>` unfurling)
- [x] **INGEST-03**: System captures non-URL text as user note included in Notion entry
- [x] **INGEST-04**: System ACKs Slack within 3 seconds and processes asynchronously in background
- [x] **INGEST-05**: System ignores bot messages to prevent feedback loops
- [x] **INGEST-06**: System ignores messages containing no URLs
- [x] **INGEST-07**: System processes multiple URLs in a single message as separate entries
- [x] **INGEST-08**: System resolves redirects and shortened URLs (t.co, bit.ly) before processing

### Content Extraction

- [x] **EXTRACT-01**: System extracts article body text via trafilatura (removes nav, ads, boilerplate)
- [x] **EXTRACT-02**: System extracts YouTube video transcripts via youtube-transcript-api
- [x] **EXTRACT-03**: System extracts metadata (title, author, date, source domain) from all content types
- [x] **EXTRACT-04**: System detects content type from URL patterns (YouTube, Substack, Medium, etc.)
- [x] **EXTRACT-05**: System enforces 30-second timeout for content extraction with graceful failure
- [x] **EXTRACT-06**: System detects paywalled content and flags entry as partial extraction
- [x] **EXTRACT-07**: System falls back to metadata-only processing for YouTube videos without captions
- [x] **EXTRACT-08**: System extracts text content from PDF links

### LLM Processing

- [ ] **LLM-01**: System processes extracted content via Gemini 3 Flash Preview with structured JSON output
- [ ] **LLM-02**: System generates 4-section page body (Summary, Key Points, Key Learnings & Actionable Steps, Detailed Notes)
- [ ] **LLM-03**: System auto-assigns category from 11 fixed options
- [ ] **LLM-04**: System auto-assigns tags (seeded core set + suggests genuinely new ones)
- [ ] **LLM-05**: System validates LLM output via Pydantic schema before Notion creation
- [ ] **LLM-06**: System retries Gemini API calls with exponential backoff (max 3 retries)
- [ ] **LLM-07**: System generates actionable steps with What / Why it matters / How to apply structure
- [ ] **LLM-08**: System orders key points by importance, not source appearance order
- [ ] **LLM-09**: System assigns priority (High/Medium/Low) based on content relevance signals
- [ ] **LLM-10**: System uses content-type-specific prompt variants (video timestamps, article sections, etc.)

### Notion Output

- [ ] **NOTION-01**: System creates Notion page with all 10 database properties populated
- [ ] **NOTION-02**: System sets status to "New" on page creation
- [ ] **NOTION-03**: System detects and skips duplicate URLs by querying Notion DB before creating
- [ ] **NOTION-04**: System manages tag schema (checks existing options, adds genuinely new tags)

### Notifications

- [ ] **NOTIFY-01**: System replies in Slack thread with Notion page link on successful processing
- [ ] **NOTIFY-02**: System replies in Slack thread with error details if processing fails
- [ ] **NOTIFY-03**: System replies in Slack thread if duplicate URL detected (includes link to existing entry)
- [ ] **NOTIFY-04**: System adds reaction emoji to original Slack message (checkmark on success, X on failure)

### Deployment & Operations

- [ ] **DEPLOY-01**: System runs as Docker container deployable to Google Cloud Run
- [ ] **DEPLOY-02**: All API keys stored in Google Secret Manager (never in code or env files)
- [ ] **DEPLOY-03**: System emits structured JSON logs for Cloud Run logging
- [ ] **DEPLOY-04**: System verifies Slack request signatures on every incoming webhook
- [ ] **DEPLOY-05**: Cloud Run configured with `--min-instances=1` to prevent cold start timeouts
- [ ] **DEPLOY-06**: System sends weekly Slack digest summarizing all entries processed that week
- [ ] **DEPLOY-07**: System logs Gemini token usage and calculates cost per entry

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Content Extraction

- **EXTRACT-09**: System extracts podcast metadata from RSS feeds or podcast platform pages
- **EXTRACT-10**: System extracts podcast transcripts where available

### Batch Processing

- **BATCH-01**: System provides endpoint for bulk URL import (CSV/JSON of URLs)
- **BATCH-02**: System rate-limits batch processing to stay within API limits

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| LLM provider abstraction layer | Gemini is locked in; if swap needed later, refactor one module |
| Quality-based auto-archiving | Removes user agency; LLM quality scores unreliable |
| Multi-user support / auth | Personal tool; no auth, no multi-tenancy |
| Browser extension / mobile app | Slack is sufficient input; share to Slack from mobile |
| Telegram bot | Additional input surface with no benefit over Slack |
| Real-time processing status UI | Slack thread reply is sufficient feedback |
| Content re-processing | One-shot processing; user edits in Notion if needed |
| Notion database views creation | Highly personal; user creates manually |
| Quality score property | Unreliable LLM scoring; Priority (H/M/L) is coarser but better |
| Token usage / processing time as Notion properties | Operational metrics belong in Cloud Run logs, not KB |
| Non-English output | Always English regardless of source language |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INGEST-01 | Phase 2 | Complete |
| INGEST-02 | Phase 2 | Complete |
| INGEST-03 | Phase 2 | Complete |
| INGEST-04 | Phase 2 | Complete |
| INGEST-05 | Phase 2 | Complete |
| INGEST-06 | Phase 2 | Complete |
| INGEST-07 | Phase 2 | Complete |
| INGEST-08 | Phase 2 | Complete |
| EXTRACT-01 | Phase 3 | Complete |
| EXTRACT-02 | Phase 3 | Complete |
| EXTRACT-03 | Phase 3 | Complete |
| EXTRACT-04 | Phase 3 | Complete |
| EXTRACT-05 | Phase 3 | Complete |
| EXTRACT-06 | Phase 3 | Complete |
| EXTRACT-07 | Phase 3 | Complete |
| EXTRACT-08 | Phase 3 | Complete |
| LLM-01 | Phase 4 | Pending |
| LLM-02 | Phase 4 | Pending |
| LLM-03 | Phase 4 | Pending |
| LLM-04 | Phase 4 | Pending |
| LLM-05 | Phase 4 | Pending |
| LLM-06 | Phase 4 | Pending |
| LLM-07 | Phase 4 | Pending |
| LLM-08 | Phase 4 | Pending |
| LLM-09 | Phase 4 | Pending |
| LLM-10 | Phase 4 | Pending |
| NOTION-01 | Phase 5 | Pending |
| NOTION-02 | Phase 5 | Pending |
| NOTION-03 | Phase 5 | Pending |
| NOTION-04 | Phase 5 | Pending |
| NOTIFY-01 | Phase 6 | Pending |
| NOTIFY-02 | Phase 6 | Pending |
| NOTIFY-03 | Phase 6 | Pending |
| NOTIFY-04 | Phase 6 | Pending |
| DEPLOY-01 | Phase 7 | Pending |
| DEPLOY-02 | Phase 7 | Pending |
| DEPLOY-03 | Phase 7 | Pending |
| DEPLOY-04 | Phase 7 | Pending |
| DEPLOY-05 | Phase 7 | Pending |
| DEPLOY-06 | Phase 7 | Pending |
| DEPLOY-07 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 41 total
- Mapped to phases: 41
- Unmapped: 0

---
*Requirements defined: 2026-02-19*
*Last updated: 2026-02-19 after roadmap creation*
