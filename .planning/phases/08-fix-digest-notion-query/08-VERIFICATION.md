---
phase: 08-fix-digest-notion-query
verified: 2026-02-22T18:30:00Z
status: passed
score: 6/6 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "POST /digest end-to-end with live Notion credentials"
    expected: "Weekly digest message delivered to Slack DM; no Notion API error in logs"
    why_human: "Requires live Notion data source ID and Slack OAuth token — cannot be verified against real API without live credentials"
---

# Phase 8: Fix Digest Notion Query — Verification Report

**Phase Goal:** The weekly digest correctly queries Notion for recent entries using the proper API endpoint
**Verified:** 2026-02-22T18:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | `query_recent_entries()` uses `client.data_sources.query` (not `client.databases.query`) | VERIFIED | Line 48 of `src/knowledge_hub/digest.py`: `result = await client.data_sources.query(**kwargs)`. Zero occurrences of `databases.query` in the file. |
| 2 | kwargs uses `data_source_id` key (not `database_id` key) | VERIFIED | Line 39 of `src/knowledge_hub/digest.py`: `"data_source_id": data_source_id,`. Zero occurrences of `database_id` as a kwarg key in the file. |
| 3 | Tests mock `client.data_sources.query` (not `client.databases.query`) | VERIFIED | Lines 106, 129 of `tests/test_digest.py` set up `mock_client.data_sources.query.return_value` and `mock_client.data_sources.query.side_effect`. Lines 118, 148 assert on `mock_client.data_sources.query`. Zero occurrences of `databases.query` in the test file. |
| 4 | Test assertions verify `data_source_id` parameter name (not `database_id`) | VERIFIED | Line 120: `assert call_kwargs["data_source_id"] == "ds-123"`. Line 121: `assert "database_id" not in call_kwargs` (negative regression guard). |
| 5 | All existing digest tests still pass | VERIFIED | `python -m pytest tests/test_digest.py -v` — 12/12 tests passed. Full suite: 235/235 passed, zero regressions. |
| 6 | No occurrences of `databases.query` remain in `digest.py` or `test_digest.py` | VERIFIED | `grep -n "databases.query" src/knowledge_hub/digest.py tests/test_digest.py` returns zero hits. |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|---------|--------|---------|
| `src/knowledge_hub/digest.py` | Fixed Notion query using `data_sources.query` endpoint | VERIFIED | Contains `client.data_sources.query` at line 48 and `"data_source_id"` kwarg at line 39. Substantive: 231 lines, full implementation of `query_recent_entries()`, `build_weekly_digest()`, `send_weekly_digest()`, `check_daily_cost()`. |
| `tests/test_digest.py` | Tests validating correct API endpoint and parameter names | VERIFIED | Contains `data_sources.query` at lines 106, 118, 119, 129, 148, 150. Substantive: 268 lines, 12 test functions with correct mocks, assertions, and negative regression guard. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `src/knowledge_hub/digest.py` | `notion.client.get_data_source_id` | `data_source_id` passed as `data_source_id` kwarg to `data_sources.query` | WIRED | Line 32: `data_source_id = await get_data_source_id()`. Line 39: `"data_source_id": data_source_id`. Line 48: `client.data_sources.query(**kwargs)`. Pattern matches `data_sources\.query\(.*data_source_id` exactly. |
| `src/knowledge_hub/digest.py` | `src/knowledge_hub/notion/duplicates.py` | Same API pattern: `get_data_source_id()` -> `data_sources.query(data_source_id=ds_id)` | WIRED | `digest.py` now mirrors `duplicates.py` exactly. Both call `get_data_source_id()` then pass the result as `data_source_id` kwarg to `client.data_sources.query(**kwargs)`. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| DEPLOY-06 | 08-01-PLAN.md | System sends weekly Slack digest summarizing all entries processed that week | SATISFIED | `query_recent_entries()` now uses the correct Notion API endpoint. `send_weekly_digest()` calls it and sends formatted digest via Slack DM. `app.py` wires `POST /digest` -> `send_weekly_digest()` (line 55-58 of `app.py`). All 12 digest tests pass. |

**Orphaned requirements check:** REQUIREMENTS.md traceability table maps DEPLOY-06 exclusively to Phase 8. No other requirements map to Phase 8. No orphaned requirements found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|---------|--------|
| — | — | — | — | No anti-patterns found in either modified file. |

No TODO/FIXME/HACK/placeholder comments. No empty implementations. No stub returns. No `console.log`-only handlers.

### Human Verification Required

#### 1. POST /digest E2E with Live Credentials

**Test:** Deploy to Cloud Run (or run locally with real secrets) and call `POST /digest` with a valid scheduler token.
**Expected:** Digest message appears in Slack DM; Cloud Run logs show no Notion API error; response is `{"status": "sent", "entries": N}`.
**Why human:** Requires live Notion data source ID and Slack OAuth token. The fix makes the correct API call at the code level, but the actual `data_sources.query` endpoint behavior with a real data source ID can only be confirmed with live credentials. Unit tests mock the Notion client so they validate the call pattern, not the API's response.

### Gaps Summary

No gaps. All six must-have truths are verified at all three levels (exists, substantive, wired).

The phase goal is achieved: `query_recent_entries()` in `digest.py` now uses `client.data_sources.query(data_source_id=...)`, matching the established project pattern from `duplicates.py`. Tests mock and assert against the correct endpoint and parameter name, and a negative regression guard (`assert "database_id" not in call_kwargs`) prevents the bug from silently reappearing. All 235 tests pass with zero regressions. Commits `940e3eb` and `f77ea0c` are confirmed present in git history.

The one human-verification item (live E2E test) is informational — it reflects an inherent limitation of unit testing against mocked external APIs, not a code deficiency.

---

_Verified: 2026-02-22T18:30:00Z_
_Verifier: Claude (gsd-verifier)_
