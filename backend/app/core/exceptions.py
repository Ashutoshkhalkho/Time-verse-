from datetime import UTC, datetime
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import logger


class AppException(Exception):
    """Base application exception producing RFC 7807 Problem Details."""

    def __init__(
        self,
        title: str,
        detail: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_SERVER_ERROR",
        errors: list[dict[str, Any]] | None = None,
    ):
        super().__init__(detail)
        self.title = title
        self.detail = detail
        self.status_code = status_code
        self.code = code
        self.errors = errors or []


class NotFoundException(AppException):
    def __init__(self, detail: str, code: str = "RESOURCE_NOT_FOUND"):
        super().__init__(
            title="Resource Not Found",
            detail=detail,
            status_code=status.HTTP_404_NOT_FOUND,
            code=code,
        )


class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Authentication credentials required", code: str = "UNAUTHORIZED"):
        super().__init__(
            title="Unauthorized",
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=code,
        )


class ForbiddenException(AppException):
    def __init__(self, detail: str = "Permission denied", code: str = "FORBIDDEN"):
        super().__init__(
            title="Forbidden",
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN,
            code=code,
        )


class ConflictException(AppException):
    def __init__(self, detail: str, code: str = "RESOURCE_CONFLICT"):
        super().__init__(
            title="Resource Conflict",
            detail=detail,
            status_code=status.HTTP_409_CONFLICT,
            code=code,
        )


class HardConstraintViolationException(AppException):
    def __init__(self, detail: str, conflicts: list[dict[str, Any]] | None = None):
        super().__init__(
            title="Hard Constraint Violation",
            detail=detail,
            status_code=status.HTTP_409_CONFLICT,
            code="HARD_CONSTRAINT_VIOLATION",
            errors=conflicts,
        )


class ValidationException(AppException):
    def __init__(self, detail: str, code: str = "VALIDATION_ERROR", errors: list[dict[str, Any]] | None = None):
        super().__init__(
            title="Validation Error",
            detail=detail,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=code,
            errors=errors,
        )



def create_problem_response(
    status_code: int,
    title: str,
    detail: str,
    instance: str,
    code: str,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    """Builds RFC 7807 compliant problem response dictionary."""
    content: dict[str, Any] = {
        "type": f"https://timewise.internal/errors/{code.lower().replace('_', '-')}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "code": code,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if errors:
        content["errors"] = errors

    return JSONResponse(status_code=status_code, content=content)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    logger.warning(
        "Application exception occurred",
        extra={
            "path": request.url.path,
            "status_code": exc.status_code,
            "code": exc.code,
            "detail": exc.detail,
        },
    )
    return create_problem_response(
        status_code=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        instance=request.url.path,
        code=exc.code,
        errors=exc.errors,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(item) for item in err.get("loc", []))
        errors.append({
            "field": loc,
            "message": err.get("msg", "Validation error"),
            "type": err.get("type", "value_error"),
        })

    logger.info(
        "Request validation failed",
        extra={
            "path": request.url.path,
            "error_count": len(errors),
            "errors": errors,
        },
    )

    return create_problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Unprocessable Entity",
        detail="Request payload or parameters failed validation.",
        instance=request.url.path,
        code="VALIDATION_ERROR",
        errors=errors,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return create_problem_response(
        status_code=exc.status_code,
        title="HTTP Error",
        detail=str(exc.detail),
        instance=request.url.path,
        code=f"HTTP_{exc.status_code}",
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled server exception",
        exc_info=exc,
        extra={"path": request.url.path},
    )
    return create_problem_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail="An unexpected server error occurred. Please contact system support.",
        instance=request.url.path,
        code="INTERNAL_SERVER_ERROR",
    )
