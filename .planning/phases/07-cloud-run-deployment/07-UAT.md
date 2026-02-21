---
status: resolved
phase: 07-cloud-run-deployment
source: [07-01-SUMMARY.md, 07-02-SUMMARY.md, 07-03-SUMMARY.md]
started: 2026-02-21T20:30:00Z
updated: 2026-02-21T22:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Full Test Suite Passes
expected: Running `uv run pytest` completes with all 231 tests passing (0 failures, 0 errors).
result: pass

### 2. Structured JSON Logging Output
expected: Running `uv run python -c "from knowledge_hub.logging_config import configure_logging; import logging; configure_logging(); logging.getLogger('test').info('hello')"` outputs a JSON line to stdout with fields including "severity" (not "levelname"), "timestamp", and "message".
result: pass

### 3. Deploy Script Complete and Executable
expected: `deploy.sh` exists, is executable (`chmod +x`), and contains all 7 secrets (SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, NOTION_TOKEN, NOTION_DATABASE_ID, JINA_API_KEY, GEMINI_API_KEY, SCHEDULER_SECRET), plus flags --min-instances=1, --no-cpu-throttling, and --cpu-boost.
result: pass

### 4. Cost Tracking in Pipeline
expected: After processing content through the LLM processor, cost_usd is returned as part of a tuple from process_content() and the Slack success notification includes "(Cost: $X.XXX)" text.
result: pass

### 5. Digest Endpoint With Auth
expected: Starting the app locally (`uv run uvicorn knowledge_hub.app:app`) and hitting `POST /digest` with header `X-Scheduler-Secret: <secret>` returns a success response. Without the header, it returns 403.
result: issue
reported: "you said with auth should be 200 but it resulted 500"
severity: major

### 6. Cost Check Endpoint With Auth
expected: Hitting `POST /cost-check` with valid `X-Scheduler-Secret` header returns a success response. Without the header, it returns 403.
result: pass

### 7. App Starts With Logging Configured
expected: Starting the app with `uv run uvicorn knowledge_hub.app:app` shows JSON-formatted startup logs (not plain text).
result: pass

## Summary

total: 7
passed: 6
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "POST /digest with valid auth returns success response"
  status: resolved
  reason: "User reported: you said with auth should be 200 but it resulted 500"
  severity: major
  test: 5
  root_cause: "send_weekly_digest() in digest.py has no error handling — unconditionally calls Notion and Slack APIs which fail with empty credentials, and app.py /digest endpoint has no try/except so the exception becomes HTTP 500"
  artifacts:
    - path: "src/knowledge_hub/digest.py"
      issue: "send_weekly_digest() lacks error handling around Notion/Slack calls"
    - path: "src/knowledge_hub/app.py"
      issue: "/digest endpoint has no try/except"
  missing:
    - "Add try/except in /digest endpoint to return structured error instead of 500"
    - "Or add pre-flight credential check in send_weekly_digest() to skip gracefully when unconfigured"
  debug_session: ".planning/debug/digest-500-no-credentials.md"
