# Pitfalls Research

**Domain:** Slack-to-LLM-to-Notion knowledge base automation pipeline
**Researched:** 2026-02-19
**Confidence:** HIGH (most pitfalls derived from well-documented API behaviors and common failure modes in this exact stack)

## Critical Pitfalls

### Pitfall 1: Slack Events API Sends Retries That Cause Duplicate Processing

**What goes wrong:**
Slack retries event deliveries if it does not receive a 200 response within 3 seconds. It retries up to 3 times with the same `event_id`. If your FastAPI handler takes longer than 3 seconds to respond (including any synchronous work before returning), Slack sends the same event again. Without deduplication, the pipeline processes the same link 2-4 times, creating duplicate Notion pages.

This is the single most common bug in Slack webhook integrations. The PRD correctly identifies the need to ACK within 3 seconds and process asynchronously, but the implementation details matter enormously.

**Why it happens:**
Developers either (a) accidentally do synchronous work before returning the response (e.g., validating the Slack signature, parsing the message, or even just importing heavy modules on cold start), or (b) they return 200 but don't track which `event_id`s have already been received, so retries still trigger duplicate processing.

**How to avoid:**
1. Return HTTP 200 immediately in the FastAPI endpoint -- before any processing. Use `BackgroundTasks` or `asyncio.create_task()` to process after response.
2. Check the `X-Slack-Retry-Num` header and return 200 immediately for any retry (value > 0). This is the simplest dedup strategy.
3. For belt-and-suspenders, also deduplicate on `event_id` from the event payload. Store seen event IDs in memory (a set with TTL, or a simple dict that prunes entries older than 5 minutes). At single-user scale, an in-memory set is sufficient -- no need for Redis.
4. Verify the Slack request signature (`X-Slack-Signature`) but do it synchronously before ACKing -- this is fast (HMAC computation) and prevents processing forged events.

**Warning signs:**
- Duplicate Notion pages appearing for the same URL
- Cloud Run logs showing multiple invocations for the same Slack message timestamp
- `X-Slack-Retry-Num` headers appearing in request logs

**Phase to address:**
Phase 1 (MVP). This must be correct from the first deployed version or you will create garbage data immediately.

---

### Pitfall 2: Cloud Run Cold Starts Exceeding Slack's 3-Second ACK Window

**What goes wrong:**
Cloud Run scales to zero. When a new request arrives after inactivity, it must pull the container image, start the container, and run the application startup. For a Python/FastAPI app with heavy dependencies (trafilatura pulls in lxml, etc.), cold starts can be 5-15 seconds. During this time, Slack has already timed out and is preparing retries.

Even if you correctly ACK before processing, you cannot ACK at all if the container hasn't started. The 3-second clock starts when Slack sends the HTTP request.

**Why it happens:**
Developers test with warm containers (locally or with `min-instances=1`) and never experience cold starts during development. The problem only surfaces in production after periods of inactivity.

**How to avoid:**
1. Set `--min-instances=1` on the Cloud Run service. At single-user volume, this costs approximately $0-2/month (depending on CPU allocation). This completely eliminates cold starts. Given the <$5/month budget, this is the right tradeoff.
2. If cost-sensitive: use a Cloud Scheduler job to ping the service every 5-10 minutes to keep it warm. This is a hack but effective.
3. Minimize container image size: use `python:3.12-slim` base, multi-stage builds, and avoid unnecessary dependencies. Aim for <200MB image.
4. Use lazy imports for heavy libraries (trafilatura, google.generativeai) -- import them inside the handler function, not at module level. This reduces startup time but adds per-request latency on the first call.
5. Set `--cpu-boost` flag on Cloud Run for faster cold starts (allocates more CPU during startup).

**Warning signs:**
- Slack retries appearing in logs after periods of inactivity (evenings, weekends)
- Cloud Run metrics showing cold start latency > 3 seconds
- Intermittent "duplicate processing" bugs that only happen after quiet periods

**Phase to address:**
Phase 1 (MVP). Configure `--min-instances=1` from the start. The cost is negligible and the reliability gain is enormous.

---

### Pitfall 3: Slack URL Unfurling Format Breaks URL Extraction

**What goes wrong:**
When a user pastes a URL in Slack, Slack wraps it in angle brackets and may add a display label: `<https://example.com|example.com>`. Some URLs also get auto-linked. If you parse the message text looking for URLs with a naive regex (e.g., `https?://\S+`), you will capture the angle brackets and pipe-separated display text as part of the URL, resulting in broken URLs that fail content extraction.

Additionally, Slack's `blocks` payload structure differs from the `text` field. The `text` field has the `<url|label>` format, while `blocks[].elements[].elements[]` of type `link` has a clean `url` field. Using the wrong field leads to mangled URLs.

**Why it happens:**
Developers test by manually constructing payloads without Slack's URL formatting. They don't realize the production event payload wraps URLs differently than plain text.

**How to avoid:**
1. Parse URLs from the `blocks` structure (specifically `rich_text` blocks with `link` type elements) rather than regex on the `text` field. The `blocks` structure provides clean URLs.
2. If using the `text` field, apply a Slack-specific URL regex: `<(https?://[^|>]+)(?:\|[^>]+)?>` to extract just the URL portion.
3. Write a test case with actual Slack event payloads (capture one from the Slack API debugger) that includes unfurled URLs.

**Warning signs:**
- Content extraction failing with "invalid URL" errors
- URLs in logs containing `|` characters or angle brackets
- Working locally but failing with real Slack messages

**Phase to address:**
Phase 1 (MVP). URL extraction is the first step of the pipeline. Get this wrong and nothing downstream works.

---

### Pitfall 4: trafilatura Returns Empty Content for JavaScript-Rendered Pages

**What goes wrong:**
trafilatura is an excellent article extractor for server-rendered HTML. However, many modern sites (Medium with its paywall interstitial, some Substack pages, SPAs) render content via JavaScript. trafilatura fetches raw HTML and parses it -- it does not execute JavaScript. For JS-rendered sites, it returns empty or minimal content (just the `<noscript>` fallback or page chrome).

The pipeline then sends near-empty content to Gemini, which either hallucinates a summary from the title alone or returns a low-quality "unable to extract meaningful content" response. Either way, the Notion entry is garbage but looks legitimate.

**Why it happens:**
Developers test with a handful of well-structured blogs and news sites that server-render. They don't test the long tail of sites (LinkedIn posts, Twitter/X threads, some newsletters, dynamically loaded content).

**How to avoid:**
1. After trafilatura extraction, check content length. If extracted text is < 100 characters but the page loaded successfully (HTTP 200), flag as "partial extraction" in the Notion entry.
2. Set trafilatura's `favor_recall=True` parameter to be more aggressive about content extraction.
3. For known JS-heavy domains (medium.com, linkedin.com, x.com/twitter.com), consider fallback extraction strategies or flag for manual review.
4. Include the extraction quality in the Slack confirmation: "Extracted 2,450 words" vs "Extracted 42 words (partial)". This makes extraction failures visible immediately.
5. Do NOT add a headless browser (Playwright/Selenium) in Phase 1 -- it massively increases container size (500MB+), cold start time, and complexity. Instead, flag partial extractions and accept that some content types need manual handling.

**Warning signs:**
- Notion entries with very short summaries that seem generic
- Content extraction returning < 200 characters for sites you know have full articles
- LLM output that restates the page title rather than summarizing content

**Phase to address:**
Phase 1 (MVP) for detection/flagging. Phase 2 for domain-specific fallback strategies. Never add headless browser rendering -- it violates the simplicity and cost constraints.

---

### Pitfall 5: youtube-transcript-api Breaks Silently When YouTube Changes

**What goes wrong:**
`youtube-transcript-api` is an unofficial library that scrapes YouTube's internal API to fetch transcripts. YouTube does not provide a stable public API for transcripts. YouTube periodically changes its internal endpoints, anti-bot measures, or page structure, breaking the library. When this happens, transcript extraction fails for all videos until the library maintainer pushes an update.

The failure mode is often not an immediate exception but rather returning an empty transcript, a transcript in the wrong language, or raising an obscure error about "no transcripts available" for videos that clearly have captions.

**Why it happens:**
YouTube intentionally does not provide a stable transcript API. All transcript extraction libraries are reverse-engineered and inherently fragile. The library works perfectly for months and then suddenly breaks.

**How to avoid:**
1. Pin `youtube-transcript-api` version but monitor for updates (set up a GitHub watch on the repo for releases).
2. Implement a fallback: if transcript extraction fails, extract metadata only (title, description, channel name) using trafilatura on the YouTube page itself. Create the Notion entry with metadata only and flag as "transcript unavailable."
3. Add a circuit breaker: if 3+ consecutive YouTube extractions fail, log an alert and skip transcript extraction for subsequent requests until manually reset. This prevents wasting processing time on a known-broken dependency.
4. Consider `yt-dlp` as a backup transcript extractor -- it has a different extraction path and may survive YouTube changes that break `youtube-transcript-api`.
5. Wrap transcript extraction in a try/except with a specific timeout (15 seconds). Do not let a hanging YouTube request block the entire pipeline.

**Warning signs:**
- Sudden spike in YouTube processing failures
- GitHub issues on `youtube-transcript-api` repo reporting extraction failures
- Transcripts returning empty or in unexpected languages

**Phase to address:**
Phase 1 (MVP) for basic error handling and metadata fallback. Phase 2 for circuit breaker pattern and yt-dlp fallback.

---

### Pitfall 6: Gemini Structured Output Returns Invalid or Schema-Violating JSON

**What goes wrong:**
Even with Gemini's JSON mode / structured output, the LLM occasionally returns JSON that violates the expected schema. Common violations: `tags` as a comma-separated string instead of an array, `quality_score` as a string "7" instead of integer 7, `null` for required fields, extra fields not in the schema, or nested objects where flat values are expected. If the pipeline blindly passes LLM output to the Notion API without validation, the Notion create-page call fails silently or creates malformed entries.

Additionally, Gemini Flash (as a smaller model) is more prone to schema violations than Gemini Pro, especially with complex prompts or unusual content.

**Why it happens:**
Developers test with a few sample inputs and the LLM happens to produce valid output. They don't test edge cases: very short content, non-English content, heavily formatted content, or content that confuses the LLM's understanding of the task.

**How to avoid:**
1. Use Pydantic models to define the expected LLM output schema. Validate every LLM response against the Pydantic model before creating Notion pages. This is the single most impactful defensive measure.
2. Use Gemini's `response_schema` parameter (not just the prompt instruction) to enforce JSON structure at the API level. Pass the actual JSON schema to the API call.
3. Implement field-level defaults: if `tags` is missing, default to `["Uncategorized"]`. If `quality_score` is missing, default to 5.
4. Add type coercion: if `quality_score` comes back as string "7", coerce to int. If `tags` comes back as a string, split on commas.
5. Log every schema validation failure with the raw LLM output for prompt tuning.
6. Retry once on schema validation failure with a simpler "fix this JSON" prompt (or just with temperature=0).

**Warning signs:**
- Notion API errors mentioning "invalid property value"
- Notion entries with missing tags, no summary, or "None" as title
- Pydantic `ValidationError` exceptions in logs

**Phase to address:**
Phase 1 (MVP). Pydantic validation should be built from day one. Schema violations are not edge cases -- they are guaranteed to happen at volume.

---

### Pitfall 7: Notion multi_select Properties Reject Unknown Tag Values

**What goes wrong:**
When creating a Notion page, if you specify a `multi_select` tag value that doesn't exist as an option in the database schema, the Notion API returns a 400 error: "Could not find option with name: [tag]". The LLM will generate new, contextually appropriate tags (e.g., "SKAN 5.0", "iOS Attribution") that don't exist in the predefined tag list. Without handling this, every entry with a novel tag fails to create.

This is explicitly called out in the project memory as a known issue.

**Why it happens:**
The Notion API documentation mentions that multi_select options can be "created by the API" but this only works if you set the property value with a `name` field and the integration has the right permissions. In practice, the behavior is inconsistent -- sometimes new options auto-create, sometimes they fail. The reliable path is to explicitly add new options to the database schema before using them.

**How to avoid:**
1. Before creating a page, query the database schema to get existing multi_select options for Tags.
2. For any LLM-generated tag that doesn't exist in the current options, use the Notion `update database` API to add the new option first.
3. Alternatively, maintain a "safe tags" set in your application config. Map LLM tags to the closest safe tag. Allow the set to grow over time with manual additions.
4. Implement a tag normalization step: lowercase, trim whitespace, deduplicate. The LLM may generate "AI" and "ai" and "Artificial Intelligence" as separate tags.

**Warning signs:**
- Notion API 400 errors mentioning multi_select options
- All entries having the same generic tags because novel ones keep failing
- Tags property being empty on Notion entries despite LLM generating them

**Phase to address:**
Phase 1 (MVP). The tag creation flow must be part of the Notion integration from the start. This was already learned in the existing `/kb` project.

---

### Pitfall 8: Background Task Exceptions Are Silently Swallowed

**What goes wrong:**
FastAPI's `BackgroundTasks` (and `asyncio.create_task()`) do not propagate exceptions to the HTTP response -- the response has already been sent. If the background processing task raises an unhandled exception (content extraction timeout, LLM API error, Notion API failure), it fails silently. No Slack error reply is sent, no log entry is written (unless you explicitly catch and log), and the user never knows their link wasn't processed.

The user pastes a link, sees no confirmation in Slack, and assumes it's "processing." Hours later they check Notion and the entry doesn't exist.

**Why it happens:**
Developers test the happy path and see the confirmation. They don't test failure scenarios in background tasks because the HTTP endpoint always returns 200 (as designed for Slack ACK), masking downstream failures.

**How to avoid:**
1. Wrap the entire background processing function in a top-level try/except that catches `Exception`.
2. In the except handler: (a) send a Slack thread reply with the error message, (b) log the full exception with traceback to Cloud Run structured logging.
3. Never let a background task exit without either a success confirmation or an error notification in Slack.
4. Use `asyncio.create_task()` with a `done_callback` that checks for exceptions, rather than fire-and-forget.
5. Add a simple "processing started" reaction or reply in Slack immediately (before background processing), so the user knows the event was received even if processing later fails.

**Warning signs:**
- Links shared in Slack with no Slack reply at all (no success, no error)
- Cloud Run logs showing unhandled exceptions in background tasks
- "Missing" Notion entries for links the user definitely shared

**Phase to address:**
Phase 1 (MVP). The error handling wrapper is trivial to implement and catastrophic to skip.

---

### Pitfall 9: Slack Request Signature Verification Fails Due to Timestamp Drift

**What goes wrong:**
Slack request signature verification requires checking the `X-Slack-Request-Timestamp` header to prevent replay attacks. The standard implementation rejects requests where the timestamp is more than 5 minutes old. If the Cloud Run server clock drifts, or if retries arrive after a cold start delay, legitimate requests get rejected. The verification also requires the raw request body bytes (not parsed JSON) to compute the signature correctly. FastAPI middleware that parses the body first corrupts the signature verification.

**Why it happens:**
Developers use a middleware or dependency that reads `request.body()` for signature verification, but another middleware or the route handler also reads the body. In ASGI (FastAPI), reading the body is a one-shot operation -- the second read returns empty bytes, causing signature mismatch.

**How to avoid:**
1. Use the `slack-bolt` library for Python, which handles signature verification correctly out of the box, including body caching.
2. If implementing manually: cache the raw body bytes in a middleware using `request.state.raw_body`, then use that cached value for both signature verification and JSON parsing.
3. Set timestamp tolerance to 5 minutes (the Slack standard), not tighter.
4. Test signature verification with actual Slack payloads, not mocked ones.

**Warning signs:**
- All Slack events returning 401/403 after deployment
- Signature verification working locally but failing on Cloud Run
- Intermittent verification failures correlating with cold starts

**Phase to address:**
Phase 1 (MVP). Security must be correct from the start. Use `slack-bolt` to avoid implementing this incorrectly.

---

### Pitfall 10: Gemini 3 Flash Preview API Changes at GA

**What goes wrong:**
Gemini 3 Flash is in Preview. Google may change the API surface, model name/identifier, pricing, rate limits, or structured output behavior when it moves to GA. Preview models sometimes get deprecated with short notice (e.g., Gemini 1.5 Flash preview models were sunset). The pipeline hard-codes the model identifier and relies on specific response format behavior.

**Why it happens:**
Google explicitly warns that Preview APIs are subject to change. Developers build on Preview because it's available now and plan to "update later" -- but the update requires code changes, prompt re-tuning, and re-testing.

**How to avoid:**
1. Isolate all Gemini API calls behind a single module (`llm.py` or similar). Model name, API configuration, and response parsing should live in one place.
2. Store the model identifier as a configuration value (environment variable or config file), not hard-coded in the processing logic.
3. Pin the API version in the google-generativeai SDK configuration.
4. When Gemini 3 Flash goes to GA, allocate a dedicated session to update the model identifier, re-test with 10-20 diverse inputs, and tune prompts if output quality changed.
5. If the model is deprecated before GA, have a pre-identified fallback: Gemini 2.0 Flash is stable and well-priced, though less capable.

**Warning signs:**
- Google AI Studio announcements about model deprecation schedules
- API errors mentioning "model not found" or "model deprecated"
- Subtle output quality changes (shorter summaries, different JSON structure)

**Phase to address:**
Phase 1 (MVP) for module isolation. Ongoing monitoring throughout all phases.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| In-memory event dedup (no persistent store) | No Redis/DB dependency | Retries during container restarts cause duplicates | Single-user scale -- acceptable permanently. Container restarts are rare with min-instances=1 |
| No request queue (direct background task) | Simpler architecture | No retry for failed processing, no backpressure | Acceptable at <150 links/month. Add Cloud Tasks only if volume grows 10x |
| Hardcoded system prompt in Python code | Fast iteration | Can't tune prompts without redeploying | Acceptable in MVP. Move to config/env var in Phase 2 |
| No database for processing state | No infra to manage | Can't retry failed links, no processing history | Acceptable permanently at this scale. Notion IS the database |
| Single Gemini prompt for all content types | One prompt to maintain | Suboptimal quality for diverse content | Acceptable in Phase 1. Add content-type prompts in Phase 2 |
| No health check endpoint | One fewer endpoint | Can't distinguish "service down" from "processing failed" | Never acceptable. Add `/health` in Phase 1 -- it's 3 lines of code |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Slack Events API | Not handling the `url_verification` challenge event during initial setup | Check `event.type == "url_verification"` and return `{"challenge": event["challenge"]}` as the first handler |
| Slack Events API | Processing `message_changed` and `message_deleted` subtypes as new messages | Filter on `event.subtype` -- only process events with no subtype (new messages) or explicitly handle edits |
| Slack Events API | Not filtering bot messages, causing infinite loops (bot replies trigger more events) | Check `event.get("bot_id")` or `event.get("subtype") == "bot_message"` and skip |
| Notion API | Sending rich text content exceeding 2000 characters per block | Split long text into multiple rich_text blocks, each under 2000 chars. Notion silently truncates or errors |
| Notion API | Using `title` property type wrong -- it must be the page title, not a rich_text property | Exactly one property of type `title` per database. Map your page title to this property |
| Notion API | Not handling 429 rate limit responses | Implement exponential backoff. Notion allows 3 requests/second per integration. At single-user scale this is unlikely but bursts can trigger it |
| Gemini API | Not setting `safety_settings` to allow processing content about sensitive topics | Default safety settings may block legitimate content about violence, politics, etc. Set thresholds to `BLOCK_NONE` or `BLOCK_ONLY_HIGH` for a personal tool |
| Gemini API | Using `generate_content()` synchronously in an async handler | Use `generate_content_async()` with the async Gemini client. Synchronous calls block the event loop |
| Cloud Run | Not setting `--concurrency=1` for CPU-bound LLM processing | Default concurrency is 80. Multiple simultaneous requests compete for CPU on a single instance. Set to 1 or a low number for LLM workloads |
| trafilatura | Not setting `include_links=False` in extraction | Extracted text includes inline markdown links that inflate content length and confuse the LLM. Strip links unless you need them |
| Google Secret Manager | Accessing secrets on every request instead of caching at startup | Secret Manager API calls add 50-200ms latency. Read secrets once at application startup and cache in module-level variables |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous content extraction | Slow processing but works | Use `asyncio.to_thread()` for trafilatura (it's sync). Use async HTTP client for other fetches | Multiple links in one message processed sequentially -- 4 links = 2 min instead of 30 sec |
| No extraction timeout | Most sites respond fast | Set `httpx` timeout to 15s, trafilatura `config` with `download_timeout=15` | One slow/hanging site blocks the pipeline for the default timeout (300s) |
| Fetching full Notion DB for duplicate check | Works with 100 entries | Use Notion's `filter` parameter with `url.equals` to query only matching URLs | At 1000+ entries, fetching all pages exceeds Notion's pagination limits and takes 5+ seconds |
| Container image bloat (>500MB) | Slower cold starts | Multi-stage Docker build, slim base image, no dev dependencies in production | Cold start exceeds 10 seconds when image approaches 1GB |
| Logging full extracted content | Useful for debugging | Log content length and first 200 chars only. Full content in debug mode only | Cloud Logging costs increase; log entries hit size limits (256KB) |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Not verifying Slack request signatures | Anyone can POST fake events to the webhook URL, triggering LLM calls (cost) and creating spam Notion entries | Verify `X-Slack-Signature` on every request. Use `slack-bolt` which does this automatically |
| Storing API keys in environment variables in the Dockerfile or docker-compose.yml | Secrets baked into the container image, visible in Cloud Run console, logged in build history | Use Google Secret Manager. Mount secrets as env vars at runtime via Cloud Run's secret configuration |
| Passing extracted web content directly into LLM prompt without sanitization | Prompt injection -- a malicious page could include text like "Ignore previous instructions and..." | Clearly delimit extracted content in the prompt (e.g., wrap in XML tags). Instruct the LLM to treat content between delimiters as data, not instructions. This is already noted in the existing CLAUDE.md |
| Cloud Run service URL is publicly accessible | Anyone with the URL can hit the webhook | Verify Slack signatures (above). Optionally, use Cloud Run's IAM to restrict invocation to Slack's IP ranges (impractical) or rely solely on signature verification (practical and sufficient) |
| Logging full Slack event payloads including user tokens | If Slack sends workspace tokens in headers/payloads, they end up in Cloud Logging | Log only the fields you need: channel, timestamp, text. Never log full headers or raw payloads in production |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No processing status feedback | User waits, uncertain if link was received | Send an immediate "processing" reaction (e.g., hourglass emoji) on the Slack message, then replace with checkmark on success |
| Generic error messages in Slack ("Processing failed") | User can't tell if it's a transient error or a permanent one | Include error type: "Content extraction failed -- site may be paywalled" or "YouTube transcript unavailable" |
| Notion entries with empty/placeholder content | User trusts automation and doesn't verify | Always include a "confidence" indicator: full extraction vs partial vs metadata-only |
| No way to re-process a failed link | User must manually create the entry or wait for a fix | Support replying to the error message with "retry" to re-trigger processing (Phase 2+) |
| Tags that are too granular or inconsistent | Knowledge base becomes unsearchable | Maintain a core tag taxonomy (10-20 tags). Normalize LLM-generated tags to the closest match. Allow new tags but review monthly |
| Summary quality varies wildly by content type | User loses trust in the system | Tune prompts per content type. A YouTube video summary should mention what was demonstrated, not just topics discussed |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Slack webhook:** Works with test payloads but not tested with `url_verification` challenge -- verify Cloud Run handles the initial Slack app setup handshake
- [ ] **URL extraction:** Works with plain URLs but not with Slack's `<url|label>` format -- test with real Slack event payloads
- [ ] **Content extraction:** Works with 5 test articles but not tested with paywalled sites, 404 pages, redirects, or non-HTML content -- test with 20+ diverse URLs
- [ ] **Duplicate detection:** Notion query works but doesn't handle URL variations (http vs https, www vs non-www, trailing slashes) -- decide if URL normalization matters (it probably does for Phase 2)
- [ ] **LLM output:** Returns valid JSON for test inputs but no Pydantic validation -- add schema validation before Notion creation
- [ ] **Error handling:** Happy path sends Slack confirmation but background task exceptions are silently swallowed -- verify error Slack replies work for every failure mode
- [ ] **Docker image:** Builds and runs locally but image size not checked -- verify it's under 300MB for acceptable cold starts
- [ ] **Secrets:** Work in local development with `.env` but not configured in Secret Manager for Cloud Run -- test the full deployed secret injection path
- [ ] **Notion page content:** Properties are populated but page body content (Summary, Key Points sections) not tested for length limits -- Notion blocks have a 2000-char limit per rich text segment
- [ ] **Bot message filtering:** Pipeline processes new messages but doesn't filter its own Slack reply events -- verify bot messages are ignored to prevent infinite loops

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Duplicate Notion pages from retry handling | LOW | Query Notion DB for duplicates (same URL, created within 1 minute of each other). Manually archive duplicates. Add dedup logic to prevent recurrence |
| Corrupted Notion entries from schema violations | LOW | Query Notion for entries with empty/null critical fields. Delete and re-process the original Slack messages. Add Pydantic validation |
| youtube-transcript-api broken by YouTube changes | MEDIUM | Update the library (`pip install --upgrade youtube-transcript-api`). If no fix available, switch to `yt-dlp` subtitle extraction. Re-process failed YouTube links |
| Gemini model deprecated | MEDIUM | Update model identifier in config. Re-test with 10-20 diverse inputs. Tune prompts if quality changed. Redeploy |
| Silent processing failures (no error notification) | HIGH | No way to know which links were lost. Audit by comparing Slack channel messages against Notion entries. Re-process missing links. This is why error handling must be correct from Phase 1 |
| Prompt injection via extracted content | LOW | Review affected Notion entries. Content is in your personal Notion (no external exposure). Harden prompt delimiters |
| Cloud Run secret misconfiguration | LOW | Service fails to start entirely (visible in Cloud Run logs). Fix secret references in Cloud Run configuration. Redeploy |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Slack retry duplicate processing | Phase 1 (MVP) | Send same Slack message twice rapidly. Verify only one Notion entry created |
| Cloud Run cold start timeout | Phase 1 (MVP) | Deploy with `--min-instances=1`. Verify response time after 30 min inactivity |
| Slack URL unfurling format | Phase 1 (MVP) | Test with real Slack messages containing URLs. Verify extracted URLs are clean |
| trafilatura empty content | Phase 1 (MVP) | Test with 5+ JS-heavy sites. Verify partial extraction is flagged, not silently accepted |
| youtube-transcript-api fragility | Phase 1 (MVP) | Verify graceful fallback when transcript unavailable. Add try/except with metadata-only fallback |
| Gemini schema violations | Phase 1 (MVP) | Send 20 diverse inputs through the LLM. Verify all pass Pydantic validation or fail gracefully |
| Notion multi_select tag creation | Phase 1 (MVP) | Create entry with novel tags. Verify tags auto-created in database schema |
| Background task silent failures | Phase 1 (MVP) | Intentionally break content extraction. Verify Slack error reply is sent |
| Slack signature verification body read | Phase 1 (MVP) | Send request with valid and invalid signatures. Verify valid passes and invalid is rejected |
| Gemini Preview API changes | Phase 1 (isolation), Ongoing (monitoring) | Model name in config, not hardcoded. Monitor Google AI announcements |
| Bot message infinite loops | Phase 1 (MVP) | Verify pipeline's own Slack replies don't trigger re-processing |
| Notion 2000-char block limit | Phase 1 (MVP) | Process a long article (5000+ words). Verify Notion page body renders correctly |
| URL normalization for dedup | Phase 2 (Polish) | Test duplicate detection with http/https and www/non-www variants of same URL |
| Content-type-specific prompt quality | Phase 2 (Polish) | A/B test generic vs specific prompts across 10 articles and 10 videos. Compare quality |
| Tag taxonomy consistency | Phase 2 (Polish) | After 50+ entries, review tag distribution. Merge synonymous tags, add normalization |

## Sources

- Slack Events API documentation (api.slack.com/events-api) -- retry behavior, signature verification, URL verification challenge [HIGH confidence - stable, well-documented API]
- Notion API documentation (developers.notion.com) -- rate limits, multi_select behavior, rich text block limits [HIGH confidence - stable API]
- Google Cloud Run documentation -- cold starts, min-instances, concurrency settings [HIGH confidence - well-documented]
- youtube-transcript-api GitHub repository -- known fragility, dependency on YouTube internals [HIGH confidence - widely reported issue]
- google-generativeai Python SDK -- structured output, async usage, safety settings [MEDIUM confidence - Gemini 3 Flash specific behaviors from training data, may have changed]
- trafilatura documentation -- extraction parameters, JS rendering limitations [HIGH confidence - stable, mature library]
- Project memory (MEMORY.md) -- Notion multi_select tag issue, prompt injection concerns [HIGH confidence - firsthand project experience]
- FastAPI documentation -- BackgroundTasks behavior, ASGI body reading [HIGH confidence - well-documented framework]

---
*Pitfalls research for: Slack-to-LLM-to-Notion knowledge base automation pipeline*
*Researched: 2026-02-19*
