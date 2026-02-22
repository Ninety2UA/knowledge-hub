# Phase 4: LLM Processing - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform extracted content (from Phase 3) into structured, actionable knowledge entries via Gemini. Produces a 4-section page body, assigns category/tags/priority, and validates output against Pydantic schema. Does NOT create Notion pages (Phase 5) or handle notifications (Phase 6).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

User deferred all implementation decisions. Claude has full flexibility on the following areas:

**Priority criteria:**
- High: Directly actionable for current work/goals, novel insights, high-signal content
- Medium: Useful reference material, solid content but not immediately actionable
- Low: Tangential interest, thin content, or already-familiar ground
- Signal from extraction status: partial/metadata-only extractions default to Low unless title/description suggests otherwise

**Tagging strategy:**
- Seeded tag set derived from the 11 categories + common cross-cutting concerns (e.g., "strategy", "tutorial", "case-study", "research", "tools", "frameworks")
- 3-7 tags per entry — enough for discoverability, not so many they lose meaning
- Conservative on new tags: only suggest genuinely new concepts not covered by existing tags
- Tags should be lowercase, hyphenated (e.g., "prompt-engineering", "growth-loops")

**Output voice & depth:**
- Professional, concise, actionable tone — not academic, not casual
- Summary: dense 3-5 sentences capturing the core argument/finding
- Key Points: concrete statements, not vague observations. Ordered by importance to a practitioner
- Key Learnings: practical, specific How-to-apply steps (not "think about X" but "do X")
- Detailed Notes: structured breakdown preserving source nuance. ~1500-2500 words depending on source depth

**Content-type handling:**
- Articles: standard processing, section headers from source structure
- Videos: include timestamp references in detailed notes where available, note video duration context
- Newsletters: treat as article, extract the substantive content (skip promotional sections)
- PDFs: treat as article
- Threads/LinkedIn posts: shorter output proportional to source length, skip detailed notes if source is < 500 words

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Models already define structure constraints:
- `NotionPage.summary_section`: 3-5 sentence executive summary
- `NotionPage.key_points`: 5-10 numbered statements, importance-ordered
- `NotionPage.key_learnings`: 3-7 structured blocks (What / Why / How to apply)
- `NotionPage.detailed_notes`: ~2500 word cap

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-llm-processing*
*Context gathered: 2026-02-20*
