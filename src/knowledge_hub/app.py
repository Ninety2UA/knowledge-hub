"""FastAPI application with lifespan and health endpoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from knowledge_hub.config import get_settings
from knowledge_hub.slack.router import router as slack_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: load config on startup, cleanup on shutdown."""
    settings = get_settings()
    app.state.settings = settings
    yield


app = FastAPI(
    title="Knowledge Hub",
    lifespan=lifespan,
)
app.include_router(slack_router)


@app.get("/health")
async def health():
    """Health check endpoint for Cloud Run and local development."""
    return {
        "status": "ok",
        "service": "knowledge-hub",
        "version": "0.1.0",
    }
