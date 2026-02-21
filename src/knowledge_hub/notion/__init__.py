"""Notion output: page creation and database management."""

from knowledge_hub.notion.blocks import build_body_blocks
from knowledge_hub.notion.client import get_data_source_id, get_notion_client, reset_client
from knowledge_hub.notion.duplicates import check_duplicate, normalize_url
from knowledge_hub.notion.models import DuplicateResult, PageResult
from knowledge_hub.notion.properties import build_properties
from knowledge_hub.notion.tags import filter_tags, get_valid_tags, invalidate_tag_cache

__all__ = [
    "build_body_blocks",
    "build_properties",
    "check_duplicate",
    "DuplicateResult",
    "filter_tags",
    "get_data_source_id",
    "get_notion_client",
    "get_valid_tags",
    "invalidate_tag_cache",
    "normalize_url",
    "PageResult",
    "reset_client",
]
