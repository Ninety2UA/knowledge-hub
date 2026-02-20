# Phase 4: LLM Processing - Research

**Researched:** 2026-02-20
**Domain:** LLM-powered content analysis (Gemini 3 Flash Preview + structured output via google-genai SDK)
**Confidence:** HIGH

## Summary

Phase 4 transforms `ExtractedContent` from Phase 3 into structured `NotionPage` objects via Google Gemini 3 Flash Preview. The system sends extracted text/transcript content to Gemini with a detailed system prompt, receives structured JSON validated against Pydantic schemas, and produces a 4-section page body (Summary, Key Points, Key Learnings & Actionable Steps, Detailed Notes) along with category/tags/priority assignments.

The `google-genai` SDK (v1.64.0, GA since May 2025) provides native Pydantic structured output support -- you pass a Pydantic `BaseModel` class as `response_schema` and the SDK guarantees valid JSON conforming to that schema. The response is accessible as a parsed Pydantic object via `response.parsed`, eliminating manual JSON parsing. The SDK also provides async support via `client.aio.models.generate_content()` which integrates naturally with the existing FastAPI async pipeline. For retry logic, tenacity (v9.1.4) is the standard Python retry library with decorator-based exponential backoff, complementing the SDK's built-in `HttpRetryOptions` for transport-level retries.

The existing codebase already defines `NotionPage`, `KnowledgeEntry`, `KeyLearning`, `Category`, `Priority`, and all related models in Phase 1. The LLM module's job is to: (1) build content-type-specific prompts, (2) call Gemini with structured output schema, (3) validate the response, and (4) return a populated `NotionPage` ready for Phase 5.

**Primary recommendation:** Use `google-genai` SDK with `response_schema=LLMResponse` (a Pydantic model mirroring the NotionPage fields the LLM must generate) for structured output. Use `client.aio.models.generate_content()` for async calls. Use tenacity `@retry` decorator with `wait_exponential_jitter` + `stop_after_attempt(3)` for application-level retries on API errors. Build content-type-specific system prompts that vary by `ContentType` enum.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

No locked decisions -- user deferred all implementation decisions to Claude's discretion.

### Claude's Discretion

User deferred all implementation decisions. Claude has full flexibility on the following areas:

**Priority criteria:**
- High: Directly actionable for current work/goals, novel insights, high-signal content
- Medium: Useful reference material, solid content but not immediately actionable
- Low: Tangential interest, thin content, or already-familiar ground
- Signal from extraction status: partial/metadata-only extractions default to Low unless title/description suggests otherwise

**Tagging strategy:**
- Seeded tag set derived from the 11 categories + common cross-cutting concerns (e.g., "strategy", "tutorial", "case-study", "research", "tools", "frameworks")
- 3-7 tags per entry -- enough for discoverability, not so many they lose meaning
- Conservative on new tags: only suggest genuinely new concepts not covered by existing tags
- Tags should be lowercase, hyphenated (e.g., "prompt-engineering", "growth-loops")

**Output voice & depth:**
- Professional, concise, actionable tone -- not academic, not casual
- Summary: dense 3-5 sentences capturing the core argument/finding
- Key Points: concrete statements, not vague observations. Ordered by importance to a practitioner
- Key Learnings: practical, specific How-to-apply steps (not "think about X" but "do X")
- Detailed Notes: structured breakdown preserving source nuance. ~1500-2500 words depending on source depth

**Content-type handling:**
- Articles: standard processing, section headers from source structure
- Videos: include timestamp references in detailed notes where available, note video duration context
- Newsletters: treat as article, extract the substantive content (skip promotional sections)
- PDFs: treat as article
- Threads/LinkedIn posts: shorter output proportional to source length, skip detailed notes if source is < 500 words

### Deferred Ideas (OUT OF SCOPE)

None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LLM-01 | System processes extracted content via Gemini 3 Flash Preview with structured JSON output | `google-genai` SDK v1.64.0 supports `response_schema` with Pydantic models on model `gemini-3-flash-preview`. SDK guarantees JSON output conforming to schema. Async via `client.aio.models.generate_content()`. |
| LLM-02 | System generates 4-section page body (Summary, Key Points, Key Learnings & Actionable Steps, Detailed Notes) | Define a Pydantic response model with `summary_section: str`, `key_points: list[str]`, `key_learnings: list[KeyLearning]`, `detailed_notes: str`. System prompt instructs the model on section requirements. |
| LLM-03 | System auto-assigns category from 11 fixed options | Include `category: Category` (str enum with 11 values) in the response schema. Gemini structured output enforces enum constraint -- only valid values accepted. |
| LLM-04 | System auto-assigns tags (seeded core set + suggests genuinely new ones) | Include `tags: list[str]` in response schema. System prompt provides the seeded tag list and instructs model to prefer existing tags, only suggesting new ones for genuinely novel concepts. Downstream validation can filter. |
| LLM-05 | System validates LLM output via Pydantic schema before Notion creation | `response.parsed` returns a validated Pydantic model instance. Catches `pydantic.ValidationError` on parse failure. Additional application-level validation (e.g., key_points count 5-10, summary sentence count) as a post-validation step. |
| LLM-06 | System retries Gemini API calls with exponential backoff (max 3 retries) | tenacity `@retry(wait=wait_exponential_jitter(initial=1, max=30), stop=stop_after_attempt(4), retry=retry_if_exception_type(...))`. Retries on `ServerError` (5xx) and `ClientError` with code 429. Does NOT retry on 400/401/403. |
| LLM-07 | System generates actionable steps with What / Why it matters / How to apply structure | `KeyLearning` model already exists with `what: str`, `why_it_matters: str`, `how_to_apply: list[str]`. Include in response schema. System prompt enforces the structure with examples. |
| LLM-08 | System orders key points by importance, not source appearance order | System prompt explicitly instructs: "Order key points by importance to a practitioner, NOT by the order they appear in the source." No code-level enforcement needed -- this is a prompt instruction. |
| LLM-09 | System assigns priority (High/Medium/Low) based on content relevance signals | Include `priority: Priority` (str enum) in response schema. System prompt provides priority criteria. Extraction status influences default: partial/metadata-only defaults to Low (enforced in code post-LLM). |
| LLM-10 | System uses content-type-specific prompt variants (video timestamps, article sections, etc.) | Build a prompt template per `ContentType`. Videos: include timestamp context, reference duration. Articles: reference section structure. Short content (<500 words): skip detailed notes instruction. |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | >=1.64.0 | Gemini API client with Pydantic structured output | Official Google SDK (GA since May 2025). Native Pydantic support via `response_schema`. Async client via `client.aio`. Built-in `HttpRetryOptions` for transport-level retries. `response.parsed` returns validated Pydantic objects. |
| tenacity | >=9.1.4 | Application-level retry with exponential backoff | Standard Python retry library. Decorator-based. Supports `wait_exponential_jitter`, `stop_after_attempt`, `retry_if_exception_type`. Cleaner than hand-rolling retry loops. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | (already installed via pydantic-settings) | LLM response validation schema | Define `LLMResponse` model for structured output. Already a project dependency. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tenacity | Hand-rolled retry loop | tenacity handles jitter, backoff math, exception filtering, logging. Hand-rolling is error-prone and verbose. |
| tenacity | google-genai built-in HttpRetryOptions | SDK retry handles transport-level failures (429, 5xx at HTTP level). tenacity handles application-level concerns (validation failures triggering re-prompt, model-specific error handling). Use both layers. |
| google-genai structured output | Manual JSON parsing + json.loads + Pydantic validate | SDK `response_schema` guarantees JSON conformance server-side. Manual parsing adds unnecessary fragility. |

**Installation:**

```bash
uv add google-genai tenacity
```

## Architecture Patterns

### Recommended Project Structure

```
src/knowledge_hub/
├── llm/
│   ├── __init__.py          # Re-export process_content() public API
│   ├── client.py            # Gemini client initialization (singleton)
│   ├── processor.py         # Main processing function: ExtractedContent -> NotionPage
│   ├── prompts.py           # System prompts and content-type prompt templates
│   └── schemas.py           # LLM response Pydantic model (what Gemini returns)
tests/
├── test_llm/
│   ├── __init__.py
│   ├── test_processor.py    # Process function tests (mock Gemini client)
│   ├── test_prompts.py      # Prompt template tests (pure functions)
│   └── test_schemas.py      # Schema validation tests (pure Pydantic)
```

### Pattern 1: Gemini Client Singleton

**What:** Create the `genai.Client` once, reuse across requests. Configure `HttpRetryOptions` for transport-level retries.
**When to use:** Client initialization at module level or via FastAPI dependency.

```python
# src/knowledge_hub/llm/client.py
from google import genai
from google.genai import types
from knowledge_hub.config import get_settings

_client: genai.Client | None = None

def get_gemini_client() -> genai.Client:
    """Return a cached Gemini client instance."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=60_000,  # 60s HTTP timeout (milliseconds)
            ),
        )
    return _client
```

### Pattern 2: Separate LLM Response Schema from NotionPage Model

**What:** Define an `LLMResponse` Pydantic model that contains ONLY the fields the LLM generates (body sections, category, tags, priority). Map it to the existing `NotionPage` model after validation.
**When to use:** Always. The LLM should not generate all NotionPage fields (e.g., `source`, `date_added`, `status`, `content_type` come from extraction, not LLM).

```python
# src/knowledge_hub/llm/schemas.py
from pydantic import BaseModel, Field
from knowledge_hub.models.knowledge import Category, Priority

class LLMKeyLearning(BaseModel):
    """A single structured learning block."""
    what: str
    why_it_matters: str
    how_to_apply: list[str] = Field(min_length=1)

class LLMResponse(BaseModel):
    """Schema for Gemini structured output. Contains only LLM-generated fields."""
    title: str = Field(description="Concise, descriptive title for the knowledge entry")
    summary: str = Field(description="3-5 sentence executive summary")
    category: Category = Field(description="Best-fit category from the 11 options")
    priority: Priority = Field(description="High/Medium/Low based on actionability")
    tags: list[str] = Field(min_length=3, max_length=7, description="3-7 relevant tags")
    summary_section: str = Field(description="3-5 sentence summary for the page body")
    key_points: list[str] = Field(min_length=5, max_length=10, description="5-10 importance-ordered key points")
    key_learnings: list[LLMKeyLearning] = Field(min_length=3, max_length=7)
    detailed_notes: str = Field(description="Structured breakdown, ~1500-2500 words")
```

### Pattern 3: Async Gemini Call with Structured Output

**What:** Call Gemini using the async client with a Pydantic response schema.
**When to use:** For every LLM processing call.

```python
# Source: google-genai SDK docs (Context7 /googleapis/python-genai)
from google.genai import types

async def call_gemini(
    client: genai.Client,
    system_prompt: str,
    user_content: str,
) -> LLMResponse:
    """Call Gemini with structured output, returning a validated LLMResponse."""
    response = await client.aio.models.generate_content(
        model="gemini-3-flash-preview",
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=LLMResponse,
            temperature=1.0,  # Gemini 3 default; do not lower
        ),
    )
    return response.parsed  # Returns LLMResponse instance
```

### Pattern 4: Tenacity Retry with Exception Filtering

**What:** Retry Gemini API calls on transient errors (429, 5xx) with exponential backoff + jitter. Do NOT retry on permanent errors (400, 401, 403).
**When to use:** Wrapping the Gemini call function.

```python
# Source: tenacity docs (Context7 /jd/tenacity)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
)
from google.genai.errors import APIError, ClientError, ServerError
import logging

logger = logging.getLogger(__name__)

def _is_retryable(error: BaseException) -> bool:
    """Return True for transient errors that should be retried."""
    if isinstance(error, ServerError):
        return True  # All 5xx errors
    if isinstance(error, ClientError) and error.code == 429:
        return True  # Rate limit
    return False

@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
    stop=stop_after_attempt(4),  # 1 initial + 3 retries = 4 attempts
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def call_gemini_with_retry(...) -> LLMResponse:
    ...
```

### Pattern 5: Content-Type-Specific Prompt Templates

**What:** Build different system prompts per content type. Videos include timestamp instructions, short content skips detailed notes.
**When to use:** Prompt construction before each Gemini call.

```python
# src/knowledge_hub/llm/prompts.py
from knowledge_hub.models.content import ContentType, ExtractedContent

def build_system_prompt(content: ExtractedContent) -> str:
    """Build a content-type-specific system prompt."""
    base = _BASE_SYSTEM_PROMPT

    if content.content_type == ContentType.VIDEO:
        base += _VIDEO_ADDENDUM  # timestamp references, duration context
    elif content.content_type in (ContentType.THREAD, ContentType.LINKEDIN_POST):
        if (content.word_count or 0) < 500:
            base += _SHORT_CONTENT_ADDENDUM  # skip detailed notes

    return base

def build_user_content(content: ExtractedContent) -> str:
    """Build the user message from extracted content."""
    parts = []
    if content.title:
        parts.append(f"Title: {content.title}")
    if content.author:
        parts.append(f"Author: {content.author}")
    if content.source_domain:
        parts.append(f"Source: {content.source_domain}")

    # Use transcript for videos, text for articles
    body = content.transcript or content.text or content.description or ""
    parts.append(f"\n---\n{body}")

    return "\n".join(parts)
```

### Pattern 6: Mapping LLMResponse to NotionPage

**What:** Combine LLM-generated fields with extraction-derived fields to produce a complete `NotionPage`.
**When to use:** After successful LLM processing, before handing off to Phase 5.

```python
from datetime import datetime, timezone
from knowledge_hub.models.content import ExtractedContent
from knowledge_hub.models.knowledge import KnowledgeEntry, Status
from knowledge_hub.models.notion import KeyLearning, NotionPage

def build_notion_page(llm_result: LLMResponse, content: ExtractedContent) -> NotionPage:
    """Combine LLM output with extraction metadata into a complete NotionPage."""
    entry = KnowledgeEntry(
        title=llm_result.title,
        category=llm_result.category,
        content_type=content.content_type,
        source=content.url,
        author=content.author,
        date_added=datetime.now(timezone.utc),
        status=Status.NEW,
        priority=llm_result.priority,
        tags=llm_result.tags,
        summary=llm_result.summary,
    )

    key_learnings = [
        KeyLearning(
            what=kl.what,
            why_it_matters=kl.why_it_matters,
            how_to_apply=kl.how_to_apply,
        )
        for kl in llm_result.key_learnings
    ]

    return NotionPage(
        entry=entry,
        summary_section=llm_result.summary_section,
        key_points=llm_result.key_points,
        key_learnings=key_learnings,
        detailed_notes=llm_result.detailed_notes,
    )
```

### Anti-Patterns to Avoid

- **Passing the full `NotionPage` model as `response_schema`:** NotionPage contains fields the LLM should NOT generate (`source`, `date_added`, `status`, `content_type`). Use a separate `LLMResponse` model with only LLM-generated fields.
- **Setting temperature below 1.0 for Gemini 3:** Gemini 3 Flash Preview docs recommend the default temperature of 1.0. Lower values may cause unexpected behavior.
- **Retrying on 400/401/403 errors:** These are permanent errors (bad request, auth failure, forbidden). Retrying wastes time and quota.
- **Using the deprecated `google-generativeai` package:** The old SDK (`google-generativeai`) is deprecated. Use `google-genai` (the GA SDK).
- **Blocking the event loop with sync `client.models.generate_content()`:** Use `client.aio.models.generate_content()` for async calls within FastAPI.
- **Hardcoding the seeded tag list in the prompt string:** Store it in a module constant or config so it can be updated without editing prompt text.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON from LLM | Custom JSON parsing + regex extraction | `response_schema=PydanticModel` | SDK enforces schema server-side. Manual parsing breaks on edge cases (nested quotes, Unicode, partial JSON). |
| Retry with exponential backoff | Custom `for` loop with `time.sleep()` | tenacity `@retry` decorator | tenacity handles jitter, logging, exception filtering, max delay capping. Hand-rolling misses edge cases (thundering herd, jitter). |
| Pydantic schema to JSON Schema conversion | Manual dict construction | google-genai SDK auto-converts | SDK handles `$defs` inlining, `nullable` conversion, enum processing, property ordering. Manual conversion is fragile. |
| API error classification (retryable vs permanent) | Status code if/else chains | `google.genai.errors.ClientError` / `ServerError` hierarchy | SDK already classifies 4xx as `ClientError`, 5xx as `ServerError`. Use the type hierarchy. |

**Key insight:** The `google-genai` SDK was designed specifically for Pydantic-native structured output. The entire pipeline from schema definition to parsed response is handled by the SDK. Adding manual JSON handling on top introduces fragility.

## Common Pitfalls

### Pitfall 1: Using the Deprecated google-generativeai Package
**What goes wrong:** Import errors, missing features, incompatible API surface.
**Why it happens:** Many tutorials and Stack Overflow answers reference `google-generativeai` (the old SDK, now deprecated). The new SDK is `google-genai`.
**How to avoid:** Always `pip install google-genai` (or `uv add google-genai`). Import as `from google import genai`.
**Warning signs:** `import google.generativeai` in code, or `pip install google-generativeai` in requirements.

### Pitfall 2: LLM Response Schema Too Complex for Gemini
**What goes wrong:** API returns error or ignores schema constraints. `response.parsed` returns None or raises `ValidationError`.
**Why it happens:** Gemini structured output has limits on schema complexity. Very deep nesting, many `anyOf` unions, or unsupported JSON Schema features (e.g., `additionalProperties`) cause failures.
**How to avoid:** Keep the response schema flat where possible. Use simple types (str, int, list[str], list[BaseModel]). Avoid union types and deeply nested objects. The `LLMResponse` schema proposed above has one level of nesting (KeyLearning inside a list) which is well within limits.
**Warning signs:** `ValueError` during schema processing, or Gemini returning malformed JSON despite schema specification.

### Pitfall 3: Not Distinguishing Transport Retries from Application Retries
**What goes wrong:** Double-retrying (SDK retries + tenacity retries) causes excessive API calls. Or: no retries at all because developer assumes SDK handles everything.
**Why it happens:** The SDK's `HttpRetryOptions` handles HTTP-level transport failures. Application-level retries (tenacity) handle API errors returned as structured responses.
**How to avoid:** Use SDK `HttpRetryOptions` for low-level transport reliability (connection resets, timeouts). Use tenacity for API-level retries (429 rate limits, 500 server errors returned as `APIError`). Don't configure both to retry on the same errors.
**Warning signs:** Log messages showing 9+ retry attempts for a single request (3 SDK retries x 3 tenacity retries).

### Pitfall 4: Prompt Not Constraining Output Length
**What goes wrong:** Gemini generates 5000+ word detailed notes, exceeding useful length. Or generates 1-sentence summaries.
**Why it happens:** Without explicit length guidance, Gemini defaults to whatever length it estimates. Content length varies wildly.
**How to avoid:** System prompt must specify target lengths: "Summary: 3-5 sentences", "Detailed Notes: approximately 1500-2500 words", "Key Points: 5-10 bullet points." For short content (<500 words), explicitly instruct to produce shorter output or skip detailed notes.
**Warning signs:** Wildly inconsistent output lengths across entries.

### Pitfall 5: Validation Error on response.parsed Crashes Pipeline
**What goes wrong:** `response.parsed` raises `pydantic.ValidationError` and the entire pipeline crashes for that URL.
**Why it happens:** Despite schema enforcement, Gemini can occasionally produce JSON that is syntactically valid but fails Pydantic validation (e.g., empty list where `min_length=3` is specified, wrong enum value casing).
**How to avoid:** Wrap `response.parsed` in a try/except `ValidationError` block. On failure, try `json.loads(response.text)` for manual inspection. Consider a retry with adjusted prompt. Always have a fallback path.
**Warning signs:** Intermittent `ValidationError` exceptions in production logs.

### Pitfall 6: Seeded Tag List Becoming Stale or Too Restrictive
**What goes wrong:** Every entry gets the same 3-4 tags because the seeded list is too narrow. Or hundreds of unique tags are created because no seeded list is provided.
**Why it happens:** Tag taxonomy requires iteration. The initial seeded set may not match actual content being processed.
**How to avoid:** Start with a broad seeded set (~30-40 tags) covering the 11 categories plus cross-cutting themes. System prompt instructs: "Prefer tags from this list. Only suggest new tags for concepts not covered." Review and update the seeded list periodically.
**Warning signs:** Tag cardinality explosion (100+ unique tags in first month) or tag stagnation (same 5 tags on every entry).

## Code Examples

### Complete Processor: ExtractedContent to NotionPage

```python
# Source: google-genai SDK (Context7), tenacity docs (Context7)
import logging
from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
)

from knowledge_hub.llm.schemas import LLMResponse
from knowledge_hub.llm.prompts import build_system_prompt, build_user_content
from knowledge_hub.models.content import ExtractedContent, ExtractionStatus
from knowledge_hub.models.notion import NotionPage

logger = logging.getLogger(__name__)

def _is_retryable(error: BaseException) -> bool:
    if isinstance(error, ServerError):
        return True
    if isinstance(error, ClientError) and error.code == 429:
        return True
    return False

@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
    stop=stop_after_attempt(4),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _call_gemini(
    client: genai.Client,
    system_prompt: str,
    user_content: str,
) -> LLMResponse:
    """Call Gemini with retry on transient errors."""
    response = await client.aio.models.generate_content(
        model="gemini-3-flash-preview",
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=LLMResponse,
            temperature=1.0,
        ),
    )
    return response.parsed

async def process_content(
    client: genai.Client,
    content: ExtractedContent,
) -> NotionPage:
    """Transform extracted content into a NotionPage via Gemini."""
    system_prompt = build_system_prompt(content)
    user_content = build_user_content(content)

    llm_result = await _call_gemini(client, system_prompt, user_content)

    # Post-processing: override priority for partial/metadata-only extractions
    if content.extraction_status in (
        ExtractionStatus.PARTIAL,
        ExtractionStatus.METADATA_ONLY,
    ):
        from knowledge_hub.models.knowledge import Priority
        llm_result.priority = Priority.LOW

    return build_notion_page(llm_result, content)
```

### System Prompt Template

```python
_BASE_SYSTEM_PROMPT = """You are a knowledge base curator. Your job is to transform raw content into structured, actionable knowledge entries.

## Output Requirements

### Title
- Concise, descriptive title (not the original article title unless it's already good)
- Should tell a reader what they'll learn

### Summary (summary field)
- 3-5 sentences capturing the core argument, finding, or value
- Dense and informative -- every sentence should carry weight

### Category
Choose exactly one from: AI & Machine Learning, Marketing, Product, Growth, Analytics, Engineering, Design, Business, Career, Productivity, Other

### Priority
- High: Directly actionable, novel insights, high-signal content
- Medium: Useful reference material, solid but not immediately actionable
- Low: Tangential interest, thin content, or already-familiar ground

### Tags
Select 3-7 tags. Prefer tags from this list:
{seeded_tags}
Only suggest new tags for genuinely novel concepts not covered above. Tags must be lowercase, hyphenated.

### Summary Section (summary_section field)
- 3-5 sentence executive summary for the page body
- Can overlap with the summary field but optimized for reading within the full page

### Key Points (key_points field)
- 5-10 concrete, specific statements
- Ordered by importance to a practitioner, NOT by source appearance order
- Each should be self-contained and informative

### Key Learnings (key_learnings field)
- 3-7 structured learning blocks
- Each block has:
  - what: The insight or learning
  - why_it_matters: Why a practitioner should care
  - how_to_apply: Concrete, sequential steps to act on this (not "think about X" but "do X")

### Detailed Notes (detailed_notes field)
- Structured breakdown preserving source nuance
- Use markdown headers, bullet points, and emphasis
- Approximately 1500-2500 words depending on source depth
- Include section headers that reflect the source structure

## Tone
Professional, concise, actionable. Not academic, not casual.
"""

_VIDEO_ADDENDUM = """
## Video-Specific Instructions
- Include timestamp references in detailed notes where available (e.g., "At 5:23, the speaker discusses...")
- Note the video duration context in the summary
- Focus on spoken content from the transcript, not visual descriptions
"""

_SHORT_CONTENT_ADDENDUM = """
## Short Content Instructions
- Source is under 500 words. Produce proportionally shorter output.
- Skip the detailed_notes section (return empty string "").
- Reduce key_points to 3-5 items.
- Reduce key_learnings to 2-3 items.
"""
```

### Seeded Tag Set

```python
# src/knowledge_hub/llm/prompts.py
SEEDED_TAGS = [
    # Category-derived
    "ai", "machine-learning", "deep-learning", "llms", "prompt-engineering",
    "marketing", "content-marketing", "seo", "paid-acquisition", "email-marketing",
    "product-management", "product-strategy", "user-research", "roadmapping",
    "growth", "growth-loops", "retention", "activation", "onboarding",
    "analytics", "data-science", "experimentation", "metrics", "dashboards",
    "engineering", "architecture", "devops", "api-design", "performance",
    "design", "ux", "ui", "design-systems", "accessibility",
    "business", "strategy", "fundraising", "pricing", "marketplace",
    "career", "leadership", "management", "hiring", "mentoring",
    "productivity", "automation", "workflows", "tools", "note-taking",
    # Cross-cutting
    "tutorial", "case-study", "research", "frameworks", "best-practices",
    "startup", "enterprise", "open-source", "trends",
]
```

### Testing Pattern: Mock Gemini Client

```python
# tests/test_llm/test_processor.py
from unittest.mock import AsyncMock, patch, MagicMock
from knowledge_hub.llm.schemas import LLMResponse, LLMKeyLearning
from knowledge_hub.models.content import ExtractedContent, ContentType, ExtractionStatus

def make_mock_llm_response() -> LLMResponse:
    """Create a valid LLMResponse for testing."""
    return LLMResponse(
        title="Test Title",
        summary="Test summary sentence one. Sentence two. Sentence three.",
        category="Engineering",
        priority="High",
        tags=["engineering", "testing", "best-practices"],
        summary_section="Body summary. More detail. Context.",
        key_points=[
            "Point 1", "Point 2", "Point 3",
            "Point 4", "Point 5",
        ],
        key_learnings=[
            LLMKeyLearning(
                what="Testing matters",
                why_it_matters="Catches bugs early",
                how_to_apply=["Write unit tests", "Run before deploy"],
            ),
            LLMKeyLearning(
                what="Mocking is essential",
                why_it_matters="Isolates components",
                how_to_apply=["Use unittest.mock", "Patch external calls"],
            ),
            LLMKeyLearning(
                what="Coverage targets help",
                why_it_matters="Ensures thoroughness",
                how_to_apply=["Set 80% minimum", "Review uncovered lines"],
            ),
        ],
        detailed_notes="## Overview\nDetailed test notes...",
    )

async def test_process_content_article():
    """Test processing an article through the LLM pipeline."""
    content = ExtractedContent(
        url="https://example.com/article",
        content_type=ContentType.ARTICLE,
        title="Test Article",
        text="Long article body text...",
        extraction_status=ExtractionStatus.FULL,
    )

    mock_response = MagicMock()
    mock_response.parsed = make_mock_llm_response()

    with patch(
        "knowledge_hub.llm.processor._call_gemini",
        new_callable=AsyncMock,
        return_value=make_mock_llm_response(),
    ):
        result = await process_content(get_gemini_client(), content)

    assert result.entry.title == "Test Title"
    assert result.entry.category == Category.ENGINEERING
    assert len(result.key_points) == 5
    assert len(result.key_learnings) == 3
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `google-generativeai` package | `google-genai` package | May 2025 (GA) | Old package deprecated. New SDK has native Pydantic support, async client, structured output. |
| Manual JSON mode + `json.loads()` | `response_schema` + `response.parsed` | google-genai SDK | Server-side schema enforcement. No manual JSON parsing needed. |
| `response_mime_type="application/json"` alone | `response_mime_type` + `response_schema` together | google-genai SDK | Schema must accompany MIME type. MIME type alone gives unstructured JSON. |
| Temperature 0.0-0.3 for deterministic output | Temperature 1.0 (default) for Gemini 3 | Gemini 3 | Gemini 3 docs recommend default 1.0. Lower values may cause unexpected behavior. |

**Deprecated/outdated:**
- `google-generativeai` -- deprecated, replaced by `google-genai`
- `genai.configure(api_key=...)` -- old initialization. New SDK uses `genai.Client(api_key=...)`.
- `model.generate_content()` -- old pattern. New SDK uses `client.models.generate_content()` or `client.aio.models.generate_content()`.

## Open Questions

1. **`response.parsed` behavior on schema violation**
   - What we know: SDK documentation says `response.parsed` validates against the Pydantic model. If the JSON doesn't match, Pydantic raises `ValidationError`.
   - What's unclear: Whether Gemini's server-side schema enforcement makes client-side validation failures truly rare, or if they happen regularly (e.g., empty lists violating `min_length`).
   - Recommendation: Always wrap `response.parsed` in try/except `ValidationError`. On failure, log `response.text` for debugging. Retry once with the same prompt. If still failing, return a degraded result. **MEDIUM confidence** -- the SDK docs promise schema conformance but Pydantic `Field` constraints (min_length, max_length) may not be enforced server-side.

2. **google-genai SDK `HttpRetryOptions` default behavior**
   - What we know: The SDK has `HttpRetryOptions` with `attempts`, `initial_delay`, `max_delay`, `exp_base` parameters. When not configured, defaults are applied but not documented.
   - What's unclear: The exact default retry behavior. The SDK may already retry 429s automatically. Adding tenacity on top could cause double-retries.
   - Recommendation: Do NOT configure `HttpRetryOptions` explicitly. Use tenacity as the sole retry mechanism. Catch `APIError` exceptions from the SDK (which means the SDK did NOT retry successfully) and let tenacity handle retries. **LOW confidence** -- defaults undocumented. Test during implementation by inducing a 429 and observing retry behavior.

3. **Gemini 3 Flash Preview stability (preview model)**
   - What we know: Model ID is `gemini-3-flash-preview`. It is a preview model. Pricing is $0.50/M input, $3/M output.
   - What's unclear: Whether the model ID will change when it exits preview (e.g., to `gemini-3-flash`). Whether structured output behavior is stable.
   - Recommendation: Store the model name as a constant, not a config value. When the stable version releases, update the constant. **MEDIUM confidence** -- Google typically keeps preview IDs working for a transition period.

4. **Pydantic `Field` constraints in `response_schema`**
   - What we know: The SDK converts Pydantic models to JSON Schema. JSON Schema supports `minItems`, `maxItems` constraints.
   - What's unclear: Whether Gemini server-side enforcement respects these constraints, or only type/enum constraints.
   - Recommendation: Include `Field(min_length=...)` constraints in the Pydantic model for documentation and client-side validation. Do not rely on server-side enforcement for these. Add post-validation checks if exact counts matter. **LOW confidence** -- needs implementation testing.

## Sources

### Primary (HIGH confidence)
- Context7 `/googleapis/python-genai` v1_33_0 -- structured output with Pydantic, async client, error handling, system instructions, GenerateContentConfig
- [google-genai PyPI](https://pypi.org/project/google-genai/) -- version 1.64.0 confirmed (released 2026-02-19)
- [Gemini 3 Flash Preview model page](https://ai.google.dev/gemini-api/docs/models/gemini-3-flash-preview) -- model ID `gemini-3-flash-preview`, 1M input / 64K output tokens, supports structured output, $0.50/$3 per M tokens
- [Gemini 3 developer guide](https://ai.google.dev/gemini-api/docs/gemini-3) -- structured output support confirmed, default temperature 1.0
- Context7 `/websites/tenacity_readthedocs_io_en` -- exponential backoff, jitter, stop after attempt, retry_if_exception
- [tenacity PyPI](https://pypi.org/project/tenacity/) -- version 9.1.4 confirmed (released 2026-02-07)

### Secondary (MEDIUM confidence)
- [google-genai errors.py source](https://github.com/googleapis/python-genai/blob/main/google/genai/errors.py) -- APIError, ClientError, ServerError hierarchy, error code mapping
- [Pydantic Model Integration DeepWiki](https://deepwiki.com/googleapis/python-genai/3.5.1-pydantic-model-integration) -- `response.parsed` flow, schema transformation pipeline, error handling patterns
- [google-genai retry issue #336](https://github.com/googleapis/python-genai/issues/336) -- HttpRetryOptions parameters (attempts, initial_delay, max_delay)
- [Gemini API structured output docs](https://ai.google.dev/gemini-api/docs/structured-output) -- JSON Schema subset support, complexity limitations

### Tertiary (LOW confidence)
- HttpRetryOptions defaults -- undocumented as of v1.64.0 ([issue #1149](https://github.com/googleapis/python-genai/issues/1149))
- Pydantic Field constraints enforcement by Gemini server -- needs implementation testing
- Gemini 3 Flash Preview model stability -- preview status, ID may change

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- google-genai v1.64.0 and tenacity v9.1.4 both verified via PyPI. Pydantic structured output verified via Context7 + official docs.
- Architecture: HIGH -- patterns follow SDK documentation. Async client, response_schema, response.parsed all verified.
- Pitfalls: HIGH -- deprecated package confusion, retry layering, and schema complexity issues all documented in GitHub issues and SDK docs.
- Prompt engineering: MEDIUM -- prompt structure follows best practices but actual LLM output quality depends on testing with real content.

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (30 days -- monitor Gemini 3 Flash Preview for model ID changes or GA release)
