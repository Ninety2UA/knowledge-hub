# Phase 1: Project Foundation - Research

**Researched:** 2026-02-19
**Domain:** Python project scaffolding (FastAPI + Pydantic + uv + Docker)
**Confidence:** HIGH

## Summary

Phase 1 is pure infrastructure scaffolding: a FastAPI application skeleton with Pydantic data models, configuration loading, Docker image, health endpoint, and test infrastructure. No v1 requirements are addressed -- this phase establishes the runnable, testable foundation that Phases 2-7 build upon.

The standard stack is well-established and verified: FastAPI 0.129.0 for the web framework, Pydantic 2.12.x for data models, pydantic-settings 2.13.0 for configuration loading from environment variables and `.env` files, uv 0.10.4 for dependency management with `pyproject.toml`, and pytest with pytest-asyncio for testing. Docker uses `python:3.12-slim` as the base image with uv for dependency installation inside the container.

**Primary recommendation:** Use `uv init --package` with src layout (`src/knowledge_hub/`), pydantic-settings `BaseSettings` for config, FastAPI lifespan for startup events, and the optimized uv Docker pattern with intermediate dependency layers.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Data model design
- KnowledgeEntry mirrors the 10 Notion database properties exactly (Title, Category, Content Type, Source, Author/Creator, Date Added, Status, Priority, Tags, Summary). No processing metadata.
- SlackEvent carries extracted fields only: channel_id, timestamp, user_id, text, extracted_urls, user_note. No raw payload storage.
- ExtractedContent is a single model with optional fields (e.g., transcript is None for articles). One type flows through the pipeline.
- NotionPage uses structured section fields for the 4-section body (summary_section, key_points, key_learnings, detailed_notes) -- each section is independently typed and validated.

#### Development workflow
- Local Python first -- run with uvicorn locally for fast iteration. Docker is for CI/deployment verification only.
- uv for dependency management
- Python 3.12
- Plain pytest for testing (no watcher or auto-rerun)

#### Project layout
- Nested packages per domain: knowledge_hub/slack/, knowledge_hub/extraction/, knowledge_hub/llm/, knowledge_hub/notion/
- Top-level package named `knowledge_hub`
- src/ layout: src/knowledge_hub/
- Separate tests/ directory at project root, mirroring source structure

### Claude's Discretion
- ExtractedContent field names and which fields are optional vs required
- Config loading approach (pydantic-settings, dotenv, etc.)
- Docker base image and build strategy
- Exact health endpoint response format

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.

</user_constraints>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.129.0 | HTTP framework, health endpoint | Async-native, Pydantic v2 integration, lifespan events for startup/shutdown. Latest stable is 0.129.0 (Feb 2026). |
| Pydantic | >=2.12.0 | Data model validation | Already bundled with FastAPI. v2 is 5-50x faster than v1. Provides `BaseModel`, `Field`, enum validation, optional fields. |
| pydantic-settings | >=2.13.0 | Config loading from env vars + `.env` | Official Pydantic extension. `BaseSettings` reads env vars with `.env` file fallback. Env vars always take priority over dotenv values. |
| uvicorn | >=0.41.0 | ASGI server | Standard FastAPI production server. Latest is 0.41.0 (Feb 2026). Use `--host 0.0.0.0 --port 8080` for Cloud Run. |
| uv | >=0.10.4 | Dependency management | Replaces pip/pip-tools/poetry. 10-100x faster. Manages `pyproject.toml`, lockfile, virtual env. Rust-based. |

### Supporting (Dev Dependencies)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.0 | Test runner | Standard Python test runner. Use `def` test functions with `TestClient` for sync endpoint testing. |
| pytest-asyncio | >=1.0.0 | Async test support | Required if testing `async def` functions directly. **Breaking change in 1.0:** default mode is now `strict` (not `auto`), `event_loop` fixture removed. Set `asyncio_mode = "auto"` in pyproject.toml to auto-detect async tests. |
| httpx | >=0.28.0 | Async HTTP client / test transport | Already a FastAPI transitive dependency. Used for async test client via `ASGITransport`. |
| ruff | >=0.9.0 | Linter + formatter | Replaces flake8 + black + isort. 10-100x faster. Single tool. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pydantic-settings | python-dotenv only | python-dotenv only loads `.env` files -- no type validation, no defaults, no env var prefix support. pydantic-settings gives typed, validated config with `.env` support built in. |
| pydantic-settings | Manual `os.environ.get()` | Loses type safety, validation, defaults, and `.env` loading. Scattered config access throughout codebase. |
| uv | pip + pip-tools | Works but 10-100x slower. No lockfile by default. No virtual env management. uv replaces the entire toolchain. |
| ruff | flake8 + black + isort | Three separate tools, three configs, 10-100x slower. ruff replaces all three. |

### Installation

```bash
# Initialize project with uv (src layout, packaged)
uv init --package knowledge-hub

# Core dependencies
uv add fastapi uvicorn pydantic-settings

# Dev dependencies
uv add --dev pytest pytest-asyncio httpx ruff
```

## Architecture Patterns

### Recommended Project Structure

The user has locked the project layout. The structure below follows the decisions exactly: `src/` layout with nested packages per domain, separate `tests/` directory mirroring source structure.

```
knowledge-hub/
├── pyproject.toml            # Project metadata, dependencies, tool config
├── uv.lock                   # Lockfile (auto-generated by uv)
├── .python-version           # Python 3.12 (auto-generated by uv)
├── Dockerfile                # Production container image
├── .env.example              # Template for local env vars
├── .dockerignore             # Exclude .venv, .git, tests, etc.
├── src/
│   └── knowledge_hub/
│       ├── __init__.py       # Package root
│       ├── app.py            # FastAPI app creation + lifespan
│       ├── config.py         # pydantic-settings BaseSettings
│       ├── models/
│       │   ├── __init__.py   # Re-export all models
│       │   ├── slack.py      # SlackEvent model
│       │   ├── content.py    # ExtractedContent model + ContentType enum
│       │   ├── knowledge.py  # KnowledgeEntry model
│       │   └── notion.py     # NotionPage model
│       ├── slack/
│       │   └── __init__.py   # Empty for Phase 1 (populated in Phase 2)
│       ├── extraction/
│       │   └── __init__.py   # Empty for Phase 1 (populated in Phase 3)
│       ├── llm/
│       │   └── __init__.py   # Empty for Phase 1 (populated in Phase 4)
│       └── notion/
│           └── __init__.py   # Empty for Phase 1 (populated in Phase 5)
└── tests/
    ├── __init__.py
    ├── conftest.py           # Shared fixtures (TestClient, settings override)
    ├── test_health.py        # Health endpoint test
    └── test_models/
        ├── __init__.py
        ├── test_slack.py     # SlackEvent validation tests
        ├── test_content.py   # ExtractedContent validation tests
        ├── test_knowledge.py # KnowledgeEntry validation tests
        └── test_notion.py    # NotionPage validation tests
```

**Key structure decisions:**
- `models/` is a sub-package under `knowledge_hub/` (not a top-level domain package) because models are shared across all domains. Domain packages (`slack/`, `extraction/`, `llm/`, `notion/`) import from `models/`.
- `app.py` not `main.py` -- avoids ambiguity with uvicorn's module path: `uvicorn knowledge_hub.app:app`.
- Domain packages are empty `__init__.py` stubs in Phase 1. They establish the import structure that Phases 2-7 populate.

### Pattern 1: FastAPI App with Lifespan

**What:** Create the FastAPI app using the modern lifespan context manager (replaces deprecated `on_startup`/`on_shutdown`).
**When to use:** Always for FastAPI apps that need startup/shutdown logic.

```python
# src/knowledge_hub/app.py
# Source: FastAPI official docs (fastapi.tiangolo.com/advanced/events/)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from knowledge_hub.config import get_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load config, validate connections
    settings = get_settings()
    app.state.settings = settings
    yield
    # Shutdown: cleanup if needed

app = FastAPI(
    title="Knowledge Hub",
    lifespan=lifespan,
)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

### Pattern 2: pydantic-settings Configuration

**What:** Use `BaseSettings` to load config from environment variables with `.env` file fallback and type validation.
**When to use:** Always for application configuration.

```python
# src/knowledge_hub/config.py
# Source: pydantic-settings docs (github.com/pydantic/pydantic-settings)
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Slack
    slack_bot_token: str = ""
    slack_signing_secret: str = ""

    # Notion
    notion_api_key: str = ""
    notion_database_id: str = ""

    # Gemini
    gemini_api_key: str = ""

    # App
    environment: str = "development"
    log_level: str = "INFO"
    port: int = 8080

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Key behaviors verified (HIGH confidence):**
- Environment variables always take priority over `.env` file values.
- If `.env` file does not exist, no error is raised -- only env vars are used.
- Fields with defaults (like `environment: str = "development"`) are optional in env.
- Fields without defaults (none in Phase 1, but will exist later) cause `ValidationError` if missing.

### Pattern 3: Pydantic Models with Enums and Optional Fields

**What:** Define data models using Pydantic v2 `BaseModel` with `str, Enum` for type-safe string enums and `| None` for optional fields.
**When to use:** For all four data models in Phase 1.

```python
# Source: Pydantic v2 docs (docs.pydantic.dev)
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl

class ContentType(str, Enum):
    ARTICLE = "article"
    VIDEO = "video"
    NEWSLETTER = "newsletter"
    PODCAST = "podcast"
    THREAD = "thread"
    LINKEDIN_POST = "linkedin_post"
    PDF = "pdf"

class Category(str, Enum):
    AI_ML = "AI & Machine Learning"
    MARKETING = "Marketing"
    # ... 11 fixed options from CLAUDE.md

class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class Status(str, Enum):
    NEW = "New"
    REVIEWED = "Reviewed"
    APPLIED = "Applied"
    ARCHIVED = "Archived"
```

### Pattern 4: TestClient for Sync Endpoint Testing

**What:** Use FastAPI's `TestClient` (wraps Starlette's, based on httpx) for synchronous endpoint testing. Test functions are plain `def`, not `async def`.
**When to use:** For testing HTTP endpoints like `/health`.

```python
# Source: FastAPI testing docs (fastapi.tiangolo.com/tutorial/testing/)
from fastapi.testclient import TestClient
from knowledge_hub.app import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
```

### Anti-Patterns to Avoid

- **Using `on_startup`/`on_shutdown` instead of `lifespan`:** Deprecated in FastAPI. The lifespan context manager is the current standard.
- **Calling `os.environ` directly for config:** Loses type safety, defaults, validation, and `.env` support. Use pydantic-settings.
- **Putting models in `__init__.py`:** Makes files large and imports confusing. One model file per model concept.
- **Using `async def` test functions with TestClient:** TestClient is sync-based. Use plain `def` test functions. If you need async tests, use `httpx.AsyncClient` with `ASGITransport` instead.
- **Forgetting `__init__.py` in test directories:** pytest discovers tests via `__init__.py` in the src layout. Without them, imports fail.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config loading from env vars | Custom `os.environ.get()` with type casting | `pydantic-settings` `BaseSettings` | Handles type coercion, validation, defaults, `.env` files, and env var priority in one class. |
| Dependency management + lockfile | Manual `requirements.txt` + `pip freeze` | `uv` with `pyproject.toml` + `uv.lock` | Lockfile ensures reproducible builds. uv resolves, installs, and manages venvs 10-100x faster. |
| Linting + formatting | Separate flake8 + black + isort configs | `ruff` | Single tool, single config section in `pyproject.toml`, 10-100x faster. |
| HTTP testing | Manual `requests` calls to running server | FastAPI `TestClient` | In-process testing without starting a server. Automatic lifespan handling when used as context manager. |

**Key insight:** Phase 1 is scaffolding. Every component has a well-established standard solution. The risk is not choosing the wrong tool -- it is over-engineering the scaffold by adding features that belong in later phases.

## Common Pitfalls

### Pitfall 1: pytest-asyncio 1.0 Breaking Changes
**What goes wrong:** Tests fail with `PytestUnhandledCoroutineWarning` or async fixtures silently do not run.
**Why it happens:** pytest-asyncio 1.0 (May 2025) changed the default mode from `auto` to `strict`. In `strict` mode, async test functions must be explicitly marked with `@pytest.mark.asyncio`. The `event_loop` fixture was also removed entirely.
**How to avoid:** Set `asyncio_mode = "auto"` in `pyproject.toml` under `[tool.pytest.ini_options]`. This restores the behavior where all async test functions are automatically detected.
**Warning signs:** Async tests appearing to pass but not actually executing, or pytest warnings about unhandled coroutines.

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### Pitfall 2: uv src Layout Import Failures
**What goes wrong:** `ModuleNotFoundError: No module named 'knowledge_hub'` when running pytest or uvicorn.
**Why it happens:** In a `src/` layout, the package is not on `sys.path` by default. The package must be installed (editable or not) into the virtual environment.
**How to avoid:** uv handles this automatically when you run `uv sync` -- it installs the project in editable mode. Always run `uv sync` after init and after any `pyproject.toml` changes. Use `uv run pytest` or `uv run uvicorn ...` to ensure the correct venv is active.
**Warning signs:** Import errors that work in one terminal but not another (venv not activated).

### Pitfall 3: Docker .venv Leaking Into Image
**What goes wrong:** Docker build copies the local `.venv/` directory into the image, causing platform-specific binary incompatibilities or bloated images.
**Why it happens:** `COPY . /app` without a `.dockerignore` includes everything.
**How to avoid:** Create a `.dockerignore` file excluding `.venv/`, `.git/`, `tests/`, `__pycache__/`, and `.env`.
**Warning signs:** Docker image is unexpectedly large (>500MB), or runtime errors about incompatible binaries.

### Pitfall 4: Forgetting pyproject.toml Build System for src Layout
**What goes wrong:** `uv sync` fails or the package is not importable despite correct directory structure.
**Why it happens:** A `src/` layout requires a build system declaration in `pyproject.toml`. Without `[build-system]`, uv cannot install the package into the venv.
**How to avoid:** Ensure `pyproject.toml` has the `[build-system]` section. Using `uv init --package` generates this automatically.
**Warning signs:** `uv sync` succeeds but `import knowledge_hub` fails.

```toml
[build-system]
requires = ["uv_build>=0.10.2,<0.11.0"]
build-backend = "uv_build"
```

### Pitfall 5: pydantic-settings Requiring All Fields at Import Time
**What goes wrong:** Application crashes on import because a `BaseSettings` instance is created at module level and required env vars are missing.
**Why it happens:** If `Settings()` is called at module level (not inside a function or cached getter), it validates immediately. During testing or local dev, required env vars may not be set.
**How to avoid:** Use a `get_settings()` function with `@lru_cache`. Create the `Settings` instance lazily, not at module level. Give all fields sensible defaults for local development (empty strings for API keys -- they will fail at usage time, not at import time).
**Warning signs:** `ValidationError` during `import knowledge_hub.config` before any app code runs.

## Code Examples

### Complete pyproject.toml

```toml
# Source: uv docs (docs.astral.sh/uv/concepts/projects/init/)
[project]
name = "knowledge-hub"
version = "0.1.0"
description = "Slack-to-Notion knowledge base automation pipeline"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.129.0",
    "uvicorn[standard]>=0.41.0",
    "pydantic-settings>=2.13.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=1.0.0",
    "httpx>=0.28.0",
    "ruff>=0.9.0",
]

[build-system]
requires = ["uv_build>=0.10.2,<0.11.0"]
build-backend = "uv_build"

[tool.pytest.ini_options]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

### Complete Dockerfile (Optimized for uv)

```dockerfile
# Source: uv Docker guide (docs.astral.sh/uv/guides/integration/docker)
FROM python:3.12-slim

# Install uv (pinned version for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /uvx /bin/

# Set environment variables
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1

WORKDIR /app

# Install dependencies first (layer caching -- deps change less often than code)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy project source
COPY . /app

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Add venv to PATH so we don't need `uv run`
ENV PATH="/app/.venv/bin:$PATH"

# Cloud Run sets PORT env var (default 8080)
EXPOSE 8080
CMD ["uvicorn", "knowledge_hub.app:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Health Endpoint Response Format

```python
# Recommendation (Claude's Discretion area)
@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run and local development."""
    return {
        "status": "ok",
        "service": "knowledge-hub",
        "version": "0.1.0",
    }
```

**Rationale:** Include `service` and `version` for operational identification. Cloud Run health checks only need a 200 status code, but additional fields help with debugging when multiple services are deployed. Keep it minimal -- no database connectivity checks in Phase 1 (no databases yet).

### ExtractedContent Field Design

```python
# Recommendation (Claude's Discretion area)
class ExtractedContent(BaseModel):
    """Content extracted from a URL. One model for all content types."""
    url: str                              # Original URL (always present)
    content_type: ContentType             # Detected content type (always present)
    title: str | None = None              # Page/video title
    author: str | None = None             # Author or channel name
    source_domain: str | None = None      # e.g., "youtube.com", "medium.com"
    text: str | None = None               # Main extracted body text / article content
    transcript: str | None = None         # YouTube transcript (None for articles)
    description: str | None = None        # Meta description or video description
    published_date: str | None = None     # Published date as string (formats vary)
    word_count: int | None = None         # Word count of extracted text
    duration_seconds: int | None = None   # Video duration (None for articles)
    extraction_method: str | None = None  # e.g., "trafilatura", "youtube-transcript-api"
    is_partial: bool = False              # True if paywall detected or extraction incomplete
```

**Rationale for optional vs required:**
- `url` and `content_type` are always known before extraction starts -- required.
- Everything else may or may not be available depending on content type and extraction success -- optional with `None` default.
- `transcript` is separate from `text` because YouTube content has both (description vs spoken words). For articles, `transcript` stays `None`.
- `is_partial` defaults to `False` (successful extraction assumed). Set to `True` for paywall detection (EXTRACT-06).
- `extraction_method` aids debugging and logging ("which extractor produced this?").

### .dockerignore

```
.venv/
.git/
.env
.env.*
__pycache__/
*.pyc
tests/
docs/
.planning/
.claude/
.DS_Store
*.egg-info/
dist/
build/
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `on_startup`/`on_shutdown` decorators | `lifespan` async context manager | FastAPI 0.93+ (2023) | Must use lifespan for new projects. Old decorators deprecated. |
| `pip` + `requirements.txt` | `uv` + `pyproject.toml` + `uv.lock` | 2024-2025 | uv is now the standard Python package manager. 10-100x faster, lockfile by default. |
| pytest-asyncio `auto` mode default | pytest-asyncio `strict` mode default | pytest-asyncio 1.0 (May 2025) | Must explicitly set `asyncio_mode = "auto"` in config if you want auto-detection. |
| `event_loop` fixture | Removed | pytest-asyncio 1.0 (May 2025) | Use `loop_scope` parameter on markers/fixtures instead. |
| flake8 + black + isort | ruff | 2023-2024 | ruff replaces all three. No reason to use separate tools anymore. |
| `python-dotenv` for config | `pydantic-settings` | pydantic-settings 2.0+ (2023) | pydantic-settings includes dotenv support natively. No need for separate python-dotenv. |
| Pydantic v1 `validator`, `root_validator` | Pydantic v2 `field_validator`, `model_validator` | Pydantic 2.0 (2023) | v2 syntax is required. FastAPI >=0.100 dropped v1 support. |
| `uv_build` not available | `uv_build` as build backend | uv 0.10+ (2026) | uv now has its own build backend. Can be used instead of `hatchling` or `setuptools`. |

**Deprecated/outdated:**
- `google-generativeai` SDK: Being superseded by `google-genai`. Not needed in Phase 1 but noted for Phase 4.
- `python-dotenv` as standalone: pydantic-settings includes this functionality.
- `pip-tools` / `pip-compile`: uv replaces the entire pip ecosystem.

## Open Questions

1. **pytest-asyncio version compatibility with pytest 8.x**
   - What we know: pytest-asyncio 1.0+ requires pytest >=8.0. Both are current.
   - What's unclear: Exact minimum pytest version for pytest-asyncio 1.3.0.
   - Recommendation: Pin `pytest>=8.0` and `pytest-asyncio>=1.0.0`. uv's resolver will catch incompatibilities.

2. **uv_build backend maturity**
   - What we know: `uv_build` was introduced recently (uv 0.10+). It works for src layout packages.
   - What's unclear: Whether `uv_build` has any edge cases compared to `hatchling` or `setuptools`.
   - Recommendation: Use `uv_build` since uv generates it by default with `--package`. It is the simplest option. Fall back to `hatchling` only if issues arise.

3. **`fastapi[standard]` vs `fastapi` + `uvicorn[standard]`**
   - What we know: `fastapi[standard]` bundles uvicorn and other extras. Installing them separately gives more control over versions.
   - What's unclear: Whether `fastapi[standard]` pins uvicorn to a specific version range.
   - Recommendation: Install `fastapi` and `uvicorn[standard]` separately for explicit version control. This avoids surprise upgrades through extras.

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/fastapi_tiangolo` - Lifespan setup, TestClient usage, testing patterns
- Context7 `/pydantic/pydantic-settings` - BaseSettings, `.env` file loading, SettingsConfigDict
- Context7 `/websites/astral_sh_uv` - Project init, src layout, Docker integration, dependency management
- Context7 `/llmstxt/pydantic_dev_llms-full_txt` - Pydantic v2 BaseModel, enum validation, optional fields, Field usage
- [uv Docker guide](https://docs.astral.sh/uv/guides/integration/docker) - Multi-stage builds, layer caching, environment variables
- [uv FastAPI guide](https://docs.astral.sh/uv/guides/integration/fastapi) - Project structure, Dockerfile, running
- [uv project init docs](https://docs.astral.sh/uv/concepts/projects/init/) - `--package` flag, src layout, pyproject.toml

### Secondary (MEDIUM confidence)
- [FastAPI PyPI](https://pypi.org/project/fastapi/) - Latest version 0.129.0 (Feb 12, 2026)
- [pydantic-settings PyPI](https://pypi.org/project/pydantic-settings/) - Latest version 2.13.0 (Feb 15, 2026)
- [uvicorn PyPI](https://pypi.org/project/uvicorn/) - Latest version 0.41.0 (Feb 16, 2026)
- [pytest-asyncio docs](https://pytest-asyncio.readthedocs.io/) - Default strict mode, configuration options
- [pytest-asyncio 1.0 migration guide](https://thinhdanggroup.github.io/pytest-asyncio-v1-migrate/) - Breaking changes documentation

### Tertiary (LOW confidence)
- None -- all findings verified with primary or secondary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are mature, well-documented, and versions verified via PyPI/WebSearch
- Architecture: HIGH - Project structure follows uv official patterns and user's locked decisions
- Pitfalls: HIGH - pytest-asyncio breaking changes verified via official changelog; uv Docker patterns from official docs
- Config approach: HIGH - pydantic-settings is the standard for FastAPI projects, verified via Context7

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (30 days -- stable ecosystem, no anticipated breaking changes)
