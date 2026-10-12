import enum
from typing import Any

from pydantic import BaseModel, Field


class EntityImportType(str, enum.Enum):
    TEACHERS = "teachers"
    ROOMS = "rooms"
    SUBJECTS = "subjects"
    REQUIREMENTS = "requirements"


class RowError(BaseModel):
    row_number: int
    field: str
    error_message: str
    value: Any = None


class ImportPreviewResponse(BaseModel):
    entity_type: EntityImportType
    total_rows: int
    valid_rows: int
    invalid_rows: int
    is_committable: bool
    errors: list[RowError] = Field(default_factory=list)
    preview_records: list[dict[str, Any]] = Field(default_factory=list)


class ImportCommitRequest(BaseModel):
    entity_type: EntityImportType
    department_id: str | None = None
    records: list[dict[str, Any]]


class ImportCommitResponse(BaseModel):
    entity_type: EntityImportType
    committed_count: int
    message: str
