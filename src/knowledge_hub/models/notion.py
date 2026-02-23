"""Notion page model with structured 4-section body."""

from pydantic import BaseModel

from knowledge_hub.models.knowledge import KnowledgeEntry


class KeyLearning(BaseModel):
    """A structured learning block for the Key Learnings section."""

    title: str  # Short heading for the learning
    what: str
    why_it_matters: str
    how_to_apply: list[str]  # Concrete, sequential steps
    resources_needed: str  # Tools/resources/prerequisites
    estimated_time: str  # Time estimate to complete


class NotionPage(BaseModel):
    """A complete Notion page with properties and 4-section body."""

    entry: KnowledgeEntry  # The 10 database properties
    summary_section: str  # 3-5 sentence executive summary
    key_points: list[str]  # 5-10 numbered statements, importance-ordered
    key_learnings: list[KeyLearning]  # 3-7 structured blocks
    detailed_notes: str  # Content-type-specific breakdown, ~2500 word cap
