"""Token usage extraction, cost calculation, and structured cost logging.

Centralizes Gemini pricing constants (single source of truth) and provides
utilities for extracting token usage from Gemini responses, calculating costs,
and logging structured usage data for monitoring and cost alerts.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# In-memory cost accumulators (reset on instance restart -- acceptable for personal tool)
_daily_cost: float = 0.0
_weekly_cost: float = 0.0


def add_cost(amount: float) -> None:
    """Add cost to both daily and weekly accumulators."""
    global _daily_cost, _weekly_cost
    _daily_cost += amount
    _weekly_cost += amount


def get_daily_cost() -> float:
    """Return accumulated daily Gemini cost."""
    return _daily_cost


def get_weekly_cost() -> float:
    """Return accumulated weekly Gemini cost."""
    return _weekly_cost


def reset_daily_cost() -> None:
    """Reset daily cost accumulator to zero."""
    global _daily_cost
    _daily_cost = 0.0


def reset_weekly_cost() -> None:
    """Reset weekly cost accumulator to zero."""
    global _weekly_cost
    _weekly_cost = 0.0


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


def merge_usage(a: TokenUsage, b: TokenUsage) -> TokenUsage:
    """Combine two TokenUsage records (e.g., transcription + analysis)."""
    return TokenUsage(
        prompt_tokens=a.prompt_tokens + b.prompt_tokens,
        completion_tokens=a.completion_tokens + b.completion_tokens,
        total_tokens=a.total_tokens + b.total_tokens,
        cost_usd=a.cost_usd + b.cost_usd,
    )


def log_usage(url: str, usage: TokenUsage) -> None:
    """Log structured token usage data for a processed URL.

    Emits a single INFO log with all usage fields as structured extra data,
    suitable for JSON log aggregation and cost monitoring.

    Args:
        url: The URL that was processed.
        usage: Token usage data from extract_usage.
    """
    # Accumulate cost for digest/alert tracking
    add_cost(usage.cost_usd)

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
