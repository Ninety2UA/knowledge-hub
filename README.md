# Knowledge Hub

**Slack-to-Notion knowledge base automation pipeline.**

<!-- Placeholder: Add a project logo or banner image -->
<!-- ![Knowledge Hub Banner](docs/screenshots/banner.png) -->

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.129+-green.svg)](https://fastapi.tiangolo.com)
[![Deployed on Cloud Run](https://img.shields.io/badge/Cloud%20Run-deployed-4285F4.svg)](https://cloud.google.com/run)
[![Tests](https://img.shields.io/badge/tests-235%20passed-brightgreen.svg)](#running-tests)

Drop a link in a Slack channel, get a structured knowledge base entry in Notion — automatically. Knowledge Hub extracts content from articles, YouTube videos, and PDFs, processes it through Gemini to generate summaries, key points, and tags, then creates a fully formatted Notion page. No manual curation required.

---

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Demo](#demo)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Running the Project](#running-the-project)
- [Deployment](#deployment)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Why This Exists

Saving interesting articles, videos, and papers to "read later" usually means "never read again." Knowledge Hub eliminates the friction between discovery and retention. Post a URL to Slack — the system extracts the content, distills it into structured notes, and files it in Notion with proper categorization, tags, and priority. You get a searchable, organized knowledge base that builds itself.

---

## Demo

### Slack Input

```
# Post a URL in your configured Slack channel:
https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

### Pipeline Output (Slack Thread Reply)

```
Saved to Notion: How to Never Give Up — A Comprehensive Guide (Cost: $0.003)
```

<!-- Screenshot: Slack channel showing a posted URL with a thread reply containing the Notion link -->
![Slack Thread Reply](docs/screenshots/slack-thread-reply.png)

<!-- Screenshot: The generated Notion page showing all 4 sections (Summary, Key Points, Key Learnings, Detailed Notes) -->
![Notion Page Output](docs/screenshots/notion-page-output.png)

<!-- Screenshot: The Notion database view showing multiple entries with tags, categories, and priorities -->
![Notion Database View](docs/screenshots/notion-database-view.png)

---

## Architecture

```mermaid
graph TB
    User([User]) -->|Posts URL| Slack[Slack Channel]
    Slack -->|Webhook POST /slack/events| FastAPI[FastAPI Service<br/>Cloud Run]

    FastAPI -->|HMAC Verify| SigCheck{Signature<br/>Valid?}
    SigCheck -->|No| Reject[403 Reject]
    SigCheck -->|Yes| ACK[200 ACK<br/>+ Background Task]

    ACK --> Extract[Content Extraction]

    Extract -->|Articles| Trafilatura[trafilatura]
    Extract -->|YouTube| YTApi[youtube-transcript-api]
    Extract -->|PDFs| PyPDF[pypdf]

    Extract --> LLM[LLM Processing]
    LLM -->|Structured Output| Gemini[Gemini 3 Flash]

    LLM --> Notion[Notion Service]
    Notion -->|Duplicate Check| NotionAPI[Notion API]
    Notion -->|Create Page| NotionAPI

    Notion --> Notify[Slack Notification]
    Notify -->|Thread Reply| Slack

    Scheduler([Cloud Scheduler]) -->|POST /digest| FastAPI
    Scheduler -->|POST /cost-check| FastAPI

    style FastAPI fill:#009688,color:#fff
    style Gemini fill:#4285F4,color:#fff
    style NotionAPI fill:#000,color:#fff
    style Slack fill:#4A154B,color:#fff
```

### Detailed Pipeline Flow

```mermaid
sequenceDiagram
    participant S as Slack
    participant F as FastAPI
    participant E as Extraction
    participant G as Gemini
    participant N as Notion

    S->>F: POST /slack/events (webhook)
    F->>F: Verify HMAC signature
    F->>F: Dedup retries (X-Slack-Retry-Num)
    F->>F: Filter (user, bot, thread, URLs)
    F-->>S: 200 OK (immediate ACK)

    Note over F: Background task starts

    F->>F: Resolve redirects (parallel)

    loop For each URL
        F->>E: extract_with_timeout(url, 30s)
        E->>E: Detect content type
        alt Article
            E->>E: trafilatura.bare_extraction()
        else YouTube
            E->>E: YouTubeTranscriptApi.fetch()
            Note over E: Falls back to Gemini<br/>if transcript unavailable
        else PDF
            E->>E: pypdf.PdfReader()
        end
        E-->>F: ExtractedContent

        F->>G: process_content(content)
        G->>G: Build prompt (type-specific)
        G->>G: Call Gemini (4 retries, exp backoff)
        G-->>F: (NotionPage, cost_usd)

        F->>N: create_notion_page(page)
        N->>N: Normalize URL, check duplicate
        N->>N: Validate tags against schema
        N->>N: Build properties + blocks
        N-->>F: PageResult | DuplicateResult

        F->>S: Thread reply (success/duplicate/error)
    end

    F->>S: Reaction (checkmark or X, best-effort)
```

---

## Features

### Content Ingestion
- **Multi-format extraction** — articles (trafilatura), YouTube videos (transcript API), and PDFs (pypdf)
- **Smart content detection** — URL pattern matching routes to the correct extractor automatically
- **YouTube Gemini fallback** — when transcript extraction fails (e.g., cloud IP blocking), Gemini processes the video natively via its built-in video understanding
- **Paywall awareness** — known paywalled domains flagged; partial content still processed at lower priority
- **Parallel URL resolution** — redirect chains resolved concurrently before extraction
- **30-second timeout + retry** — transient network errors get one automatic retry

### AI Processing
- **Structured output** — Gemini 3 Flash generates title, summary, category, tags, priority, key points, key learnings, and detailed notes via JSON schema
- **Content-aware prompts** — video, short-content, and article prompts are tailored to content type
- **Tag validation** — LLM-suggested tags are filtered against the Notion database schema; unknown tags are silently dropped
- **Cost tracking** — per-request cost logged and accumulated for daily/weekly reporting

### Knowledge Base
- **10-property Notion pages** — Title, URL, Source, Category, Tags, Priority, Status, Content Type, Date Added, Summary
- **4-section page body** — Summary, Key Points (bulleted), Key Learnings (what/why/application), Detailed Notes (headings + bullets)
- **Duplicate detection** — normalized URL matching prevents re-processing the same content
- **Tag schema enforcement** — only pre-approved tags from the Notion database are applied

### Operations
- **Weekly digest** — Slack DM every Monday with entry counts, category breakdown, top tags, and total Gemini cost
- **Daily cost alerts** — notification when daily Gemini spend exceeds $5
- **Fire-and-forget notifications** — Slack notification failures never crash the pipeline
- **Structured JSON logging** — GCP-compatible severity levels for Cloud Run observability

---

## Tech Stack

| Category | Technology | Purpose |
|---|---|---|
| **Runtime** | Python 3.12 | Application language |
| **Framework** | FastAPI | Async HTTP server, webhook handling |
| **Server** | Uvicorn | ASGI server |
| **LLM** | Gemini 3 Flash | Content analysis + structured output |
| **Extraction** | trafilatura | Article text extraction |
| **Extraction** | youtube-transcript-api | YouTube transcript extraction |
| **Extraction** | pypdf | PDF text extraction |
| **Database** | Notion API | Knowledge base storage |
| **Messaging** | Slack SDK | Webhook verification, notifications |
| **HTTP** | httpx | Async HTTP client (redirects, PDF download) |
| **Config** | pydantic-settings | Environment variable management |
| **Retry** | tenacity | Exponential backoff with jitter |
| **Caching** | cachetools | TTL cache for Notion tag schema |
| **Logging** | python-json-logger | Structured JSON log output |
| **Packaging** | uv | Fast dependency resolution + lockfile |
| **Deployment** | Google Cloud Run | Serverless container hosting |
| **Scheduling** | Google Cloud Scheduler | Cron-triggered digest + cost check |
| **Secrets** | GCP Secret Manager | Production secret injection |
| **Linting** | Ruff | Fast Python linter (E, F, I, UP rules) |
| **Testing** | pytest + pytest-asyncio | Async-native test framework |

---

## Prerequisites

- **Python 3.12+** — check with `python3 --version`
- **[uv](https://docs.astral.sh/uv/)** — Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **A Slack workspace** with permission to create apps
- **A Notion workspace** with an integration and a database
- **A Google AI API key** for Gemini access
- **Google Cloud SDK** (for deployment only) — `gcloud` CLI authenticated

### Required External Accounts

| Service | What You Need | Where to Get It |
|---|---|---|
| **Slack** | Bot token + signing secret | [api.slack.com/apps](https://api.slack.com/apps) |
| **Notion** | Integration token + database ID | [developers.notion.com](https://developers.notion.com) |
| **Google AI** | Gemini API key | [aistudio.google.com](https://aistudio.google.com) |
| **GCP** (deploy only) | Project with Cloud Run enabled | [console.cloud.google.com](https://console.cloud.google.com) |

---

## Installation & Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/knowledge-hub.git
cd knowledge-hub
```

### 2. Install dependencies

```bash
uv sync
```

This installs all runtime and dev dependencies from the lockfile (`uv.lock`). Expect to see packages like `fastapi`, `slack-sdk`, `google-genai`, etc.

### 3. Create the environment file

```bash
cp .env.example .env   # If .env.example exists
# Otherwise, create .env manually:
```

Add the following variables to `.env`:

```env
# Slack
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_SIGNING_SECRET=your-slack-signing-secret
ALLOWED_USER_ID=U0XXXXXXXXX

# Notion
NOTION_API_KEY=ntn_your-notion-api-key
NOTION_DATABASE_ID=your-notion-database-uuid

# Gemini
GEMINI_API_KEY=your-gemini-api-key

# Scheduler (used for /digest and /cost-check endpoints)
SCHEDULER_SECRET=any-random-secret-string

# App
ENVIRONMENT=development
LOG_LEVEL=INFO
PORT=8080
```

Secure the file:

```bash
chmod 600 .env
```

### 4. Set up the Slack app

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app
2. Under **OAuth & Permissions**, add these bot token scopes:
   - `chat:write` — send messages
   - `channels:history` — read channel messages
   - `reactions:write` — add reactions (optional — the bot works without this but won't add checkmark/X reactions)
3. Under **Event Subscriptions**, enable events and set the request URL to your service URL + `/slack/events` (e.g., `https://your-service.run.app/slack/events`)
4. Subscribe to the `message.channels` bot event
5. Install the app to your workspace
6. Copy the **Bot User OAuth Token** (`xoxb-...`) to `SLACK_BOT_TOKEN`
7. Copy the **Signing Secret** (under **Basic Information**) to `SLACK_SIGNING_SECRET`
8. Invite the bot to your target Slack channel — the channel **must be public** (`message.channels` does not receive events from private channels)

### 5. Set up the Notion database

1. Go to [notion.so](https://notion.so) and create a new database with these properties:

   | Property | Type |
   |---|---|
   | Title | Title (default) |
   | URL | URL |
   | Source | Rich text |
   | Category | Select: `Engineering`, `AI/ML`, `Product`, `Design`, `Business`, `Science`, `Other` |
   | Tags | Multi-select (pre-populate with relevant tags) |
   | Priority | Select: `HIGH`, `MEDIUM`, `LOW` |
   | Status | Select: `Unread`, `Reading`, `Completed`, `Archived` |
   | Content Type | Select: `Article`, `Video`, `PDF`, `Newsletter`, `Paper` |
   | Date Added | Date |
   | Summary | Rich text |

2. Create a [Notion internal integration](https://www.notion.com/profile/integrations) and connect it to the database (click "..." on the database → **Connections** → add your integration)
3. Copy the integration token to `NOTION_API_KEY`
4. Copy the database ID from the URL (the 32-char hex string) to `NOTION_DATABASE_ID`

### 6. Get a Gemini API key

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Create an API key
3. Copy it to `GEMINI_API_KEY`

### 7. Find your Slack user ID

1. In Slack, click your profile picture → **Profile**
2. Click the three dots (**...**) → **Copy member ID**
3. Set this as `ALLOWED_USER_ID` in `.env` (only this user's messages will be processed)

---

## Running the Project

### Development Mode

```bash
uv run uvicorn knowledge_hub.app:app --reload
```

Expected output:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
```

For local Slack webhook testing, use a tunnel like [ngrok](https://ngrok.com):

```bash
ngrok http 8000
```

Then set the ngrok HTTPS URL as your Slack Event Subscriptions request URL.

### Production Mode (Local)

```bash
uv run uvicorn knowledge_hub.app:app --host 0.0.0.0 --port 8080
```

### Docker

```bash
docker build -t knowledge-hub .
docker run -p 8080:8080 --env-file .env knowledge-hub
```

### Running Tests

```bash
uv run pytest
```

Expected output:

```
================================ test session starts =================================
collected 235 items

tests/test_health.py ..                                                        [  0%]
tests/test_app.py ......                                                       [  3%]
tests/test_cost.py .....                                                       [  5%]
...
================================ 235 passed in 4.52s =================================
```

Run a specific test module:

```bash
uv run pytest tests/test_slack/test_pipeline.py -v
```

### Linting

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

---

## Deployment

Knowledge Hub is designed for **Google Cloud Run** with secrets managed via **GCP Secret Manager**.

### Architecture

```mermaid
graph LR
    Slack([Slack API]) -->|Webhook| CR[Cloud Run<br/>knowledge-hub]
    CS([Cloud Scheduler]) -->|POST /digest<br/>POST /cost-check| CR
    CR -->|API calls| Gemini[Gemini API]
    CR -->|API calls| NotionAPI[Notion API]
    CR -->|Replies| Slack
    SM[(Secret Manager)] -->|Injected at boot| CR

    style CR fill:#4285F4,color:#fff
    style SM fill:#F4B400,color:#000
```

### Step 1: Create secrets in GCP Secret Manager

```bash
PROJECT_ID=your-gcp-project

# Create each secret (you'll be prompted to enter the value)
for secret in slack-bot-token slack-signing-secret notion-api-key \
              notion-database-id gemini-api-key allowed-user-id scheduler-secret; do
    echo -n "Enter value for $secret: "
    read -s value
    echo
    echo -n "$value" | gcloud secrets create "$secret" \
        --project="$PROJECT_ID" \
        --data-file=-
done
```

### Step 2: Grant the service account access

```bash
# The default compute service account needs secret access
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### Step 3: Deploy to Cloud Run

```bash
PROJECT_ID=your-gcp-project ./deploy.sh
```

<details>
<summary>What deploy.sh does</summary>

- Runs `gcloud run deploy --source .` (builds the container remotely via Cloud Build)
- Sets region to `europe-west4`
- Injects 7 secrets from Secret Manager
- Configures: `--min-instances=1`, `--memory=512Mi`, `--cpu=1`, `--allow-unauthenticated`
- Outputs the service URL

</details>

Expected output:

```
Deploying knowledge-hub to Cloud Run...
  Project:  your-gcp-project
  Region:   europe-west4
...
Deployment complete. Service URL:
https://knowledge-hub-xxxxxxxxxx-ez.a.run.app
```

### Step 4: Configure Slack webhook URL

Update your Slack app's Event Subscriptions request URL to:

```
https://knowledge-hub-xxxxxxxxxx-ez.a.run.app/slack/events
```

### Step 5: Set up Cloud Scheduler (optional)

For weekly digest and daily cost alerts, follow the setup commands in `deploy.sh` comments:

```bash
# Create scheduler service account
gcloud iam service-accounts create scheduler-sa \
    --project="$PROJECT_ID" \
    --display-name="Cloud Scheduler SA"

# Grant Cloud Run invoker role
gcloud run services add-iam-policy-binding knowledge-hub \
    --region=europe-west4 \
    --project="$PROJECT_ID" \
    --member="serviceAccount:scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Weekly digest — Monday 08:00 Amsterdam
# Note: Cloud Scheduler may not be available in all regions.
# Use a nearby region (e.g., europe-west3) if your Cloud Run region isn't supported.
gcloud scheduler jobs create http weekly-digest \
    --project="$PROJECT_ID" \
    --location=europe-west3 \
    --schedule="0 8 * * 1" \
    --time-zone="Europe/Amsterdam" \
    --http-method=POST \
    --uri="SERVICE_URL/digest" \
    --oidc-service-account-email="scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --oidc-token-audience="SERVICE_URL"

# Daily cost check — 23:55 Amsterdam
gcloud scheduler jobs create http daily-cost-check \
    --project="$PROJECT_ID" \
    --location=europe-west3 \
    --schedule="55 23 * * *" \
    --time-zone="Europe/Amsterdam" \
    --http-method=POST \
    --uri="SERVICE_URL/cost-check" \
    --oidc-service-account-email="scheduler-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --oidc-token-audience="SERVICE_URL"
```

Replace `SERVICE_URL` with the URL from Step 3.

### Step 6: Verify deployment

```bash
# Health check
curl https://knowledge-hub-xxxxxxxxxx-ez.a.run.app/health
# Expected: {"status":"ok","service":"knowledge-hub","version":"0.1.0"}
```

Then post a URL in your Slack channel and verify a Notion page is created.

---

## API Reference

| Method | Route | Description | Auth |
|---|---|---|---|
| `GET` | `/health` | Health check | None |
| `POST` | `/slack/events` | Slack webhook receiver | HMAC signature |
| `POST` | `/digest` | Trigger weekly digest | `X-Scheduler-Secret` header |
| `POST` | `/cost-check` | Trigger daily cost alert | `X-Scheduler-Secret` header |

### `GET /health`

```bash
curl https://your-service.run.app/health
```

```json
{
  "status": "ok",
  "service": "knowledge-hub",
  "version": "0.1.0"
}
```

### `POST /slack/events`

Receives Slack Event API payloads. Handles two event types:

- **`url_verification`** — responds with the challenge token (Slack setup handshake)
- **`event_callback`** — processes `message` events from the subscribed channel

Slack retries are deduplicated via the `X-Slack-Retry-Num` header.

### `POST /digest`

Requires `X-Scheduler-Secret` header matching the configured `SCHEDULER_SECRET`.

```bash
curl -X POST https://your-service.run.app/digest \
  -H "X-Scheduler-Secret: your-secret"
```

```json
{
  "status": "sent",
  "entries_count": 12,
  "period_days": 7
}
```

### `POST /cost-check`

Requires `X-Scheduler-Secret` header.

```bash
curl -X POST https://your-service.run.app/cost-check \
  -H "X-Scheduler-Secret: your-secret"
```

```json
{
  "status": "ok",
  "daily_cost_usd": 0.042,
  "alert_sent": false
}
```

---

## Project Structure

```
knowledge-hub/
├── src/knowledge_hub/
│   ├── app.py                          # FastAPI app, health + scheduled endpoints
│   ├── config.py                       # pydantic-settings configuration
│   ├── cost.py                         # Gemini cost tracking + accumulators
│   ├── digest.py                       # Weekly digest + daily cost alerts
│   ├── logging_config.py              # Structured JSON logging for GCP
│   ├── models/
│   │   ├── content.py                  # ExtractedContent, ContentType, ExtractionStatus
│   │   ├── knowledge.py               # KnowledgeEntry, Category, Priority enums
│   │   ├── notion.py                   # NotionPage (entry + 4 body sections)
│   │   └── slack.py                    # SlackEvent model
│   ├── extraction/
│   │   ├── router.py                   # URL → content type detection
│   │   ├── article.py                  # trafilatura article extraction
│   │   ├── youtube.py                  # YouTube transcript extraction
│   │   ├── pdf.py                      # PDF text extraction
│   │   ├── paywall.py                  # Paywalled domain detection
│   │   ├── paywalled_domains.yaml      # Known paywalled domains list
│   │   └── timeout.py                  # 30s timeout + retry wrapper
│   ├── llm/
│   │   ├── client.py                   # Gemini client singleton
│   │   ├── processor.py               # Content → NotionPage via Gemini
│   │   ├── prompts.py                  # System/user prompt templates
│   │   └── schemas.py                  # LLMResponse structured output schema
│   ├── notion/
│   │   ├── client.py                   # Notion client singleton
│   │   ├── service.py                  # Page creation orchestrator
│   │   ├── properties.py              # Notion property builder
│   │   ├── blocks.py                   # Notion block builder (page body)
│   │   ├── duplicates.py              # URL normalization + duplicate check
│   │   ├── tags.py                     # Tag schema cache + validation
│   │   └── models.py                   # PageResult, DuplicateResult
│   └── slack/
│       ├── router.py                   # POST /slack/events route
│       ├── handlers.py                # Event dispatch + pipeline orchestration
│       ├── client.py                   # Slack client singleton
│       ├── notifier.py                # Fire-and-forget Slack notifications
│       ├── urls.py                     # URL extraction + redirect resolution
│       └── verification.py           # HMAC signature verification
├── tests/                              # 235 tests mirroring src/ structure
├── docs/
│   ├── KB-Automation-PRD.md           # Original product requirements document
│   └── screenshots/                    # Screenshots (see Demo section)
├── Dockerfile                          # Python 3.12-slim + uv
├── deploy.sh                           # Cloud Run deployment script
├── pyproject.toml                      # Dependencies, pytest/ruff config
├── uv.lock                             # Locked dependency tree
└── .python-version                     # 3.12
```

---

## Configuration

All configuration is via environment variables (or `.env` file for local development).

| Variable | Required | Default | Description |
|---|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | `""` | Slack bot OAuth token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | Yes | `""` | Slack app signing secret for webhook HMAC verification |
| `ALLOWED_USER_ID` | Yes | `""` | Slack user ID of the single authorized user |
| `NOTION_API_KEY` | Yes | `""` | Notion integration token |
| `NOTION_DATABASE_ID` | Yes | `""` | UUID of the target Notion database |
| `GEMINI_API_KEY` | Yes | `""` | Google AI API key for Gemini |
| `SCHEDULER_SECRET` | Yes | `""` | Shared secret for `/digest` and `/cost-check` auth |
| `ENVIRONMENT` | No | `development` | App environment (`development` or `production`) |
| `LOG_LEVEL` | No | `INFO` | Python logging level |
| `PORT` | No | `8080` | HTTP server port |

---

## Troubleshooting

### Slack events not arriving

- Verify the request URL in Slack Event Subscriptions matches your service URL + `/slack/events`
- **The channel must be public** — `message.channels` only fires for public channels. If your channel is private, convert it to public in Slack channel settings.
- Check that the bot is invited to the target channel (channel settings → **Integrations** → **Add apps**)
- Confirm `SLACK_SIGNING_SECRET` matches the value in your Slack app's **Basic Information** page (not the bot token)
- For local development, ensure your tunnel (ngrok) is running and the URL is updated in Slack

### "Invalid scheduler secret" on `/digest` or `/cost-check`

- The `X-Scheduler-Secret` header must exactly match the `SCHEDULER_SECRET` environment variable
- For Cloud Scheduler, the secret is passed via the `--headers` flag or as a request header in the job configuration

### Notion page creation fails with "validation_error"

- **Tag mismatch**: The LLM may suggest tags not present in your Notion database schema. Tags are filtered automatically, but if the Tags property has no options at all, add some initial options to the database
- **Property mismatch**: Ensure all 10 properties exist in the Notion database with the exact types listed in [Setup Step 5](#5-set-up-the-notion-database)
- Verify the Notion integration has access to the database (click "..." on the database → "Connections" → add your integration)

### YouTube transcripts not extracted

- The video may have transcripts disabled by the creator
- Auto-generated captions are used as fallback; if neither exists, the extraction status will be `METADATA_ONLY`
- **Cloud IP blocking**: YouTube may block transcript requests from cloud provider IPs (including Cloud Run). When this happens, the pipeline automatically falls back to Gemini's native video understanding — the video URL is passed directly to Gemini for analysis. Quality is comparable but timestamps may be less precise.
- Check the logs for `TranscriptsDisabled`, `NoTranscriptFound`, or `will use Gemini fallback` messages

### High Gemini costs

- Each URL costs approximately $0.001–$0.005 depending on content length
- The daily cost check alerts at $5/day; adjust monitoring via the `/cost-check` endpoint
- Cost accumulators reset on Cloud Run instance restart (since they're in-memory)

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Install dev dependencies: `uv sync`
4. Make your changes
5. Run linting: `uv run ruff check src/ tests/`
6. Run tests: `uv run pytest`
7. Commit and push your branch
8. Open a pull request

### Code Style

- **Linter**: Ruff with rules `E`, `F`, `I`, `UP` (errors, pyflakes, isort, pyupgrade)
- **Line length**: 100 characters
- **Target**: Python 3.12
- **Async tests**: `asyncio_mode = "auto"` — no need for `@pytest.mark.asyncio`

---

## License

No license file is currently included in this repository.
