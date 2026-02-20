"""LLM processor: ExtractedContent -> NotionPage via Gemini.

Wires together the schema, client, and prompt modules into a complete pipeline.
Handles Gemini API calls with tenacity retry logic, validates responses via
Pydantic, and maps LLM output to domain models with post-processing rules.
"""

import logging
from datetime import datetime, timezone

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError
from pydantic import ValidationError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from knowledge_hub.llm.prompts import GEMINI_MODEL, build_system_prompt, build_user_content
from knowledge_hub.llm.schemas import LLMResponse
from knowledge_hub.models.content import ExtractedContent, ExtractionStatus
from knowledge_hub.models.knowledge import KnowledgeEntry, Priority, Status
from knowledge_hub.models.notion import KeyLearning, NotionPage

logger = logging.getLogger(__name__)


def _is_retryable(error: BaseException) -> bool:
    """Determine if a Gemini API error is transient and worth retrying.

    Returns True for server errors (5xx) and rate limits (429).
    Returns False for permanent client errors (400, 401, 403).
    """
    if isinstance(error, ServerError):
        return True
    if isinstance(error, ClientError) and error.code == 429:
        return True
    return False


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
    stop=stop_after_attempt(4),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _call_gemini(
    client: genai.Client,
    system_prompt: str,
    user_content: str,
) -> LLMResponse:
    """Call Gemini with structured output, retrying on transient errors.

    Args:
        client: Configured Gemini client instance.
        system_prompt: Content-type-specific system prompt.
        user_content: Assembled user message with metadata and body.

    Returns:
        Validated LLMResponse from Gemini structured output.

    Raises:
        ClientError: On permanent API errors (400, 401, 403).
        ServerError: After exhausting retries on server errors.
    """
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=LLMResponse,
            temperature=1.0,
        ),
    )
    return response.parsed


def build_notion_page(llm_result: LLMResponse, content: ExtractedContent) -> NotionPage:
    """Combine LLM-generated fields with extraction-derived fields into a NotionPage.

    LLM provides: title, category, priority, tags, summary, body sections.
    Extraction provides: content_type, source URL, author.
    Processor sets: date_added (now), status (NEW).

    Args:
        llm_result: Validated LLM response with generated fields.
        content: Original extracted content with metadata.

    Returns:
        Complete NotionPage ready for Notion writing.
    """
    entry = KnowledgeEntry(
        title=llm_result.title,
        category=llm_result.category,
        content_type=content.content_type,
        source=content.url,
        author=content.author,
        date_added=datetime.now(timezone.utc),
        status=Status.NEW,
        priority=llm_result.priority,
        tags=llm_result.tags,
        summary=llm_result.summary,
    )

    key_learnings = [
        KeyLearning(
            what=kl.what,
            why_it_matters=kl.why_it_matters,
            how_to_apply=kl.how_to_apply,
        )
        for kl in llm_result.key_learnings
    ]

    return NotionPage(
        entry=entry,
        summary_section=llm_result.summary_section,
        key_points=llm_result.key_points,
        key_learnings=key_learnings,
        detailed_notes=llm_result.detailed_notes,
    )


async def process_content(client: genai.Client, content: ExtractedContent) -> NotionPage:
    """Transform extracted content into a structured NotionPage via Gemini.

    This is the main public API for the LLM processing stage. It:
    1. Builds content-type-specific prompts
    2. Calls Gemini with structured output + retry logic
    3. Applies post-processing rules (priority override for partial extractions)
    4. Maps LLM output to domain models

    Args:
        client: Configured Gemini client instance.
        content: Extracted content from Phase 3.

    Returns:
        Complete NotionPage with all properties and body sections.

    Raises:
        ValidationError: If Gemini response fails schema validation.
        APIError: On non-retryable Gemini API errors.
    """
    system_prompt = build_system_prompt(content)
    user_content = build_user_content(content)

    try:
        llm_result = await _call_gemini(client, system_prompt, user_content)
    except ValidationError:
        logger.error(
            "Gemini response failed schema validation for %s",
            content.url,
            exc_info=True,
        )
        raise
    except APIError:
        logger.error(
            "Gemini API error processing %s",
            content.url,
            exc_info=True,
        )
        raise

    # Post-processing: override priority for partial/metadata-only extractions (LLM-09)
    if content.extraction_status in (ExtractionStatus.PARTIAL, ExtractionStatus.METADATA_ONLY):
        llm_result.priority = Priority.LOW

    return build_notion_page(llm_result, content)
