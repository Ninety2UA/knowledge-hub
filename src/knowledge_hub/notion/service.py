"""Page creation service orchestrating all Notion modules.

Wires duplicate check, tag filtering, property/block building, and
Notion API calls into a single create_notion_page function. Handles
100-block batch limits and stale tag cache recovery.
"""

import logging

from notion_client import errors as notion_errors

from knowledge_hub.notion.blocks import build_body_blocks
from knowledge_hub.notion.client import get_data_source_id, get_notion_client
from knowledge_hub.notion.duplicates import check_duplicate, normalize_url
from knowledge_hub.notion.models import DuplicateResult, PageResult
from knowledge_hub.notion.properties import build_properties
from knowledge_hub.notion.tags import filter_tags, get_valid_tags, invalidate_tag_cache

logger = logging.getLogger(__name__)

_BLOCK_BATCH_SIZE = 100


async def create_notion_page(page) -> PageResult | DuplicateResult:
    """Create a Notion page from a NotionPage model.

    Orchestrates the full pipeline:
    1. Normalize URL for consistent duplicate matching
    2. Check for duplicate (skip if found)
    3. Filter tags against Notion schema (drop unknown)
    4. Build properties and body blocks
    5. Create page via Notion API with 100-block batching
    6. Return PageResult or DuplicateResult

    Lets notion_client.errors.APIResponseError propagate to the caller
    (Phase 6 orchestrator handles error routing).
    """
    # 1. Normalize URL and update entry for consistent Source property
    page.entry.source = normalize_url(page.entry.source)

    # 2. Duplicate check (NOTION-03)
    duplicate = await check_duplicate(page.entry.source)
    if duplicate is not None:
        logger.warning(
            "Duplicate URL skipped: %s (existing page: %s)",
            page.entry.source,
            duplicate.page_id,
        )
        return duplicate

    # 3. Tag filtering (NOTION-04)
    valid_tags = await get_valid_tags()
    page.entry.tags = filter_tags(page.entry.tags, valid_tags)

    # 4. Build properties (NOTION-01, NOTION-02) and blocks
    properties = build_properties(page)
    blocks = build_body_blocks(page)

    # 5. Create page with batch handling
    client = await get_notion_client()
    ds_id = await get_data_source_id()

    first_batch = blocks[:_BLOCK_BATCH_SIZE]
    overflow = blocks[_BLOCK_BATCH_SIZE:]

    try:
        created_page = await client.pages.create(
            parent={"type": "data_source_id", "data_source_id": ds_id},
            properties=properties,
            children=first_batch,
        )
    except notion_errors.APIResponseError as exc:
        # Stale tag cache: if error mentions multi_select validation,
        # invalidate cache, re-filter tags, and retry once
        if "multi_select" in str(exc):
            logger.warning("Stale tag cache detected, retrying with fresh tags")
            invalidate_tag_cache()
            fresh_valid = await get_valid_tags()
            page.entry.tags = filter_tags(page.entry.tags, fresh_valid)
            properties = build_properties(page)
            created_page = await client.pages.create(
                parent={"type": "data_source_id", "data_source_id": ds_id},
                properties=properties,
                children=first_batch,
            )
        else:
            raise

    page_id = created_page["id"]

    # Append overflow blocks in batches of 100
    for i in range(0, len(overflow), _BLOCK_BATCH_SIZE):
        batch = overflow[i : i + _BLOCK_BATCH_SIZE]
        await client.blocks.children.append(block_id=page_id, children=batch)

    # 6. Return PageResult
    logger.info("Created Notion page: %s (%s)", page.entry.title, page_id)
    return PageResult(
        page_id=page_id,
        page_url=created_page["url"],
        title=page.entry.title,
    )
