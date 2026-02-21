"""System prompt templates and content builder functions for Gemini.

Provides content-type-specific prompt construction and user content assembly.
Seeded tags stored as module constant for easy maintenance without editing prompt text.
Model name stored as constant per research recommendation for preview model management.
"""

from knowledge_hub.models.content import ContentType, ExtractedContent

# Gemini model constant -- update here when stable version releases
GEMINI_MODEL = "gemini-3-flash-preview"

# Seeded tag list covering all 11 categories plus cross-cutting themes (~55 tags)
SEEDED_TAGS = [
    # AI & Machine Learning
    "ai", "machine-learning", "deep-learning", "llms", "prompt-engineering",
    # Marketing
    "marketing", "content-marketing", "seo", "paid-acquisition", "email-marketing",
    # Product
    "product-management", "product-strategy", "user-research", "roadmapping",
    # Growth
    "growth", "growth-loops", "retention", "activation", "onboarding",
    # Analytics
    "analytics", "data-science", "experimentation", "metrics", "dashboards",
    # Engineering
    "engineering", "architecture", "devops", "api-design", "performance",
    # Design
    "design", "ux", "ui", "design-systems", "accessibility",
    # Business
    "business", "strategy", "fundraising", "pricing", "marketplace",
    # Career
    "career", "leadership", "management", "hiring", "mentoring",
    # Productivity
    "productivity", "automation", "workflows", "tools", "note-taking",
    # Cross-cutting themes
    "tutorial", "case-study", "research", "frameworks", "best-practices",
    "startup", "enterprise", "open-source", "trends",
]

_BASE_SYSTEM_PROMPT = """\
You are a knowledge base curator. Your job is to transform raw content into \
structured, actionable knowledge entries.

## Output Requirements

### Title
- Concise, descriptive title (not the original article title unless it's already good)
- Should tell a reader what they'll learn

### Summary (summary field)
- 3-5 sentences capturing the core argument, finding, or value
- Dense and informative -- every sentence should carry weight

### Category
Choose exactly one from: AI & Machine Learning, Marketing, Product, Growth, \
Analytics, Engineering, Design, Business, Career, Productivity, Other

### Priority
- High: Directly actionable, novel insights, high-signal content
- Medium: Useful reference material, solid but not immediately actionable
- Low: Tangential interest, thin content, or already-familiar ground

### Tags
Select 3-7 tags. Prefer tags from this list:
{seeded_tags}
Only suggest new tags for genuinely novel concepts not covered above. \
Tags must be lowercase, hyphenated.

### Summary Section (summary_section field)
- 3-5 sentence executive summary for the page body
- Can overlap with the summary field but optimized for reading within the full page

### Key Points (key_points field)
- 5-10 concrete, specific statements
- Ordered by importance to a practitioner, NOT by source appearance order
- Each should be self-contained and informative

### Key Learnings (key_learnings field)
- 3-7 structured learning blocks
- Each block has:
  - what: The insight or learning
  - why_it_matters: Why a practitioner should care
  - how_to_apply: Concrete, sequential steps to act on this (not "think about X" but "do X")

### Detailed Notes (detailed_notes field)
- Structured breakdown preserving source nuance
- Use markdown headers, bullet points, and emphasis
- Approximately 1500-2500 words depending on source depth
- Include section headers that reflect the source structure

## Tone
Professional, concise, actionable. Not academic, not casual.
"""

_VIDEO_ADDENDUM = """
## Video-Specific Instructions
- Include timestamp references in detailed notes where available \
(e.g., "At 5:23, the speaker discusses...")
- Note the video duration context in the summary
- Focus on spoken content from the transcript, not visual descriptions
"""

_SHORT_CONTENT_ADDENDUM = """
## Short Content Instructions
- Source is under 500 words. Produce proportionally shorter output.
- Skip the detailed_notes section (return empty string "").
- Reduce key_points to 3-5 items.
- Reduce key_learnings to 2-3 items.
"""


def build_system_prompt(content: ExtractedContent) -> str:
    """Build a content-type-specific system prompt.

    Starts with base prompt, then appends addenda based on content type
    and word count.

    Args:
        content: Extracted content with type and metadata.

    Returns:
        Assembled system prompt string with seeded tags injected.
    """
    prompt = _BASE_SYSTEM_PROMPT.format(seeded_tags=", ".join(SEEDED_TAGS))

    if content.content_type == ContentType.VIDEO:
        prompt += _VIDEO_ADDENDUM
    elif (content.word_count or 0) < 500:
        # Short content addendum applies to ANY content type under 500 words
        prompt += _SHORT_CONTENT_ADDENDUM

    return prompt


def build_user_content(content: ExtractedContent) -> str:
    """Build the user message from extracted content metadata and body.

    Assembles title, author, source domain as labeled metadata lines,
    then appends the content body separated by a divider.

    Args:
        content: Extracted content with text/transcript and metadata.

    Returns:
        Assembled user content string.
    """
    parts: list[str] = []

    if content.title:
        parts.append(f"Title: {content.title}")
    if content.author:
        parts.append(f"Author: {content.author}")
    if content.source_domain:
        parts.append(f"Source: {content.source_domain}")
    if content.user_note:
        parts.append(f"User Note: {content.user_note}")

    # Use transcript for videos, text for articles, description as fallback
    body = content.transcript or content.text or content.description or ""
    parts.append(f"\n---\n{body}")

    return "\n".join(parts)
