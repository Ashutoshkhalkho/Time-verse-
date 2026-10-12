from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRoleEnum


class LoginRequest(BaseModel):
    email: EmailStr = Field(description="User login email address")
    password: str = Field(min_length=6, description="User password")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(description="Valid refresh token string")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    refresh_token: str | None = None
    refresh_expires_at: str | None = None


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRoleEnum
    institution_id: str
    department_ids: list[str]
    section_ids: list[str]
    permissions: list[str]
    is_active: bool


class LoginResponse(BaseModel):
    tokens: TokenResponse
    user: UserProfileResponse
