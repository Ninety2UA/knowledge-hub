# Phase 7: Cloud Run Deployment - Research

**Researched:** 2026-02-21
**Domain:** Google Cloud Run deployment, Secret Manager, structured logging, scheduled tasks, cost tracking
**Confidence:** HIGH

## Summary

This phase deploys the existing Knowledge Hub FastAPI application to Google Cloud Run with production-grade configuration. The codebase already has a working Dockerfile, Slack signature verification, background task processing via FastAPI `BackgroundTasks`, and pydantic-settings configuration via environment variables. The deployment requires: (1) storing secrets in Google Secret Manager and mounting them as environment variables, (2) enabling structured JSON logging via `python-json-logger`, (3) configuring Cloud Run with `--min-instances=1` and `--no-cpu-throttling` to prevent cold start timeouts and keep background tasks alive, (4) adding Gemini token usage/cost tracking to the processing pipeline, (5) implementing a weekly digest endpoint triggered by Cloud Scheduler, and (6) adding a daily cost alert mechanism via Slack DM.

The architecture is straightforward: the existing app gains a logging configuration module, a cost-tracking module that wraps the Gemini response, a digest endpoint, and a deploy script. No new external services beyond GCP primitives (Secret Manager, Cloud Scheduler, Artifact Registry) are needed. For daily cost accumulation, Cloud Run Logs can be queried via Cloud Logging API, or a simpler in-memory approach works since `--min-instances=1` with `--no-cpu-throttling` keeps a single instance alive with stable state. However, since instances can still be recycled, the most reliable approach is to query structured logs at digest/alert time.

**Primary recommendation:** Mount all 5 secrets via `--set-secrets` as environment variables (pydantic-settings reads them transparently), configure `python-json-logger` with GCP `severity` field mapping, add token usage extraction from `response.usage_metadata` after every Gemini call, and use Cloud Scheduler to invoke a `/digest` endpoint weekly and a `/cost-check` endpoint daily.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use existing GCP project (user already has one)
- Deploy to **europe-west4** (Netherlands)
- Manual deployment via `gcloud run deploy` -- no CI/CD pipeline
- Use default Cloud Run `*.run.app` URL -- no custom domain
- Log Gemini token usage and cost per entry in structured JSON logs (full detail: tokens, model, cost)
- Include **total cost only** (e.g., "Cost: $0.003") in Slack confirmation replies -- no token breakdown
- Include weekly total Gemini cost in the weekly digest
- **Daily cost alert**: Send Slack DM if daily Gemini spend exceeds **$5/day**
- Weekly digest: Send **Monday morning** (summarizing previous week's entries)
- Deliver digest as a **DM** to the user -- not in #knowledge-base channel
- Digest content: Entry count + list of titles with Notion links, Category breakdown, Top tags that week, Total Gemini cost for the week
- **Always send digest**, even if zero entries -- confirms the service is running
- Docker base image and build configuration: Claude's discretion
- Secret Manager integration pattern: Claude's discretion
- Structured log field schema (beyond cost fields): Claude's discretion
- Cloud Run instance sizing (memory, CPU): Claude's discretion
- Slack signature verification implementation: Claude's discretion (already implemented in codebase)
- Cold start mitigation approach: Claude's discretion (min-instances=1 is required)
- Scheduling mechanism for weekly digest: Claude's discretion
- Cost alert tracking mechanism: Claude's discretion

### Claude's Discretion
- Docker base image and build configuration
- Secret Manager integration pattern
- Structured log field schema (beyond cost fields)
- Cloud Run instance sizing (memory, CPU)
- Slack signature verification implementation
- Cold start mitigation approach (min-instances=1 is required, details flexible)
- Scheduling mechanism for weekly digest (Cloud Scheduler, cron, etc.)
- Cost alert tracking mechanism (how to accumulate daily costs)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEPLOY-01 | System runs as Docker container deployable to Google Cloud Run | Existing Dockerfile works; deploy via `gcloud run deploy --source .` or build+push to Artifact Registry. Verified with GCP official docs. |
| DEPLOY-02 | All API keys stored in Google Secret Manager (never in code or env files) | Use `--set-secrets` flag to mount Secret Manager secrets as env vars. pydantic-settings reads them transparently -- no code changes to config.py needed. |
| DEPLOY-03 | System emits structured JSON logs for Cloud Run logging | `python-json-logger` JsonFormatter with `severity` field rename. Cloud Run auto-extracts `severity`, `message`, and trace fields from JSON stdout. |
| DEPLOY-04 | System verifies Slack request signatures on every incoming webhook | Already implemented in `slack/verification.py` using `slack_sdk.signature.SignatureVerifier`. No changes needed -- just ensure `SLACK_SIGNING_SECRET` is in Secret Manager. |
| DEPLOY-05 | Cloud Run configured with `--min-instances=1` to prevent cold start timeouts | Use `--min-instances=1` + `--no-cpu-throttling` flags. The combination keeps CPU allocated for background tasks after HTTP response. |
| DEPLOY-06 | System sends weekly Slack digest summarizing all entries processed that week | New `/digest` endpoint triggered by Cloud Scheduler on Monday mornings. Queries Notion database for entries from previous week. Sends DM via `chat_postMessage` with `channel=USER_ID`. |
| DEPLOY-07 | System logs Gemini token usage and calculates cost per entry | Extract `usage_metadata` from Gemini response (prompt_token_count, candidates_token_count). Calculate cost using Gemini 3 Flash pricing ($0.50/1M input, $3.00/1M output). Log as structured JSON. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-json-logger | 3.x | Structured JSON logging for Cloud Run | Only Python JSON logging library with GCP `severity` field rename, static fields, and dictConfig support. 90.7 benchmark score on Context7. |
| google-cloud-secret-manager | (not needed) | Secret Manager access | NOT needed -- Cloud Run's `--set-secrets` mounts secrets as env vars at instance startup. No SDK dependency required. |
| gcloud CLI | latest | Manual deployment tool | User-decided: manual `gcloud run deploy`, no CI/CD. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| google-cloud-logging | (not needed) | Cloud Logging client | NOT needed -- Cloud Run auto-ingests JSON from stdout. Just write structured JSON to stdout. |
| google-cloud-scheduler | (not needed) | Cloud Scheduler client | NOT needed -- Cloud Scheduler is configured via gcloud CLI, not SDK. It sends HTTP requests to Cloud Run endpoints. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-json-logger | structlog | structlog is more powerful but heavier; python-json-logger is simpler and sufficient for field renaming + static fields |
| Cloud Run `--set-secrets` | Secret Manager SDK in code | `--set-secrets` requires zero code changes; SDK adds dependency and complexity |
| Cloud Scheduler + HTTP endpoint | APScheduler in-process | APScheduler doesn't survive instance restarts; Cloud Scheduler is durable and external |
| Structured logs for cost tracking | Firestore for cost state | Structured logs are already being emitted; querying them avoids adding a database dependency |

**Installation:**
```bash
uv add python-json-logger
```

No other new dependencies required. All GCP configuration is via gcloud CLI flags and Cloud Console, not Python SDKs.

## Architecture Patterns

### Recommended Project Structure
```
src/knowledge_hub/
├── logging_config.py     # NEW: JSON logging setup with GCP severity mapping
├── cost.py               # NEW: Token usage extraction, cost calculation, cost logging
├── digest.py             # NEW: Weekly digest builder + daily cost alert logic
├── config.py             # MODIFIED: Add ALLOWED_USER_ID default handling
├── app.py                # MODIFIED: Add logging config, /digest and /cost-check routes
├── llm/
│   └── processor.py      # MODIFIED: Extract usage_metadata, call cost logger
└── slack/
    └── notifier.py       # MODIFIED: Add cost to success notification
```

### Pattern 1: Structured JSON Logging with GCP Severity Mapping
**What:** Configure Python's stdlib logging to emit JSON with `severity` field that Cloud Run extracts into LogEntry severity.
**When to use:** All logging in the application.
**Example:**
```python
# Source: python-json-logger Context7 + GCP structured logging docs
import logging
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "rename_fields": {
                "levelname": "severity",
                "asctime": "timestamp",
            },
            "static_fields": {
                "service": "knowledge-hub",
            },
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}

def configure_logging():
    logging.config.dictConfig(LOGGING_CONFIG)
```

### Pattern 2: Gemini Token Usage Extraction and Cost Calculation
**What:** Extract `usage_metadata` from the Gemini API response and calculate cost based on model pricing.
**When to use:** After every successful `generate_content` call.
**Example:**
```python
# Source: google-genai SDK docs + Gemini pricing page
from dataclasses import dataclass

# Gemini 3 Flash Preview pricing (per token)
INPUT_PRICE_PER_TOKEN = 0.50 / 1_000_000   # $0.50 per 1M input tokens
OUTPUT_PRICE_PER_TOKEN = 3.00 / 1_000_000   # $3.00 per 1M output tokens

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float

def extract_usage(response) -> TokenUsage:
    """Extract token usage and calculate cost from a Gemini response."""
    meta = response.usage_metadata
    prompt = meta.prompt_token_count or 0
    completion = meta.candidates_token_count or 0
    cost = (prompt * INPUT_PRICE_PER_TOKEN) + (completion * OUTPUT_PRICE_PER_TOKEN)
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        cost_usd=cost,
    )
```

### Pattern 3: Cloud Run Secret Mounting via Environment Variables
**What:** Mount Secret Manager secrets as environment variables at instance startup. pydantic-settings reads them automatically.
**When to use:** All API keys and signing secrets.
**Example:**
```bash
# Source: GCP Cloud Run secrets documentation
gcloud run deploy knowledge-hub \
  --source . \
  --region europe-west4 \
  --set-secrets="SLACK_BOT_TOKEN=slack-bot-token:latest,\
SLACK_SIGNING_SECRET=slack-signing-secret:latest,\
NOTION_API_KEY=notion-api-key:latest,\
NOTION_DATABASE_ID=notion-database-id:latest,\
GEMINI_API_KEY=gemini-api-key:latest,\
ALLOWED_USER_ID=allowed-user-id:latest" \
  --min-instances=1 \
  --no-cpu-throttling \
  --cpu-boost \
  --memory=512Mi \
  --cpu=1 \
  --allow-unauthenticated
```

### Pattern 4: Cloud Scheduler for Weekly Digest and Daily Cost Alert
**What:** External scheduler sends HTTP POST to Cloud Run endpoints on a cron schedule.
**When to use:** Weekly digest on Monday morning + daily cost check.
**Example:**
```bash
# Source: GCP Cloud Scheduler + Cloud Run docs

# Create a service account for scheduler
gcloud iam service-accounts create scheduler-sa \
  --display-name "Cloud Scheduler SA"

# Grant invoker role
gcloud run services add-iam-policy-binding knowledge-hub \
  --region=europe-west4 \
  --member=serviceAccount:scheduler-sa@PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/run.invoker

# Weekly digest: Monday 8:00 AM CET
gcloud scheduler jobs create http weekly-digest \
  --schedule="0 8 * * 1" \
  --time-zone="Europe/Amsterdam" \
  --http-method=POST \
  --uri="https://knowledge-hub-HASH.run.app/digest" \
  --oidc-service-account-email=scheduler-sa@PROJECT_ID.iam.gserviceaccount.com \
  --oidc-token-audience="https://knowledge-hub-HASH.run.app"

# Daily cost check: Every day at 23:55 CET
gcloud scheduler jobs create http daily-cost-check \
  --schedule="55 23 * * *" \
  --time-zone="Europe/Amsterdam" \
  --http-method=POST \
  --uri="https://knowledge-hub-HASH.run.app/cost-check" \
  --oidc-service-account-email=scheduler-sa@PROJECT_ID.iam.gserviceaccount.com \
  --oidc-token-audience="https://knowledge-hub-HASH.run.app"
```

### Pattern 5: Sending Slack DMs
**What:** Send a direct message to the user by passing user ID as the `channel` parameter.
**When to use:** Weekly digest and daily cost alert -- both are DMs, not channel messages.
**Example:**
```python
# Source: Slack API docs chat.postMessage
client = await get_slack_client()
settings = get_settings()

# DM to user -- pass user ID as channel
await client.chat_postMessage(
    channel=settings.allowed_user_id,  # User ID = DM channel
    text="Weekly Digest: 5 entries processed this week...",
)
```

### Pattern 6: Weekly Digest via Notion Query
**What:** Query the Notion database for entries created in the past 7 days, aggregate stats, and send a formatted Slack DM.
**When to use:** The `/digest` endpoint triggered by Cloud Scheduler.
**Example:**
```python
# Query Notion for entries from the past week
from datetime import datetime, timedelta, timezone

one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

response = await client.data_sources.query(
    data_source_id=ds_id,
    filter={
        "property": "Date Added",
        "date": {"on_or_after": one_week_ago},
    },
)
entries = response["results"]
# Paginate if has_more is true
```

### Anti-Patterns to Avoid
- **Importing google-cloud-secret-manager SDK:** Cloud Run's `--set-secrets` handles this at the infrastructure level. Adding the SDK is unnecessary complexity.
- **Using APScheduler or in-process cron:** These don't survive instance recycling. Cloud Scheduler is external and durable.
- **Writing cost state to Firestore:** Adds a database dependency. Structured logs + log queries are sufficient for the low volume of this personal tool.
- **Using `print(json.dumps(...))` for logging:** Use `python-json-logger` with stdlib logging instead. It properly handles exception formatting, log levels, and extra fields.
- **Hardcoding Gemini pricing in multiple places:** Define pricing constants in one module (`cost.py`) and import everywhere.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON log formatting | Custom JSON formatter | python-json-logger `JsonFormatter` | Handles exception serialization, extra fields, field renaming, static fields |
| GCP severity mapping | Manual levelname-to-severity dict | JsonFormatter `rename_fields={"levelname": "severity"}` | One config line vs. custom formatter class |
| Secret injection | Custom secret-loading code | Cloud Run `--set-secrets` flag | Zero code changes; env vars appear automatically |
| Cron scheduling | In-process scheduler | Cloud Scheduler | Survives instance restarts; managed service |
| Slack signature verification | Custom HMAC implementation | `slack_sdk.signature.SignatureVerifier` (already in use) | Handles timestamp validation, constant-time comparison |

**Key insight:** This phase is primarily infrastructure configuration, not application code. Most "deployment" work is gcloud CLI flags and a few small Python modules. The existing codebase was built with Cloud Run in mind (pydantic-settings env vars, FastAPI BackgroundTasks, Slack signature verification).

## Common Pitfalls

### Pitfall 1: CPU Throttling Kills Background Tasks
**What goes wrong:** Without `--no-cpu-throttling`, Cloud Run throttles CPU to near-zero after the HTTP response is sent. FastAPI `BackgroundTasks` that run after `return JSONResponse({"ok": True})` get starved of CPU and time out.
**Why it happens:** Default Cloud Run billing is request-based -- CPU is only allocated during request processing.
**How to avoid:** Always deploy with `--no-cpu-throttling` (instance-based billing). Combined with `--min-instances=1`, this keeps CPU available for background processing.
**Warning signs:** Background tasks take 10-100x longer than expected, or Gemini API calls time out after response is sent.

### Pitfall 2: Slack 3-Second ACK Timeout on Cold Start
**What goes wrong:** Slack requires a response within 3 seconds. A cold start can take 5-10 seconds (Python startup + dependency imports + pydantic-settings loading). Slack retries, leading to duplicate processing.
**Why it happens:** No warm instances available, `--min-instances` not set.
**How to avoid:** Set `--min-instances=1` to keep one instance warm. Optionally add `--cpu-boost` for faster cold starts when scaling beyond 1 instance.
**Warning signs:** Seeing `X-Slack-Retry-Num` headers frequently. The retry dedup in `router.py` handles this gracefully, but cold starts still delay the user experience.

### Pitfall 3: Secrets Resolved at Startup, Not Runtime
**What goes wrong:** When secrets are mounted as environment variables, they're read once at instance startup. If a secret is rotated in Secret Manager, running instances still use the old value.
**Why it happens:** Cloud Run resolves env-var secrets at instance creation time, not on each request.
**How to avoid:** For this personal tool, this is acceptable. If a secret is rotated, deploy a new revision (`gcloud run deploy`) which creates new instances that pick up the new secret value.
**Warning signs:** Authentication failures after rotating a secret without redeploying.

### Pitfall 4: Logging to stderr vs. stdout
**What goes wrong:** Python's default `logging.StreamHandler` writes to `stderr`. Cloud Run treats stderr as ERROR severity, regardless of the JSON `severity` field.
**Why it happens:** Python logging default behavior.
**How to avoid:** Explicitly set `stream=sys.stdout` in the handler configuration.
**Warning signs:** All logs appear as ERROR severity in Cloud Logging despite JSON containing `"severity": "INFO"`.

### Pitfall 5: Forgetting IAM for Secret Manager Access
**What goes wrong:** Deployment succeeds but the service crashes at startup with "Permission denied" when trying to read secrets.
**Why it happens:** The Cloud Run service account doesn't have `roles/secretmanager.secretAccessor`.
**How to avoid:** Grant the role to the compute service account before deploying: `gcloud secrets add-iam-policy-binding SECRET_NAME --member=serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor`.
**Warning signs:** Instance crashes immediately after startup in Cloud Run logs.

### Pitfall 6: Cloud Scheduler OIDC Audience Mismatch
**What goes wrong:** Cloud Scheduler job executes but gets 401/403 from Cloud Run.
**Why it happens:** The `--oidc-token-audience` doesn't match the Cloud Run service URL, or the scheduler service account lacks `roles/run.invoker`.
**How to avoid:** Set `--oidc-token-audience` to the exact Cloud Run service URL (no trailing path). Grant `roles/run.invoker` to the scheduler service account on the specific service.
**Warning signs:** Scheduler job shows "FAILED" status with 401/403 response code.

### Pitfall 7: Notion Pagination in Digest Query
**What goes wrong:** Digest only shows first 100 entries if more than 100 entries were created in a week.
**Why it happens:** Notion API returns max 100 results per page. For a personal tool processing a few links per day, this is unlikely but should be handled.
**How to avoid:** Check `has_more` in the response and paginate with `start_cursor` if needed.
**Warning signs:** Digest consistently shows exactly 100 entries.

## Code Examples

Verified patterns from official sources:

### Structured Logging Configuration (dictConfig)
```python
# Source: python-json-logger Context7 docs
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(funcName)s %(message)s",
            "rename_fields": {
                "levelname": "severity",
                "asctime": "timestamp",
                "name": "logger",
            },
            "static_fields": {
                "service": "knowledge-hub",
            },
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",  # stdout, NOT stderr
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
```

### Token Usage Logging After Gemini Call
```python
# Source: google-genai SDK docs, Gemini pricing page
import logging

logger = logging.getLogger(__name__)

# After _call_gemini returns:
# response = await client.aio.models.generate_content(...)
meta = response.usage_metadata
prompt_tokens = meta.prompt_token_count or 0
completion_tokens = meta.candidates_token_count or 0
cost = (prompt_tokens * 0.50 / 1_000_000) + (completion_tokens * 3.00 / 1_000_000)

logger.info(
    "Gemini processing complete",
    extra={
        "url": content.url,
        "model": "gemini-3-flash-preview",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": round(cost, 6),
    },
)
```

### Full Deploy Command
```bash
# Source: GCP Cloud Run official docs (multiple pages)
gcloud run deploy knowledge-hub \
  --source . \
  --region europe-west4 \
  --set-secrets="SLACK_BOT_TOKEN=slack-bot-token:latest,\
SLACK_SIGNING_SECRET=slack-signing-secret:latest,\
NOTION_API_KEY=notion-api-key:latest,\
NOTION_DATABASE_ID=notion-database-id:latest,\
GEMINI_API_KEY=gemini-api-key:latest,\
ALLOWED_USER_ID=allowed-user-id:latest" \
  --set-env-vars="ENVIRONMENT=production,LOG_LEVEL=INFO" \
  --min-instances=1 \
  --no-cpu-throttling \
  --cpu-boost \
  --memory=512Mi \
  --cpu=1 \
  --allow-unauthenticated \
  --project=PROJECT_ID
```

### Digest Slack DM Format
```python
# Source: Slack API chat.postMessage docs
blocks_text = "\n".join(
    f"- <{entry['url']}|{entry['title']}>"
    for entry in entries
)

message = (
    f"*Weekly Knowledge Base Digest*\n"
    f"_{start_date} to {end_date}_\n\n"
    f"*{len(entries)} entries processed*\n"
    f"{blocks_text}\n\n"
    f"*Categories:* {category_breakdown}\n"
    f"*Top tags:* {top_tags}\n"
    f"*Total Gemini cost:* ${total_cost:.4f}"
)

await client.chat_postMessage(
    channel=settings.allowed_user_id,
    text=message,
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `google-cloud-logging` SDK for Cloud Run | JSON to stdout with `severity` field | 2022+ | No SDK dependency; Cloud Run natively parses JSON from stdout |
| Container Registry (gcr.io) | Artifact Registry | 2024 (Container Registry deprecated) | Must use `REGION-docker.pkg.dev` format for image URLs |
| `--cpu-always-allocated` | `--no-cpu-throttling` | 2023 | Flag renamed; same behavior (instance-based billing) |
| `gcloud run deploy --image` only | `gcloud run deploy --source .` | 2022+ | Source-based deploy builds container automatically via Cloud Build |

**Deprecated/outdated:**
- Container Registry (`gcr.io`): Deprecated. Use Artifact Registry (`REGION-docker.pkg.dev`).
- The flag name `--cpu-always-allocated` (mentioned in STATE.md blockers) is NOT the correct flag. The actual flag is `--no-cpu-throttling`.

## Open Questions

1. **Digest endpoint authentication**
   - What we know: Cloud Scheduler uses OIDC tokens. The `/slack/events` endpoint uses `allow-unauthenticated` (Slack sends webhooks without GCP auth). The `/digest` and `/cost-check` endpoints should only be callable by Cloud Scheduler.
   - What's unclear: Whether to use a shared secret header check or rely on OIDC token validation.
   - Recommendation: Use Cloud Run's built-in IAM authentication. Make the service `--allow-unauthenticated` for Slack webhooks, but validate scheduler requests via a shared secret header OR use a separate internal-only service. Simplest: validate a `X-CloudScheduler` header or check the OIDC token audience. Since this is a personal tool, a simple shared secret in the request body/header (stored in Secret Manager) is pragmatic.

2. **Cost tracking for daily alert: log query vs. in-memory accumulation**
   - What we know: With `--min-instances=1` and `--no-cpu-throttling`, a single instance stays alive and could accumulate costs in memory. But instances can still be recycled (deployments, scaling events, 15-min idle after traffic drops to zero with multiple instances).
   - What's unclear: Whether the instance will reliably keep state for a full day.
   - Recommendation: Use structured logs as the source of truth. The `/cost-check` endpoint queries today's structured logs for cost entries. Alternative: accumulate in-memory with a daily reset, and accept that a restarted instance may under-report (acceptable for a $5 alert threshold on a personal tool). Simplest pragmatic approach: in-memory accumulation with an `AtomicFloat` + daily reset -- good enough for a personal tool where missing one day's alert due to instance restart is not critical.

3. **Artifact Registry repository creation**
   - What we know: `gcloud run deploy --source .` auto-creates an Artifact Registry repo if one doesn't exist. Manual `docker build && docker push` requires pre-creating a repo.
   - What's unclear: Whether the user has an existing Artifact Registry repo or Docker installed locally.
   - Recommendation: Use `gcloud run deploy --source .` which handles both building and pushing automatically via Cloud Build. This avoids needing Docker locally (user noted Docker not installed on dev machine in Phase 1).

## Sources

### Primary (HIGH confidence)
- [GCP Cloud Run Secrets Documentation](https://docs.cloud.google.com/run/docs/configuring/services/secrets) - `--set-secrets` flag syntax, IAM requirements
- [GCP Cloud Run Billing Settings](https://docs.cloud.google.com/run/docs/configuring/billing-settings) - `--no-cpu-throttling` flag, background task survival, instance-based billing
- [GCP Cloud Run Logging](https://docs.cloud.google.com/run/docs/logging) - Structured JSON logging, `severity` field extraction, trace correlation
- [GCP Cloud Scheduler + Cloud Run](https://docs.cloud.google.com/run/docs/triggering/using-scheduler) - Scheduler setup, OIDC auth, service account IAM
- [GCP Cloud Run FastAPI Quickstart](https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service) - Source-based deployment, `--source .` flag
- [python-json-logger Context7](/nhairs/python-json-logger) - JsonFormatter configuration, field renaming, static fields, dictConfig setup
- [google-genai SDK Context7](/googleapis/python-genai) - GenerateContentResponse, usage_metadata attributes (prompt_token_count, candidates_token_count)
- [Gemini API Tokens Documentation](https://ai.google.dev/gemini-api/docs/tokens) - usage_metadata access pattern
- [Slack API chat.postMessage](https://api.slack.com/methods/chat.postMessage) - DM via user ID as channel parameter

### Secondary (MEDIUM confidence)
- [Gemini 3 Flash Pricing](https://ai.google.dev/gemini-api/docs/pricing) - $0.50/1M input, $3.00/1M output -- verified across multiple sources
- [GCP Cloud Run CPU Configuration](https://docs.cloud.google.com/run/docs/configuring/services/cpu) - CPU and memory limits
- [GCP Artifact Registry Transition](https://docs.cloud.google.com/artifact-registry/docs/transition/changes-gcp) - Container Registry deprecation

### Tertiary (LOW confidence)
- In-memory cost accumulation reliability with `--min-instances=1` -- based on reasoning about Cloud Run behavior, not explicit documentation. Instance recycling frequency is not documented.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - python-json-logger verified via Context7, gcloud flags verified via official docs
- Architecture: HIGH - patterns based on existing codebase structure + GCP official documentation
- Pitfalls: HIGH - all pitfalls verified against official documentation (severity field, CPU throttling, cold starts)
- Cost tracking: MEDIUM - Gemini pricing confirmed across multiple sources; daily accumulation approach is pragmatic but not battle-tested
- Weekly digest: MEDIUM - Notion query pattern extrapolated from existing `data_sources.query` usage in codebase; Cloud Scheduler setup verified via official docs

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (30 days -- GCP services and pricing are stable)
