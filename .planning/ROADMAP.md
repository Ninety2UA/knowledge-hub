# Roadmap: Knowledge Base Automation

## Overview

This roadmap delivers a hosted Slack-to-Notion automation pipeline in 7 phases following the component dependency graph. Each phase builds on the types and services of the previous one, and each is independently testable before the next begins. The ordering is driven by a hard constraint: you cannot test orchestration until services exist, you cannot test services until the ingress exists to trigger them, and none of it works until the foundation is sound. Phase 1 establishes the runnable skeleton; Phases 2-5 build each pipeline stage (ingress, extraction, LLM, output); Phase 6 wires them into a complete pipeline with user-facing notifications; Phase 7 deploys to production.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Project Foundation** - Runnable FastAPI skeleton with data models, config, Docker, and test infrastructure
- [x] **Phase 2: Slack Ingress** - Webhook handler that receives Slack events, validates them, extracts URLs, and dispatches to background processing
- [ ] **Phase 3: Content Extraction** - Extractors for articles and YouTube videos with content-type routing, timeouts, and fallback handling
- [ ] **Phase 4: LLM Processing** - Gemini-powered structured content analysis with 4-section output, categorization, tagging, and priority assignment
- [ ] **Phase 5: Notion Output** - Page creation with all 10 properties, 4-section body, duplicate detection, and tag schema management
- [ ] **Phase 6: Pipeline Integration & Notifications** - End-to-end orchestration wiring all services together with Slack thread replies for every outcome
- [ ] **Phase 7: Cloud Run Deployment** - Production deployment with secrets management, cold start prevention, CPU allocation, and operational logging

## Phase Details

### Phase 1: Project Foundation
**Goal**: A runnable, testable FastAPI application skeleton that all subsequent phases build upon
**Depends on**: Nothing (first phase)
**Requirements**: None (infrastructure scaffolding -- requirements are addressed in Phases 2-7)
**Success Criteria** (what must be TRUE):
  1. FastAPI app starts and responds to GET /health with 200 OK
  2. All Pydantic data models (SlackEvent, ExtractedContent, KnowledgeEntry, NotionPage) are defined and importable
  3. Config loading reads environment variables with sensible defaults for local development
  4. Docker image builds successfully and runs the app with the same health check behavior
  5. pytest runs and passes with at least one test per model validating schema correctness
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md -- Project scaffold + config + FastAPI app + data models
- [x] 01-02-PLAN.md -- Tests + Docker

### Phase 2: Slack Ingress
**Goal**: The system reliably receives Slack messages from #knowledge-inbox and extracts clean URLs for processing
**Depends on**: Phase 1
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06, INGEST-07, INGEST-08
**Success Criteria** (what must be TRUE):
  1. POST /slack/events with a valid Slack payload returns 200 within 3 seconds and triggers background processing
  2. Bot messages and URL-less messages are silently ignored (no processing, no error)
  3. URLs are correctly extracted from Slack's `<url|label>` format, including multiple URLs in a single message
  4. Shortened/redirect URLs (t.co, bit.ly) are resolved to their final destination before being passed downstream
  5. Non-URL text from the message is captured as a user note alongside the extracted URLs
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md -- Slack ingress implementation (dependencies, config, verification, URLs, handlers, router)
- [x] 02-02-PLAN.md -- TDD tests (URL extraction unit tests, handler filter tests, router integration tests)

### Phase 3: Content Extraction
**Goal**: The system extracts meaningful text and metadata from article URLs and YouTube videos
**Depends on**: Phase 2
**Requirements**: EXTRACT-01, EXTRACT-02, EXTRACT-03, EXTRACT-04, EXTRACT-05, EXTRACT-06, EXTRACT-07, EXTRACT-08
**Success Criteria** (what must be TRUE):
  1. Given an article URL, the system returns clean body text (no nav, ads, boilerplate) with title, author, and source metadata
  2. Given a YouTube URL, the system returns the video transcript with title, channel, and metadata
  3. YouTube videos without captions fall back to metadata-only extraction (no crash, no empty result)
  4. Paywalled content is detected and flagged as partial extraction rather than silently returning empty content
  5. All extraction operations complete or timeout within 30 seconds with a graceful failure message
**Plans**: 2 plans

Plans:
- [ ] 03-01-PLAN.md -- Model update + content type router + paywall config + extractors (article, YouTube, PDF)
- [ ] 03-02-PLAN.md -- Pipeline orchestration + timeout wrapper + comprehensive TDD tests

### Phase 4: LLM Processing
**Goal**: The system transforms extracted content into structured, actionable knowledge entries via Gemini
**Depends on**: Phase 3
**Requirements**: LLM-01, LLM-02, LLM-03, LLM-04, LLM-05, LLM-06, LLM-07, LLM-08, LLM-09, LLM-10
**Success Criteria** (what must be TRUE):
  1. Given extracted content, the system produces a 4-section page body (Summary, Key Points, Key Learnings & Actionable Steps, Detailed Notes)
  2. Key Points are ordered by importance and actionable steps follow the What / Why it matters / How to apply structure
  3. Category is assigned from the 11 fixed options, tags are selected from the seeded set or genuinely new ones suggested, and priority is assigned as High/Medium/Low
  4. Every LLM response is validated against a Pydantic schema before being passed to Notion -- invalid responses are caught and retried
  5. Gemini API failures are retried with exponential backoff (max 3 attempts) before being reported as errors
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

### Phase 5: Notion Output
**Goal**: The system creates fully populated Notion knowledge base pages and manages the database schema
**Depends on**: Phase 4
**Requirements**: NOTION-01, NOTION-02, NOTION-03, NOTION-04
**Success Criteria** (what must be TRUE):
  1. A Notion page is created with all 10 database properties correctly populated (Title, Category, Content Type, Source, Author/Creator, Date Added, Status=New, Priority, Tags, Summary)
  2. The page body contains all 4 sections rendered as properly formatted Notion blocks (headings, paragraphs, numbered lists)
  3. Duplicate URLs are detected by querying the Notion database before creation -- duplicates are skipped, not created
  4. New tags suggested by the LLM are added to the database schema before being used on a page
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Pipeline Integration & Notifications
**Goal**: The full pipeline works end-to-end with Slack thread replies confirming every outcome to the user
**Depends on**: Phase 2, Phase 3, Phase 4, Phase 5
**Requirements**: NOTIFY-01, NOTIFY-02, NOTIFY-03, NOTIFY-04
**Success Criteria** (what must be TRUE):
  1. Pasting a URL in #knowledge-inbox produces a Notion page AND a Slack thread reply with the Notion link
  2. If processing fails at any stage, the user receives a Slack thread reply with specific error details (not a generic failure message)
  3. If a duplicate URL is detected, the user receives a Slack thread reply with a link to the existing Notion entry
  4. The original Slack message receives a reaction emoji (checkmark on success, X on failure)
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

### Phase 7: Cloud Run Deployment
**Goal**: The pipeline runs in production on Cloud Run with proper secrets, logging, and operational configuration
**Depends on**: Phase 6
**Requirements**: DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05, DEPLOY-06, DEPLOY-07
**Success Criteria** (what must be TRUE):
  1. The service is deployed on Cloud Run and processes a real Slack message end-to-end within 60 seconds
  2. All API keys are stored in Google Secret Manager and loaded at startup (no keys in code, env files, or Docker images)
  3. Slack request signatures are verified on every incoming webhook -- unsigned or tampered requests are rejected
  4. Cold starts do not cause Slack ACK timeouts (min-instances=1) and background tasks survive after HTTP response (CPU always allocated)
  5. Processing logs are structured JSON visible in Cloud Run logging, including Gemini token usage and cost per entry
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Project Foundation | 2/2 | Complete    | 2026-02-20 |
| 2. Slack Ingress | 2/2 | Complete    | 2026-02-20 |
| 3. Content Extraction | 0/? | Not started | - |
| 4. LLM Processing | 0/? | Not started | - |
| 5. Notion Output | 0/? | Not started | - |
| 6. Pipeline Integration & Notifications | 0/? | Not started | - |
| 7. Cloud Run Deployment | 0/? | Not started | - |
