# Phase 5: Notion Output - Research

**Researched:** 2026-02-21
**Domain:** Notion API integration (page creation, database querying, schema management)
**Confidence:** HIGH

## Summary

Phase 5 transforms the `NotionPage` model (produced by Phase 4's LLM processor) into actual Notion pages with all 10 database properties and a 4-section formatted body. The primary library is `notion-client` v3.0.0 (the official Python SDK for Notion, `notion-sdk-py`), which ships with full async support via `AsyncClient` and defaults to Notion API version `2025-09-03`.

The API version `2025-09-03` introduced a significant breaking change: databases now contain "data sources" and most operations (query, schema retrieval, schema update) moved from `/v1/databases/` to `/v1/data_sources/`. The project's existing `NOTION_DATABASE_ID` config must be used to discover the `data_source_id` at startup via `databases.retrieve()`, which returns a `data_sources` array. All subsequent operations (duplicate check via URL filter, tag schema reads, page creation) use the `data_source_id`.

Duplicate detection uses the `data_sources.query()` endpoint with a URL property filter (`url.equals`), preceded by URL normalization (strip UTM params, normalize protocol to https, remove trailing slashes). Tag management reads existing multi_select options from the data source schema via `data_sources.retrieve()` and caches them with a TTL. LLM-suggested tags not in the schema are silently dropped per user decision.

**Primary recommendation:** Use `notion-client` 3.0.0 `AsyncClient` with `data_sources` endpoints throughout. Discover `data_source_id` once at startup from `NOTION_DATABASE_ID`. Use `url-normalize` for URL normalization before duplicate checks. Split long text into multiple rich_text objects (2000-char limit) and multiple block batches (100-block limit per request).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Match duplicates using **normalized URLs** -- strip tracking params (utm_*), normalize protocol to https, remove trailing slashes before comparing
- When a duplicate is found: **skip creation, return existing page info** (page ID, URL, and title) so Phase 6 can tell the user "Already saved: [Title]" with a link
- Always skip -- no option to refresh/update existing pages. User must delete the old page manually if they want re-processing
- No staleness tracking or age reporting on duplicates
- **Notion database is the source of truth** for valid tags -- not the hardcoded SEEDED_TAGS list in code
- Fetch available tags from Notion's Tags multi_select property and **cache with TTL** (refresh periodically, not per-link)
- **Only use existing Notion tags** -- if the LLM suggests a tag not in the Notion schema, drop it. No auto-adding new tags to the schema
- If a cached tag becomes stale (removed from Notion between cache refresh and page creation), **drop silently** -- page gets created with fewer tags

### Claude's Discretion
- Page body formatting (how 4 sections render as Notion blocks -- heading levels, list styles, dividers)
- Cache TTL duration for tags
- Error handling on Notion API failures

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| NOTION-01 | System creates Notion page with all 10 database properties populated | `notion-client` 3.0.0 `AsyncClient.pages.create()` with `data_source_id` parent. Property mapping for title, select, multi_select, url, rich_text, date all documented with exact JSON structures. |
| NOTION-02 | System sets status to "New" on page creation | Status is a `select` property. Set via `{"Status": {"select": {"name": "New"}}}` in page properties. Already enforced by `KnowledgeEntry.status = Status.NEW` default. |
| NOTION-03 | System detects and skips duplicate URLs by querying Notion DB before creating | `data_sources.query()` with `{"property": "Source", "url": {"equals": normalized_url}}` filter. URL normalization via `url-normalize` library (strips utm_*, normalizes protocol, trailing slashes). Return existing page info (id, url, title) for downstream notification. |
| NOTION-04 | System manages tag schema (checks existing options, adds genuinely new tags) | User decision: NO auto-adding. Fetch existing tags from `data_sources.retrieve()` response `properties.Tags.multi_select.options[].name`. Cache with TTL. Drop LLM-suggested tags not in cache. Silently handle stale cache (Notion API rejects unknown tag -> drop and retry, or pre-filter only). |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| notion-client | 3.0.0 | Notion API SDK (sync + async) | Official Python SDK by ramnes, mirrors JS SDK, HIGH reputation, 103 code snippets in Context7. Defaults to API version 2025-09-03. |
| url-normalize | 2.2.1 | URL normalization for duplicate detection | Handles utm_* stripping, protocol normalization, trailing slashes. 100% test coverage. No heavy dependencies. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| cachetools | 5.x | TTL cache for tag options | Lightweight in-memory TTL cache. Avoids building custom expiry logic. Already widely used in Python ecosystem. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| notion-client | httpx direct API calls | More control but reimplements auth, pagination, error handling. SDK is thin wrapper anyway. |
| url-normalize | urllib.parse (stdlib) | Manual implementation for utm stripping. url-normalize handles edge cases (IDN, ports, empty params). |
| cachetools | Custom dict with timestamp | Works but cachetools.TTLCache is 3 lines vs 15+ for manual expiry. |

**Installation:**
```bash
uv add notion-client url-normalize cachetools
```

## Architecture Patterns

### Recommended Project Structure
```
src/knowledge_hub/notion/
    __init__.py          # Public API: create_page, check_duplicate
    client.py            # AsyncClient singleton (like llm/client.py pattern)
    properties.py        # NotionPage -> Notion property dict mapping
    blocks.py            # NotionPage body sections -> Notion block list
    tags.py              # Tag cache with TTL, validation
    duplicates.py        # URL normalization + duplicate query
    models.py            # Result types (PageResult, DuplicateResult)
```

### Pattern 1: Async Client Singleton (matching existing project pattern)
**What:** Cached `AsyncClient` instance, created on first use from settings.
**When to use:** All Notion API calls throughout the module.
**Example:**
```python
# Source: Context7 /ramnes/notion-sdk-py + project's llm/client.py pattern
from notion_client import AsyncClient
from knowledge_hub.config import get_settings

_client: AsyncClient | None = None
_data_source_id: str | None = None

async def get_notion_client() -> AsyncClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncClient(auth=settings.notion_api_key)
    return _client

async def get_data_source_id() -> str:
    """Discover data_source_id from database_id on first call."""
    global _data_source_id
    if _data_source_id is None:
        client = await get_notion_client()
        settings = get_settings()
        db = await client.databases.retrieve(database_id=settings.notion_database_id)
        _data_source_id = db["data_sources"][0]["id"]
    return _data_source_id
```

### Pattern 2: Property Builder (pure function, no API calls)
**What:** Maps `NotionPage` model to Notion API property dict.
**When to use:** Before `pages.create()` call.
**Example:**
```python
# Source: Notion API docs (create page) + Context7 notion-sdk-py
from knowledge_hub.models.notion import NotionPage

def build_properties(page: NotionPage) -> dict:
    entry = page.entry
    return {
        "Title": {"title": [{"text": {"content": entry.title}}]},
        "Category": {"select": {"name": entry.category.value}},
        "Content Type": {"select": {"name": entry.content_type.value}},
        "Source": {"url": entry.source},
        "Author/Creator": {"rich_text": [{"text": {"content": entry.author or ""}}]},
        "Date Added": {"date": {"start": entry.date_added.isoformat()}},
        "Status": {"select": {"name": entry.status.value}},
        "Priority": {"select": {"name": entry.priority.value}},
        "Tags": {"multi_select": [{"name": t} for t in entry.tags]},
        "Summary": {"rich_text": _split_rich_text(entry.summary)},
    }
```

### Pattern 3: Block Builder (pure function, handles 2000-char splitting)
**What:** Converts 4-section body into Notion block objects with text splitting.
**When to use:** Before `pages.create()` or `blocks.children.append()`.
**Example:**
```python
# Source: Notion API docs (block types) + request limits (2000 char)
def _split_rich_text(text: str, limit: int = 2000) -> list[dict]:
    """Split text into multiple rich_text objects respecting 2000-char limit."""
    chunks = []
    for i in range(0, len(text), limit):
        chunks.append({"type": "text", "text": {"content": text[i:i + limit]}})
    return chunks

def _heading_block(text: str, level: int = 2) -> dict:
    key = f"heading_{level}"
    return {"object": "block", "type": key, key: {
        "rich_text": [{"type": "text", "text": {"content": text}}]
    }}

def _paragraph_block(text: str) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {
        "rich_text": _split_rich_text(text)
    }}

def _numbered_item_block(text: str) -> dict:
    return {"object": "block", "type": "numbered_list_item",
        "numbered_list_item": {
            "rich_text": _split_rich_text(text)
        }}

def _divider_block() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}
```

### Pattern 4: Duplicate Check with Normalized URLs
**What:** Normalize URL, query Notion, return result.
**When to use:** Before any page creation attempt.
**Example:**
```python
# Source: url-normalize docs + Notion API data_sources.query filter docs
from url_normalize import url_normalize

def normalize_url(raw_url: str) -> str:
    """Normalize URL for duplicate comparison."""
    return url_normalize(raw_url, filter_params=True)

async def check_duplicate(raw_url: str) -> DuplicateResult | None:
    """Query Notion for existing page with same normalized URL."""
    client = await get_notion_client()
    ds_id = await get_data_source_id()
    normalized = normalize_url(raw_url)

    results = await client.data_sources.query(
        data_source_id=ds_id,
        filter={"property": "Source", "url": {"equals": normalized}},
        page_size=1,
    )
    if results["results"]:
        page = results["results"][0]
        return DuplicateResult(
            page_id=page["id"],
            url=page["url"],
            title=page["properties"]["Title"]["title"][0]["plain_text"],
        )
    return None
```

### Pattern 5: Tag Validation with TTL Cache
**What:** Fetch valid tags from Notion schema, cache them, filter LLM suggestions.
**When to use:** Before building page properties.
**Example:**
```python
# Source: Notion API data_sources.retrieve + cachetools TTLCache
import time
from cachetools import TTLCache

_tag_cache = TTLCache(maxsize=1, ttl=300)  # 5-minute TTL
_TAG_CACHE_KEY = "tags"

async def get_valid_tags() -> set[str]:
    """Return set of valid tag names from Notion schema, cached with TTL."""
    if _TAG_CACHE_KEY in _tag_cache:
        return _tag_cache[_TAG_CACHE_KEY]

    client = await get_notion_client()
    ds_id = await get_data_source_id()
    ds = await client.data_sources.retrieve(data_source_id=ds_id)
    options = ds["properties"]["Tags"]["multi_select"]["options"]
    tags = {opt["name"] for opt in options}
    _tag_cache[_TAG_CACHE_KEY] = tags
    return tags

def filter_tags(suggested: list[str], valid: set[str]) -> list[str]:
    """Keep only tags that exist in Notion schema. Pure function."""
    return [t for t in suggested if t in valid]
```

### Anti-Patterns to Avoid
- **Building page in single API call when body exceeds 100 blocks:** `pages.create()` accepts max 100 children. Use `pages.create()` for properties + first batch of blocks, then `blocks.children.append()` for overflow.
- **Storing data_source_id in config:** It can change. Discover it at runtime from `databases.retrieve()`.
- **Using databases.query instead of data_sources.query:** `notion-client` 3.0.0 defaults to API `2025-09-03`. The `databases.query` endpoint is deprecated for this version.
- **Assuming all text fits in one rich_text object:** Notion enforces 2000-char limit per `text.content`. Always split.
- **Caching tags forever:** Tags can be added/removed in Notion UI. Use TTL cache.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL normalization | Custom urllib.parse + regex for utm stripping | `url-normalize` 2.2.1 with `filter_params=True` | IDN handling, port normalization, edge cases with empty params, 100% test coverage |
| Notion API client | httpx + manual auth headers + pagination | `notion-client` 3.0.0 AsyncClient | Handles auth, pagination, rate limit headers, API versioning, error types |
| TTL caching | Dict + timestamp comparison | `cachetools.TTLCache` | Thread-safe, maxsize control, automatic expiry, 3 lines vs 15+ |
| Rich text splitting | Manual string slicing | Utility function (simple, but must exist) | 2000-char limit is non-negotiable; every text field needs this |

**Key insight:** The Notion API has many subtle constraints (2000-char rich_text, 100-block children, multi_select options must exist in schema). The SDK handles auth/pagination, but property formatting and block construction require careful builder functions that respect these limits.

## Common Pitfalls

### Pitfall 1: Rich Text 2000-Character Limit
**What goes wrong:** `summary`, `detailed_notes`, or `Author/Creator` fields exceed 2000 chars. API returns 400 error.
**Why it happens:** LLM `detailed_notes` field can be 1500-2500 words (~7500-15000 chars). Summary field can also be long.
**How to avoid:** Split every text value into chunks of <= 2000 chars before building rich_text arrays. Apply to both page properties (Summary, Author/Creator) and block content (paragraphs, list items).
**Warning signs:** 400 errors mentioning "body failed validation" or "text.content" length.

### Pitfall 2: Children Block Limit (100 per request)
**What goes wrong:** Page body has more than 100 blocks. `pages.create()` fails silently or returns error.
**Why it happens:** Key Points (10 items) + Key Learnings (7 items x 4-5 sub-blocks each) + Detailed Notes (many paragraphs) + headings + dividers can exceed 100.
**How to avoid:** Count blocks before sending. If > 100, send first 100 with `pages.create()`, then batch remaining with `blocks.children.append()` (also capped at 100 per call).
**Warning signs:** Pages created with truncated body content.

### Pitfall 3: API Version Mismatch (databases vs data_sources)
**What goes wrong:** Using `databases.query()` with `notion-client` 3.0.0 (which defaults to API 2025-09-03) returns errors once the database has multiple data sources.
**Why it happens:** `notion-client` 3.0.0 sends `Notion-Version: 2025-09-03` by default. In this version, most operations moved to `data_sources.*`.
**How to avoid:** Use `data_sources.query()`, `data_sources.retrieve()`, `data_sources.update()` for all schema and query operations. Use `databases.retrieve()` only to discover the `data_source_id`.
**Warning signs:** "Databases with multiple data sources are not supported" errors.

### Pitfall 4: Multi-Select Tags Not in Schema
**What goes wrong:** LLM suggests a tag that doesn't exist in the Notion database. API returns validation error.
**Why it happens:** `multi_select` values must match existing options in the schema. Unlike the old MEMORY.md note about auto-adding, the user decision is to DROP unknown tags.
**How to avoid:** Fetch valid tags from schema, cache with TTL, filter LLM suggestions before page creation. On `APIResponseError` during page creation, catch and retry with reduced tags.
**Warning signs:** 400 errors on page creation mentioning "multi_select" validation.

### Pitfall 5: URL Normalization Inconsistency
**What goes wrong:** Same URL stored with and without trailing slash, or with/without utm params. Duplicate check misses it.
**Why it happens:** URLs entered differently each time. Notion stores them as-is.
**How to avoid:** Normalize URL BOTH when storing (Source property) AND when querying. Use the same `normalize_url()` function for both paths.
**Warning signs:** Duplicate pages appearing for the same content.

### Pitfall 6: Data Source ID Discovery Failure
**What goes wrong:** `databases.retrieve()` returns empty `data_sources` array, or the database has no data sources yet.
**Why it happens:** New database, or database not properly configured.
**How to avoid:** Validate at startup that `data_sources` array is non-empty. Log clear error message. Consider fallback: if `data_sources` is empty or missing, the database_id itself may work as data_source_id for single-source databases (needs testing).
**Warning signs:** `KeyError` or `IndexError` on `db["data_sources"][0]["id"]`.

## Code Examples

Verified patterns from official sources:

### Creating a Full Page with Properties and Children
```python
# Source: Context7 /ramnes/notion-sdk-py + Notion API create page docs
async def create_notion_page(page: NotionPage) -> dict:
    client = await get_notion_client()
    ds_id = await get_data_source_id()

    properties = build_properties(page)
    blocks = build_body_blocks(page)

    # pages.create accepts max 100 children
    first_batch = blocks[:100]
    overflow = blocks[100:]

    result = await client.pages.create(
        parent={"type": "data_source_id", "data_source_id": ds_id},
        properties=properties,
        children=first_batch,
    )

    # Append overflow blocks in batches of 100
    page_id = result["id"]
    for i in range(0, len(overflow), 100):
        batch = overflow[i:i + 100]
        await client.blocks.children.append(block_id=page_id, children=batch)

    return result
```

### Building the 4-Section Body as Blocks
```python
# Source: Notion API block types + project NotionPage model
def build_body_blocks(page: NotionPage) -> list[dict]:
    blocks: list[dict] = []

    # Section 1: Summary
    blocks.append(_heading_block("Summary"))
    blocks.append(_paragraph_block(page.summary_section))
    blocks.append(_divider_block())

    # Section 2: Key Points (numbered list)
    blocks.append(_heading_block("Key Points"))
    for point in page.key_points:
        blocks.append(_numbered_item_block(point))
    blocks.append(_divider_block())

    # Section 3: Key Learnings & Actionable Steps
    blocks.append(_heading_block("Key Learnings & Actionable Steps"))
    for kl in page.key_learnings:
        # "What" as bold paragraph
        blocks.append(_paragraph_block(f"**{kl.what}**"))
        # "Why it matters" as paragraph
        blocks.append(_paragraph_block(f"Why it matters: {kl.why_it_matters}"))
        # "How to apply" as numbered sub-steps
        for step in kl.how_to_apply:
            blocks.append(_numbered_item_block(step))
        # Spacer between learnings (empty paragraph or nothing)
    blocks.append(_divider_block())

    # Section 4: Detailed Notes
    blocks.append(_heading_block("Detailed Notes"))
    # Split detailed_notes by paragraphs (double newline)
    for para in page.detailed_notes.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if para.startswith("## "):
            blocks.append(_heading_block(para[3:], level=3))
        elif para.startswith("- "):
            for line in para.split("\n"):
                line = line.lstrip("- ").strip()
                if line:
                    blocks.append({"object": "block", "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": _split_rich_text(line)}})
        else:
            blocks.append(_paragraph_block(para))

    return blocks
```

### Querying for Duplicate URL
```python
# Source: Notion API data_sources.query + URL filter docs
async def check_duplicate(raw_url: str) -> DuplicateResult | None:
    client = await get_notion_client()
    ds_id = await get_data_source_id()
    normalized = normalize_url(raw_url)

    response = await client.data_sources.query(
        data_source_id=ds_id,
        filter={
            "property": "Source",
            "url": {"equals": normalized},
        },
        page_size=1,
    )

    if not response["results"]:
        return None

    page = response["results"][0]
    title_prop = page["properties"]["Title"]["title"]
    title = title_prop[0]["plain_text"] if title_prop else "Untitled"

    return DuplicateResult(
        page_id=page["id"],
        page_url=page["url"],
        title=title,
    )
```

### Fetching and Filtering Tags
```python
# Source: Notion API data_sources.retrieve + cachetools
from cachetools import TTLCache

_tag_cache = TTLCache(maxsize=1, ttl=300)

async def get_valid_tags() -> set[str]:
    cached = _tag_cache.get("valid_tags")
    if cached is not None:
        return cached

    client = await get_notion_client()
    ds_id = await get_data_source_id()
    ds = await client.data_sources.retrieve(data_source_id=ds_id)

    tag_options = ds["properties"]["Tags"]["multi_select"]["options"]
    valid = {opt["name"] for opt in tag_options}
    _tag_cache["valid_tags"] = valid
    return valid

def filter_tags(suggested: list[str], valid: set[str]) -> list[str]:
    return [tag for tag in suggested if tag in valid]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `databases.query()` | `data_sources.query()` | API 2025-09-03 (Sep 2025) | Must discover data_source_id from database_id first |
| `databases.retrieve()` for schema | `data_sources.retrieve()` for schema | API 2025-09-03 | Properties/schema now on data source, not database |
| `databases.update()` for schema changes | `data_sources.update()` | API 2025-09-03 | Same pattern, different endpoint |
| `parent: {database_id: ...}` in pages.create | `parent: {data_source_id: ...}` | API 2025-09-03 | Pages are children of data sources, not databases |
| notion-client 2.x (API 2022-06-28) | notion-client 3.0.0 (API 2025-09-03) | Feb 2026 | Default API version changed; all examples use new endpoints |

**Deprecated/outdated:**
- `databases.query()`: Still works for single-data-source databases but officially replaced by `data_sources.query()`
- `parent: {"database_id": ...}` in `pages.create()`: Replaced by `parent: {"data_source_id": ...}` in API 2025-09-03
- MEMORY.md note about auto-adding tags: User decision in CONTEXT.md overrides this -- tags are now DROP-only

## Open Questions

1. **Data source ID stability**
   - What we know: `databases.retrieve()` returns a `data_sources` array. For single-source databases (our case), it should have exactly 1 entry.
   - What's unclear: Whether the data_source_id changes if the user modifies the database in Notion UI. Also unclear if a brand-new database starts with 0 data sources.
   - Recommendation: Discover at startup, cache in module global. If discovery fails, log a clear error. Consider adding `NOTION_DATA_SOURCE_ID` as optional override in config for robustness.

2. **Bold/italic rendering in Notion blocks**
   - What we know: Notion rich_text supports `annotations` (bold, italic, etc.) and markdown-like syntax in `text.content` does NOT auto-render.
   - What's unclear: Whether `**bold**` in text.content renders as bold or as literal asterisks.
   - Recommendation: For key learnings "what" field, use rich_text annotations `{"bold": true}` instead of markdown syntax. Validate during implementation.

3. **Normalized URL in Source property**
   - What we know: Duplicate check uses normalized URL for query. But we also store the URL in the Source property.
   - What's unclear: Should Source property store the original URL or the normalized URL? If original, duplicate check may miss matches for same content stored with different URL forms.
   - Recommendation: Store the **normalized** URL in Source. This ensures duplicate check always matches. The original URL format has no user value over the normalized one.

## Sources

### Primary (HIGH confidence)
- Context7 `/ramnes/notion-sdk-py` - AsyncClient usage, data_sources.query, pages.create, blocks.children.append, databases.retrieve
- [Notion API: Create a page](https://developers.notion.com/reference/post-page) - Property value types, parent structure, children blocks
- [Notion API: Query a data source](https://developers.notion.com/reference/query-a-data-source) - URL filter confirmed supported with equals/contains/starts_with operators
- [Notion API: Request limits](https://developers.notion.com/reference/request-limits) - 2000-char rich_text, 100-block children, 500KB payload
- [Notion API: Retrieve a data source](https://developers.notion.com/reference/retrieve-a-data-source) - Schema/properties including multi_select options
- [notion-client on PyPI](https://pypi.org/project/notion-client/) - v3.0.0 released 2026-02-16, Python 3.8-3.14
- [url-normalize on PyPI](https://pypi.org/project/url-normalize/) - v2.2.1, filter_params=True for UTM stripping

### Secondary (MEDIUM confidence)
- [Notion API: Upgrade guide 2025-09-03](https://developers.notion.com/docs/upgrade-guide-2025-09-03) - databases -> data_sources migration
- [Notion API: Upgrade FAQs 2025-09-03](https://developers.notion.com/docs/upgrade-faqs-2025-09-03) - data_source_id != database_id, discovery via databases.retrieve()
- [Notion API: Filter database entries](https://developers.notion.com/reference/post-database-query-filter) - URL property filter operators (deprecated page but operators confirmed in new API)

### Tertiary (LOW confidence)
- [Notion API: Append block children](https://developers.notion.com/reference/patch-block-children) - Max 100 blocks per append call (verified via request limits page)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - notion-client 3.0.0 verified on PyPI (2026-02-16), API 2025-09-03 confirmed via Context7 and official docs
- Architecture: HIGH - Patterns follow existing project conventions (llm/client.py singleton, pure builder functions, async throughout)
- Pitfalls: HIGH - 2000-char limit, 100-block limit, and data_sources migration all verified with multiple sources
- URL normalization: HIGH - url-normalize 2.2.1 verified on PyPI with filter_params feature documented
- Tag management: MEDIUM - data_sources.retrieve() schema structure confirmed but exact response shape for multi_select options not verified with live API call

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (stable -- Notion API version unlikely to change within 30 days)
