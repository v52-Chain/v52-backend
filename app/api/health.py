"""
GET /healthz — health check endpoint.

Returns {"status": "ok", "version": "0.1.0"} when the application is running.
This endpoint is used by Docker healthchecks and monitoring.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

APP_VERSION = "0.1.0"


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get(
    "/healthz",
    response_model=HealthResponse,
    summary="Health check",
    tags=["system"],
)
async def healthz() -> HealthResponse:
    """
    Returns application health status and version.
    Always returns 200 when the process is alive.
    """
    return HealthResponse(status="ok", version=APP_VERSION)
