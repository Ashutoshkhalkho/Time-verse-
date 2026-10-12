from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", example="ok")
    app_name: str = Field(default="Timeverse", example="Timeverse")
    version: str = Field(default="0.1.0", example="0.1.0")
    environment: str = Field(default="development", example="development")
    timestamp: datetime = Field(description="Current UTC timestamp")


class ReadinessResponse(HealthResponse):
    database_connected: bool = Field(description="True if database connection ping succeeded")
    redis_connected: bool = Field(default=False, description="True if Redis ping succeeded")
