# Knowledge Base Automation

## What This Is

A hosted automation pipeline that transforms links shared in a Slack channel into structured, actionable knowledge base entries in Notion. The user pastes a URL in `#knowledge-inbox`, and within 60 seconds a fully formatted Notion page appears with a summary, key takeaways, actionable steps, tags, and metadata — requiring zero manual effort.

Built for a single user (performance marketing professional building AI/LLM capabilities) who consumes 5-10 links per day across AI, marketing, and product domains.

## Core Value

Every link shared in Slack becomes a structured, searchable, actionable Notion entry — automatically, reliably, within 60 seconds.

## Requirements

### Validated

- ✓ Slack → Cloud Run webhook pipeline (FastAPI, async processing) — v1.0
- ✓ Content extraction for articles (trafilatura), YouTube (youtube-transcript-api), and PDFs (pypdf) — v1.0
- ✓ LLM processing via Gemini 3 Flash Preview with structured JSON output — v1.0
- ✓ Notion page creation with 10 database properties and 4-section page template — v1.0
- ✓ Slack thread reply confirmations (success with Notion link, error with details) — v1.0
- ✓ Duplicate URL detection via Notion DB query — v1.0
- ✓ Cloud Run deployment with Docker (source-based deploy) — v1.0
- ✓ GCP Secret Manager for all API keys — v1.0
- ✓ Structured JSON Cloud Run logging — v1.0
- ✓ Slack reaction emojis on success/failure — v1.0
- ✓ Content-type-specific prompt variants — v1.0
- ✓ Redirect and shortened URL handling — v1.0
- ✓ Paywall detection with partial extraction flagging — v1.0
- ✓ Weekly Slack digest of processed entries — v1.0
- ✓ Gemini token usage and cost tracking per entry — v1.0

### Active

- [ ] Batch processing endpoint for backlog import
- [ ] Podcast metadata + transcript support

### Out of Scope

- LLM provider abstraction / swappability — Gemini is locked in
- Mobile app or browser extension input sources
- Telegram bot as alternative input
- Multi-user support — single user only
- Non-English output — always English regardless of source language
- Quality-based auto-archiving — no quality gate, user curates in Notion
- Real-time chat or interactive features
- Notion database views (created manually by user)
- Token usage / processing time as Notion properties — operational metrics belong in Cloud Run logs

## Context

Shipped v1.0 with 2,554 LOC Python (+ 3,859 LOC tests, 235 passing).
Tech stack: Python 3.12, FastAPI, Gemini 3 Flash Preview, Cloud Run, trafilatura, youtube-transcript-api, pypdf.
41 requirements satisfied across 8 phases in 4 days.

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.12 + FastAPI |
| LLM | Gemini 3 Flash Preview ($0.50/$3.00 per MTok) |
| Hosting | Google Cloud Run (source-based deploy, min-instances=1) |
| Trigger | Slack Events API (webhook) |
| Output | Notion API (via notion-client) |
| Content extraction | trafilatura (articles) + youtube-transcript-api (videos) + pypdf (PDFs) |
| Containerization | Docker |
| Secrets | Google Secret Manager |
| Logging | python-json-logger (structured JSON) |

### Notion Database Properties (10)

| Property | Type | Notes |
|----------|------|-------|
| Title | Title | Cleaned-up content title |
| Category | Select | 11 fixed options |
| Content Type | Select | Video, Article, Newsletter, Podcast, Thread, LinkedIn Post, PDF |
| Source | URL | Original link |
| Author/Creator | Rich text | — |
| Date Added | Date | Slack message timestamp |
| Status | Select | New, Reviewed, Applied, Archived (default: New) |
| Priority | Select | High, Medium, Low |
| Tags | Multi-select | 58 seeded tags, unknown tags silently dropped |
| Summary | Rich text | One-paragraph summary |

### Notion Page Template (4 sections)

1. **Summary** — 3-5 sentence executive summary. Reading only this should give 80% of the value.
2. **Key Points** — 5-10 numbered statements, importance-ordered, second-person voice.
3. **Key Learnings & Actionable Steps** — 3-7 structured blocks, each with What / Why it matters / How to apply.
4. **Detailed Notes** — Content-type-specific breakdown. Cap at ~2,500 words.

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
| Gemini 3 Flash Preview as sole LLM | $0.50/$3.00 per MTok, 1M context, frontier quality at lowest cost | ✓ Good — cost tracking shows well under $5/month budget |
| Cloud Run over Lambda/Vercel | GCP ecosystem consistency, scales to zero, generous free tier | ✓ Good — source-based deploy works, min-instances=1 prevents cold starts |
| trafilatura for article extraction | Best-in-class article extraction, handles nav/ads/boilerplate removal | ✓ Good |
| Seeded + dynamic tags → silently drop unknown | Core 58-tag set for consistency, unknown tags dropped (not auto-created) | ⚠️ Revisit — original intent was auto-create; changed to drop for schema safety |
| New #knowledge-inbox channel | Keeps hosted pipeline separate from existing /kb Claude Code command | ✓ Good |
| No quality gate | Process everything equally, user curates in Notion | ✓ Good |
| English-only output | Simplifies prompt design, user's KB is English | ✓ Good |
| 10 properties (not PRD's 14) | Leaner schema — dropped Quality Score, Relevance Areas, Token Usage, Processing Time, Date Published, User Note | ✓ Good — simpler, all useful fields retained |
| 4-section page template | Summary, Key Points, Key Learnings & Actionable Steps, Detailed Notes | ✓ Good |
| Source-based Cloud Run deploy | Avoids needing Docker locally; GCP builds container from source | ✓ Good — simplified dev workflow |
| In-memory cost accumulators | Not Cloud Logging queries; resets on instance restart | ⚠️ Revisit if multi-instance |
| Fire-and-forget notifications | Slack notify functions catch errors and log, never raise | ✓ Good — pipeline never fails due to notification issues |
| Tuple return for cost | `(NotionPage, cost_usd)` from `process_content` | ✓ Good — keeps domain model clean |

---
*Last updated: 2026-02-22 after v1.0 milestone*
