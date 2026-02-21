"""Result types for Notion operations.

Separate from domain models since these are Notion-service-specific
return types used by downstream consumers (Phase 6 integration).
"""

from pydantic import BaseModel


class PageResult(BaseModel):
    """Returned after successful Notion page creation."""

    page_id: str
    page_url: str
    title: str


class DuplicateResult(BaseModel):
    """Returned when a duplicate URL is found in the Notion database."""

    page_id: str
    page_url: str
    title: str
