---
phase: 08-fix-digest-notion-query
plan: 01
subsystem: api
tags: [notion, digest, data-sources, bug-fix]

# Dependency graph
requires:
  - phase: 07-cloud-run-deployment
    provides: digest.py and test_digest.py with Notion query logic
provides:
  - Fixed Notion query using data_sources.query endpoint in digest.py
  - Regression-guarded tests asserting correct API endpoint and parameter names
affects: [deployment, digest]

# Tech tracking
tech-stack:
  added: []
  patterns: [data_sources.query with data_source_id kwarg for all Notion database queries]

key-files:
  created: []
  modified:
    - src/knowledge_hub/digest.py
    - tests/test_digest.py

key-decisions:
  - "No new decisions -- followed plan exactly as written"

patterns-established:
  - "All Notion database queries use client.data_sources.query(data_source_id=...) pattern consistently"

requirements-completed: [DEPLOY-06]

# Metrics
duration: 2min
completed: 2026-02-22
---

# Phase 08 Plan 01: Fix Digest Notion Query Summary

**Fixed data_source_id/database_id mismatch in digest.py -- query_recent_entries now uses client.data_sources.query(data_source_id=...) matching duplicates.py pattern**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-22T18:20:20Z
- **Completed:** 2026-02-22T18:21:54Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Fixed digest.py to use `client.data_sources.query` with `data_source_id` kwarg (was `client.databases.query` with `database_id`)
- Updated all test mocks to target the correct API endpoint
- Added negative assertion `"database_id" not in call_kwargs` to prevent regression
- All 235 tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix digest.py Notion API endpoint and parameter name** - `940e3eb` (fix)
2. **Task 2: Update test_digest.py to mock correct API endpoint and assert correct parameter name** - `f77ea0c` (test)

## Files Created/Modified
- `src/knowledge_hub/digest.py` - Changed `database_id` kwarg to `data_source_id`, changed `client.databases.query` to `client.data_sources.query`
- `tests/test_digest.py` - Updated 7 mock references from `databases.query` to `data_sources.query`, updated parameter assertion from `database_id` to `data_source_id`, added negative regression assertion

## Decisions Made
None - followed plan as specified.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Digest endpoint ready for production deployment
- All Notion query patterns now consistent across codebase (digest.py matches duplicates.py)

## Self-Check: PASSED

- FOUND: src/knowledge_hub/digest.py
- FOUND: tests/test_digest.py
- FOUND: 08-01-SUMMARY.md
- FOUND: commit 940e3eb (Task 1)
- FOUND: commit f77ea0c (Task 2)

---
*Phase: 08-fix-digest-notion-query*
*Completed: 2026-02-22*
