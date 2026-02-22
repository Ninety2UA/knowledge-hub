---
phase: 07-cloud-run-deployment
verified: 2026-02-21T22:00:00Z
status: passed
score: 9/9 must-haves verified
re_verification:
  previous_status: passed
  previous_score: 8/8
  gaps_closed:
    - "POST /digest with valid auth returns 200 (not 500) when Notion/Slack credentials are missing or APIs fail"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Run ./deploy.sh against a live GCP project with Secret Manager secrets pre-created"
    expected: "Cloud Run service deploys; container starts emitting JSON logs with severity field parsed by Cloud Logging"
    why_human: "Requires a live GCP project with APIs enabled"
  - test: "Send a malformed webhook to the deployed /slack/events endpoint without X-Slack-Signature"
    expected: "403 response; no processing occurs"
    why_human: "Signature verification depends on real SLACK_SIGNING_SECRET from Secret Manager"
  - test: "Trigger POST /digest with valid X-Scheduler-Secret after entries have been processed"
    expected: "Slack DM received with entry count, clickable Notion links, category breakdown, top tags, and Gemini cost"
    why_human: "Requires live Notion database entries and live Slack DM delivery"
  - test: "Configure Cloud Scheduler and wait for Monday 08:00 Amsterdam time"
    expected: "/digest triggered automatically; weekly digest Slack DM received"
    why_human: "Requires live Cloud Scheduler setup and waiting for the schedule window"
---

# Phase 7: Cloud Run Deployment Verification Report

**Phase Goal:** The pipeline runs in production on Cloud Run with proper secrets, logging, and operational configuration
**Verified:** 2026-02-21T22:00:00Z
**Status:** PASSED
**Re-verification:** Yes — after UAT gap closure (Plan 04 error handling)

## Re-verification Context

The initial VERIFICATION.md (2026-02-21T21:00:00Z) reported status `passed` at 8/8 truths. After that verification, UAT was completed and found one issue: `POST /digest` returned HTTP 500 when Notion/Slack credentials were not configured. Root cause: `send_weekly_digest()` made unconditional API calls with no error handling, and the endpoint had no `try/except`.

Plan 04 (commits `94a1195`, `7e55d3a`, `bcc2348`) was executed to close the gap:
- Two-layer error handling added: function-level `try/except` in `digest.py` + defense-in-depth in `app.py` endpoint handlers
- 4 new tests added covering all error paths
- Total test count: 235 (was 231)

This re-verification confirms the gap was closed and no regressions were introduced.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Application emits structured JSON logs with GCP severity field to stdout | VERIFIED | `logging_config.py` uses `pythonjsonlogger.json.JsonFormatter` with `rename_fields: {levelname: severity}`, handler writes to `ext://sys.stdout` |
| 2 | Deploy script configures Cloud Run with secrets, min-instances=1, and no-cpu-throttling | VERIFIED | `deploy.sh` contains `--min-instances=1`, `--no-cpu-throttling`, `--set-secrets` with 7 secrets |
| 3 | Slack signature verification is active (signing secret mounted via Secret Manager) | VERIFIED | `verification.py` uses `SignatureVerifier(signing_secret=settings.slack_signing_secret)`; `SLACK_SIGNING_SECRET=slack-signing-secret:latest` in `deploy.sh` |
| 4 | Every Gemini API call logs token usage and cost as structured JSON | VERIFIED | `cost.py::log_usage()` emits structured dict with url, model, prompt/completion/total tokens, cost_usd; called from `processor.py` after every Gemini call |
| 5 | Slack success notification includes total cost (e.g., "Cost: $0.003") | VERIFIED | `notifier.py::notify_success()` appends `(Cost: ${cost_usd:.3f})` when `cost_usd is not None`; `handlers.py` passes `cost_usd=cost_usd` |
| 6 | Cost calculation uses Gemini 2.0 Flash pricing constants defined in one place | VERIFIED | `INPUT_PRICE_PER_TOKEN = 0.50 / 1_000_000` and `OUTPUT_PRICE_PER_TOKEN = 3.00 / 1_000_000` defined once in `cost.py` |
| 7 | POST /digest queries Notion for past week's entries and sends Slack DM with formatted summary | VERIFIED | `digest.py::send_weekly_digest()` calls `query_recent_entries(days=7)`, builds message via `build_weekly_digest()`, sends `chat_postMessage` to `settings.allowed_user_id`; zero-entry case sends "Service is running" confirmation |
| 8 | Logging is initialized at app startup via configure_logging() | VERIFIED | `app.py::lifespan()` calls `configure_logging()` as the first statement before yielding |
| 9 | POST /digest with valid auth returns 200 (not 500) when Notion/Slack APIs fail | VERIFIED | `digest.py` wraps Notion query (lines 166-171) and Slack send (lines 180-188) in `try/except`, returning `{"status": "error", ...}`. `app.py` wraps `send_weekly_digest()` (lines 57-62) for defense-in-depth. `test_digest_endpoint_internal_error` asserts 200 status when digest raises. 235 tests pass. |

**Score:** 9/9 truths verified

---

## Required Artifacts

### Plan 01 Artifacts

| Artifact | Provides | Status | Details |
|----------|----------|--------|---------|
| `src/knowledge_hub/logging_config.py` | Structured JSON logging with GCP severity mapping | VERIFIED | `pythonjsonlogger.json.JsonFormatter`, `rename_fields`, stdout handler, `configure_logging()` present |
| `deploy.sh` | Cloud Run deployment script with all required gcloud flags | VERIFIED | 101 lines; executable; `--set-secrets` with 7 secrets, `--min-instances=1`, `--no-cpu-throttling`, `--cpu-boost`, `--source .` |

### Plan 02 Artifacts

| Artifact | Provides | Status | Details |
|----------|----------|--------|---------|
| `src/knowledge_hub/cost.py` | Token usage extraction, cost calculation, structured cost logging | VERIFIED | `extract_usage`, `log_usage`, `TokenUsage`, pricing constants, in-memory accumulators all present |
| `tests/test_cost.py` | Unit tests for cost calculation | VERIFIED | 5 tests; all pass |

### Plan 03 Artifacts

| Artifact | Provides | Status | Details |
|----------|----------|--------|---------|
| `src/knowledge_hub/digest.py` | Weekly digest builder and daily cost alert logic | VERIFIED | 231 lines; all five functions present with error handling |
| `src/knowledge_hub/app.py` | FastAPI app with /digest and /cost-check endpoints, logging initialization | VERIFIED | 74 lines; `configure_logging()` in lifespan; both endpoints with `Depends(verify_scheduler)` and defense-in-depth `try/except` |
| `tests/test_digest.py` | Tests for digest building, cost alert, and error paths | VERIFIED | 267 lines; 12 tests including 3 new error-path tests |
| `tests/test_app.py` | App endpoint auth and error-handling tests | VERIFIED | 95 lines; 6 tests including `test_digest_endpoint_internal_error` |

### Plan 04 Artifacts (Gap Closure)

| Artifact | Provides | Status | Details |
|----------|----------|--------|---------|
| `src/knowledge_hub/digest.py` | Error-handled `send_weekly_digest` and `check_daily_cost` | VERIFIED | Lines 166-171: Notion query `try/except` returns `{"status": "error", ...}`; lines 180-188: Slack send `try/except`; lines 211-219: cost alert `try/except`; `reset_weekly_cost` only on success path |
| `src/knowledge_hub/app.py` | Defense-in-depth `try/except` in `/digest` and `/cost-check` handlers | VERIFIED | Lines 57-62: `/digest` `try/except`; lines 69-73: `/cost-check` `try/except`; `logger` module-level instance on line 13 |
| `tests/test_digest.py` | Tests: Notion error, Slack error in digest, Slack error in cost alert | VERIFIED | `test_send_weekly_digest_notion_error` (line 209), `test_send_weekly_digest_slack_error` (line 227), `test_check_daily_cost_slack_error` (line 250) all present and pass |
| `tests/test_app.py` | Test: defense-in-depth returns 200 when digest raises | VERIFIED | `test_digest_endpoint_internal_error` (line 78); asserts `status_code == 200` and `body["status"] == "error"` when `send_weekly_digest` raises |

---

## Key Link Verification

### Plan 01 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `logging_config.py` | `python-json-logger` | `pythonjsonlogger.json.JsonFormatter` in dictConfig | WIRED | Line 19: `"()": "pythonjsonlogger.json.JsonFormatter"` |
| `deploy.sh` | Google Secret Manager | `--set-secrets` mounting env vars | WIRED | Lines 35-41: 7 secrets mounted including `SLACK_SIGNING_SECRET`, `SCHEDULER_SECRET` |

### Plan 02 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `llm/processor.py` | `cost.py` | `from knowledge_hub.cost import extract_usage, log_usage, TokenUsage` | WIRED | Import confirmed; `extract_usage(response)` then `log_usage(content.url, usage)` called after every Gemini call |
| `slack/notifier.py` | cost_usd parameter | `notify_success` accepts `cost_usd` and includes in message | WIRED | `cost_usd: float | None = None` parameter; conditional append `(Cost: ${cost_usd:.3f})` |
| `slack/handlers.py` | cost_usd propagation | `process_message_urls` passes cost from processor to notifier | WIRED | `notion_page, cost_usd = await process_content(...)` then `notify_success(..., cost_usd=cost_usd)` |

### Plan 03 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app.py` | `logging_config.py` | `configure_logging()` called in lifespan | WIRED | Line 10: import; line 19: first call in lifespan |
| `app.py` | `digest.py` | `/digest` and `/cost-check` route handlers | WIRED | Lines 54-73: both endpoints present with `Depends(verify_scheduler)` |
| `digest.py` | Notion API | `client.databases.query` with date filter and pagination | WIRED | Lines 38-54: pagination loop with `on_or_after` filter |
| `digest.py` | Slack API | `chat_postMessage` DM to `allowed_user_id` | WIRED | Lines 181-185: `await client.chat_postMessage(channel=settings.allowed_user_id, text=message)` |

### Plan 04 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app.py` | `digest.py` | `try/except` around `send_weekly_digest()` call | WIRED | Lines 57-62: `try: result = await send_weekly_digest()` with `except Exception as e: return {"status": "error", ...}` |
| `digest.py` | Notion/Slack APIs | `try/except` around external calls returning structured error dict | WIRED | Lines 166-171: Notion `try/except`; lines 180-188: Slack `try/except`; both return `{"status": "error", ...}` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| DEPLOY-01 | 07-01 | System runs as Docker container deployable to Google Cloud Run | SATISFIED | `Dockerfile` exists; `deploy.sh` uses `--source .` for Cloud Build source-based deploy |
| DEPLOY-02 | 07-01 | All API keys stored in Google Secret Manager (never in code or env files) | SATISFIED | `deploy.sh` mounts 7 secrets via `--set-secrets`; no secrets in code; `config.py` reads from env vars injected by Secret Manager |
| DEPLOY-03 | 07-01 | System emits structured JSON logs for Cloud Run logging | SATISFIED | `logging_config.py` with `pythonjsonlogger` emitting JSON to stdout with `severity`, `timestamp`, `logger`, `service` fields |
| DEPLOY-04 | 07-01 | System verifies Slack request signatures on every incoming webhook | SATISFIED | `slack/verification.py` uses `SignatureVerifier` from `slack-sdk`; wired as FastAPI `Depends` on `/slack/events` route |
| DEPLOY-05 | 07-01 | Cloud Run configured with `--min-instances=1` to prevent cold start timeouts | SATISFIED | `deploy.sh`: `--min-instances=1`, `--no-cpu-throttling`, `--cpu-boost` |
| DEPLOY-06 | 07-03, 07-04 | System sends weekly Slack digest summarizing all entries processed that week | SATISFIED | `POST /digest` calls `send_weekly_digest()` which queries Notion 7-day window, builds formatted message, sends Slack DM; returns structured JSON (never 500) for both success and error paths; 235 tests passing |
| DEPLOY-07 | 07-02 | System logs Gemini token usage and calculates cost per entry | SATISFIED | `cost.py::extract_usage()` extracts token counts; `log_usage()` emits structured JSON; `process_content` calls both after every Gemini API call; in-memory accumulators track daily/weekly cost |

**All 7 requirements satisfied. No orphaned requirements.**

---

## Anti-Patterns Found

None. Scanned all Plan 04 modified files:
- `src/knowledge_hub/digest.py` — clean; error handling uses structured `logger.error()` calls, no bare prints or empty except blocks
- `src/knowledge_hub/app.py` — clean; defense-in-depth returns 200 with error dict rather than swallowing exceptions silently
- `tests/test_digest.py` — clean; proper use of `unittest.mock.patch` context managers with assertions on non-call
- `tests/test_app.py` — clean; proper assertion of 200 status for defense-in-depth test

No TODO/FIXME/PLACEHOLDER patterns, no empty return statements, no stub implementations detected.

---

## Human Verification Required

The following items require a live deployment to confirm. All automated checks have passed up to the integration boundary.

### 1. Cloud Run Deployment Execution

**Test:** Run `PROJECT_ID=<your-project> ./deploy.sh` with secrets pre-created in Secret Manager
**Expected:** Cloud Run service deploys successfully; container starts with JSON logs visible in Cloud Run Logs console with the `severity` field correctly parsed by Cloud Logging
**Why human:** Requires a live GCP project with APIs enabled, Secret Manager secrets created, and Cloud Run API active

### 2. Slack Signature Rejection in Production

**Test:** Send a malformed webhook request to the deployed `/slack/events` endpoint without a valid `X-Slack-Signature` header
**Expected:** 403 response; no processing occurs
**Why human:** Signature verification depends on the real `SLACK_SIGNING_SECRET` from Secret Manager

### 3. Weekly Digest Content and Formatting

**Test:** Trigger `POST /digest` with valid `X-Scheduler-Secret` header after some entries have been processed
**Expected:** Slack DM received with correct entry count, clickable Notion links, category breakdown, top tags, and Gemini cost
**Why human:** Requires live Notion database entries and live Slack DM delivery

### 4. Cloud Scheduler Wiring

**Test:** Follow the Cloud Scheduler setup commands in `deploy.sh` comments; wait for Monday 08:00 Amsterdam time
**Expected:** `/digest` endpoint triggered automatically; weekly digest Slack DM received
**Why human:** Requires live Cloud Scheduler setup and waiting for the schedule window

---

## Gaps Summary

No gaps remain. The UAT gap (POST /digest returning HTTP 500) was closed by Plan 04:

- `send_weekly_digest()` now catches Notion API failures (returns `{"status": "error", "error": "Failed to query Notion: ..."}`) and Slack send failures (returns `{"status": "error", "error": "Failed to send Slack message: ...", "entries": N}`)
- `check_daily_cost()` now catches Slack alert failures (returns `{"status": "error", "error": "Failed to send cost alert: ...", "cost": N}`)
- `/digest` and `/cost-check` endpoints have defense-in-depth `try/except` returning HTTP 200 with `{"status": "error", ...}` instead of 500 — Cloud Scheduler treats non-2xx as failures and retries, which would cause duplicate alerts
- `reset_weekly_cost()` is only called on the success path — prevents losing cost accumulation data when Slack is temporarily down
- 4 new tests cover all error paths; full suite: 235 tests, all passing

The phase delivered all four plans completely:
- **Plan 01**: Structured JSON logging module and deployment script with all required Cloud Run flags
- **Plan 02**: Token usage tracking and cost propagation through the full pipeline with cost display in Slack notifications
- **Plan 03**: Weekly digest and daily cost alert endpoints wired into the FastAPI app with scheduler secret authentication
- **Plan 04** (gap closure): Two-layer error handling so `/digest` never returns 500 from unhandled exceptions

All 7 DEPLOY requirements are satisfied. The phase goal is achieved.

---

_Verified: 2026-02-21T22:00:00Z_
_Verifier: Claude (gsd-verifier)_
