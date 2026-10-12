from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRoleEnum


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Initial account password")
    full_name: str = Field(min_length=2)
    phone: str | None = None
    role: UserRoleEnum
    department_ids: list[str] = Field(default_factory=list)
    section_ids: list[str] = Field(default_factory=list)


class UserUpdateRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    role: UserRoleEnum | None = None
    is_active: bool | None = None
    department_ids: list[str] | None = None
    section_ids: list[str] | None = None


class UserDetailResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str | None
    role: UserRoleEnum
    institution_id: str
    is_active: bool
    department_ids: list[str]
    section_ids: list[str]
    created_at: str


class AuditLogResponse(BaseModel):
    id: str
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str
    before_state: dict | None
    after_state: dict | None
    reason: str | None
    ip_address: str | None
    created_at: str
