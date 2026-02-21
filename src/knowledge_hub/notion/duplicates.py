"""URL normalization and duplicate detection against the Notion database.

Normalizes URLs by stripping utm_* tracking parameters and applying
protocol/trailing-slash normalization before querying Notion's
data_sources.query endpoint for exact matches on the Source property.
"""

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from url_normalize import url_normalize

from knowledge_hub.notion.client import get_data_source_id, get_notion_client
from knowledge_hub.notion.models import DuplicateResult


def normalize_url(raw_url: str) -> str:
    """Normalize a URL for duplicate comparison.

    Strips utm_* tracking parameters, then applies protocol normalization
    (http -> https), trailing slash removal, and other standard normalizations
    via the url-normalize library.

    We manually strip utm_* params rather than using url-normalize's
    filter_params=True which removes ALL query params.
    """
    # Parse and strip utm_* params
    parsed = urlparse(raw_url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in params.items() if not k.startswith("utm_")}
    clean_query = urlencode(filtered, doseq=True)
    cleaned = urlunparse(parsed._replace(query=clean_query))

    # Apply standard normalization (protocol, trailing slash, encoding)
    return url_normalize(cleaned)


async def check_duplicate(raw_url: str) -> DuplicateResult | None:
    """Query Notion for an existing page with the same normalized URL.

    Returns DuplicateResult with page info if found, None otherwise.
    Uses data_sources.query with a URL property filter for exact match.
    """
    client = await get_notion_client()
    ds_id = await get_data_source_id()
    normalized = normalize_url(raw_url)

    response = await client.data_sources.query(
        data_source_id=ds_id,
        filter={"property": "Source", "url": {"equals": normalized}},
        page_size=1,
    )

    if not response["results"]:
        return None

    page = response["results"][0]
    title_prop = page.get("properties", {}).get("Title", {}).get("title", [])
    title = title_prop[0]["plain_text"] if title_prop else "Untitled"

    return DuplicateResult(
        page_id=page["id"],
        page_url=page["url"],
        title=title,
    )
