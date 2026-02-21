"""Tests for URL normalization and duplicate checking."""

from unittest.mock import AsyncMock, patch

from knowledge_hub.notion.duplicates import check_duplicate, normalize_url
from knowledge_hub.notion.models import DuplicateResult


# --- URL normalization tests ---


def test_normalize_strips_utm_params():
    """utm_* params removed, other params preserved."""
    result = normalize_url(
        "https://example.com/post?utm_source=twitter&utm_medium=social&id=5"
    )
    assert "utm_source" not in result
    assert "utm_medium" not in result
    assert "id=5" in result


def test_normalize_preserves_protocol():
    """url_normalize preserves the original protocol (RFC normalization only)."""
    result = normalize_url("http://example.com/page")
    assert result == "http://example.com/page"
    result_https = normalize_url("https://example.com/page")
    assert result_https == "https://example.com/page"


def test_normalize_preserves_trailing_slash():
    """url_normalize preserves trailing slashes (RFC normalization only)."""
    result = normalize_url("https://example.com/page/")
    assert result == "https://example.com/page/"


def test_normalize_combined():
    """utm_* params stripped while protocol and path preserved."""
    result = normalize_url("http://example.com/page/?utm_source=x&utm_campaign=y")
    assert "utm_source" not in result
    assert "utm_campaign" not in result
    # Protocol and trailing slash preserved by url_normalize (RFC normalization)
    assert result.startswith("http://")
    assert "example.com/page/" in result


def test_normalize_preserves_non_utm_params():
    """Non-utm query params preserved, utm removed."""
    result = normalize_url("https://example.com/page?ref=abc&utm_campaign=x")
    assert "ref=abc" in result
    assert "utm_campaign" not in result


# --- Duplicate check tests ---


@patch("knowledge_hub.notion.duplicates.get_data_source_id", new_callable=AsyncMock)
@patch("knowledge_hub.notion.duplicates.get_notion_client", new_callable=AsyncMock)
async def test_check_duplicate_found(mock_get_client, mock_get_ds_id):
    """Returns DuplicateResult when query finds existing page."""
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_get_ds_id.return_value = "ds-123"

    mock_client.data_sources.query.return_value = {
        "results": [
            {
                "id": "page-abc",
                "url": "https://notion.so/page-abc",
                "properties": {
                    "Title": {
                        "title": [{"plain_text": "Existing Article"}]
                    }
                },
            }
        ]
    }

    result = await check_duplicate("https://example.com/article")
    assert isinstance(result, DuplicateResult)
    assert result.page_id == "page-abc"
    assert result.page_url == "https://notion.so/page-abc"
    assert result.title == "Existing Article"


@patch("knowledge_hub.notion.duplicates.get_data_source_id", new_callable=AsyncMock)
@patch("knowledge_hub.notion.duplicates.get_notion_client", new_callable=AsyncMock)
async def test_check_duplicate_not_found(mock_get_client, mock_get_ds_id):
    """Returns None when no duplicate found."""
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_get_ds_id.return_value = "ds-123"

    mock_client.data_sources.query.return_value = {"results": []}

    result = await check_duplicate("https://example.com/new-article")
    assert result is None


@patch("knowledge_hub.notion.duplicates.get_data_source_id", new_callable=AsyncMock)
@patch("knowledge_hub.notion.duplicates.get_notion_client", new_callable=AsyncMock)
async def test_check_duplicate_no_title_fallback(mock_get_client, mock_get_ds_id):
    """Falls back to 'Untitled' when title array is empty."""
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_get_ds_id.return_value = "ds-123"

    mock_client.data_sources.query.return_value = {
        "results": [
            {
                "id": "page-xyz",
                "url": "https://notion.so/page-xyz",
                "properties": {"Title": {"title": []}},
            }
        ]
    }

    result = await check_duplicate("https://example.com/no-title")
    assert isinstance(result, DuplicateResult)
    assert result.title == "Untitled"
