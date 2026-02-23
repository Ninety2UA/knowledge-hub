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
You are a knowledge base curator for a performance marketing professional building AI expertise. \
Your job is to transform raw content into structured, actionable knowledge entries.

## Voice & Quality
- Clear, direct, second-person voice ("You can...", "The key insight is...")
- Depth over breadth: 3 deeply detailed learning blocks beats 7 shallow ones
- Process the ENTIRE content. Never hallucinate or invent information.
- If content is inaccessible, state what you could and couldn't access.
- If extracted content exceeds ~8,000 tokens, produce a truncated analysis and note the truncation in detailed_notes.

## Output Requirements

### Title
- Concise, descriptive title (not the original article title unless it's already good)
- Should tell a reader what they'll learn

### Author
- Extract the author or creator name from the content (byline, attribution, channel name, etc.)
- Return null if the author cannot be identified from the content

### Summary (summary field)
- 3-5 sentences for the database property
- Dense and informative -- every sentence should carry weight

### Category
Choose exactly one from: AI & Machine Learning, Marketing & Growth, Ad Tech & Media, \
Product & Strategy, Engineering & Development, Data & Analytics, \
Career & Professional Development, Productivity & Systems, Design & UX, \
Business & Finance, Miscellaneous
If unsure between categories, pick the one most aligned with actionable application \
for a performance marketing professional building AI expertise. Add the secondary as a tag.
Never create new Category options. Use "Miscellaneous" as catch-all.

### Priority
- High: Directly actionable for performance marketing or AI work. Contains specific \
frameworks, tools, or techniques implementable this week. Time-sensitive or competitive intelligence.
- Medium: Relevant and informative but requires adaptation. Good reference material. \
Builds foundational understanding.
- Low: General interest or tangentially related. Background knowledge, industry trends, \
inspirational content without immediate application.

### Tags
Select 3-7 tags. Prefer tags from this list:
{seeded_tags}
Only suggest new tags for genuinely novel concepts not covered above. \
Tags must be lowercase, hyphenated.

### Summary Section (summary_section field)
- 3-5 sentence executive summary for the page body
- Answer: What is this about? Why does it matter? What's the single most important takeaway?
- Reading ONLY this section should give 80% of the value

### Key Points (key_points field)
- 5-10 concrete, specific statements
- Second-person voice ("You can...", "The key insight is...")
- One clear, self-contained statement per point (1-2 sentences)
- Ordered by importance to a practitioner, NOT by source appearance order

### Key Learnings (key_learnings field)
**This is the most important section.** 3-7 structured learning blocks.
- Each block has:
  - title: Clear, specific title for the learning (e.g., "Mine Reddit for User Research Using Perplexity's Discussion Filter")
  - what: 2-3 sentences explaining the concept/framework/insight
  - why_it_matters: 1-2 sentences on relevance for performance marketing / AI / tech
  - how_to_apply: Steps must be:
    - CONCRETE ("open [tool], go to [section], do [action]") — not vague ("think about X")
    - SEQUENTIAL — numbered in execution order
    - SELF-CONTAINED — followable without the original content
    - CONTEXT-SPECIFIC — reference real tools (Google Ads, BigQuery, Claude, Notion, etc.)
    - TIME-ESTIMATED — rough time per step in parentheses (e.g., "Open Perplexity and enter your query (~1 min)")
  - resources_needed: Specific tools, accounts, or prerequisites (e.g., "Perplexity (free tier works, Pro recommended)")
  - estimated_time: Total implementation duration (e.g., "10-15 minutes")

### Detailed Notes (detailed_notes field)
- Structured breakdown preserving source nuance
- Use markdown: ## for section headers, ### for subsections, - for bullet points, **bold** for emphasis
- Cap at ~2,500 words depending on source depth
- Capture: numbers, frameworks, tools mentioned, people referenced, companies discussed
"""

_VIDEO_ADDENDUM = """
## Video/Podcast-Specific Instructions
- Structure detailed_notes as section-by-section summaries with timestamp ranges \
as subheadings (e.g., "### Using Perplexity for Research (6:15-11:19)")
- Include key examples and data points from each section
- Focus on spoken content from the transcript, not visual descriptions
- For videos over 45 minutes: use structured section summaries, not transcript reproduction
"""

_ARTICLE_ADDENDUM = """
## Article/Blog-Specific Instructions
- Structure detailed_notes as section breakdown with paraphrased key quotes + annotations
- Capture key arguments, examples, and data points from each section
"""

_THREAD_ADDENDUM = """
## Thread-Specific Instructions
- Structure detailed_notes as argument flow with commentary
- Preserve the thread's logical progression
"""

_NEWSLETTER_ADDENDUM = """
## Newsletter-Specific Instructions
- Structure detailed_notes as topic-by-topic breakdown
- Cover each topic section distinctly
"""

_SHORT_CONTENT_ADDENDUM = """
## Short Content Instructions
- Source is under 500 words. Produce proportionally shorter output.
- Never skip sections. If a section is N/A, write "N/A — [reason]."
- For detailed_notes, write "N/A — source content too brief for detailed breakdown."
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

    # Short content override takes priority
    if (content.word_count or 0) < 500:
        prompt += _SHORT_CONTENT_ADDENDUM
        return prompt

    # Content-type-specific addenda
    if content.content_type in (ContentType.VIDEO, ContentType.PODCAST):
        prompt += _VIDEO_ADDENDUM
    elif content.content_type == ContentType.THREAD:
        prompt += _THREAD_ADDENDUM
    elif content.content_type == ContentType.NEWSLETTER:
        prompt += _NEWSLETTER_ADDENDUM
    elif content.content_type == ContentType.ARTICLE:
        prompt += _ARTICLE_ADDENDUM

    return prompt


def build_user_content(content: ExtractedContent) -> list | str:
    """Build the user message from extracted content metadata and body.

    Assembles title, author, source domain as labeled metadata lines,
    then appends the content body separated by a divider.

    For YouTube videos without a transcript (e.g., cloud IP blocked),
    returns a list of Parts including the video URL as FileData so
    Gemini can process the video natively.

    Args:
        content: Extracted content with text/transcript and metadata.

    Returns:
        Assembled user content string, or list of Parts for video inputs.
    """
    from google.genai import types

    metadata_parts: list[str] = []

    if content.title:
        metadata_parts.append(f"Title: {content.title}")
    if content.author:
        metadata_parts.append(f"Author: {content.author}")
    if content.source_domain:
        metadata_parts.append(f"Source: {content.source_domain}")
    if content.user_note:
        metadata_parts.append(f"User Note: {content.user_note}")

    # If YouTube video has no transcript, pass the URL directly to Gemini
    # for native video processing (e.g., when transcript API is IP-blocked)
    if content.content_type == ContentType.VIDEO and not content.transcript:
        metadata_text = "\n".join(metadata_parts)
        desc_text = f"\nDescription: {content.description}" if content.description else ""
        return [
            types.Part(
                file_data=types.FileData(file_uri=content.url)
            ),
            types.Part(
                text=f"{metadata_text}{desc_text}\n\n---\nPlease analyze this video."
            ),
        ]

    # Use transcript for videos, text for articles, description as fallback
    body = content.transcript or content.text or content.description or ""
    metadata_parts.append(f"\n---\n{body}")

    return "\n".join(metadata_parts)
