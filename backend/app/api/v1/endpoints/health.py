from datetime import UTC, datetime

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.db.session import check_database_connection
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["Health & Diagnostics"])


@router.get(
    "/healthz",
    response_model=HealthResponse,
    summary="Liveness Probe",
    description="Returns 200 OK if the FastAPI process is running.",
)
async def liveness() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.APP_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/healthz/ready",
    response_model=ReadinessResponse,
    summary="Readiness Probe",
    description="Verifies that the database pool is reachable before accepting traffic.",
)
async def readiness(response: Response) -> ReadinessResponse:
    db_ok = await check_database_connection()

    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ok" if db_ok else "unhealthy",
        app_name=settings.APP_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(UTC),
        database_connected=db_ok,
        redis_connected=False,  # Will integrate with redis client in M2
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="API Health Check",
    description="Standard health check alias under API prefix.",
)
async def health_alias() -> HealthResponse:
    return await liveness()
