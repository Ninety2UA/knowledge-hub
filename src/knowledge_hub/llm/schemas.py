"""LLM response schema for Gemini structured output.

Contains only fields the LLM generates. Fields like source, date_added,
status, and content_type come from extraction metadata in the processor.
"""

from pydantic import BaseModel, Field

from knowledge_hub.models.knowledge import Category, Priority


class LLMKeyLearning(BaseModel):
    """A single structured learning block with What / Why / How structure."""

    what: str
    why_it_matters: str
    how_to_apply: list[str] = Field(min_length=1)


class LLMResponse(BaseModel):
    """Schema for Gemini structured output. Used as response_schema parameter."""

    title: str = Field(description="Concise, descriptive title for the knowledge entry")
    summary: str = Field(description="3-5 sentence executive summary")
    category: Category = Field(description="Best-fit category from the 11 options")
    priority: Priority = Field(description="High/Medium/Low based on actionability")
    tags: list[str] = Field(
        min_length=3, max_length=7, description="3-7 relevant tags"
    )
    summary_section: str = Field(
        description="3-5 sentence summary for the page body"
    )
    key_points: list[str] = Field(
        min_length=5, max_length=10, description="5-10 importance-ordered key points"
    )
    key_learnings: list[LLMKeyLearning] = Field(min_length=3, max_length=7)
    detailed_notes: str = Field(
        description="Structured breakdown, ~1500-2500 words"
    )
