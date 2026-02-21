"""FastAPI application with lifespan and health endpoint."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request

from knowledge_hub.config import get_settings
from knowledge_hub.digest import check_daily_cost, send_weekly_digest
from knowledge_hub.logging_config import configure_logging
from knowledge_hub.slack.router import router as slack_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: configure logging and load config on startup."""
    configure_logging()
    settings = get_settings()
    app.state.settings = settings
    yield


app = FastAPI(
    title="Knowledge Hub",
    lifespan=lifespan,
)
app.include_router(slack_router)


async def verify_scheduler(request: Request) -> None:
    """Verify the scheduler secret header for protected endpoints.

    Compares the X-Scheduler-Secret header against the configured secret.
    Raises HTTPException 403 if the header is missing, empty, or mismatched.
    """
    settings = get_settings()
    secret = request.headers.get("X-Scheduler-Secret", "")
    if not settings.scheduler_secret or secret != settings.scheduler_secret:
        raise HTTPException(status_code=403, detail="Invalid scheduler secret")


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run and local development."""
    return {
        "status": "ok",
        "service": "knowledge-hub",
        "version": "0.1.0",
    }


@app.post("/digest")
async def digest_endpoint(_: None = Depends(verify_scheduler)):
    """Trigger weekly digest: query Notion, build summary, send Slack DM."""
    result = await send_weekly_digest()
    return result


@app.post("/cost-check")
async def cost_check_endpoint(_: None = Depends(verify_scheduler)):
    """Trigger daily cost check: alert if Gemini spend exceeds threshold."""
    result = await check_daily_cost()
    return result
