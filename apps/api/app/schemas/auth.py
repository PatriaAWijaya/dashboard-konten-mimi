import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import get_settings


def _password_rules(cls, v: str) -> str:
    min_len = get_settings().PASSWORD_MIN_LENGTH
    if len(v) < min_len:
        raise ValueError(f"Kata sandi minimal {min_len} karakter.")
    return v


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str
    whatsapp: str | None = Field(default=None, max_length=30)

    _pw = field_validator("password")(classmethod(_password_rules))


class RegisterResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    message: str


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    is_superadmin: bool


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10)
    new_password: str

    _pw = field_validator("new_password")(classmethod(_password_rules))


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    whatsapp: str | None
    is_active: bool
    is_superadmin: bool
    email_verified: bool


class UpdateProfileRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    whatsapp: str | None = Field(default=None, max_length=30)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    _pw = field_validator("new_password")(classmethod(_password_rules))
