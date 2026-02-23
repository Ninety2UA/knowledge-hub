"""Tests for the page creation service orchestrator."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

from knowledge_hub.models.content import ContentType
from knowledge_hub.models.knowledge import Category, KnowledgeEntry, Priority
from knowledge_hub.models.notion import KeyLearning, NotionPage
from knowledge_hub.notion.models import DuplicateResult, PageResult
from knowledge_hub.notion.service import create_notion_page


def _make_page(**overrides) -> NotionPage:
    """Create a valid NotionPage with sensible defaults."""
    entry_defaults = {
        "title": "Test Article",
        "category": Category.AI_ML,
        "content_type": ContentType.ARTICLE,
        "source": "https://example.com/test",
        "author": "Test Author",
        "date_added": datetime(2026, 2, 20),
        "priority": Priority.HIGH,
        "tags": ["AI", "Python"],
        "summary": "A test summary.",
    }
    entry_defaults.update(overrides.pop("entry_overrides", {}))
    entry = KnowledgeEntry(**entry_defaults)
    page_defaults = {
        "entry": entry,
        "summary_section": "Executive summary.",
        "key_points": ["Point 1", "Point 2"],
        "key_learnings": [
            KeyLearning(
                title="Testing Best Practices",
                what="Testing matters",
                why_it_matters="Catches bugs early",
                how_to_apply=["Write tests"],
                resources_needed="pytest",
                estimated_time="15 minutes",
            )
        ],
        "detailed_notes": "Detailed notes.",
    }
    page_defaults.update(overrides)
    return NotionPage(**page_defaults)


def _mock_pages_create_response(page_id="page-new-123"):
    """Return a mock Notion pages.create response."""
    return {
        "id": page_id,
        "url": f"https://notion.so/{page_id}",
    }


@patch("knowledge_hub.notion.service.get_data_source_id", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.get_notion_client", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.get_valid_tags", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.check_duplicate", new_callable=AsyncMock)
async def test_create_page_success(
    mock_dup, mock_tags, mock_get_client, mock_get_ds_id
):
    """Successful page creation returns PageResult with correct fields."""
    mock_dup.return_value = None
    mock_tags.return_value = {"AI", "Python"}
    mock_get_ds_id.return_value = "ds-456"
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_client.pages.create.return_value = _mock_pages_create_response()

    page = _make_page()
    result = await create_notion_page(page)

    assert isinstance(result, PageResult)
    assert result.page_id == "page-new-123"
    assert result.page_url == "https://notion.so/page-new-123"
    assert result.title == "Test Article"
    mock_client.pages.create.assert_called_once()


@patch("knowledge_hub.notion.service.check_duplicate", new_callable=AsyncMock)
async def test_create_page_duplicate_skipped(mock_dup):
    """Duplicate URL returns DuplicateResult without calling pages.create."""
    dup = DuplicateResult(
        page_id="page-existing",
        page_url="https://notion.so/page-existing",
        title="Existing Article",
    )
    mock_dup.return_value = dup

    page = _make_page()
    result = await create_notion_page(page)

    assert isinstance(result, DuplicateResult)
    assert result.page_id == "page-existing"
    assert result.title == "Existing Article"


@patch("knowledge_hub.notion.service.get_data_source_id", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.get_notion_client", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.get_valid_tags", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.check_duplicate", new_callable=AsyncMock)
async def test_create_page_tags_filtered(
    mock_dup, mock_tags, mock_get_client, mock_get_ds_id
):
    """Unknown tags are filtered out before page creation."""
    mock_dup.return_value = None
    mock_tags.return_value = {"AI", "Python"}  # "Unknown" not in valid set
    mock_get_ds_id.return_value = "ds-456"
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_client.pages.create.return_value = _mock_pages_create_response()

    page = _make_page(entry_overrides={"tags": ["AI", "Unknown", "Python"]})
    await create_notion_page(page)

    call_kwargs = mock_client.pages.create.call_args
    props = call_kwargs.kwargs["properties"]
    tag_names = [t["name"] for t in props["Tags"]["multi_select"]]
    assert tag_names == ["AI", "Python"]
    assert "Unknown" not in tag_names


@patch("knowledge_hub.notion.service.get_data_source_id", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.get_notion_client", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.get_valid_tags", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.check_duplicate", new_callable=AsyncMock)
async def test_create_page_url_normalized(
    mock_dup, mock_tags, mock_get_client, mock_get_ds_id
):
    """Source URL is normalized before page creation."""
    mock_dup.return_value = None
    mock_tags.return_value = {"AI"}
    mock_get_ds_id.return_value = "ds-456"
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_client.pages.create.return_value = _mock_pages_create_response()

    page = _make_page(
        entry_overrides={
            "source": "http://example.com/post?utm_source=x",
            "tags": ["AI"],
        }
    )
    await create_notion_page(page)

    call_kwargs = mock_client.pages.create.call_args
    props = call_kwargs.kwargs["properties"]
    url = props["Source"]["url"]
    # utm_* stripped; protocol preserved by url_normalize (RFC normalization)
    assert "utm_source" not in url
    assert "example.com/post" in url


@patch("knowledge_hub.notion.service.build_body_blocks")
@patch("knowledge_hub.notion.service.get_data_source_id", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.get_notion_client", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.get_valid_tags", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.check_duplicate", new_callable=AsyncMock)
async def test_create_page_overflow_blocks(
    mock_dup, mock_tags, mock_get_client, mock_get_ds_id, mock_build_blocks
):
    """Pages with >100 blocks use batched appends."""
    mock_dup.return_value = None
    mock_tags.return_value = {"AI"}
    mock_get_ds_id.return_value = "ds-456"
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_client.pages.create.return_value = _mock_pages_create_response()

    # 150 dummy blocks
    mock_build_blocks.return_value = [
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}}
        for _ in range(150)
    ]

    page = _make_page(entry_overrides={"tags": ["AI"]})
    await create_notion_page(page)

    # pages.create called with first 100
    create_call = mock_client.pages.create.call_args
    assert len(create_call.kwargs["children"]) == 100

    # blocks.children.append called with remaining 50
    append_call = mock_client.blocks.children.append.call_args
    assert append_call.kwargs["block_id"] == "page-new-123"
    assert len(append_call.kwargs["children"]) == 50


@patch("knowledge_hub.notion.service.get_data_source_id", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.get_notion_client", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.get_valid_tags", new_callable=AsyncMock)
@patch("knowledge_hub.notion.service.check_duplicate", new_callable=AsyncMock)
async def test_create_page_status_new(
    mock_dup, mock_tags, mock_get_client, mock_get_ds_id
):
    """Status property is always 'New'."""
    mock_dup.return_value = None
    mock_tags.return_value = {"AI"}
    mock_get_ds_id.return_value = "ds-456"
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_client.pages.create.return_value = _mock_pages_create_response()

    page = _make_page(entry_overrides={"tags": ["AI"]})
    await create_notion_page(page)

    call_kwargs = mock_client.pages.create.call_args
    props = call_kwargs.kwargs["properties"]
    assert props["Status"]["select"]["name"] == "New"
