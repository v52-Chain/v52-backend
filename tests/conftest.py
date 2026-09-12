"""
Test configuration and shared fixtures.

Tests exercise real Ethereum RPC and The Graph endpoints (no mocks). Values
come from the backend's local .env when present. Tests that need The Graph
API key skip themselves automatically when it isn't configured; no
credentials are hardcoded here or anywhere else in the test suite.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Load real environment from backend .env
_env_file = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_file)

# .env declares these keys even when left blank, so os.environ already has an
# empty string for them by this point — plain setdefault()/get(key, default)
# would never apply a fallback. Only fall back when the value is unset or empty.
os.environ.setdefault("V52_ENV", "development")
if not os.environ.get("V52_RPC_URL"):
    os.environ["V52_RPC_URL"] = "https://eth.drpc.org"
if not os.environ.get("V52_GRAPH_ENDPOINT"):
    os.environ["V52_GRAPH_ENDPOINT"] = (
        "https://gateway.thegraph.com/api/{api_key}/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
    )
# No fallback for V52_GRAPH_API_KEY: it's a secret and must come from .env or
# the environment. Graph-gateway tests skip themselves when it's absent.

from app.config import invalidate_settings  # noqa: E402 — must follow env setup above
from app.main import app  # noqa: E402


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
