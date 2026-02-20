"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient

from knowledge_hub.app import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Create a TestClient for the FastAPI app."""
    return TestClient(app)
