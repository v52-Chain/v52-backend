"""
Vector52 FastAPI application.

Starts the API server with:
  - /healthz (no auth)
  - /v1/claim-audit
  - /v1/cases/{case_id}
  - /v1/cases/{case_id}/evidence
  - /v1/cases/{case_id}/package
  - /v1/verify
  - /docs (OpenAPI)

Rules:
  - No secrets in log output (settings.safe_repr() is used).
  - CORS uses an explicit allowlist from configuration.
  - In development, localhost frontend origins are also enabled.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import audits, cases, claim_audit, health, providers, rpc, verify
from app.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
# Provider URLs may contain API keys in their path. Keep transport loggers quiet;
# Vector52 emits its own redacted acquisition events instead.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Log configuration summary on startup (secrets redacted)."""
    settings = get_settings()
    logger.info("Vector52 backend starting — config: %s", settings.safe_repr())
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    yield
    logger.info("Vector52 backend shutting down.")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Vector52 API",
        description=(
            "Evidence-first Ethereum claim auditor. "
            "Don't just trace the money. Prove the claim."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Browser origins are explicit. Production commonly serves the PWA and API
    # from different hosts (for example Vercel + a Python host), so the allowlist
    # comes from V52_CORS_ORIGINS instead of assuming a same-origin deployment.
    development_origins = [
        "http://localhost:5173",  # Vite default
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
    allowed_origins = list(
        dict.fromkeys(
            ([] if settings.is_production else development_origins) + settings.cors_origins
        )
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Content-Type",
            "Accept",
            "Payment-Signature",
            "Payment-Required",
            "X-Payment",
        ],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(providers.router)
    app.include_router(rpc.router)
    app.include_router(audits.router)
    app.include_router(claim_audit.router)
    app.include_router(cases.router)
    app.include_router(verify.router)

    # ── Global error handler — never expose stack traces in production ─────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal error occurred. No secrets were exposed."},
        )

    return app


app = create_app()
