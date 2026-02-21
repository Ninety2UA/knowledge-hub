---
status: resolved
trigger: "POST /digest returns HTTP 500 when called with valid X-Scheduler-Secret but without Notion/Slack credentials configured"
created: 2026-02-21T00:00:00Z
updated: 2026-02-21T00:00:00Z
---

## Current Focus

hypothesis: send_weekly_digest has no error handling; it unconditionally calls Notion and Slack clients that fail when credentials are empty strings
test: trace the code path comparing /digest vs /cost-check
expecting: /digest always hits network calls; /cost-check only hits them conditionally
next_action: document root cause and return findings

## Symptoms

expected: POST /digest with valid auth returns a graceful error or degraded response when Notion/Slack credentials are not configured
actual: POST /digest returns HTTP 500 (unhandled exception)
errors: Likely APIResponseError from notion-client or slack_sdk when using empty-string tokens
reproduction: Run app locally without NOTION_API_KEY / SLACK_BOT_TOKEN in env, POST /digest with valid X-Scheduler-Secret
started: Always broken under this condition (no error handling was ever added)

## Eliminated

(none - root cause identified on first hypothesis)

## Evidence

- timestamp: 2026-02-21T00:00:00Z
  checked: send_weekly_digest() in digest.py (lines 157-190)
  found: Function ALWAYS calls query_recent_entries() (line 166) which calls get_notion_client() -> AsyncClient(auth="") -> databases.query(). No try/except anywhere.
  implication: Empty notion_api_key causes Notion SDK to make an API call with invalid auth, raising an exception that propagates as HTTP 500.

- timestamp: 2026-02-21T00:00:00Z
  checked: send_weekly_digest() Slack path (lines 179-183)
  found: Even if Notion call somehow succeeded, function ALWAYS calls get_slack_client() -> AsyncWebClient(token="") -> chat_postMessage(). No try/except. Also sends to channel=settings.allowed_user_id which is "" when unconfigured.
  implication: Two separate failure points, both unconditional, both unhandled.

- timestamp: 2026-02-21T00:00:00Z
  checked: check_daily_cost() in digest.py (lines 193-218)
  found: This function calls get_daily_cost() which returns an in-memory float (line 200). It only calls get_slack_client() inside the `if cost > 5.0` branch (line 203). On a fresh app with no processing, cost is 0.0, so it skips the Slack call entirely and returns {"status":"ok","cost":0.0}.
  implication: This explains why /cost-check works -- it never touches Notion and only touches Slack conditionally. The asymmetry is the key.

- timestamp: 2026-02-21T00:00:00Z
  checked: notion/client.py get_notion_client() (lines 16-26) and get_data_source_id() (lines 29-47)
  found: get_notion_client() creates AsyncClient(auth="") without validation. get_data_source_id() calls client.databases.retrieve() which will fail with an auth error from the Notion API.
  implication: No defensive checks at the client layer either.

- timestamp: 2026-02-21T00:00:00Z
  checked: config.py Settings class (lines 8-34)
  found: All credential fields default to "" (empty string). No validation that credentials are non-empty.
  implication: App starts fine with no credentials -- failure is deferred to first use.

## Resolution

root_cause: send_weekly_digest() has zero error handling. It unconditionally calls Notion API (query_recent_entries -> get_notion_client -> get_data_source_id -> databases.retrieve/query) and Slack API (get_slack_client -> chat_postMessage), both of which fail when credentials are empty strings. The exception propagates uncaught through the /digest endpoint handler, causing FastAPI to return HTTP 500. By contrast, check_daily_cost() works because it only reads an in-memory float and conditionally calls Slack (which it skips when cost is 0.0).

fix: (not applied - diagnosis only)
verification: (not applied - diagnosis only)
files_changed: []
