"""Tag validation with TTL cache against the Notion database schema.

Fetches valid tag names from the Tags multi_select property in Notion
and caches them with a 5-minute TTL. LLM-suggested tags not in the
Notion schema are silently dropped per user decision.
"""

from cachetools import TTLCache

from knowledge_hub.notion.client import get_data_source_id, get_notion_client

_tag_cache: TTLCache = TTLCache(maxsize=1, ttl=300)  # 5-minute TTL
_TAG_CACHE_KEY = "valid_tags"


async def get_valid_tags() -> set[str]:
    """Return the set of valid tag names from the Notion database schema.

    Fetches from Notion on first call or after TTL expiry, caches the result.
    """
    cached = _tag_cache.get(_TAG_CACHE_KEY)
    if cached is not None:
        return cached

    client = await get_notion_client()
    ds_id = await get_data_source_id()
    ds = await client.data_sources.retrieve(data_source_id=ds_id)

    options = ds["properties"]["Tags"]["multi_select"]["options"]
    valid = {opt["name"] for opt in options}
    _tag_cache[_TAG_CACHE_KEY] = valid
    return valid


def filter_tags(suggested: list[str], valid: set[str]) -> list[str]:
    """Keep only tags that exist in the Notion schema. Pure function.

    Preserves the order of suggested tags.
    """
    return [t for t in suggested if t in valid]


def invalidate_tag_cache() -> None:
    """Clear the tag cache. Used for testing."""
    _tag_cache.clear()
