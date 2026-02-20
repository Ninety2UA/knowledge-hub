# Phase 3: Content Extraction - Research

**Researched:** 2026-02-20
**Domain:** Web content extraction (trafilatura + youtube-transcript-api + pypdf)
**Confidence:** HIGH

## Summary

Phase 3 implements content extraction from three source types: web articles (via trafilatura), YouTube videos (via youtube-transcript-api), and PDFs (via pypdf). The system routes URLs by content type using regex pattern matching, extracts text and metadata through type-specific extractors, and handles failures gracefully with a status enum (`full | partial | metadata_only | failed`).

All three core libraries are mature, well-documented, and synchronous. Since the application runs on FastAPI (async), all extraction calls must be wrapped in `asyncio.to_thread()` to avoid blocking the event loop. A 30-second wall-clock timeout wraps the entire extraction pipeline per URL using `asyncio.timeout()` (Python 3.11+ context manager). The existing `ExtractedContent` model needs one change: replace `is_partial: bool` with an `ExtractionStatus` enum to capture the four extraction outcomes decided by the user.

**Primary recommendation:** Use trafilatura `bare_extraction()` for articles (returns a Document object with all metadata fields), youtube-transcript-api `fetch()` for YouTube transcripts, pypdf `PdfReader` from `BytesIO` for PDFs. Wrap all sync calls in `asyncio.to_thread()`. Route by URL regex. Keep paywalled domain list in a YAML/TOML config file.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Content type routing
- URL pattern matching (regex) to detect content type -- no HTTP header checks
- Four extractor types: YouTube (transcript), PDF (text extraction), platform-specific (Substack, Medium -- better metadata only, same body extraction via trafilatura), and general article (trafilatura for everything else)
- Unknown URL types fall through to the general article extractor
- Platform-specific extractors enhance metadata only (newsletter name, author bio, series info) -- body text still uses trafilatura

#### Failure & fallback chain
- When body text extraction fails but metadata is available, proceed with metadata-only -- mark as partial extraction
- 30-second hard cap on total wall-clock time per URL (not per extractor step)
- One retry on transient failures (network timeouts, 5xx responses), still within the 30s budget
- Accept any extraction result regardless of text length -- no minimum threshold

#### PDF extraction depth
- Extract full text from entire PDF (LLM phase handles summarization downstream)
- No OCR for scanned/image-based PDFs -- fall back to metadata-only
- 20MB file size cap -- skip extraction for larger PDFs, flag as metadata-only
- Extract author/title from PDF document properties (embedded metadata) when available

#### Paywall handling
- Known paywalled domain list stored in config (not hardcoded) for easy updates
- Still attempt extraction on paywalled domains -- some give partial content (first paragraphs)
- Flag extraction result using a status enum: `full | partial | metadata_only | failed`
- The extraction status enum captures all failure modes (paywall, timeout, empty, error) in one field

### Claude's Discretion
- Choice of PDF extraction library
- Exact regex patterns for content type detection
- Which domains to include in the initial paywalled domain list
- Platform-specific metadata field mapping for Substack/Medium

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXTRACT-01 | System extracts article body text via trafilatura (removes nav, ads, boilerplate) | trafilatura `bare_extraction()` returns clean body text in `text` field, stripping boilerplate by default. Version 2.0.0 verified. |
| EXTRACT-02 | System extracts YouTube video transcripts via youtube-transcript-api | youtube-transcript-api `fetch()` returns transcript snippets. Version 1.2.4 verified. Must use instance method (not removed static methods). |
| EXTRACT-03 | System extracts metadata (title, author, date, source domain) from all content types | trafilatura Document has `title`, `author`, `date`, `sitename`, `hostname` fields. YouTube metadata via transcript `.language`, `.is_generated`. pypdf `reader.metadata` has `.title`, `.author`. |
| EXTRACT-04 | System detects content type from URL patterns (YouTube, Substack, Medium, etc.) | Regex-based URL matching: YouTube (`youtube.com/watch`, `youtu.be`), PDF (`.pdf` extension or content-type), Substack (`*.substack.com`), Medium (`medium.com/*`, `*.medium.com`). |
| EXTRACT-05 | System enforces 30-second timeout for content extraction with graceful failure | `asyncio.timeout(30)` context manager (Python 3.12) wraps entire extraction pipeline. On timeout, returns metadata-only result with `failed` status. |
| EXTRACT-06 | System detects paywalled content and flags entry as partial extraction | Configurable domain list in YAML/TOML. Pre-check URL domain before extraction. If paywall domain, attempt extraction anyway but flag result as `partial` if body text is short/empty. |
| EXTRACT-07 | System falls back to metadata-only processing for YouTube videos without captions | Catch `TranscriptsDisabled` and `NoTranscriptFound` exceptions from youtube-transcript-api. Return `metadata_only` status with whatever metadata was available. |
| EXTRACT-08 | System extracts text content from PDF links | pypdf `PdfReader(BytesIO(bytes))` for in-memory PDF reading. Download via httpx with Content-Length check (20MB cap). Extract text from all pages. |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| trafilatura | >=2.0.0 | Article body text + metadata extraction | Standard Python web extraction library. Used by HuggingFace, IBM, Microsoft Research. Handles boilerplate removal, metadata (title, author, date, sitename), multiple output formats. |
| youtube-transcript-api | >=1.2.4 | YouTube video transcript extraction | Only maintained library for YouTube transcript retrieval without browser automation. v1.1.0+ uses innertube API instead of HTML scraping. Specific exception types for all failure modes. |
| pypdf | >=6.7.1 | PDF text and metadata extraction | Pure-Python PDF library (no C dependencies). Supports text extraction from all pages, metadata reading (title, author, dates). Works with `BytesIO` for in-memory processing. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | >=0.28.1 | PDF downloading, HTTP requests | Already a project dependency. Use `AsyncClient` for downloading PDFs before passing to pypdf. Check Content-Length header for 20MB cap. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pypdf | PyMuPDF (pymupdf) | PyMuPDF is faster and handles more edge cases, but requires C bindings (MuPDF). pypdf is pure-Python, simpler to deploy in Docker, and sufficient for text extraction from well-formed PDFs. |
| pypdf | pdfplumber | Built on pdfminer, better table extraction. Overkill for this use case -- we just need full text and metadata. |
| trafilatura | newspaper3k | newspaper3k is unmaintained. trafilatura is actively developed, better extraction quality, and more metadata fields. |
| trafilatura | readability-lxml | Only extracts body text, no metadata extraction. trafilatura includes metadata, date extraction, and better boilerplate removal. |

**Recommendation (Claude's Discretion -- PDF library):** Use **pypdf** because it is pure-Python (no C dependencies), works with `BytesIO` for in-memory processing, handles metadata extraction, and is sufficient for text-based PDFs. The no-OCR decision (user locked) means we do not need PyMuPDF's image handling capabilities.

### Installation

```bash
uv add trafilatura youtube-transcript-api pypdf
```

**Note on dependencies:**
- trafilatura pulls in several sub-dependencies (courlan, htmldate, justext, lxml). These are all standard and well-maintained.
- youtube-transcript-api depends on `defusedxml` and `requests`. The `requests` dependency is separate from `httpx` but lightweight.
- pypdf is pure-Python with no external dependencies.

## Architecture Patterns

### Recommended Project Structure

```
src/knowledge_hub/
├── extraction/
│   ├── __init__.py          # Re-export extract_content() public API
│   ├── router.py            # URL pattern matching → content type routing
│   ├── base.py              # ExtractionResult dataclass, shared types
│   ├── article.py           # trafilatura-based article extractor
│   ├── youtube.py           # youtube-transcript-api extractor
│   ├── pdf.py               # pypdf extractor (download + extract)
│   ├── timeout.py           # 30s timeout wrapper with asyncio.timeout()
│   └── paywall.py           # Paywalled domain list loading and checking
├── models/
│   └── content.py           # ExtractedContent model + ExtractionStatus enum (updated)
└── config/
    └── paywalled_domains.yaml  # Configurable paywall domain list
tests/
├── test_extraction/
│   ├── __init__.py
│   ├── test_router.py       # URL → content type routing tests
│   ├── test_article.py      # trafilatura extraction tests (mocked)
│   ├── test_youtube.py      # YouTube transcript tests (mocked)
│   ├── test_pdf.py          # PDF extraction tests (mocked)
│   ├── test_timeout.py      # Timeout behavior tests
│   └── test_paywall.py      # Paywall detection tests
```

### Pattern 1: Content Type Router (URL Pattern Matching)

**What:** Detect content type from URL using regex patterns, dispatch to the appropriate extractor.
**When to use:** Entry point for all extraction -- called once per URL.

```python
# src/knowledge_hub/extraction/router.py
import re
from urllib.parse import urlparse
from knowledge_hub.models.content import ContentType

# Patterns ordered by specificity
YOUTUBE_PATTERN = re.compile(
    r"(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/shorts/)"
)
PDF_PATTERN = re.compile(r"\.pdf(?:\?.*)?$", re.IGNORECASE)
SUBSTACK_PATTERN = re.compile(r"\.substack\.com/")
MEDIUM_PATTERN = re.compile(r"(?:medium\.com/|\.medium\.com/)")

def detect_content_type(url: str) -> ContentType:
    """Detect content type from URL patterns. Unknown URLs default to ARTICLE."""
    if YOUTUBE_PATTERN.search(url):
        return ContentType.VIDEO
    if PDF_PATTERN.search(url):
        return ContentType.PDF
    if SUBSTACK_PATTERN.search(url):
        return ContentType.NEWSLETTER
    if MEDIUM_PATTERN.search(url):
        return ContentType.ARTICLE  # Medium uses trafilatura like articles
    return ContentType.ARTICLE  # Default fallback
```

### Pattern 2: Sync-to-Async Wrapping with asyncio.to_thread()

**What:** Wrap synchronous library calls (trafilatura, youtube-transcript-api, pypdf) in `asyncio.to_thread()` so they do not block the FastAPI event loop.
**When to use:** Every extraction call. All three core libraries are synchronous.

```python
# src/knowledge_hub/extraction/article.py
import asyncio
from trafilatura import fetch_url, bare_extraction

async def extract_article(url: str) -> dict:
    """Extract article content via trafilatura (runs in thread pool)."""
    # Both fetch_url and bare_extraction are synchronous/blocking
    downloaded = await asyncio.to_thread(fetch_url, url)
    if downloaded is None:
        return None
    result = await asyncio.to_thread(bare_extraction, downloaded, url=url)
    return result
```

### Pattern 3: 30-Second Wall-Clock Timeout

**What:** Wrap the entire extraction pipeline (fetch + extract + retry) in a single 30-second timeout using `asyncio.timeout()`.
**When to use:** Top-level extraction entry point for every URL.

```python
# src/knowledge_hub/extraction/timeout.py
import asyncio
from knowledge_hub.models.content import ExtractedContent, ExtractionStatus

async def extract_with_timeout(url: str, timeout_seconds: float = 30.0) -> ExtractedContent:
    """Run extraction with a wall-clock timeout. Returns partial result on timeout."""
    try:
        async with asyncio.timeout(timeout_seconds):
            return await _extract_pipeline(url)
    except TimeoutError:
        return ExtractedContent(
            url=url,
            content_type=detect_content_type(url),
            extraction_status=ExtractionStatus.FAILED,
            extraction_method="timeout",
        )
```

### Pattern 4: YouTube Transcript Extraction with Fallback

**What:** Fetch YouTube transcript, catch specific exceptions to determine fallback behavior.
**When to use:** For all YouTube URLs.

```python
# src/knowledge_hub/extraction/youtube.py
import asyncio
import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

VIDEO_ID_PATTERN = re.compile(
    r"(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})"
)

def extract_video_id(url: str) -> str | None:
    """Extract the 11-character video ID from a YouTube URL."""
    match = VIDEO_ID_PATTERN.search(url)
    return match.group(1) if match else None

async def extract_youtube(url: str) -> dict:
    """Extract YouTube transcript and metadata."""
    video_id = extract_video_id(url)
    if not video_id:
        return {"error": "invalid_video_id", "url": url}

    ytt_api = YouTubeTranscriptApi()
    try:
        # Sync call wrapped in to_thread
        transcript = await asyncio.to_thread(
            ytt_api.fetch, video_id, languages=["en"]
        )
        text = " ".join(snippet.text for snippet in transcript)
        return {
            "transcript": text,
            "language": transcript.language,
            "is_generated": transcript.is_generated,
            "video_id": video_id,
        }
    except (TranscriptsDisabled, NoTranscriptFound):
        # Fallback: metadata-only (EXTRACT-07)
        return {"transcript": None, "video_id": video_id, "fallback": True}
    except VideoUnavailable:
        return {"error": "video_unavailable", "video_id": video_id}
```

### Pattern 5: PDF Download + Extract with Size Cap

**What:** Download PDF via httpx, check size, extract text via pypdf.
**When to use:** For URLs ending in `.pdf`.

```python
# src/knowledge_hub/extraction/pdf.py
import asyncio
from io import BytesIO
import httpx
from pypdf import PdfReader

MAX_PDF_SIZE = 20 * 1024 * 1024  # 20MB

async def extract_pdf(url: str) -> dict:
    """Download and extract text from a PDF URL."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(25.0)) as client:
        # Check Content-Length first (HEAD request)
        head_resp = await client.head(url, follow_redirects=True)
        content_length = int(head_resp.headers.get("content-length", 0))
        if content_length > MAX_PDF_SIZE:
            return {"error": "pdf_too_large", "size": content_length}

        # Download PDF
        response = await client.get(url, follow_redirects=True)
        if len(response.content) > MAX_PDF_SIZE:
            return {"error": "pdf_too_large", "size": len(response.content)}

    # pypdf is synchronous -- run in thread
    reader = await asyncio.to_thread(PdfReader, BytesIO(response.content))
    text = ""
    for page in reader.pages:
        page_text = await asyncio.to_thread(page.extract_text)
        if page_text:
            text += page_text + "\n"

    # Extract metadata
    meta = reader.metadata
    return {
        "text": text.strip() if text.strip() else None,
        "title": meta.title if meta else None,
        "author": meta.author if meta else None,
    }
```

### Pattern 6: ExtractionStatus Enum (Model Update)

**What:** Replace `is_partial: bool` with a status enum to capture all extraction outcomes.
**When to use:** This is a model change from Phase 1. The existing `ExtractedContent.is_partial` field must be replaced.

```python
# src/knowledge_hub/models/content.py (updated)
from enum import Enum

class ExtractionStatus(str, Enum):
    """Extraction outcome status."""
    FULL = "full"
    PARTIAL = "partial"
    METADATA_ONLY = "metadata_only"
    FAILED = "failed"

class ExtractedContent(BaseModel):
    # ... existing fields ...
    extraction_status: ExtractionStatus = ExtractionStatus.FULL  # Replaces is_partial
    # Remove: is_partial: bool = False
```

### Anti-Patterns to Avoid

- **Calling trafilatura/youtube-transcript-api directly without `asyncio.to_thread()`:** These are synchronous libraries that do network I/O. Calling them in an async function without `to_thread()` blocks the entire FastAPI event loop.
- **Per-step timeouts instead of wall-clock timeout:** The user locked "30-second hard cap on total wall-clock time per URL." Do NOT set separate 10s timeouts on fetch + 10s on extract + 10s on retry. Use a single `asyncio.timeout(30)` wrapping the entire pipeline.
- **Using `trafilatura.extract()` instead of `bare_extraction()`:** `extract()` returns formatted text (string). `bare_extraction()` returns a Document object with structured metadata fields. We need both text AND metadata.
- **Using deprecated static methods on YouTubeTranscriptApi:** `get_transcript()`, `get_transcripts()`, and `list_transcripts()` were **removed** in v1.1.0. Always use instance methods: `ytt_api = YouTubeTranscriptApi()` then `ytt_api.fetch()`.
- **Downloading entire PDF before checking size:** Check `Content-Length` header first with a HEAD request. If the header is unavailable, stream and abort when exceeding 20MB.
- **Hardcoding paywalled domain list:** User decision requires config file. Keep it in YAML or a simple text file for easy updates.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Article text extraction | Custom HTML parsing with BeautifulSoup | trafilatura `bare_extraction()` | Boilerplate removal is a research-grade problem. trafilatura handles nav, ads, sidebars, comments. Years of refinement. |
| YouTube transcript retrieval | YouTube Data API v3 + caption download | youtube-transcript-api `fetch()` | YouTube transcript format is complex (timed text XML). The library handles all the innertube API negotiation, language fallback, auto-generated subtitle detection. |
| PDF text extraction | Manual PDF binary parsing | pypdf `PdfReader` | PDF is a notoriously complex format. Even "simple" text extraction has edge cases (encodings, font mappings, layout). |
| HTML metadata extraction | Custom meta tag parsing | trafilatura `bare_extraction()` / Document object | trafilatura already extracts title, author, date, sitename from meta tags, OpenGraph, JSON-LD, and HTML elements. |
| Date extraction from HTML | Custom regex date parsing | trafilatura (uses htmldate internally) | Date formats on the web are wildly inconsistent. htmldate handles dozens of formats. |

**Key insight:** Content extraction is the domain where "it works on my test URLs" is the most dangerous signal. Real-world URLs have infinite edge cases (malformed HTML, JavaScript-rendered content, CDN redirects, cookie walls). Use battle-tested libraries.

## Common Pitfalls

### Pitfall 1: youtube-transcript-api v1 API Breaking Changes
**What goes wrong:** `AttributeError: type object 'YouTubeTranscriptApi' has no attribute 'get_transcript'`
**Why it happens:** v1.1.0 (2025) removed deprecated static methods `get_transcript()`, `get_transcripts()`, `list_transcripts()`. Many tutorials and Stack Overflow answers still show the old API.
**How to avoid:** Always use instance methods: `ytt_api = YouTubeTranscriptApi()` then `ytt_api.fetch(video_id)`. Never use `YouTubeTranscriptApi.get_transcript()`.
**Warning signs:** Copying code from tutorials dated before 2025.

### Pitfall 2: Blocking the Event Loop with Sync Libraries
**What goes wrong:** FastAPI stops responding to health checks and new requests during extraction. Under load, Slack retries pile up.
**Why it happens:** trafilatura, youtube-transcript-api, and pypdf are all synchronous. Calling them in an `async def` function without `to_thread()` blocks the event loop.
**How to avoid:** Every call to `fetch_url()`, `bare_extraction()`, `ytt_api.fetch()`, `PdfReader()`, and `page.extract_text()` must be wrapped in `await asyncio.to_thread(...)`.
**Warning signs:** Health endpoint becomes slow or unresponsive during content extraction.

### Pitfall 3: trafilatura `bare_extraction()` Returns None
**What goes wrong:** `bare_extraction()` returns `None` instead of a Document, and code crashes with `AttributeError`.
**Why it happens:** If trafilatura cannot extract any content (empty page, JavaScript-only rendering, connection failure), it returns `None`.
**How to avoid:** Always check for `None` before accessing Document fields. This maps to `metadata_only` or `failed` extraction status.
**Warning signs:** `NoneType` errors in production logs.

### Pitfall 4: YouTube Video ID Extraction Misses Edge Cases
**What goes wrong:** Extraction fails for valid YouTube URLs because the video ID regex doesn't match.
**Why it happens:** YouTube has many URL formats: `youtube.com/watch?v=ID`, `youtu.be/ID`, `youtube.com/shorts/ID`, `youtube.com/embed/ID`, URLs with additional query params (`&t=123`, `&list=PLxxx`).
**How to avoid:** Use a comprehensive regex that captures the 11-character ID from all known formats. Test with edge cases including URLs with timestamps, playlist params, and mobile URLs.
**Warning signs:** Valid YouTube links returning "invalid_video_id" error.

### Pitfall 5: PDF Content-Length Header Absent or Lies
**What goes wrong:** HEAD request returns no Content-Length, or Content-Length doesn't match actual body size. Large PDF downloads continue past 20MB cap.
**Why it happens:** Many CDNs strip Content-Length, use chunked transfer encoding, or serve different content for HEAD vs GET requests.
**How to avoid:** Use Content-Length as an optimization hint only. Always check `len(response.content)` after download as the authoritative size check. For streaming, track bytes received and abort when exceeding the cap.
**Warning signs:** Memory usage spikes when processing PDF URLs.

### Pitfall 6: Retry Logic Consuming the Timeout Budget
**What goes wrong:** First attempt takes 25 seconds, retry starts at 25s, and the 30s timeout fires during retry -- wasting the retry.
**Why it happens:** Retry logic doesn't consider remaining time budget.
**How to avoid:** Check remaining time before retrying. If less than ~5 seconds remain, skip retry and return whatever partial result exists. The `asyncio.timeout()` context manager handles cancellation, but the retry logic should be aware of the budget to avoid starting a doomed retry.
**Warning signs:** Retries that always time out.

## Code Examples

### Complete Article Extraction with trafilatura

```python
# Source: trafilatura 2.0.0 docs + Context7 /adbar/trafilatura
import asyncio
from trafilatura import fetch_url, bare_extraction

async def extract_article_content(url: str) -> dict | None:
    """Extract article text and metadata. Returns None on failure."""
    downloaded = await asyncio.to_thread(fetch_url, url)
    if downloaded is None:
        return None

    doc = await asyncio.to_thread(bare_extraction, downloaded, url=url)
    if doc is None:
        return None

    return {
        "text": doc.text,
        "title": doc.title,
        "author": doc.author,
        "date": doc.date,
        "sitename": doc.sitename,
        "description": doc.description,
        "hostname": doc.hostname,
    }
```

**Document fields available (verified, HIGH confidence):**
- `text` -- main extracted body text
- `title` -- page title
- `author` -- author name(s)
- `date` -- publication date (string)
- `sitename` -- site/publisher name
- `description` -- meta description
- `hostname` -- domain extracted from URL
- `categories` -- topic categories
- `tags` -- keywords/tags
- `image` -- featured image URL
- `pagetype` -- og:type value
- `license` -- copyright/license info
- `language` -- detected language
- `comments` -- extracted comments (if `include_comments=True`)

### Complete YouTube Extraction

```python
# Source: youtube-transcript-api 1.2.4 docs + Context7 /jdepoix/youtube-transcript-api
import asyncio
import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    InvalidVideoId,
)

VIDEO_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?.*v=|shorts/|embed/)|youtu\.be/)([a-zA-Z0-9_-]{11})"
)

async def extract_youtube_content(url: str) -> dict:
    """Extract YouTube transcript and metadata."""
    match = VIDEO_ID_RE.search(url)
    if not match:
        return {"extraction_status": "failed", "error": "invalid_video_id"}

    video_id = match.group(1)
    ytt_api = YouTubeTranscriptApi()

    try:
        transcript = await asyncio.to_thread(
            ytt_api.fetch, video_id, languages=["en"]
        )
        full_text = " ".join(snippet.text for snippet in transcript)
        return {
            "extraction_status": "full",
            "transcript": full_text,
            "language": transcript.language,
            "is_generated": transcript.is_generated,
            "video_id": video_id,
        }
    except (TranscriptsDisabled, NoTranscriptFound):
        return {
            "extraction_status": "metadata_only",
            "transcript": None,
            "video_id": video_id,
        }
    except VideoUnavailable:
        return {"extraction_status": "failed", "error": "video_unavailable"}
    except InvalidVideoId:
        return {"extraction_status": "failed", "error": "invalid_video_id"}
```

### Complete PDF Extraction

```python
# Source: pypdf 6.7.1 docs + Context7 /py-pdf/pypdf
import asyncio
from io import BytesIO
import httpx
from pypdf import PdfReader

MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024  # 20MB

async def extract_pdf_content(url: str) -> dict:
    """Download PDF and extract text + metadata."""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(25.0), follow_redirects=True
    ) as client:
        # Optimization: check Content-Length header first
        try:
            head = await client.head(url)
            content_length = int(head.headers.get("content-length", "0"))
            if content_length > MAX_PDF_SIZE_BYTES:
                return {"extraction_status": "metadata_only", "error": "pdf_too_large"}
        except (httpx.HTTPError, ValueError):
            pass  # HEAD failed or no Content-Length -- proceed with GET

        response = await client.get(url)
        response.raise_for_status()

    if len(response.content) > MAX_PDF_SIZE_BYTES:
        return {"extraction_status": "metadata_only", "error": "pdf_too_large"}

    # pypdf is synchronous
    reader = await asyncio.to_thread(PdfReader, BytesIO(response.content))

    pages_text = []
    for page in reader.pages:
        page_text = await asyncio.to_thread(page.extract_text)
        if page_text:
            pages_text.append(page_text)
    text = "\n".join(pages_text).strip()

    meta = reader.metadata
    return {
        "extraction_status": "full" if text else "metadata_only",
        "text": text or None,
        "title": meta.title if meta else None,
        "author": meta.author if meta else None,
    }
```

### Paywalled Domain Config

```yaml
# src/knowledge_hub/config/paywalled_domains.yaml
# Known paywalled domains. Extraction still attempted but result flagged as partial.
domains:
  # Major newspapers
  - nytimes.com
  - washingtonpost.com
  - wsj.com
  - ft.com
  - economist.com
  - thetimes.co.uk
  - bloomberg.com
  - theathletic.com
  # Tech/business
  - hbr.org
  - businessinsider.com
  - seekingalpha.com
  - informationweek.com
  # Platform paywalls (member-only content)
  - medium.com  # Some articles are member-only
```

### Retry Pattern Within Timeout Budget

```python
import asyncio
import time

async def extract_with_retry(url: str, deadline: float) -> dict:
    """Extract content with one retry on transient failures, respecting deadline."""
    last_error = None
    for attempt in range(2):  # max 2 attempts (1 original + 1 retry)
        remaining = deadline - time.monotonic()
        if remaining < 3.0 and attempt > 0:
            break  # Not enough time for a meaningful retry
        try:
            return await _do_extract(url)
        except TransientError as e:
            last_error = e
            if attempt == 0:
                await asyncio.sleep(min(1.0, remaining / 2))
    return _make_failed_result(url, str(last_error))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `YouTubeTranscriptApi.get_transcript()` (static) | `ytt_api = YouTubeTranscriptApi(); ytt_api.fetch()` (instance) | v1.1.0 (2025) | Static methods REMOVED. Must use instance methods. |
| youtube-transcript-api scraping /watch HTML | Innertube API for caption retrieval | v1.1.0 (2025) | More reliable, but new `PoTokenRequired` exception possible. |
| trafilatura `extract()` returns string | `bare_extraction()` returns Document object | trafilatura 2.0.0 | Document has `.as_dict()`, structured field access. More useful than string output. |
| PyPDF2 | pypdf (renamed) | 2023 | PyPDF2 is deprecated. pypdf is the successor. Same maintainer. |
| `asyncio.wait_for()` for timeouts | `asyncio.timeout()` context manager | Python 3.11 | Context manager is cleaner, recommended for new code. |

**Deprecated/outdated:**
- `YouTubeTranscriptApi.get_transcript()` -- removed in v1.1.0, use instance `.fetch()` method
- `YouTubeTranscriptApi.get_transcripts()` -- removed in v1.1.0
- `YouTubeTranscriptApi.list_transcripts()` -- removed in v1.1.0
- PyPDF2 -- renamed to pypdf, PyPDF2 is unmaintained
- newspaper3k -- unmaintained since 2020, replaced by trafilatura

## Open Questions

1. **trafilatura fetch_url timeout behavior**
   - What we know: trafilatura uses urllib internally for fetching. It has some internal timeout handling.
   - What's unclear: Whether `fetch_url()` respects a custom timeout parameter, or if the 30s wall-clock timeout via `asyncio.timeout()` is the only way to enforce it. The `asyncio.timeout()` cancels the thread, but thread cancellation is cooperative in Python -- the thread may not stop immediately.
   - Recommendation: Rely on `asyncio.timeout(30)` as the wall-clock guard. trafilatura's internal fetch should complete in reasonable time for most URLs. If a URL causes trafilatura to hang, the timeout will catch it and return a failed result. **LOW confidence** on exact thread cancellation behavior -- test during implementation.

2. **Platform-specific metadata for Substack/Medium**
   - What we know: User wants enhanced metadata (newsletter name, author bio, series info) for these platforms.
   - What's unclear: Exactly what extra metadata Substack/Medium expose that trafilatura doesn't already capture.
   - Recommendation: trafilatura already extracts `sitename` (which will be the newsletter name for Substack). Start with trafilatura's default metadata and only add platform-specific parsing if gaps are found during testing. **MEDIUM confidence** -- trafilatura may already cover enough.

3. **youtube-transcript-api `PoTokenRequired` exception**
   - What we know: v1.1.0 added this exception for cases where YouTube's timedtext URLs require a PO token.
   - What's unclear: How common this is in practice, and whether it's a permanent block or transient.
   - Recommendation: Catch it alongside `TranscriptsDisabled`/`NoTranscriptFound` and treat as metadata-only fallback. **LOW confidence** -- depends on YouTube's server-side behavior.

4. **`asyncio.to_thread()` cancellation on timeout**
   - What we know: `asyncio.timeout()` cancels the awaitable. `asyncio.to_thread()` runs in a thread pool.
   - What's unclear: Whether cancelling a `to_thread()` awaitable actually stops the thread, or if the thread continues running in the background (just orphaned).
   - Recommendation: In practice, the thread will continue until the sync call returns, but the caller gets the timeout error immediately and can return a failed result. For trafilatura (which does HTTP I/O), the thread will eventually finish when the HTTP request completes or times out internally. This is acceptable -- we just need the caller to respond within 30s. **MEDIUM confidence** -- standard Python behavior but worth noting.

## Sources

### Primary (HIGH confidence)
- Context7 `/adbar/trafilatura` -- bare_extraction usage, metadata fields, fetch_url patterns
- Context7 `/jdepoix/youtube-transcript-api` -- fetch() API, exception types, language fallback, transcript metadata
- Context7 `/py-pdf/pypdf` -- PdfReader text extraction, metadata reading, BytesIO support
- [trafilatura PyPI](https://pypi.org/project/trafilatura/) -- version 2.0.0 confirmed
- [youtube-transcript-api PyPI](https://pypi.org/project/youtube-transcript-api/) -- version 1.2.4 confirmed
- [pypdf PyPI](https://pypi.org/project/pypdf/) -- version 6.7.1 confirmed
- [trafilatura 2.0.0 docs](https://trafilatura.readthedocs.io/en/latest/) -- core functions, Python usage, Document class
- [trafilatura metadata source](https://github.com/adbar/trafilatura/blob/master/trafilatura/metadata.py) -- Document class fields enumeration

### Secondary (MEDIUM confidence)
- [youtube-transcript-api GitHub releases](https://github.com/jdepoix/youtube-transcript-api/releases) -- v1.1.0 breaking changes (static method removal, innertube migration)
- [pypdf streaming data docs](https://pypdf.readthedocs.io/en/stable/user/streaming-data.html) -- BytesIO usage pattern
- [Python asyncio docs](https://docs.python.org/3/library/asyncio-task.html) -- `asyncio.timeout()`, `asyncio.to_thread()`
- [State of Digital Publishing](https://www.stateofdigitalpublishing.com/monetization/news-sites-with-paywalls/) -- paywalled domain reference list

### Tertiary (LOW confidence)
- Thread cancellation behavior with `asyncio.to_thread()` -- based on general Python threading knowledge, not verified with trafilatura specifically.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all three libraries verified via Context7 + PyPI with current versions
- Architecture: HIGH -- patterns follow established Python async conventions, verified with official docs
- Pitfalls: HIGH -- youtube-transcript-api breaking changes verified via GitHub releases; event loop blocking is well-documented
- Model changes: HIGH -- ExtractionStatus enum directly maps to user's locked decision
- Thread cancellation: MEDIUM -- standard Python behavior but edge cases possible

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (30 days -- youtube-transcript-api may need monitoring due to YouTube API changes)
