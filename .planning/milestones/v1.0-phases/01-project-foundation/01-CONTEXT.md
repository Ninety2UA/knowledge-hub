# Phase 1: Project Foundation - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Runnable, testable FastAPI application skeleton that all subsequent phases build upon. Includes data models, config loading, Docker image, health endpoint, and test infrastructure. No v1 requirements are addressed here -- this is pure scaffolding.

</domain>

<decisions>
## Implementation Decisions

### Data model design
- KnowledgeEntry mirrors the 10 Notion database properties exactly (Title, Category, Content Type, Source, Author/Creator, Date Added, Status, Priority, Tags, Summary). No processing metadata.
- SlackEvent carries extracted fields only: channel_id, timestamp, user_id, text, extracted_urls, user_note. No raw payload storage.
- ExtractedContent is a single model with optional fields (e.g., transcript is None for articles). One type flows through the pipeline.
- NotionPage uses structured section fields for the 4-section body (summary_section, key_points, key_learnings, detailed_notes) -- each section is independently typed and validated.

### Development workflow
- Local Python first -- run with uvicorn locally for fast iteration. Docker is for CI/deployment verification only.
- uv for dependency management
- Python 3.12
- Plain pytest for testing (no watcher or auto-rerun)

### Project layout
- Nested packages per domain: knowledge_hub/slack/, knowledge_hub/extraction/, knowledge_hub/llm/, knowledge_hub/notion/
- Top-level package named `knowledge_hub`
- src/ layout: src/knowledge_hub/
- Separate tests/ directory at project root, mirroring source structure

### Claude's Discretion
- ExtractedContent field names and which fields are optional vs required
- Config loading approach (pydantic-settings, dotenv, etc.)
- Docker base image and build strategy
- Exact health endpoint response format

</decisions>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 01-project-foundation*
*Context gathered: 2026-02-19*
