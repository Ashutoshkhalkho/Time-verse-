from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.faculty_directory import ProfileStatusEnum


class FacultyMemberBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name preserving exact supplied spelling")
    designation: str | None = Field(default=None, max_length=255, description="Formal academic designation (nullable until verified)")
    department: str = Field(default="Department of Professional Management Studies", max_length=255)
    institution: str = Field(default="Kristu Jayanti University", max_length=255)
    faculty_id: str | None = Field(default=None, max_length=100)
    official_email: str | None = Field(default=None, max_length=255)
    profile_photo: str | None = Field(default=None, max_length=500)
    subjects_taught: list[str] = Field(default_factory=list)
    specialisation: str | None = Field(default=None, max_length=500)
    office_location: str | None = Field(default=None, max_length=255)
    profile_status: ProfileStatusEnum = Field(default=ProfileStatusEnum.PENDING_VERIFICATION)
    is_verified: bool = Field(default=False)
    source_notes: str | None = None
    verification_notes: str | None = None

    @field_validator("official_email")
    @classmethod
    def validate_email_format(cls, v: str | None) -> str | None:
        if v is not None and v.strip():
            v = v.strip()
            if "@" not in v or "." not in v.split("@")[-1]:
                raise ValueError("official_email must be a valid email format (e.g. name@kristujayanti.com)")
            return v
        return None


class FacultyMemberCreate(FacultyMemberBase):
    pass


class FacultyMemberUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    designation: str | None = None
    department: str | None = None
    institution: str | None = None
    faculty_id: str | None = None
    official_email: str | None = None
    profile_photo: str | None = None
    subjects_taught: list[str] | None = None
    specialisation: str | None = None
    office_location: str | None = None
    profile_status: ProfileStatusEnum | None = None
    source_notes: str | None = None
    verification_notes: str | None = None

    @field_validator("official_email")
    @classmethod
    def validate_email_format(cls, v: str | None) -> str | None:
        if v is not None and v.strip():
            v = v.strip()
            if "@" not in v or "." not in v.split("@")[-1]:
                raise ValueError("official_email must be a valid email format")
            return v
        return None


class FacultyMemberVerifyRequest(BaseModel):
    designation: str | None = Field(default=None, description="Verified formal designation (optional override)")
    verification_notes: str = Field(..., min_length=5, description="Administrative audit statement explaining verification basis")
    profile_status: ProfileStatusEnum = Field(default=ProfileStatusEnum.ACTIVE)
    acknowledged_responsibility: bool = Field(
        ...,
        description="Explicit administrator attestation that information has been checked against official university records",
    )

    @field_validator("acknowledged_responsibility")
    @classmethod
    def require_acknowledgement(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Administrator must acknowledge verification responsibility before marking profile as verified.")
        return v


class FacultyMemberArchiveRequest(BaseModel):
    confirmed: bool = Field(..., description="Confirmation flag required before archiving")
    reason: str | None = Field(default=None, description="Optional administrative reason for archiving")

    @field_validator("confirmed")
    @classmethod
    def require_confirmation(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Explicit confirmation is required to archive a faculty record.")
        return v


class FacultyMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    normalized_name: str
    designation: str | None
    department: str
    institution: str
    faculty_id: str | None
    official_email: str | None
    profile_photo: str | None
    subjects_taught: list[str]
    specialisation: str | None
    office_location: str | None
    profile_status: ProfileStatusEnum
    is_verified: bool
    source_notes: str | None
    verification_notes: str | None
    verified_by_user_id: str | None
    verified_by_name: str | None = None
    verified_at: datetime | None
    archived_at: datetime | None
    duplicate_flag: bool
    duplicate_notes: str | None
    potential_duplicate_of_id: str | None
    missing_fields: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CSVPreviewRow(BaseModel):
    row_number: int
    full_name: str
    raw_designation: str | None = None
    mapped_designation: str | None = None
    source_notes: str | None = None
    is_valid: bool = True
    validation_errors: list[str] = Field(default_factory=list)
    is_potential_duplicate: bool = False
    potential_duplicate_reason: str | None = None
    existing_member_id: str | None = None
    existing_member_name: str | None = None
    existing_is_verified: bool = False
    unrecognized_columns: dict[str, Any] = Field(default_factory=dict)


class CSVPreviewResponse(BaseModel):
    total_rows: int
    valid_rows_count: int
    invalid_rows_count: int
    potential_duplicates_count: int
    detected_headers: list[str]
    unrecognized_headers: list[str]
    rows: list[CSVPreviewRow]


class CSVCommitRow(BaseModel):
    full_name: str
    designation: str | None = None
    source_notes: str | None = None
    unrecognized_columns: dict[str, Any] = Field(default_factory=dict)


class CSVCommitRequest(BaseModel):
    confirmed: bool = Field(..., description="Confirmation flag required to execute commit")
    rows: list[CSVCommitRow]
    overwrite_verified: bool = Field(
        default=False,
        description="Whether to overwrite existing verified designations with CSV unverified values (defaults to False for safety)",
    )

    @field_validator("confirmed")
    @classmethod
    def require_confirmation(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Explicit administrator confirmation is required before committing CSV import.")
        return v


class CSVCommitResponse(BaseModel):
    total_processed: int
    created_count: int
    updated_count: int
    skipped_count: int
    rejected_count: int
    messages: list[str]
