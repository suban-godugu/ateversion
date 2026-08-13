from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.rbac import Role


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    username: str
    user_id: str
    expires_in_minutes: int


class UserOut(BaseModel):
    user_id: str
    username: str
    full_name: str
    role: Role
    permissions: list[str]
