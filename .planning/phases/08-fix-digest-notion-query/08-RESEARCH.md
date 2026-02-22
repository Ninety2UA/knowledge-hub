# Phase 8: Fix Digest Notion Query - Research

**Researched:** 2026-02-22
**Domain:** Notion API data_sources.query vs databases.query, Python SDK usage patterns
**Confidence:** HIGH

## Summary

The weekly digest in `digest.py` has a cross-phase wiring bug: `query_recent_entries()` calls `get_data_source_id()` (which returns the Notion data source ID) but then passes it as `database_id` to `client.databases.query()`. This is semantically wrong -- the `databases.query()` endpoint expects a database UUID (the `notion_database_id` config value), not a data source ID. The correct pattern, already used in `duplicates.py`, is `client.data_sources.query(data_source_id=ds_id)`.

The tests mask this bug because the mock returns `"ds-123"` from `get_data_source_id()` and the assertion checks `call_kwargs["database_id"] == "ds-123"` -- confirming the code path but not catching the API endpoint mismatch. Both the production code and the test mock the same wrong method (`client.databases.query`), so tests pass despite the runtime-breaking bug.

The fix is straightforward: change `client.databases.query(**kwargs)` to `client.data_sources.query(**kwargs)` and update the kwargs key from `database_id` to `data_source_id`. The filter format (`{"property": "Date Added", "date": {"on_or_after": cutoff}}`) is compatible with both APIs. Pagination parameters (`start_cursor`, `has_more`, `next_cursor`) work identically on `data_sources.query`.

**Primary recommendation:** Mirror the `duplicates.py` pattern exactly -- use `client.data_sources.query(data_source_id=ds_id, filter=..., start_cursor=...)` and update tests to mock `client.data_sources.query` instead of `client.databases.query`, with assertions on `data_source_id` parameter name (not `database_id`).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPLOY-06 | System sends weekly Slack digest summarizing all entries processed that week | Fix `query_recent_entries()` to use `data_sources.query` with correct parameter names; update tests to validate correct API endpoint; verify POST /digest E2E flow |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| notion-client (notion-sdk-py) | Already installed | Notion API client with `data_sources.query` method | Used throughout project; `AsyncClient` with data_sources namespace |
| pytest / pytest-asyncio | Already installed | Test runner for async test functions | Used throughout project |
| unittest.mock | stdlib | AsyncMock for Notion client mocking | Used throughout project |

### Supporting
No new libraries needed. This is a code-level fix within existing dependencies.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `data_sources.query(data_source_id=...)` | `databases.query(database_id=settings.notion_database_id)` | Would work but diverges from the pattern established by `duplicates.py`, `tags.py`, and `service.py` which all use `data_sources.*` methods. Consistency is more important than correctness of either approach. |

**Installation:** No new packages needed.

## Architecture Patterns

### The Existing Correct Pattern (from `duplicates.py`)

**What:** Use `client.data_sources.query()` with `data_source_id` parameter
**When to use:** Any time querying the Notion database for pages
**Example:**
```python
# Source: src/knowledge_hub/notion/duplicates.py (lines 47-50)
response = await client.data_sources.query(
    data_source_id=ds_id,
    filter={"property": "Source", "url": {"equals": normalized}},
    page_size=1,
)
```

### The Bug Pattern (in `digest.py`)

**What:** Incorrectly uses `client.databases.query()` with `database_id` set to a data_source_id value
**Why it's wrong:** `databases.query()` expects a database UUID (matching `settings.notion_database_id`), but receives a data_source_id (the ID from `db["data_sources"][0]["id"]`). These are different identifiers.
```python
# Source: src/knowledge_hub/digest.py (lines 38-48) -- THE BUG
kwargs: dict = {
    "database_id": data_source_id,  # WRONG: passing data_source_id as database_id
    "filter": {
        "property": "Date Added",
        "date": {"on_or_after": cutoff},
    },
}
result = await client.databases.query(**kwargs)  # WRONG: should be data_sources.query
```

### The Fix Pattern

**What:** Change to `client.data_sources.query()` with `data_source_id` parameter
```python
# CORRECT: matches duplicates.py pattern
kwargs: dict = {
    "data_source_id": data_source_id,
    "filter": {
        "property": "Date Added",
        "date": {"on_or_after": cutoff},
    },
}
if start_cursor:
    kwargs["start_cursor"] = start_cursor

result = await client.data_sources.query(**kwargs)
```

### Notion API Compatibility

The `data_sources.query` endpoint (POST `/v1/data_sources/{data_source_id}/query`) supports:
- **`filter`**: Same property-based filter objects as `databases.query` (verified via Context7 Notion API reference)
- **`start_cursor`**: Same pagination cursor mechanism (verified via Context7)
- **`page_size`**: Same 100-max page size (verified via Context7)
- **Response format**: Same `results`, `has_more`, `next_cursor` structure (verified via Context7)

The filter `{"property": "Date Added", "date": {"on_or_after": cutoff}}` is valid for `data_sources.query` -- Context7 confirms property-based filters work identically.

### Anti-Patterns to Avoid
- **Mock string reuse masking bugs:** The current test uses `"ds-123"` as both the mocked `get_data_source_id()` return value AND the asserted `database_id` parameter value. Since both sides use the same string, the assertion passes even though the parameter name is wrong. Fix: use distinct mock values and assert against the correct parameter name (`data_source_id`, not `database_id`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pagination | Custom cursor management | `data_sources.query` with `start_cursor` | Already handles pagination correctly -- just needs the right endpoint |
| Date filtering | Manual date comparison | Notion API `on_or_after` filter | Already implemented correctly -- filter format is API-endpoint-agnostic |

**Key insight:** This is a minimal fix -- only the API endpoint method and parameter name change. All other logic (pagination, filter construction, entry extraction, digest building) is correct.

## Common Pitfalls

### Pitfall 1: Mock String Reuse Masking Semantic Errors
**What goes wrong:** Test mocks return a value (e.g., `"ds-123"`) and assertions check the same string appears in kwargs. The test passes even when the parameter NAME is wrong (e.g., `database_id` vs `data_source_id`).
**Why it happens:** Mocking both the source and consumer of an ID with the same string means the test only validates data flow, not semantic correctness.
**How to avoid:** Assert the method called (`client.data_sources.query` not `client.databases.query`) AND assert the parameter name (`data_source_id` in kwargs, not `database_id`). Use the mock's `assert_called_once()` on the CORRECT method object.
**Warning signs:** Tests pass but production fails at runtime with API errors.

### Pitfall 2: Forgetting Pagination Test Update
**What goes wrong:** Fixing the main query test but forgetting to update the pagination test, leaving `client.databases.query` mocked in one test.
**Why it happens:** There are TWO test functions that mock the Notion query: `test_query_recent_entries` and `test_query_recent_entries_pagination`. Both need updating.
**How to avoid:** Search for ALL occurrences of `databases.query` in the test file and update each one.
**Warning signs:** `grep -n "databases.query" tests/test_digest.py` returns hits after the fix.

### Pitfall 3: Filter Format Incompatibility
**What goes wrong:** Assuming `data_sources.query` uses a different filter format than `databases.query`.
**Why it happens:** The Notion API reference shows some filters without the `property` key at the top level.
**How to avoid:** The property-based filter format (`{"property": "Date Added", "date": {"on_or_after": cutoff}}`) works on `data_sources.query`. Verified via Context7: `duplicates.py` uses `{"property": "Source", "url": {"equals": normalized}}` successfully with `data_sources.query`.
**Warning signs:** N/A -- the existing filter format is compatible.

## Code Examples

Verified patterns from project source and Context7:

### Correct data_sources.query Usage (from duplicates.py)
```python
# Source: src/knowledge_hub/notion/duplicates.py (lines 43-50)
client = await get_notion_client()
ds_id = await get_data_source_id()

response = await client.data_sources.query(
    data_source_id=ds_id,
    filter={"property": "Source", "url": {"equals": normalized}},
    page_size=1,
)
```

### Correct data_sources.query with Pagination (Context7 verified)
```python
# Source: Context7 /ramnes/notion-sdk-py - AsyncClient usage
results = await notion.data_sources.query(
    data_source_id="897e5a76-ae52-4b48-9fdf-e71f5945d1af",
    filter={"property": "Status", "select": {"equals": "Active"}}
)
# Response has: results["results"], results["has_more"], results["next_cursor"]
```

### Test Mock Pattern for data_sources.query
```python
# Correct mock pattern -- mock data_sources.query, assert data_source_id param
mock_client = AsyncMock()
mock_client.data_sources.query.return_value = {
    "results": [_make_notion_page()],
    "has_more": False,
}

with (
    patch("knowledge_hub.digest.get_notion_client", return_value=mock_client),
    patch("knowledge_hub.digest.get_data_source_id", return_value="ds-123"),
):
    entries = await query_recent_entries(days=7)

mock_client.data_sources.query.assert_called_once()
call_kwargs = mock_client.data_sources.query.call_args[1]
assert "data_source_id" in call_kwargs        # Correct param name
assert call_kwargs["data_source_id"] == "ds-123"
assert "database_id" not in call_kwargs        # Ensure old param NOT present
```

### Diff Summary of Required Changes

**`src/knowledge_hub/digest.py` (2 changes):**
1. Line 39: `"database_id": data_source_id` -> `"data_source_id": data_source_id`
2. Line 48: `client.databases.query(**kwargs)` -> `client.data_sources.query(**kwargs)`

**`tests/test_digest.py` (changes in 2 test functions):**
1. `test_query_recent_entries`: Mock `data_sources.query` instead of `databases.query`, assert `data_source_id` param name
2. `test_query_recent_entries_pagination`: Same mock/assertion changes

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `databases.query(database_id=...)` | `data_sources.query(data_source_id=...)` | Notion API 2025-09-03 | The project already adopted the new API for duplicates, tags, and service -- only digest.py was missed |

**Deprecated/outdated:**
- `databases.query()` with `database_id`: Still functional but the project convention uses `data_sources.query()` with `data_source_id`. The `get_data_source_id()` helper was built specifically for this pattern.

## Open Questions

1. **Filter format validation**
   - What we know: The filter `{"property": "Date Added", "date": {"on_or_after": cutoff}}` should work with `data_sources.query` based on Context7 examples showing property-based filters on that endpoint
   - What's unclear: Whether "Date Added" (a created_time property in Notion) requires any special handling vs. a standard date property
   - Recommendation: The duplicates.py pattern uses property-based filters successfully. Keep the same filter format. If it fails at runtime, the error will be clear and diagnosable.

## Sources

### Primary (HIGH confidence)
- Context7 `/ramnes/notion-sdk-py` - AsyncClient `data_sources.query` method signature, parameters, async usage
- Context7 `/websites/developers_notion_reference` - `POST /v1/data_sources/{data_source_id}/query` endpoint spec, filter format, pagination parameters
- Project source `src/knowledge_hub/notion/duplicates.py` - Working reference implementation of `data_sources.query`
- Project source `src/knowledge_hub/notion/client.py` - `get_data_source_id()` implementation and caching
- Project source `src/knowledge_hub/digest.py` - Current buggy implementation
- Project source `tests/test_digest.py` - Current tests with mock masking
- Audit report `.planning/v1.0-MILESTONE-AUDIT.md` - Bug identification and fix options

### Secondary (MEDIUM confidence)
- Context7 `/websites/developers_notion_reference` - Date filter format for data_sources.query (examples show property-based filters work)

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new libraries; existing project dependencies
- Architecture: HIGH - Fix mirrors existing working pattern in duplicates.py; API compatibility verified via Context7
- Pitfalls: HIGH - Bug is well-characterized in audit; fix is mechanical with clear test pattern

**Research date:** 2026-02-22
**Valid until:** 2026-04-22 (stable -- Notion API versioning is slow-moving)
