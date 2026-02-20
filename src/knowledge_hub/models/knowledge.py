"""Knowledge entry model mirroring the 10 Notion database properties."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from knowledge_hub.models.content import ContentType


class Category(str, Enum):
    """Fixed categories for knowledge entries (11 values)."""

    AI_ML = "AI & Machine Learning"
    MARKETING = "Marketing"
    PRODUCT = "Product"
    GROWTH = "Growth"
    ANALYTICS = "Analytics"
    ENGINEERING = "Engineering"
    DESIGN = "Design"
    BUSINESS = "Business"
    CAREER = "Career"
    PRODUCTIVITY = "Productivity"
    OTHER = "Other"


class Priority(str, Enum):
    """Priority levels for knowledge entries."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Status(str, Enum):
    """Processing status of a knowledge entry."""

    NEW = "New"
    REVIEWED = "Reviewed"
    APPLIED = "Applied"
    ARCHIVED = "Archived"


class KnowledgeEntry(BaseModel):
    """A knowledge entry mirroring the 10 Notion database properties exactly."""

    title: str
    category: Category
    content_type: ContentType
    source: str  # Original URL
    author: str | None = None
    date_added: datetime
    status: Status = Status.NEW
    priority: Priority
    tags: list[str] = []
    summary: str
