"""Schema validation tests for LLMResponse and LLMKeyLearning."""

import pytest
from pydantic import ValidationError

from knowledge_hub.llm.schemas import LLMKeyLearning, LLMResponse
from knowledge_hub.models.knowledge import Category, Priority


def _make_valid_llm_response() -> dict:
    """Return a dict with all valid fields for LLMResponse construction."""
    return {
        "title": "Understanding RAG Pipelines",
        "summary": "A comprehensive guide to building RAG pipelines for LLM applications.",
        "category": "Engineering",
        "priority": "High",
        "tags": ["engineering", "llms", "architecture"],
        "summary_section": "This article covers the fundamentals of RAG pipeline design.",
        "key_points": [
            "RAG reduces hallucinations by grounding in source data",
            "Chunk size affects retrieval quality significantly",
            "Embedding model choice impacts recall metrics",
            "Hybrid search combines dense and sparse retrieval",
            "Re-ranking improves precision at the cost of latency",
        ],
        "key_learnings": [
            {
                "what": "Chunk overlap improves context continuity",
                "why_it_matters": "Without overlap, key context can be split across chunks",
                "how_to_apply": ["Set chunk overlap to 10-20% of chunk size"],
            },
            {
                "what": "Hybrid search outperforms dense-only retrieval",
                "why_it_matters": "Keyword matching catches exact terms that embeddings miss",
                "how_to_apply": ["Combine BM25 with vector search", "Weight keyword at 0.3"],
            },
            {
                "what": "Re-ranking is worth the latency cost",
                "why_it_matters": "Cross-encoder re-ranking improves precision by 15-20%",
                "how_to_apply": ["Add a re-ranker after initial retrieval"],
            },
        ],
        "detailed_notes": "## RAG Pipeline Architecture\n\nDetailed breakdown of components...",
    }


def test_valid_llm_response_parses():
    """Full valid data parses to LLMResponse."""
    data = _make_valid_llm_response()
    result = LLMResponse(**data)
    assert result.title == "Understanding RAG Pipelines"
    assert result.category == Category.ENGINEERING
    assert result.priority == Priority.HIGH
    assert len(result.tags) == 3
    assert len(result.key_points) == 5
    assert len(result.key_learnings) == 3


def test_llm_response_requires_title():
    """Missing title raises ValidationError."""
    data = _make_valid_llm_response()
    del data["title"]
    with pytest.raises(ValidationError):
        LLMResponse(**data)


def test_llm_response_category_enum():
    """Valid category string maps to Category enum."""
    data = _make_valid_llm_response()
    data["category"] = "Engineering"
    result = LLMResponse(**data)
    assert result.category == Category.ENGINEERING


def test_llm_response_invalid_category():
    """Invalid category string raises ValidationError."""
    data = _make_valid_llm_response()
    data["category"] = "Nonexistent Category"
    with pytest.raises(ValidationError):
        LLMResponse(**data)


def test_llm_response_priority_enum():
    """Valid priority string maps to Priority enum."""
    data = _make_valid_llm_response()
    data["priority"] = "High"
    result = LLMResponse(**data)
    assert result.priority == Priority.HIGH


def test_llm_response_tags_min_length():
    """Fewer than 3 tags raises ValidationError."""
    data = _make_valid_llm_response()
    data["tags"] = ["ai", "ml"]
    with pytest.raises(ValidationError):
        LLMResponse(**data)


def test_llm_response_tags_max_length():
    """More than 7 tags raises ValidationError."""
    data = _make_valid_llm_response()
    data["tags"] = ["a", "b", "c", "d", "e", "f", "g", "h"]
    with pytest.raises(ValidationError):
        LLMResponse(**data)


def test_llm_response_key_points_min():
    """Fewer than 5 key points raises ValidationError."""
    data = _make_valid_llm_response()
    data["key_points"] = ["point 1", "point 2", "point 3", "point 4"]
    with pytest.raises(ValidationError):
        LLMResponse(**data)


def test_llm_response_key_points_max():
    """More than 10 key points raises ValidationError."""
    data = _make_valid_llm_response()
    data["key_points"] = [f"point {i}" for i in range(11)]
    with pytest.raises(ValidationError):
        LLMResponse(**data)


def test_llm_response_key_learnings_min():
    """Fewer than 3 key learnings raises ValidationError."""
    data = _make_valid_llm_response()
    data["key_learnings"] = data["key_learnings"][:2]
    with pytest.raises(ValidationError):
        LLMResponse(**data)


def test_llm_key_learning_how_to_apply_nonempty():
    """LLMKeyLearning with empty how_to_apply raises ValidationError."""
    with pytest.raises(ValidationError):
        LLMKeyLearning(
            what="Some insight",
            why_it_matters="Important reason",
            how_to_apply=[],
        )


def test_llm_key_learning_valid():
    """Valid LLMKeyLearning parses successfully."""
    kl = LLMKeyLearning(
        what="Chunk overlap improves context",
        why_it_matters="Prevents context loss at boundaries",
        how_to_apply=["Set overlap to 10-20%", "Test with sample queries"],
    )
    assert kl.what == "Chunk overlap improves context"
    assert len(kl.how_to_apply) == 2
