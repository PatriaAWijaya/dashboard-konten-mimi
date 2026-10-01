"""Skema request/response onboarding."""

import uuid

from pydantic import BaseModel, Field


class OnboardingStatusOut(BaseModel):
    ada: bool
    langkah_terakhir: int
    selesai: bool
    ditutup: bool


class ProgressRequest(BaseModel):
    brand_id: uuid.UUID
    langkah: int = Field(ge=0)


class SelesaiRequest(BaseModel):
    brand_id: uuid.UUID


class TutupRequest(BaseModel):
    brand_id: uuid.UUID


class PreviewDraft(BaseModel):
    tiktok_er: float = Field(gt=0, lt=1)
    instagram_er: float = Field(gt=0, lt=1)
    facebook_er: float = Field(gt=0, lt=1)
    skor_menang: float | None = Field(default=None, gt=0, lt=1)
    skor_cukup: float | None = Field(default=None, gt=0, lt=1)


class PreviewRequest(BaseModel):
    brand_id: uuid.UUID
    draft: PreviewDraft


class PlatformPreviewOut(BaseModel):
    menang: int
    total: int


class PreviewOut(BaseModel):
    menang: int
    total: int
    per_platform: dict[str, PlatformPreviewOut]


class TemplateThresholdOut(BaseModel):
    kategori: str
    tiktok_er: float
    instagram_er: float
    facebook_er: float
    skor_menang: float
    skor_cukup: float


class ProfilBrandRequest(BaseModel):
    nama: str | None = Field(default=None, min_length=1, max_length=160)
    kategori_industri: str | None = None


class BrandProfilOut(BaseModel):
    id: uuid.UUID
    nama: str
    kategori_industri: str | None
    logo_url: str | None


class LogoOut(BaseModel):
    logo_url: str
