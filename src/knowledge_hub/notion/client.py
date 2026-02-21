"""Async Notion client singleton with data source discovery.

Creates a cached AsyncClient instance configured with the API key from
application settings. Discovers the data_source_id from the database on
first use (required by Notion API 2025-09-03).
"""

from notion_client import AsyncClient

from knowledge_hub.config import get_settings

_client: AsyncClient | None = None
_data_source_id: str | None = None


async def get_notion_client() -> AsyncClient:
    """Return a cached async Notion client instance.

    Creates the client on first call using notion_api_key from settings.
    Subsequent calls return the cached instance.
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncClient(auth=settings.notion_api_key)
    return _client


async def get_data_source_id() -> str:
    """Discover and cache the data_source_id from the configured database.

    Uses databases.retrieve() to find the data_source_id array, then caches
    the first entry. Raises RuntimeError if no data sources are found.
    """
    global _data_source_id
    if _data_source_id is None:
        client = await get_notion_client()
        settings = get_settings()
        db = await client.databases.retrieve(database_id=settings.notion_database_id)
        data_sources = db.get("data_sources", [])
        if not data_sources:
            raise RuntimeError(
                f"No data sources found for database {settings.notion_database_id}. "
                "Ensure the database exists and has at least one data source."
            )
        _data_source_id = data_sources[0]["id"]
    return _data_source_id


def reset_client() -> None:
    """Reset cached client and data_source_id. Used for testing."""
    global _client, _data_source_id
    _client = None
    _data_source_id = None
