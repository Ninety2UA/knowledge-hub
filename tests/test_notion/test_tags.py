"""Tests for tag caching and filtering."""

from unittest.mock import AsyncMock, patch

from knowledge_hub.notion.tags import (
    _TAG_CACHE_KEY,
    _tag_cache,
    filter_tags,
    get_valid_tags,
    invalidate_tag_cache,
)


# --- filter_tags tests (pure function, no mocking needed) ---


def test_filter_tags_keeps_valid():
    """Only valid tags are kept."""
    result = filter_tags(["AI", "Unknown", "Python"], {"AI", "Python", "Data"})
    assert result == ["AI", "Python"]


def test_filter_tags_preserves_order():
    """Output order matches input order."""
    result = filter_tags(["Python", "AI", "Data"], {"AI", "Python", "Data"})
    assert result == ["Python", "AI", "Data"]


def test_filter_tags_all_invalid():
    """All invalid tags returns empty list."""
    result = filter_tags(["Foo", "Bar", "Baz"], {"AI", "Python"})
    assert result == []


def test_filter_tags_all_valid():
    """All valid tags returned as-is."""
    result = filter_tags(["AI", "Python"], {"AI", "Python", "Data"})
    assert result == ["AI", "Python"]


# --- get_valid_tags tests (async, needs mocking) ---


@patch("knowledge_hub.notion.tags.get_data_source_id", new_callable=AsyncMock)
@patch("knowledge_hub.notion.tags.get_notion_client", new_callable=AsyncMock)
async def test_get_valid_tags_caches(mock_get_client, mock_get_ds_id):
    """Second call uses cache; retrieve called only once."""
    invalidate_tag_cache()
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_get_ds_id.return_value = "ds-123"

    mock_client.data_sources.retrieve.return_value = {
        "properties": {
            "Tags": {
                "multi_select": {
                    "options": [
                        {"name": "AI"},
                        {"name": "Python"},
                    ]
                }
            }
        }
    }

    result1 = await get_valid_tags()
    result2 = await get_valid_tags()
    assert result1 == {"AI", "Python"}
    assert result2 == {"AI", "Python"}
    mock_client.data_sources.retrieve.assert_called_once()


@patch("knowledge_hub.notion.tags.get_data_source_id", new_callable=AsyncMock)
@patch("knowledge_hub.notion.tags.get_notion_client", new_callable=AsyncMock)
async def test_get_valid_tags_after_invalidate(mock_get_client, mock_get_ds_id):
    """After invalidate, retrieve is called again."""
    invalidate_tag_cache()
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_get_ds_id.return_value = "ds-123"

    mock_client.data_sources.retrieve.return_value = {
        "properties": {
            "Tags": {
                "multi_select": {
                    "options": [{"name": "AI"}]
                }
            }
        }
    }

    await get_valid_tags()
    invalidate_tag_cache()
    await get_valid_tags()
    assert mock_client.data_sources.retrieve.call_count == 2
