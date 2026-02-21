---
phase: 07-cloud-run-deployment
plan: 02
subsystem: llm
tags: [gemini, token-tracking, cost-calculation, structured-logging]

# Dependency graph
requires:
  - phase: 04-llm-processing
    provides: "Gemini processor pipeline (_call_gemini, process_content)"
  - phase: 06-pipeline-integration
    provides: "Pipeline wiring (handlers.py process_message_urls, notifier.py)"
provides:
  - "cost.py module with Gemini pricing constants, TokenUsage dataclass, extract_usage(), log_usage()"
  - "Structured JSON cost logging for every Gemini API call"
  - "Cost display in Slack success notifications"
  - "cost_usd propagation through full pipeline (processor -> handlers -> notifier)"
affects: [07-cloud-run-deployment]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Structured cost logging with extra dict", "Lazy import to break circular dependency", "Tuple return for cost propagation"]

key-files:
  created:
    - "src/knowledge_hub/cost.py"
    - "tests/test_cost.py"
  modified:
    - "src/knowledge_hub/llm/processor.py"
    - "src/knowledge_hub/slack/notifier.py"
    - "src/knowledge_hub/slack/handlers.py"
    - "tests/test_llm/test_processor.py"
    - "tests/test_slack/test_notifier.py"
    - "tests/test_slack/test_pipeline.py"

key-decisions:
  - "Lazy import of GEMINI_MODEL in log_usage to break circular dependency (cost -> llm.prompts -> llm.__init__ -> processor -> cost)"
  - "Tuple return (NotionPage, cost_usd) from process_content rather than embedding cost in NotionPage model"

patterns-established:
  - "Centralized pricing constants: single source of truth in cost.py for Gemini pricing"
  - "Structured logging with extra dict: all cost/usage data as structured fields for JSON aggregation"

requirements-completed: [DEPLOY-07]

# Metrics
duration: 5min
completed: 2026-02-21
---

# Phase 7 Plan 02: Token Usage Tracking Summary

**Gemini token usage extraction, cost calculation, and structured logging with cost display in Slack notifications**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-21T20:15:31Z
- **Completed:** 2026-02-21T20:20:44Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Created cost.py module with centralized Gemini 3 Flash pricing constants, TokenUsage dataclass, extract_usage(), and log_usage()
- Wired token usage tracking into pipeline: processor extracts and logs usage, returns cost through handlers to notifier
- Slack success notifications now display "(Cost: $X.XXX)" for each processed URL
- Full test coverage: 5 new cost tests, 1 new processor test, 2 new notifier tests, plus all existing tests updated

## Task Commits

Each task was committed atomically:

1. **Task 1: Create cost module and wire into pipeline** - `875d90f` (feat)
2. **Task 2: Tests for cost module and updated pipeline** - `91603f4` (test)

## Files Created/Modified
- `src/knowledge_hub/cost.py` - Token usage extraction, cost calculation, structured logging
- `src/knowledge_hub/llm/processor.py` - Returns (NotionPage, cost_usd) tuple, extracts and logs usage
- `src/knowledge_hub/slack/notifier.py` - notify_success accepts cost_usd, displays in message
- `src/knowledge_hub/slack/handlers.py` - Unpacks cost from process_content, passes to notify_success
- `tests/test_cost.py` - 5 tests: normal extraction, None handling, precision, no metadata, structured logging
- `tests/test_llm/test_processor.py` - Updated for tuple return, added test_process_content_returns_cost
- `tests/test_slack/test_notifier.py` - Added with_cost and without_cost tests
- `tests/test_slack/test_pipeline.py` - Updated all mocks for (NotionPage, cost_usd) tuple

## Decisions Made
- Used lazy import for GEMINI_MODEL in log_usage() to break circular dependency chain (cost -> llm.prompts -> llm.__init__ -> processor -> cost)
- Returned cost as tuple element (NotionPage, cost_usd) rather than embedding in NotionPage -- keeps domain model clean, cost is pipeline metadata

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Circular import between cost.py and llm.prompts**
- **Found during:** Task 1 (Create cost module)
- **Issue:** cost.py imported GEMINI_MODEL from llm.prompts at module level, but llm/__init__.py imports processor.py which imports cost.py, creating a circular dependency
- **Fix:** Changed to lazy import inside log_usage() function body
- **Files modified:** src/knowledge_hub/cost.py
- **Verification:** `python -c "from knowledge_hub.cost import ..."` succeeds
- **Committed in:** 875d90f (Task 1 commit)

**2. [Rule 3 - Blocking] Pipeline integration tests broken by tuple return type**
- **Found during:** Task 2 (Tests)
- **Issue:** test_pipeline.py mocked process_content to return MagicMock() (single value), but handlers.py now unpacks (notion_page, cost_usd) tuple
- **Fix:** Updated all pipeline test mocks to return (MagicMock(), 0.001) tuples, updated success assertion to include cost_usd kwarg
- **Files modified:** tests/test_slack/test_pipeline.py
- **Verification:** All 10 pipeline tests pass
- **Committed in:** 91603f4 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Cost data is now available for the weekly digest and daily cost alert planned in 07-03
- Structured logging emits all fields needed for Cloud Run log aggregation
- All 217 tests pass (209 existing + 8 new)

## Self-Check: PASSED

All files created/modified exist on disk. All commit hashes verified in git log.

---
*Phase: 07-cloud-run-deployment*
*Completed: 2026-02-21*
