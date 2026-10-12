from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", "backend/.env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    APP_NAME: str = "Timeverse"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = Field(
        default="development-insecure-secret-key-that-must-be-changed-in-production-32chars",
        description="Cryptographic secret key for signing JWTs",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Networking & CORS
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///backend/timewise_dev.db",
        description="Async connection string for SQLAlchemy",
    )
    DATABASE_SYNC_URL: str = Field(
        default="sqlite:///backend/timewise_dev.db",
        description="Synchronous connection string for Alembic migrations",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    # Redis Cache & Broker
    REDIS_URL: str = "redis://localhost:6379/0"
    ALERT_DEDUPLICATION_WINDOW_SECONDS: int = 300

    # Optimization
    SOLVER_TIMEOUT_SECONDS: int = 60
    SOLVER_MAX_SEARCH_WORKERS: int = 8

    # AI Assistant & LLM Integration (Optional)
    GEMINI_API_KEY: str | None = Field(
        default=None,
        description="Google Gemini API key for natural language explanation enhancement. Core scheduling runs locally via OR-Tools CP-SAT.",
    )
    GEMINI_MODEL: str = Field(
        default="gemini-flash-latest",
        description="Google Gemini model identifier",
    )

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"

    # Institutional Defaults
    DEFAULT_PERIOD_DURATION_MINUTES: int = 50
    DEFAULT_PERIODS_PER_DAY: int = 7
    DEFAULT_MAX_FACULTY_CONSECUTIVE_HOURS: int = 3
    DEFAULT_MAX_FACULTY_DAILY_LOAD: int = 5

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
        return v if isinstance(v, list) else ["*"]


settings = Settings()
