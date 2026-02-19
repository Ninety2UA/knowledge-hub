# Knowledge Base Automation

## What This Is

A hosted automation pipeline that transforms links shared in a Slack channel into structured, actionable knowledge base entries in Notion. The user pastes a URL in `#knowledge-inbox`, and within 60 seconds a fully formatted Notion page appears with a summary, key takeaways, actionable steps, tags, and metadata — requiring zero manual effort.

Built for a single user (performance marketing professional building AI/LLM capabilities) who consumes 5-10 links per day across AI, marketing, and product domains.

## Core Value

Every link shared in Slack becomes a structured, searchable, actionable Notion entry — automatically, reliably, within 60 seconds.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Slack → Cloud Run webhook pipeline (FastAPI, async processing)
- [ ] Content extraction for articles (trafilatura) and YouTube (youtube-transcript-api)
- [ ] LLM processing via Gemini 3 Flash Preview with structured JSON output
- [ ] Notion page creation with 10 database properties and 4-section page template
- [ ] Slack thread reply confirmations (success with Notion link, error with details)
- [ ] Duplicate URL detection via Notion DB query
- [ ] Cloud Run deployment with Docker
- [ ] GCP Secret Manager for all API keys
- [ ] Structured Cloud Run logging
- [ ] Slack reaction emojis on success/failure
- [ ] Content-type-specific prompt variants
- [ ] Redirect and shortened URL handling
- [ ] Paywall detection with partial extraction flagging
- [ ] Batch processing endpoint for backlog import
- [ ] Weekly Slack digest of processed entries
- [ ] Podcast metadata + transcript support
- [ ] PDF link extraction support

### Out of Scope

- LLM provider abstraction / swappability — Gemini is locked in
- Mobile app or browser extension input sources
- Telegram bot as alternative input
- Multi-user support — single user only
- Non-English output — always English regardless of source language
- Quality-based auto-archiving — no quality gate, user curates in Notion
- Real-time chat or interactive features
- Notion database views (created manually by user)

## Context

### Tech Stack (Decided)

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.12 + FastAPI |
| LLM | Gemini 3 Flash Preview ($0.50/$3.00 per MTok) |
| Hosting | Google Cloud Run (scales to zero) |
| Trigger | Slack Events API |
| Output | Notion API |
| Content extraction | trafilatura (articles) + youtube-transcript-api (videos) |
| Containerization | Docker |
| Secrets | Google Secret Manager |

### Notion Database Properties (10)

| Property | Type | Notes |
|----------|------|-------|
| Title | Title | Cleaned-up content title |
| Category | Select | 11 fixed options (from CLAUDE.md) |
| Content Type | Select | Video, Article, Newsletter, Podcast, Thread, LinkedIn Post, PDF |
| Source | URL | Original link |
| Author/Creator | Rich text | — |
| Date Added | Date | Slack message timestamp |
| Status | Select | New, Reviewed, Applied, Archived (default: New) |
| Priority | Select | High, Medium, Low |
| Tags | Multi-select | Cross-cutting themes (seeded core set + LLM-suggested additions) |
| Summary | Rich text | One-paragraph summary |

### Notion Page Template (4 sections)

1. **Summary** — 3-5 sentence executive summary. Reading only this should give 80% of the value.
2. **Key Points** — 5-10 numbered statements, importance-ordered, second-person voice.
3. **Key Learnings & Actionable Steps** — 3-7 structured blocks, each with What / Why it matters / How to apply (concrete, sequential, self-contained, time-estimated steps).
4. **Detailed Notes** — Content-type-specific breakdown. Cap at ~2,500 words. For videos, use section summaries rather than transcript reproduction.

### GCP Status

GCP project exists with billing enabled. Cloud Run and Secret Manager need to be configured.

### Slack Channel

New `#knowledge-inbox` channel (separate from existing `#knowledge-base` used by `/kb` command).

### Existing PRD

Detailed PRD exists at `docs/KB-Automation-PRD.md` covering architecture, data flow, requirements, schema, prompt design, phasing, risks, and cost estimates.

## Constraints

- **LLM**: Gemini 3 Flash Preview only — no abstraction layer needed
- **Cost**: < $5/month at 150 links/month volume
- **Latency**: < 60 seconds end-to-end (Slack message → Notion entry)
- **Slack timeout**: Must ACK within 3 seconds, process asynchronously
- **Hosting**: Google Cloud Run (scales to zero, minimal infra management)
- **Single user**: No auth, no multi-tenancy, no access control

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Gemini 3 Flash Preview as sole LLM | $0.50/$3.00 per MTok, 1M context, frontier quality at lowest cost | — Pending |
| Cloud Run over Lambda/Vercel | GCP ecosystem consistency, scales to zero, generous free tier | — Pending |
| trafilatura for article extraction | Best-in-class article extraction, handles nav/ads/boilerplate removal | — Pending |
| Seeded + dynamic tags | Core tag set for consistency, LLM can suggest new ones auto-created | — Pending |
| New #knowledge-inbox channel | Keeps hosted pipeline separate from existing /kb Claude Code command | — Pending |
| No quality gate | Process everything equally, user curates in Notion | — Pending |
| English-only output | Simplifies prompt design, user's KB is English | — Pending |
| 10 properties (not PRD's 14) | Leaner schema — dropped Quality Score, Relevance Areas, Token Usage, Processing Time, Date Published, User Note | — Pending |
| 4-section page template | Summary, Key Points, Key Learnings & Actionable Steps, Detailed Notes — actionable and scannable | — Pending |

---
*Last updated: 2026-02-19 after initialization*
