---
phase: 05-notion-output
plan: 01
subsystem: notion
tags: [notion-client, url-normalize, cachetools, pydantic, async]

# Dependency graph
requires:
  - phase: 04-llm-processing
    provides: NotionPage model with KnowledgeEntry and 4-section body
  - phase: 01-project-setup
    provides: Settings config with notion_api_key and notion_database_id
provides:
  - AsyncClient singleton with data_source_id discovery
  - PageResult and DuplicateResult models for downstream consumers
  - URL normalization and duplicate detection via data_sources.query
  - Tag validation cache with 5-minute TTL
  - Property builder mapping all 10 KnowledgeEntry fields to Notion API format
  - Block builder rendering 4-section body as Notion block objects
affects: [05-02, 06-pipeline-integration]

# Tech tracking
tech-stack:
  added: [notion-client 3.0.0, url-normalize 2.2.1, cachetools 7.0.1]
  patterns: [async client singleton with data_source_id discovery, pure function builders for Notion API, TTL-cached schema reads]

key-files:
  created:
    - src/knowledge_hub/notion/client.py
    - src/knowledge_hub/notion/models.py
    - src/knowledge_hub/notion/duplicates.py
    - src/knowledge_hub/notion/tags.py
    - src/knowledge_hub/notion/properties.py
    - src/knowledge_hub/notion/blocks.py
  modified:
    - src/knowledge_hub/notion/__init__.py
    - pyproject.toml
    - uv.lock

key-decisions:
  - "Manual utm_* stripping before url_normalize -- url-normalize filter_params=True removes ALL params"
  - "Duplicated _split_rich_text in properties.py and blocks.py for module self-containment"
  - "Bold annotations via Notion rich_text annotations object instead of markdown syntax"

patterns-established:
  - "Notion client singleton: same async-cached pattern as llm/client.py but with data_source_id discovery"
  - "Pure builder functions: build_properties() and build_body_blocks() take models, return API dicts"
  - "Tag validation: Notion schema is source of truth, cached with TTL, unknown tags silently dropped"

requirements-completed: [NOTION-01, NOTION-02, NOTION-03, NOTION-04]

# Metrics
duration: 3min
completed: 2026-02-21
---

# Phase 5 Plan 1: Notion Building Blocks Summary

**Notion API building blocks: client singleton, URL duplicate detection, tag cache, property mapper, and 4-section block builder**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-21T16:18:44Z
- **Completed:** 2026-02-21T16:21:31Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- AsyncClient singleton with data_source_id discovery from Notion database (API 2025-09-03)
- URL normalization stripping utm_* tracking params + duplicate detection via data_sources.query
- Tag validation with 5-minute TTL cache against Notion schema, unknown tags silently dropped
- Property builder mapping all 10 KnowledgeEntry fields with 2000-char text splitting
- Block builder rendering 4 sections (Summary, Key Points, Key Learnings, Detailed Notes) as Notion blocks with headings, numbered lists, bold annotations, bulleted lists, and dividers

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies, create client singleton, result models, duplicate detection, and tag cache** - `82d9755` (feat)
2. **Task 2: Build property mapper and block builder for Notion page creation** - `48a55f9` (feat)

## Files Created/Modified
- `src/knowledge_hub/notion/client.py` - AsyncClient singleton + data_source_id discovery (54 lines)
- `src/knowledge_hub/notion/models.py` - PageResult and DuplicateResult Pydantic models (23 lines)
- `src/knowledge_hub/notion/duplicates.py` - URL normalization + duplicate query (64 lines)
- `src/knowledge_hub/notion/tags.py` - Tag cache with 5-min TTL + filter function (45 lines)
- `src/knowledge_hub/notion/properties.py` - NotionPage to Notion API property dict builder (44 lines)
- `src/knowledge_hub/notion/blocks.py` - NotionPage body to Notion block list builder (151 lines)
- `src/knowledge_hub/notion/__init__.py` - Updated with all public API exports (23 lines)
- `pyproject.toml` - Added notion-client, url-normalize, cachetools dependencies
- `uv.lock` - Updated lockfile

## Decisions Made
- **Manual utm_* stripping:** url-normalize's `filter_params=True` removes ALL query params. We manually strip only `utm_*` params before passing to `url_normalize()` for protocol/format normalization.
- **Duplicated _split_rich_text:** Both properties.py and blocks.py have their own copy. Keeps modules self-contained rather than creating a shared utils file for a 6-line helper.
- **Bold via annotations, not markdown:** Notion renders `**text**` as literal asterisks. Key Learnings "what" field uses rich_text annotations `{"bold": true}` instead.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 7 Notion building block modules are importable and functional
- Plan 02 can wire these into a complete page creation service with tests
- 145 existing tests still pass with 0 regressions

## Self-Check: PASSED

- All 7 files exist at expected paths
- Both commits verified in git log (82d9755, 48a55f9)
- All minimum line counts met (client:54/30, models:23/15, duplicates:64/25, tags:45/30, properties:44/30, blocks:151/60)
- 145 existing tests pass with 0 regressions

---
*Phase: 05-notion-output*
*Completed: 2026-02-21*
