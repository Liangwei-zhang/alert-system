from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SendCodeRequest(BaseModel):
    email: EmailStr


class SendCodeResponse(BaseModel):
    message: str
    dev_code: str | None = None


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    locale: str | None = None
    timezone: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutResponse(BaseModel):
    message: str


class AuthUserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str | None = None
    plan: str
    locale: str
    timezone: str
    is_new: bool


class AuthSessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: AuthUserResponse
