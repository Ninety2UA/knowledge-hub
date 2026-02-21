---
phase: 07-cloud-run-deployment
plan: 03
subsystem: api
tags: [digest, cost-alert, slack-dm, notion-query, scheduler-auth, fastapi-endpoints]

# Dependency graph
requires:
  - phase: 07-cloud-run-deployment
    provides: "Structured logging (logging_config.py), deploy script (deploy.sh), cost module (cost.py)"
provides:
  - "Weekly digest endpoint (POST /digest) with Notion query, Slack DM, and cost summary"
  - "Daily cost alert endpoint (POST /cost-check) with $5 threshold Slack alert"
  - "Scheduler secret authentication for protected endpoints"
  - "In-memory cost accumulators in cost.py wired into log_usage"
  - "configure_logging() called at app startup in lifespan"
affects: [07-cloud-run-deployment]

# Tech tracking
tech-stack:
  added: []
  patterns: ["In-memory cost accumulation for single-instance personal tool", "Scheduler secret header auth for Cloud Scheduler endpoints", "Notion pagination loop with start_cursor"]

key-files:
  created:
    - src/knowledge_hub/digest.py
    - tests/test_digest.py
    - tests/test_app.py
  modified:
    - src/knowledge_hub/config.py
    - src/knowledge_hub/cost.py
    - src/knowledge_hub/app.py
    - deploy.sh

key-decisions:
  - "In-memory cost accumulators (not Cloud Logging queries) -- pragmatic for --min-instances=1 personal tool; instance restart resets are acceptable"
  - "Scheduler secret header auth (X-Scheduler-Secret) over IAM-only -- simple defense-in-depth for scheduled endpoints"
  - "Weekly cost reset after digest send, daily cost not reset by cost-check (natural reset on new day's entries)"

patterns-established:
  - "Scheduler auth dependency: verify_scheduler(request) -> HTTPException(403) for protected cron endpoints"
  - "Notion pagination: loop with has_more/next_cursor/start_cursor for complete result sets"

requirements-completed: [DEPLOY-06]

# Metrics
duration: 3min
completed: 2026-02-21
---

# Phase 7 Plan 03: Weekly Digest and Cost Alerts Summary

**Weekly digest endpoint querying Notion for recent entries with formatted Slack DM, daily cost alert with $5 threshold, and scheduler secret auth on both endpoints**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-21T20:23:56Z
- **Completed:** 2026-02-21T20:26:57Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Created digest.py with query_recent_entries (paginated Notion query), build_weekly_digest (formatted Slack message with entry list, categories, top tags, cost), send_weekly_digest, and check_daily_cost
- Added in-memory cost accumulators to cost.py (add_cost, get/reset daily/weekly) wired into log_usage for automatic tracking
- Wired configure_logging() into app.py lifespan, added POST /digest and POST /cost-check with scheduler secret authentication
- Added scheduler_secret config field and SCHEDULER_SECRET to deploy.sh secrets mapping
- 14 new tests (9 digest + 5 app endpoint) covering all functions; 231 total tests passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Create digest module and wire app.py** - `6178930` (feat)
2. **Task 2: Tests for digest module and app endpoints** - `be48895` (test)

## Files Created/Modified
- `src/knowledge_hub/digest.py` - Weekly digest builder, Notion query, daily cost alert, Slack DM sender
- `src/knowledge_hub/config.py` - Added scheduler_secret field
- `src/knowledge_hub/cost.py` - Added in-memory cost accumulators (daily/weekly) wired into log_usage
- `src/knowledge_hub/app.py` - Logging init in lifespan, /digest and /cost-check endpoints with scheduler auth
- `deploy.sh` - Added SCHEDULER_SECRET to --set-secrets mapping
- `tests/test_digest.py` - 9 tests: entry extraction, digest building, Notion querying with pagination, digest sending, cost alerts
- `tests/test_app.py` - 5 tests: scheduler auth rejection, successful endpoint calls with valid auth

## Decisions Made
- In-memory cost accumulators rather than querying Cloud Logging -- pragmatic for a personal tool with --min-instances=1 keeping the instance alive; instance restart resets are acceptable
- Scheduler secret as X-Scheduler-Secret header -- simple shared secret between Cloud Scheduler and the app, defense-in-depth alongside IAM authentication
- Weekly cost accumulator resets after digest is sent; daily cost is NOT reset by the cost-check endpoint (resets naturally when instance processes new day's entries)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - scheduler_secret will be configured when creating the Secret Manager secret during deployment.

## Next Phase Readiness
- All 3 plans in Phase 7 complete: structured logging, cost tracking, digest/alerts
- Full application ready for Cloud Run deployment via deploy.sh
- 231 tests passing across all modules
- Cloud Scheduler setup documented in deploy.sh comments (requires service URL from first deploy)

## Self-Check: PASSED

- All created files exist (digest.py, test_digest.py, test_app.py, 07-03-SUMMARY.md)
- All task commits verified (6178930, be48895)
- Full test suite: 231 passed

---
*Phase: 07-cloud-run-deployment*
*Completed: 2026-02-21*
