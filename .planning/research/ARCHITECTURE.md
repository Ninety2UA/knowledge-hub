# Architecture Research

**Domain:** Slack-to-Notion knowledge automation pipeline
**Researched:** 2026-02-19
**Confidence:** MEDIUM (training data only -- web search and Context7 unavailable; patterns well-established but verify Cloud Run CPU allocation behavior and Gemini 3 Flash Preview structured output specifics against current docs)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          INGRESS LAYER                                  │
│  ┌──────────────┐                                                       │
│  │ Slack Events │─── POST /slack/events ──▶ Signature Verify            │
│  │   API        │                           + URL Challenge             │
│  └──────────────┘                           + Event Dedup               │
├─────────────────────────────────────────────────────────────────────────┤
│                         APPLICATION LAYER                               │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     FastAPI (Cloud Run)                           │   │
│  │                                                                  │   │
│  │  Webhook Handler ──▶ ACK 200 immediately                         │   │
│  │       │                                                          │   │
│  │       ▼                                                          │   │
│  │  Background Task (asyncio.create_task)                           │   │
│  │       │                                                          │   │
│  │       ├──▶ URL Parser ──▶ Content Router                         │   │
│  │       │                       │                                  │   │
│  │       │         ┌─────────────┼─────────────┐                    │   │
│  │       │         ▼             ▼             ▼                    │   │
│  │       │    trafilatura   yt-transcript   fallback                │   │
│  │       │    (articles)    (YouTube)       (httpx raw)             │   │
│  │       │         └─────────────┼─────────────┘                    │   │
│  │       │                       ▼                                  │   │
│  │       ├──▶ Gemini 3 Flash (structured JSON output)               │   │
│  │       │                       │                                  │   │
│  │       ├──▶ Notion API (create page + properties)                 │   │
│  │       │                       │                                  │   │
│  │       └──▶ Slack API (thread reply confirmation)                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                        EXTERNAL SERVICES                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌────────────────┐      │
│  │  Slack   │  │  Notion  │  │ Gemini API   │  │ GCP Secret Mgr │      │
│  │  API     │  │  API     │  │              │  │                │      │
│  └──────────┘  └──────────┘  └──────────────┘  └────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Webhook Handler | Verify Slack signatures, ACK within 3s, dispatch to background | FastAPI route with `BackgroundTasks` or `asyncio.create_task` |
| Event Deduplicator | Prevent processing the same Slack event twice on retries | In-memory set (TTL-based) keyed on `event_id` |
| URL Parser | Extract URLs from Slack message format, classify content type | Regex + URL pattern matching (`<https://url\|display>` format) |
| Content Router | Dispatch to correct extractor based on URL/content type | Strategy pattern or simple if/elif dispatch |
| Article Extractor | Fetch and clean article text, remove boilerplate | trafilatura with fallback timeout |
| YouTube Extractor | Fetch video transcript and metadata | youtube-transcript-api |
| LLM Processor | Send content + system prompt, receive structured JSON | google-genai SDK with JSON schema enforcement |
| Notion Writer | Create database page with properties + block content | notion-client SDK |
| Slack Notifier | Thread replies for success/error/duplicate | slack-sdk `chat_postMessage` with `thread_ts` |
| Secret Manager | Load API keys at startup | google-cloud-secret-manager SDK |

## Recommended Project Structure

```
src/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app creation, lifespan, middleware
│   ├── config.py            # Settings via pydantic-settings (loads from env/secrets)
│   ├── dependencies.py      # FastAPI dependency injection (clients, config)
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── slack_webhook.py # POST /slack/events endpoint
│   │   └── health.py        # GET /health for Cloud Run health checks
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pipeline.py      # Orchestrates the full processing pipeline
│   │   ├── slack.py         # Slack API interactions (thread replies, reactions)
│   │   ├── notion.py        # Notion page creation, duplicate checking
│   │   ├── gemini.py        # LLM processing with structured output
│   │   └── extractors/
│   │       ├── __init__.py
│   │       ├── base.py      # Extractor protocol/ABC
│   │       ├── article.py   # trafilatura-based extraction
│   │       ├── youtube.py   # youtube-transcript-api extraction
│   │       └── router.py    # URL -> extractor dispatch
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── slack.py         # Pydantic models for Slack event payloads
│   │   ├── content.py       # ExtractedContent, ContentType enum
│   │   ├── gemini.py        # LLM input/output schemas
│   │   └── notion.py        # Notion property mapping models
│   │
│   └── prompts/
│       ├── __init__.py
│       └── knowledge.py     # System prompt + content-type variants
│
├── Dockerfile
├── pyproject.toml
├── requirements.txt         # Pinned production deps (or use pyproject.toml)
└── tests/
    ├── conftest.py
    ├── test_webhook.py
    ├── test_pipeline.py
    ├── test_extractors.py
    ├── test_gemini.py
    └── test_notion.py
```

### Structure Rationale

- **`api/`:** Thin HTTP layer. Webhook handler does signature verification, ACK, and dispatches. No business logic here.
- **`services/`:** All business logic. Each service wraps one external dependency (Slack, Notion, Gemini) or orchestrates others (`pipeline.py`). This isolation means each service is independently testable with mocked HTTP clients.
- **`services/extractors/`:** Separate module because extractors multiply (article, YouTube, podcast, PDF). The router pattern keeps the pipeline service clean while allowing new extractors without touching existing code.
- **`models/`:** Pydantic models for type safety and validation. Slack payloads are complex and nested -- typed models prevent runtime key errors. Gemini output schema doubles as the structured output enforcement.
- **`prompts/`:** Prompts as code, not strings buried in service logic. Makes prompt iteration easy (version control, review, test).
- **Flat `app/` root:** No unnecessary nesting. `main.py`, `config.py`, and `dependencies.py` at root because they are cross-cutting.

## Architectural Patterns

### Pattern 1: Immediate ACK + Background Task (Critical)

**What:** Return HTTP 200 to Slack within 3 seconds, then process asynchronously in the same request lifecycle.

**When to use:** Always -- Slack Events API requires acknowledgment within 3 seconds or it retries (up to 3 times with exponential backoff).

**Trade-offs:**
- PRO: No external queue needed (Pub/Sub, Cloud Tasks). Simpler infrastructure.
- PRO: Cloud Run keeps the container alive while the background task runs (if CPU allocation is configured correctly).
- CON: If the container crashes mid-processing, the work is lost. For a personal tool at 5-10 links/day, this is acceptable.
- CON: Requires Cloud Run "CPU always allocated" or the task may be killed after response is sent.

**Critical Cloud Run configuration:**
Cloud Run has two CPU allocation modes. By default, CPU is only allocated during request processing. Once the HTTP response is sent, the container's CPU may be throttled. For background tasks that continue after the response, you MUST set CPU allocation to "CPU is always allocated" (or use Cloud Run's second-generation execution environment). Without this, your background task will stall or be killed after the 200 OK response.

**Example:**
```python
from fastapi import FastAPI, Request, BackgroundTasks
import asyncio

app = FastAPI()

@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()

    # Handle Slack URL verification challenge
    if body.get("type") == "url_verification":
        return {"challenge": body["challenge"]}

    # Verify Slack request signature (middleware or here)
    # ...

    # ACK immediately -- Slack needs this within 3 seconds
    event = body.get("event", {})
    background_tasks.add_task(process_event, event)
    return {"ok": True}

async def process_event(event: dict):
    """Runs after response is sent. Cloud Run keeps container alive."""
    try:
        # Full pipeline: extract -> LLM -> Notion -> Slack reply
        await pipeline.process(event)
    except Exception as e:
        # Notify user of failure in Slack thread
        await slack_service.send_error(event, e)
```

**Why `BackgroundTasks` over `asyncio.create_task`:**
FastAPI's `BackgroundTasks` is tied to the Starlette response lifecycle. It runs after the response is sent but before the ASGI scope closes. This is the correct pattern for Cloud Run because the request is still "active" from Cloud Run's perspective (important for CPU allocation). Using raw `asyncio.create_task` would also work but is harder to test and has no guarantee of lifecycle tracking.

### Pattern 2: Event Deduplication with TTL Cache

**What:** Track processed Slack event IDs in memory to ignore retries.

**When to use:** Always. Slack retries events if it does not receive a timely ACK. Even with fast ACKs, network issues can cause duplicates. Slack sends a unique `event_id` in every event payload.

**Trade-offs:**
- PRO: Simple, no external state needed.
- CON: Not durable across container restarts. For a single-user tool, duplicates from cold starts are rare and harmless (duplicate check against Notion catches them).

**Example:**
```python
from collections import OrderedDict
import time

class EventDeduplicator:
    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000):
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._ttl = ttl_seconds
        self._max_size = max_size

    def is_duplicate(self, event_id: str) -> bool:
        self._evict_expired()
        if event_id in self._seen:
            return True
        self._seen[event_id] = time.monotonic()
        if len(self._seen) > self._max_size:
            self._seen.popitem(last=False)
        return False

    def _evict_expired(self):
        cutoff = time.monotonic() - self._ttl
        while self._seen and next(iter(self._seen.values())) < cutoff:
            self._seen.popitem(last=False)
```

### Pattern 3: Strategy-Based Content Extraction

**What:** Route URLs to specialized extractors based on URL pattern, with a shared interface.

**When to use:** When supporting multiple content types (articles, YouTube, podcasts, PDFs) that each need different extraction logic.

**Trade-offs:**
- PRO: Adding a new content type = add one extractor class + one URL pattern. No changes to pipeline.
- PRO: Each extractor is independently testable.
- CON: Slight over-engineering for only 2 extractors in MVP. Worth it because the PRD explicitly plans for podcast and PDF support.

**Example:**
```python
from dataclasses import dataclass
from enum import Enum
from typing import Protocol
import re

class ContentType(str, Enum):
    ARTICLE = "article"
    YOUTUBE = "youtube"
    PODCAST = "podcast"
    PDF = "pdf"
    UNKNOWN = "unknown"

@dataclass
class ExtractedContent:
    url: str
    content_type: ContentType
    title: str | None
    author: str | None
    text: str                    # Main extracted text/transcript
    metadata: dict               # Type-specific extras (duration, channel, etc.)

class ContentExtractor(Protocol):
    async def extract(self, url: str) -> ExtractedContent: ...
    def can_handle(self, url: str) -> bool: ...

class ContentRouter:
    def __init__(self, extractors: list[ContentExtractor]):
        self._extractors = extractors

    async def extract(self, url: str) -> ExtractedContent:
        for extractor in self._extractors:
            if extractor.can_handle(url):
                return await extractor.extract(url)
        # Fallback: attempt generic extraction
        return await self._fallback_extract(url)
```

### Pattern 4: Structured LLM Output with Pydantic Validation

**What:** Define the expected LLM output as a Pydantic model, use Gemini's structured output mode, and validate the response.

**When to use:** Always when calling an LLM that supports structured output. Eliminates JSON parsing errors and output format drift.

**Trade-offs:**
- PRO: Guaranteed valid JSON matching your schema (Gemini enforces it server-side).
- PRO: Pydantic model serves triple duty: schema definition, response validation, IDE autocomplete.
- CON: Structured output mode may slightly constrain the LLM's creativity. Not an issue for extraction tasks.

**Example:**
```python
from pydantic import BaseModel, Field

class KnowledgeEntry(BaseModel):
    title: str = Field(description="Cleaned content title")
    summary: str = Field(description="3-5 sentence executive summary")
    key_points: list[str] = Field(description="5-10 key points, importance-ordered")
    actionable_steps: list[ActionStep] = Field(description="3-7 concrete steps")
    category: str = Field(description="One of the 11 fixed categories")
    content_type: str
    tags: list[str] = Field(description="3-8 topical tags")
    priority: str = Field(description="High, Medium, or Low")
    author: str | None = None

class ActionStep(BaseModel):
    what: str
    why_it_matters: str
    how_to_apply: str
```

## Data Flow

### Primary Request Flow

```
Slack Event (message_channels)
    │
    ▼
POST /slack/events
    │
    ├──▶ Verify signature (x-slack-signature header + signing secret)
    │    FAIL? → 401 Unauthorized (Slack stops retrying)
    │
    ├──▶ URL verification challenge?
    │    YES? → Return {"challenge": ...} (one-time setup)
    │
    ├──▶ Check event_id in dedup cache
    │    DUPLICATE? → Return 200 OK (ignore)
    │
    ├──▶ Is message from a bot?
    │    YES? → Return 200 OK (prevent loops)
    │
    ├──▶ Extract URLs from message text
    │    NO URLS? → Return 200 OK (ignore)
    │
    ├──▶ Return 200 OK to Slack    ◀── MUST happen within 3 seconds
    │
    └──▶ Background: for each URL:
         │
         ├──▶ Query Notion DB for existing URL
         │    DUPLICATE? → Slack thread reply "already processed" with link
         │    STOP
         │
         ├──▶ Resolve redirects (follow 301/302, handle t.co/bit.ly)
         │
         ├──▶ Route to extractor:
         │    youtube.com, youtu.be → YouTubeExtractor
         │    *.pdf URL             → PDFExtractor (Phase 3)
         │    everything else       → ArticleExtractor (trafilatura)
         │
         ├──▶ Send to Gemini 3 Flash:
         │    Input: system_prompt + extracted_content + user_note
         │    Output: KnowledgeEntry (structured JSON)
         │    Retry: 3 attempts, exponential backoff
         │
         ├──▶ Create Notion page:
         │    Map KnowledgeEntry → 10 DB properties + 4-section page body
         │    Handle new tags (ensure multi_select options exist)
         │    Retry: 2 attempts
         │
         └──▶ Slack thread reply:
              SUCCESS → "Created: [Title](notion_url)"
              ERROR   → "Failed to process: {error details}"
```

### Error Propagation Flow

```
Any step failure
    │
    ├──▶ Log structured error to Cloud Run (JSON with event context)
    │
    ├──▶ Slack thread reply with error details
    │    (user always knows what happened)
    │
    └──▶ DO NOT re-raise (prevent container crash)
         The event is ACK'd. Slack will not retry.
         User can re-post the link to retry manually.
```

### Key Data Transformations

1. **Slack Event -> ProcessingRequest:** Extract URL(s), user note, thread_ts, channel, message_ts from nested Slack event payload.
2. **URL -> ExtractedContent:** Raw URL becomes structured content with text, metadata, content type classification.
3. **ExtractedContent -> KnowledgeEntry:** LLM transforms raw content into structured knowledge (summary, key points, action items, tags, category).
4. **KnowledgeEntry -> Notion Page:** Map Pydantic model fields to Notion database properties (Select, Multi-select, Rich Text, URL, Date types) and page body blocks (Heading, Paragraph, Bulleted List, Numbered List, To-do block types).

## Scaling Considerations

This is a single-user personal tool processing 5-10 links/day. Scaling is not a primary concern, but understanding the architecture's limits helps avoid painting into a corner.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 5-10 links/day (current) | In-process background tasks. No queue. No database. Cloud Run scales to zero. Cost: ~$0/month compute. |
| 50-100 links/day | Same architecture holds. Cloud Run handles concurrent requests. May see occasional cold start delays. |
| 500+ links/day | Consider Cloud Tasks or Pub/Sub for queueing. In-process background tasks can exhaust Cloud Run concurrency limits. Add a dead-letter mechanism for failed processing. |

### Scaling Priorities

1. **First bottleneck: Gemini API rate limits.** At high volume, Gemini rate limits (requests per minute) will be hit before any infrastructure limit. Mitigation: simple semaphore limiting concurrent Gemini calls.
2. **Second bottleneck: Cloud Run concurrency.** If many Slack messages arrive simultaneously (e.g., batch import), background tasks from multiple requests compete for CPU. Mitigation: Set `--concurrency=1` on Cloud Run so each container handles one request at a time, and let Cloud Run scale out horizontally.

## Anti-Patterns

### Anti-Pattern 1: Processing Before ACK

**What people do:** Run content extraction or LLM calls before returning the HTTP response to Slack.
**Why it is wrong:** Slack requires 200 OK within 3 seconds. Content extraction alone can take 5-15 seconds. If Slack does not get ACK in time, it retries -- leading to duplicate processing, wasted API calls, and confusing duplicate Notion entries.
**Do this instead:** Return 200 OK immediately. Move ALL processing to a background task. The only work before ACK should be: signature verification, dedup check, URL presence check. All are sub-millisecond.

### Anti-Pattern 2: Relying on Cloud Run Default CPU Allocation

**What people do:** Use Cloud Run with default settings ("CPU allocated during request processing only") and expect background tasks to complete after the response.
**Why it is wrong:** Once the HTTP response is sent, Cloud Run may throttle CPU to near-zero. Your background task stalls indefinitely or is killed. This is the single most common cause of "it works locally but fails on Cloud Run" for async webhook patterns.
**Do this instead:** Set CPU allocation to "CPU is always allocated" in Cloud Run service configuration. This costs slightly more (CPU charged even when idle) but Cloud Run scales to zero anyway, so idle cost is zero. The flag only affects the window between "response sent" and "background task completes."

### Anti-Pattern 3: No Event Deduplication

**What people do:** Trust that Slack sends each event exactly once.
**Why it is wrong:** Slack explicitly documents at-least-once delivery. Network hiccups, slow ACKs, and Cloud Run cold starts all cause retries. Without dedup, you get duplicate Notion entries.
**Do this instead:** Two layers of dedup: (1) In-memory event_id cache for fast Slack-level dedup, (2) Notion URL query for persistence-level dedup. Belt and suspenders.

### Anti-Pattern 4: Monolithic LLM Prompt

**What people do:** Stuff everything into one massive system prompt -- extraction instructions, output format, content-type variations, tag taxonomy, quality scoring -- creating a 3000+ token prompt that is hard to debug and iterate on.
**Why it is wrong:** Prompt changes become high-risk (breaking one content type while fixing another). Hard to A/B test. Difficult to review.
**Do this instead:** Compose the prompt from modular parts: base system prompt (role, output format) + content-type-specific instructions (appended dynamically based on detected type) + tag taxonomy reference. Keep each part in its own constant or file. The final prompt is assembled at call time but each piece is independently version-controlled.

### Anti-Pattern 5: Passing Raw Notion Block JSON

**What people do:** Build Notion API block arrays by hand with deeply nested dicts.
**Why it is wrong:** Notion's block format is verbose and error-prone. A single heading with rich text requires 4 levels of nesting. Bugs are hard to spot in dict literals.
**Do this instead:** Create helper functions that generate Notion blocks from simple inputs. For example: `heading2("Summary")`, `paragraph(text)`, `numbered_list(items)`. These helpers encapsulate the Notion block format and make the page template readable.

## Integration Points

### External Services

| Service | Integration Pattern | Key Gotchas |
|---------|---------------------|-------------|
| Slack Events API | Inbound webhook (POST to your endpoint) | Must verify `x-slack-signature` header with signing secret + timestamp. Must handle `url_verification` challenge. 3-second ACK deadline. At-least-once delivery. |
| Slack Web API | Outbound REST calls (`chat.postMessage`, `reactions.add`) | Bot token required. `thread_ts` must match original message for thread replies. Rate limit: ~1 req/sec for `chat.postMessage`. |
| Notion API | Outbound REST calls (create page, query database) | Multi-select options must exist in schema before use (or create with update-database call). Rich text blocks have 2000-character limit per block. Rate limit: 3 requests/second. Page content is blocks, not markdown. |
| Gemini API | Outbound REST/gRPC (generate content) | Use `response_mime_type: "application/json"` + `response_schema` for structured output. Retry on 429 and 503. Token counting for cost tracking. 1M context window means you never need to truncate articles. |
| Google Secret Manager | SDK call at startup | Load secrets during FastAPI lifespan event, not per-request. Cache in memory. Secret versions are immutable -- use `latest` alias for convenience. |
| trafilatura | In-process Python library call | Can be slow on large pages (5-10s). Set `no_fallback=False` for best extraction. Returns None on failure -- handle gracefully. May struggle with SPAs (JavaScript-rendered content). |
| youtube-transcript-api | In-process Python library call | Fails on videos without captions. Some auto-generated captions are low quality. Handle `TranscriptsDisabled` and `NoTranscriptFound` exceptions explicitly. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Webhook Handler <-> Pipeline | Direct async function call via BackgroundTasks | Handler passes a parsed `ProcessingRequest` dataclass, not raw Slack JSON. Pipeline never touches Slack payload format. |
| Pipeline <-> Extractors | Async method call through `ContentRouter` | Pipeline gets back `ExtractedContent` regardless of source. Extractors are interchangeable. |
| Pipeline <-> Gemini Service | Async method call | Pipeline passes `ExtractedContent` + user note. Gets back `KnowledgeEntry`. Gemini service owns prompt assembly and retry logic. |
| Pipeline <-> Notion Service | Async method call | Pipeline passes `KnowledgeEntry`. Notion service owns property mapping and block generation. Returns Notion page URL. |
| Pipeline <-> Slack Service | Async method call | Pipeline calls `send_success` or `send_error` with channel, thread_ts, and message content. Slack service owns message formatting. |

## Build Order (Dependencies)

The following build order respects component dependencies -- each phase can be tested independently before the next begins.

### Phase 1: Foundation (no external calls)
Build: Project scaffolding, Dockerfile, config, Pydantic models, health endpoint.
**Why first:** Everything else depends on the app skeleton, config loading, and model definitions. Can be tested with `pytest` and `docker build` alone.

### Phase 2: Slack Ingress (Slack Events API only)
Build: Webhook handler, signature verification, URL verification challenge, event deduplication, URL extraction from Slack message format.
**Why second:** This is the entry point. Without it, nothing triggers. Can be tested with curl/httpie against local server sending mock Slack payloads. No other services needed.

### Phase 3: Content Extraction (trafilatura + youtube-transcript-api)
Build: ArticleExtractor, YouTubeExtractor, ContentRouter, ExtractedContent model.
**Why third:** Extractors are pure functions (URL in, content out). Can be tested independently against real URLs without any other service. This validates that you can actually get content before involving the LLM.

### Phase 4: LLM Processing (Gemini API)
Build: Gemini service, prompt templates, structured output schema, retry logic.
**Why fourth:** Depends on ExtractedContent model from Phase 3. Can be tested by feeding saved extraction results into Gemini. This is where you iterate on prompt quality.

### Phase 5: Notion Output (Notion API)
Build: Notion service, property mapping, block generation helpers, duplicate checking, tag management.
**Why fifth:** Depends on KnowledgeEntry model from Phase 4. Can be tested by feeding mock KnowledgeEntry objects into Notion. Validates the full output format.

### Phase 6: Pipeline Orchestration + Slack Notifications
Build: Pipeline service that wires everything together. Slack notification service (thread replies).
**Why last:** This is pure orchestration -- calling services built in Phases 2-5 in sequence. Integration testing validates the full flow.

### Phase 7: Cloud Run Deployment
Build: Cloud Run configuration, Secret Manager integration, CPU allocation settings, CI/CD.
**Why last:** Everything works locally first. Deployment is configuration, not code.

## Sources

- Slack Events API documentation (api.slack.com/events-api) -- MEDIUM confidence (training data, not live-verified)
- FastAPI BackgroundTasks documentation (fastapi.tiangolo.com/tutorial/background-tasks/) -- MEDIUM confidence
- Cloud Run CPU allocation documentation (cloud.google.com/run/docs/configuring/cpu-allocation) -- MEDIUM confidence (verify "always allocated" setting name and behavior against current docs)
- Notion API reference (developers.notion.com/reference) -- MEDIUM confidence
- Gemini API structured output documentation (ai.google.dev/gemini-api/docs/structured-output) -- LOW confidence (Gemini 3 Flash Preview is new; verify structured output support and parameter names)
- trafilatura documentation (trafilatura.readthedocs.io) -- MEDIUM confidence
- youtube-transcript-api documentation (github.com/jdepoix/youtube-transcript-api) -- MEDIUM confidence

**Important note on confidence:** All sources are from training data. Web search and Context7 were unavailable during research. The architectural patterns (webhook ACK + background task, event deduplication, strategy-based extraction) are well-established and unlikely to have changed. However, specific API details for Gemini 3 Flash Preview (parameter names, structured output syntax) and Cloud Run CPU allocation (exact flag name, billing implications) should be verified against current documentation before implementation.

---
*Architecture research for: Slack-to-Notion knowledge automation pipeline*
*Researched: 2026-02-19*
