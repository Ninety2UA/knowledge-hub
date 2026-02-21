"""Tests for token usage extraction, cost calculation, and structured logging."""

from unittest.mock import MagicMock, patch

from knowledge_hub.cost import (
    INPUT_PRICE_PER_TOKEN,
    OUTPUT_PRICE_PER_TOKEN,
    TokenUsage,
    extract_usage,
    log_usage,
)


def _make_mock_response(prompt_tokens: int | None, completion_tokens: int | None) -> MagicMock:
    """Build a mock Gemini response with usage_metadata."""
    metadata = MagicMock()
    metadata.prompt_token_count = prompt_tokens
    metadata.candidates_token_count = completion_tokens
    response = MagicMock()
    response.usage_metadata = metadata
    return response


def test_extract_usage_normal():
    """Normal response with token counts produces correct TokenUsage."""
    response = _make_mock_response(prompt_tokens=100, completion_tokens=50)

    usage = extract_usage(response)

    assert usage.prompt_tokens == 100
    assert usage.completion_tokens == 50
    assert usage.total_tokens == 150
    # (100 * 0.50/1M) + (50 * 3.00/1M) = 0.000050 + 0.000150 = 0.000200
    expected_cost = (100 * INPUT_PRICE_PER_TOKEN) + (50 * OUTPUT_PRICE_PER_TOKEN)
    assert abs(usage.cost_usd - expected_cost) < 1e-10
    assert abs(usage.cost_usd - 0.000200) < 1e-10


def test_extract_usage_none_counts():
    """Response with None token counts defaults to 0 tokens and $0 cost."""
    response = _make_mock_response(prompt_tokens=None, completion_tokens=None)

    usage = extract_usage(response)

    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0
    assert usage.total_tokens == 0
    assert usage.cost_usd == 0.0


def test_extract_usage_cost_precision():
    """Large token counts produce correct cost: 1M input + 100K output = $0.80."""
    response = _make_mock_response(prompt_tokens=1_000_000, completion_tokens=100_000)

    usage = extract_usage(response)

    assert usage.prompt_tokens == 1_000_000
    assert usage.completion_tokens == 100_000
    assert usage.total_tokens == 1_100_000
    # (1M * $0.50/1M) + (100K * $3.00/1M) = $0.50 + $0.30 = $0.80
    assert abs(usage.cost_usd - 0.80) < 1e-10


def test_extract_usage_no_metadata():
    """Response with no usage_metadata attribute defaults to 0 tokens."""
    response = MagicMock(spec=[])  # No attributes at all

    usage = extract_usage(response)

    assert usage.prompt_tokens == 0
    assert usage.completion_tokens == 0
    assert usage.cost_usd == 0.0


def test_log_usage_structured_output():
    """log_usage emits INFO log with structured extra fields."""
    usage = TokenUsage(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd=0.000200,
    )

    with patch("knowledge_hub.cost.logger") as mock_logger:
        log_usage("https://example.com/article", usage)

    mock_logger.info.assert_called_once()
    call_args = mock_logger.info.call_args
    assert call_args[0][0] == "Gemini processing complete"
    extra = call_args[1]["extra"]
    assert extra["url"] == "https://example.com/article"
    assert extra["model"] == "gemini-3-flash-preview"
    assert extra["prompt_tokens"] == 100
    assert extra["completion_tokens"] == 50
    assert extra["total_tokens"] == 150
    assert extra["cost_usd"] == 0.0002
