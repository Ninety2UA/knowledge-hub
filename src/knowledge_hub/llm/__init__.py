"""LLM processing: structured content analysis via Gemini.

Public API:
    process_content(client, content) -> NotionPage
        Transforms ExtractedContent into a fully populated NotionPage
        via Gemini structured output with retry logic.
"""

from knowledge_hub.llm.client import get_gemini_client, reset_client
from knowledge_hub.llm.processor import process_content
from knowledge_hub.llm.schemas import LLMResponse

__all__ = [
    "get_gemini_client",
    "reset_client",
    "process_content",
    "LLMResponse",
]
