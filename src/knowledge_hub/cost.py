"""Token usage extraction, cost calculation, and structured cost logging.

Centralizes Gemini pricing constants (single source of truth) and provides
utilities for extracting token usage from Gemini responses, calculating costs,
and logging structured usage data for monitoring and cost alerts.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Gemini 3 Flash pricing -- single source of truth
INPUT_PRICE_PER_TOKEN = 0.50 / 1_000_000  # $0.50 per 1M input tokens
OUTPUT_PRICE_PER_TOKEN = 3.00 / 1_000_000  # $3.00 per 1M output tokens


@dataclass
class TokenUsage:
    """Token counts and calculated cost for a single Gemini API call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float


def extract_usage(response: object) -> TokenUsage:
    """Extract token usage from a Gemini GenerateContentResponse.

    Safely handles None values in usage_metadata by defaulting to 0.

    Args:
        response: A Gemini GenerateContentResponse with usage_metadata.

    Returns:
        TokenUsage with token counts and calculated cost.
    """
    metadata = getattr(response, "usage_metadata", None)
    prompt_tokens = getattr(metadata, "prompt_token_count", 0) or 0
    completion_tokens = getattr(metadata, "candidates_token_count", 0) or 0
    total_tokens = prompt_tokens + completion_tokens
    cost_usd = (prompt_tokens * INPUT_PRICE_PER_TOKEN) + (
        completion_tokens * OUTPUT_PRICE_PER_TOKEN
    )

    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
    )


def log_usage(url: str, usage: TokenUsage) -> None:
    """Log structured token usage data for a processed URL.

    Emits a single INFO log with all usage fields as structured extra data,
    suitable for JSON log aggregation and cost monitoring.

    Args:
        url: The URL that was processed.
        usage: Token usage data from extract_usage.
    """
    # Lazy import to avoid circular dependency (cost -> llm.prompts -> llm -> processor -> cost)
    from knowledge_hub.llm.prompts import GEMINI_MODEL

    logger.info(
        "Gemini processing complete",
        extra={
            "url": url,
            "model": GEMINI_MODEL,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "cost_usd": round(usage.cost_usd, 6),
        },
    )
