import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.permissions import VALID_ROLES


def _validate_role(cls, v: str) -> str:
    if v not in VALID_ROLES:
        raise ValueError(f"Peran tidak valid. Pilihan: {', '.join(VALID_ROLES)}.")
    return v


VALID_PLATFORMS = ("instagram", "facebook", "tiktok")


def _validate_platform(cls, v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip().lower()
    if v not in VALID_PLATFORMS:
        raise ValueError(f"Platform tidak valid. Pilihan: {', '.join(VALID_PLATFORMS)}.")
    return v


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class OrganizationListItem(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    membership_status: str | None


class MembershipMini(BaseModel):
    status: str
    ends_at: datetime | None


class OrganizationDetail(BaseModel):
    id: uuid.UUID
    name: str
    membership: MembershipMini | None


class BrandCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    industry: str | None = Field(default=None, max_length=120)
    platform: str | None = Field(default=None, description="instagram | facebook | tiktok")

    _platform = field_validator("platform")(classmethod(_validate_platform))


class BrandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    platform: str | None
    display_name: str
    industry: str | None
    organization_id: uuid.UUID
    created_at: datetime


class MemberAdd(BaseModel):
    email: EmailStr
    role: str = Field(default="viewer")

    _role = field_validator("role")(classmethod(_validate_role))


class MemberOut(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    role: str


class MemberRoleUpdate(BaseModel):
    role: str

    _role = field_validator("role")(classmethod(_validate_role))
