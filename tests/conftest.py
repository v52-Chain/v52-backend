"""
Test configuration and shared fixtures.

Tests run without live credentials.  Provider calls are mocked via respx.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Set environment before importing app modules.
os.environ.setdefault("V52_ENV", "development")
os.environ.setdefault("V52_RPC_URL", "")
os.environ.setdefault("V52_GRAPH_ENDPOINT", "")

from app.config import invalidate_settings
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Ensure settings cache is cleared between tests."""
    invalidate_settings()
    yield
    invalidate_settings()


@pytest.fixture()
def client() -> TestClient:
    """FastAPI test client."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def tmp_data_dir(tmp_path: Path) -> Path:
    """Temporary data directory for vault and case repository tests."""
    return tmp_path / "evidence_vault"
