---
phase: 07-cloud-run-deployment
plan: 01
subsystem: infra
tags: [python-json-logger, cloud-run, gcloud, structured-logging, secret-manager, deployment]

# Dependency graph
requires:
  - phase: 06-pipeline-integration
    provides: Complete pipeline with Slack notifications ready for production deployment
provides:
  - Structured JSON logging module (logging_config.py) with GCP severity mapping
  - Cloud Run deploy script (deploy.sh) with all secrets, CPU, and cold start flags
  - Verified Dockerfile and .dockerignore compatibility with source-based deploy
affects: [07-02, 07-03]

# Tech tracking
tech-stack:
  added: [python-json-logger]
  patterns: [dictConfig JSON logging with GCP severity field rename, Cloud Run source-based deploy]

key-files:
  created:
    - src/knowledge_hub/logging_config.py
    - deploy.sh
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "python-json-logger v4.0.0 resolved by uv (>=3.2.1 specified) -- v4 API is backward compatible with dictConfig rename_fields and static_fields"
  - "stdout handler (not stderr) to prevent Cloud Run from overriding severity to ERROR"
  - "Source-based deploy (--source .) avoids needing Docker installed locally"
  - "Cloud Scheduler commands documented as comments in deploy.sh (require service URL from first deploy)"

patterns-established:
  - "GCP structured logging: rename levelname->severity, asctime->timestamp, name->logger via python-json-logger"
  - "Cloud Run deployment: --no-cpu-throttling + --min-instances=1 for background task survival"

requirements-completed: [DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, DEPLOY-05]

# Metrics
duration: 2min
completed: 2026-02-21
---

# Phase 7 Plan 01: Infrastructure Foundation Summary

**Structured JSON logging module with GCP severity mapping and Cloud Run deploy script with 6 Secret Manager secrets, cold start prevention, and CPU always-allocated**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T20:15:35Z
- **Completed:** 2026-02-21T20:17:46Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created logging_config.py with python-json-logger dictConfig outputting JSON to stdout with GCP-compatible severity field
- Added python-json-logger dependency (v4.0.0 resolved, backward-compatible API)
- Created deploy.sh with complete gcloud run deploy command including all 6 secrets, --min-instances=1, --no-cpu-throttling, --cpu-boost, 512Mi/1CPU
- Verified existing Dockerfile (python:3.12-slim + uv multi-layer caching) and .dockerignore are Cloud Build compatible
- Documented Cloud Scheduler setup for weekly digest and daily cost check in deploy script comments

## Task Commits

Each task was committed atomically:

1. **Task 1: Create structured JSON logging module** - `006c7b3` (feat)
2. **Task 2: Create deploy script and verify Dockerfile** - `14acd6a` (feat)

## Files Created/Modified
- `src/knowledge_hub/logging_config.py` - Structured JSON logging configuration with configure_logging() function
- `deploy.sh` - Cloud Run deployment script with secrets, CPU, memory, and cold start flags
- `pyproject.toml` - Added python-json-logger>=3.2.1 dependency
- `uv.lock` - Updated lockfile with python-json-logger v4.0.0

## Decisions Made
- python-json-logger v4.0.0 resolved by uv (plan specified >=3.2.1) -- verified v4 API is fully backward-compatible with dictConfig rename_fields and static_fields
- Handler writes to stdout (ext://sys.stdout), not stderr -- Cloud Run overrides severity to ERROR for all stderr output regardless of JSON severity field
- Used --source . deployment (Cloud Build builds the container remotely) since Docker is not installed on the dev machine
- Cloud Scheduler setup documented as comments rather than auto-executed (requires the service URL from the first deploy)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required for this plan. Secret Manager setup and Cloud Scheduler configuration are documented in deploy.sh comments for when the user is ready to deploy.

## Next Phase Readiness
- logging_config.py ready for import -- will be wired into app.py lifespan in Plan 03
- deploy.sh ready to execute once secrets are created in Secret Manager
- Foundation set for Plan 02 (cost tracking module) and Plan 03 (digest, cost alert, app.py wiring)

## Self-Check: PASSED

- All created files exist (logging_config.py, deploy.sh, 07-01-SUMMARY.md)
- deploy.sh is executable
- All task commits verified (006c7b3, 14acd6a)

---
*Phase: 07-cloud-run-deployment*
*Completed: 2026-02-21*
