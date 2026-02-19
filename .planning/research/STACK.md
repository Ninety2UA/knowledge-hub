# Stack Research

**Domain:** Slack-to-Notion knowledge base automation pipeline
**Researched:** 2026-02-19
**Confidence:** MEDIUM (versions from training data, not verified against live PyPI -- see Sources)

## Verification Note

WebSearch, WebFetch, and Bash were unavailable during this research session. All version numbers are from training data (cutoff ~May 2025). Before pinning versions in `requirements.txt`, run `pip index versions <package>` to confirm latest stable releases. Confidence is MEDIUM across the board for version specifics, HIGH for library selection rationale.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Runtime | Latest stable with best performance. 3.12 has significant speedups (5-15%) over 3.11. Avoid 3.13 on Cloud Run -- GCP base images may lag. |
| FastAPI | >=0.115.0 | HTTP framework | Async-native, auto OpenAPI docs, Pydantic v2 integration for request/response validation. Only framework where Slack webhook + background task is ~20 lines. |
| Uvicorn | >=0.32.0 | ASGI server | Standard FastAPI production server. Use `--workers 1` on Cloud Run (one container = one worker, Cloud Run handles scaling). |
| google-genai | >=1.10.0 | Gemini API client | Official Google Gen AI SDK. Replaces the older `google-generativeai` package. Supports structured output (JSON schema), streaming, async, and automatic retries. |
| trafilatura | >=2.0.0 | Article extraction | Best-in-class web content extraction. Handles nav, ads, boilerplate removal. Falls back to `readability` internally. Faster and more accurate than BeautifulSoup + manual parsing or newspaper3k (unmaintained). |
| youtube-transcript-api | >=1.0.0 | YouTube transcript extraction | Direct YouTube transcript/caption retrieval without API key. No YouTube Data API quota consumed. Supports auto-generated captions and multiple languages. |
| notion-client | >=2.2.0 | Notion API client | Official Notion Python SDK (`notion-client` on PyPI, imported as `notion_client`). Typed, handles pagination, retries. Do NOT confuse with `notion` (unofficial, abandoned). |
| slack-sdk | >=3.33.0 | Slack API client | Official Slack SDK. Use `WebClient` for posting messages and `SignatureVerifier` for webhook security. Do NOT use `slack-bolt` (adds unnecessary web server complexity when you already have FastAPI). |
| Pydantic | >=2.9.0 | Data validation | Already bundled with FastAPI. Use for Gemini output schema validation, Notion property mapping, and Slack event parsing. Pydantic v2 is 5-50x faster than v1. |
| Docker | N/A | Containerization | Required for Cloud Run. Use `python:3.12-slim` base image (not `alpine` -- musl libc causes issues with some C extensions). |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | >=0.28.0 | HTTP client | For URL redirect resolution (following shortened URLs) and any HTTP calls not covered by SDKs. Already a FastAPI dependency. Async-native unlike `requests`. |
| tenacity | >=9.0.0 | Retry logic | Exponential backoff for Gemini, Notion, and Slack API calls. More ergonomic than hand-rolled retry loops. `@retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(3))`. |
| structlog | >=24.4.0 | Structured logging | JSON logging that Cloud Run understands natively. Attaches request IDs, timing, token counts to every log line. Standard Python `logging` produces unstructured text that is painful to query in Cloud Logging. |
| google-cloud-secret-manager | >=2.21.0 | Secrets access | Read API keys from Secret Manager at startup. Use `SecretManagerServiceClient` with `access_secret_version`. Cache values in memory (they do not change during a container lifecycle). |
| python-dotenv | >=1.0.0 | Local dev secrets | Load `.env` file locally so you do not need Secret Manager running during development. Never used in production (Cloud Run injects secrets as env vars or mounts). |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff | Linter + formatter | Replaces flake8 + isort + black in one tool. 10-100x faster. Use `ruff check` and `ruff format`. Config in `pyproject.toml`. |
| pytest | Testing | Standard Python test runner. Use `pytest-asyncio` for testing async FastAPI endpoints. Use `pytest-httpx` for mocking HTTP calls. |
| pytest-asyncio | Async test support | Required for testing `async def` endpoints. Set `asyncio_mode = "auto"` in `pyproject.toml`. |

---

## Installation

```bash
# Core application dependencies
pip install \
  fastapi \
  uvicorn[standard] \
  google-genai \
  trafilatura \
  youtube-transcript-api \
  notion-client \
  slack-sdk \
  httpx \
  tenacity \
  structlog \
  google-cloud-secret-manager \
  pydantic

# Local development only
pip install \
  python-dotenv

# Dev dependencies
pip install \
  ruff \
  pytest \
  pytest-asyncio \
  pytest-httpx
```

Pin exact versions in `requirements.txt` after verifying latest from PyPI. Use `pip-compile` from `pip-tools` if you want reproducible builds from a `requirements.in` file.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| FastAPI | Flask | Never for this project. Flask lacks native async (needed for background tasks after Slack ACK). Flask's async support via `async def` routes exists but is bolted on and less ergonomic. |
| FastAPI | Django | Never for this project. Django is for database-backed web apps with admin panels. Massive overkill for a webhook pipeline. Cold starts would be 3-5x slower. |
| google-genai | google-generativeai | Never. `google-generativeai` is the older SDK. `google-genai` is the current official SDK with better structured output support, async, and cleaner API. Google is directing all new development to `google-genai`. |
| google-genai | litellm / openai (with Gemini) | Only if you plan to swap LLM providers frequently. The project explicitly locks to Gemini, so the abstraction overhead and extra dependency are not worth it. Direct SDK gives you access to Gemini-specific features (grounding, code execution, etc.) without translation layers. |
| trafilatura | newspaper3k / newspaper4k | Only if trafilatura fails on a specific site. newspaper3k is unmaintained (last release 2018). newspaper4k is a community fork that is active but less accurate at boilerplate removal. trafilatura benchmarks consistently higher on extraction quality. |
| trafilatura | BeautifulSoup + readability-lxml | Only if you need fine-grained control over HTML parsing. This is what trafilatura does internally, but with years of heuristics on top. Rolling your own is reinventing the wheel. |
| notion-client | Direct HTTP to Notion API | Only if you need bleeding-edge Notion API features before the SDK adds them. The SDK handles pagination, rate limiting, and auth header injection. |
| slack-sdk (WebClient) | slack-bolt | Only if building a Slack app with modals, shortcuts, and interactive components. Bolt adds its own HTTP server which conflicts with FastAPI. For a simple webhook receiver + message poster, `slack-sdk` directly is cleaner. |
| structlog | stdlib logging | Only if you want zero dependencies for logging. But then you must manually format JSON, attach context fields, and configure Cloud Run integration. structlog does all of this in 5 lines of setup. |
| tenacity | Manual retry loops | Never. Hand-rolled retry logic is error-prone (forgetting jitter, wrong backoff math). tenacity is battle-tested and declarative. |
| httpx | requests | Never for this project. `requests` is synchronous-only. Since FastAPI is async, you need an async HTTP client. httpx supports both sync and async, and is already a transitive dependency of FastAPI's test client. |
| ruff | flake8 + black + isort | Never. ruff replaces all three in a single tool that is 10-100x faster. There is no reason to use the separate tools anymore. |
| pytest | unittest | Never for new projects. pytest has better assertion introspection, fixtures, and plugin ecosystem. unittest's verbose class-based style is obsolete for application testing. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `google-generativeai` | Older Gemini SDK being superseded by `google-genai`. Will eventually be deprecated. Structured output support is less robust. | `google-genai` |
| `slack-bolt` | Starts its own HTTP server. Conflicts with FastAPI. Adds complexity for no benefit when you only need webhook receiving + message posting. | `slack-sdk` (WebClient + SignatureVerifier) |
| `newspaper3k` | Unmaintained since 2018. Broken on many modern sites. Known memory leaks. | `trafilatura` |
| `requests` | Synchronous only. Blocks the event loop in async FastAPI. Using it with `run_in_executor` is a hack. | `httpx` |
| `celery` / `redis` / task queues | Massive overkill for single-user, <10 requests/day. Adds infrastructure cost and complexity. Cloud Run already handles concurrency. | FastAPI `BackgroundTasks` or `asyncio.create_task()` |
| `langchain` | Enormous dependency tree (100+ packages). Abstracts away the Gemini API behind layers that make debugging impossible. Constant breaking changes. You are calling one LLM with one prompt. | Direct `google-genai` SDK calls |
| `python:3.12-alpine` Docker base | musl libc causes compilation failures for C extensions (lxml, which trafilatura depends on). Build times are 5-10x longer due to compiling from source. | `python:3.12-slim` (Debian-based) |
| `notion` (PyPI) | Unofficial, abandoned Notion client. Last updated years ago. Incompatible with current Notion API. | `notion-client` (official) |
| `beautifulsoup4` (for extraction) | Fine for parsing, but for article extraction you would need to pair it with readability-lxml and write custom heuristics. trafilatura does all this better. | `trafilatura` (uses BS4 internally) |
| `flask[async]` | Flask's async support is bolted on. No native BackgroundTasks equivalent. ASGI support requires additional adapters. | FastAPI (async-native from the ground up) |
| Environment variables for secrets (production) | Env vars are visible in Cloud Run console, logged in crash dumps, and shared across all containers. | Google Secret Manager (accessed at startup, cached in memory) |

---

## Stack Patterns by Variant

**If Gemini 3 Flash is unavailable or deprecated at GA:**
- Switch to `gemini-2.0-flash` or `gemini-2.5-flash` (next stable flash model)
- The `google-genai` SDK abstracts model names, so it is a one-line config change
- Do NOT introduce litellm just for this possibility

**If content extraction needs expand to PDFs:**
- Add `pymupdf` (aka `fitz`) for PDF text extraction
- Alternatively `pdfplumber` for table-heavy PDFs
- trafilatura does not handle PDFs

**If podcast transcript support is needed:**
- For podcasts on YouTube, `youtube-transcript-api` already handles it
- For non-YouTube podcasts, there is no free transcript API
- Options: (a) extract audio and use Gemini's multimodal audio input, (b) use a speech-to-text service (adds cost), (c) extract only metadata (title, description, show notes) from the podcast page
- Recommended: Start with metadata-only, add audio transcription later if needed

**If batch processing is needed:**
- Do NOT add a task queue (Celery/Redis)
- Use a simple `/batch` endpoint that processes URLs sequentially with `asyncio.sleep(1)` between calls to respect rate limits
- Cloud Run request timeout can be extended to 60 minutes for batch jobs

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| FastAPI >=0.100 | Pydantic v2 only | FastAPI dropped Pydantic v1 support. Ensure all models use Pydantic v2 syntax (`model_validator` not `validator`). |
| trafilatura >=1.0 | lxml, courlan | trafilatura pulls in lxml (C extension, needs `python:3.12-slim` not `alpine`). |
| google-genai | google-auth, google-api-core | Handles auth automatically on Cloud Run via default service account. No manual credential setup needed in production. |
| slack-sdk >=3.27 | Python 3.12 | Older slack-sdk versions had Python 3.12 compatibility issues. Use >=3.27. |
| structlog >=24.1 | stdlib logging | structlog wraps stdlib logging. Configure once at app startup. Compatible with Cloud Run's log agent. |

---

## Key Configuration Notes

### FastAPI + Slack Integration Pattern

```python
from fastapi import FastAPI, Request, BackgroundTasks
from slack_sdk.signature import SignatureVerifier

app = FastAPI()
verifier = SignatureVerifier(signing_secret=SLACK_SIGNING_SECRET)

@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    # Verify Slack signature (CRITICAL for security)
    body = await request.body()
    if not verifier.is_valid_request(body, request.headers):
        raise HTTPException(status_code=403)

    payload = await request.json()

    # Handle Slack URL verification challenge
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    # ACK immediately (Slack requires response within 3 seconds)
    background_tasks.add_task(process_link, payload)
    return {"ok": True}
```

### Gemini Structured Output Pattern

```python
from google import genai
from pydantic import BaseModel

class KBEntry(BaseModel):
    title: str
    summary: str
    key_points: list[str]
    tags: list[str]
    content_type: str
    priority: str

client = genai.Client()
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=prompt,
    config=genai.types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=KBEntry,
        max_output_tokens=4096,
    ),
)
entry = KBEntry.model_validate_json(response.text)
```

### Cloud Run Dockerfile Pattern

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run sets PORT env var
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```

---

## Sources

All recommendations are based on training data (cutoff ~May 2025). Web verification was unavailable during this research session.

- **FastAPI**: Training data knowledge of FastAPI 0.100+ with Pydantic v2. MEDIUM confidence on exact latest version.
- **google-genai**: Training data knowledge of the SDK transition from `google-generativeai` to `google-genai`. The structured output API (`response_schema`) is well-documented. MEDIUM confidence on exact version -- verify with `pip index versions google-genai`.
- **trafilatura**: Training data knowledge through v1.x releases. HIGH confidence on recommendation (benchmark comparisons are well-established), MEDIUM confidence on exact latest version.
- **youtube-transcript-api**: Training data knowledge. Known to break periodically when YouTube changes their frontend. MEDIUM confidence -- verify it still works before committing to it.
- **notion-client**: Training data knowledge of official Notion SDK. HIGH confidence on recommendation, MEDIUM confidence on version.
- **slack-sdk**: Training data knowledge of Slack SDK v3.x. HIGH confidence.
- **Gemini 3 Flash Preview**: This is a very new model (early 2026). LOW confidence on exact SDK parameter names for structured output. Verify with `google-genai` docs or Context7 before implementation.
- **Cloud Run**: HIGH confidence on patterns (well-established GCP service).
- **structlog, tenacity, httpx, ruff**: HIGH confidence -- these are mature, stable libraries with infrequent breaking changes.

**Critical verification needed before implementation:**
1. `google-genai` exact structured output API for Gemini 3 Flash Preview
2. `youtube-transcript-api` still functional (YouTube frequently breaks scrapers)
3. Exact latest versions of all packages via `pip index versions <package>`

---
*Stack research for: Slack-to-Notion knowledge base automation pipeline*
*Researched: 2026-02-19*
