"""LLM response schema for Gemini structured output.

Contains only fields the LLM generates. Fields like source, date_added,
status, and content_type come from extraction metadata in the processor.
"""

from pydantic import BaseModel, Field

from knowledge_hub.models.knowledge import Category, Priority


class LLMKeyLearning(BaseModel):
    """A single structured learning block with What / Why / How structure."""

    title: str = Field(description="Short descriptive title for the learning heading")
    what: str = Field(description="2-3 sentences explaining the concept/framework/insight")
    why_it_matters: str = Field(description="1-2 sentences on relevance for performance marketing / AI / tech")
    how_to_apply: list[str] = Field(min_length=1, description="Concrete sequential steps with time estimates")
    resources_needed: str = Field(description="Tools, resources, or prerequisites needed")
    estimated_time: str = Field(description="Total time estimate to complete the steps")


class LLMResponse(BaseModel):
    """Schema for Gemini structured output. Used as response_schema parameter."""

    title: str = Field(description="Concise, descriptive title for the knowledge entry")
    author: str | None = Field(
        default=None,
        description="Author or creator name extracted from the content. None if not identifiable.",
    )
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
