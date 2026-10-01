"""Skema Fase 2: OAuth/koneksi, planner, undangan, ringkasan, notifikasi, pengaturan."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# OAuth / koneksi
# ---------------------------------------------------------------------------

class OAuthMulaiOut(BaseModel):
    auth_url: str


class KoneksiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    platform: str
    account_name: str | None
    status: str
    last_sync_at: datetime | None
    connected_at: datetime = Field(description="Waktu koneksi dibuat (created_at).")


class SyncOut(BaseModel):
    contents_baru: int
    contents_diupdate: int


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class PlannedPostIn(BaseModel):
    judul: str
    format: str
    tujuan: str
    tanggal_rencana: date
    status: str | None = None
    catatan: str | None = None
    rekomendasi_sumber_id: uuid.UUID | None = None


class PlannedPostUpdate(BaseModel):
    judul: str | None = None
    format: str | None = None
    tujuan: str | None = None
    tanggal_rencana: date | None = None
    status: str | None = None
    catatan: str | None = None
    rekomendasi_sumber_id: uuid.UUID | None = None


class PlannedPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    judul: str
    platform: str | None = None
    format: str
    tujuan: str
    tanggal_rencana: date
    status: str
    catatan: str | None
    rekomendasi_sumber_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Koneksi multi-akun
# ---------------------------------------------------------------------------

class KoneksiStatusItem(BaseModel):
    terpakai: int
    batas: int
    boleh_tambah: bool


class KoneksiStatusOut(BaseModel):
    platforms: dict[str, KoneksiStatusItem]


# ---------------------------------------------------------------------------
# Konfigurasi planner
# ---------------------------------------------------------------------------

class PlannerKonfigurasiIn(BaseModel):
    kapasitas_mingguan: int | None = None
    target_distribusi: dict[str, float] | None = None
    porsi_eksperimen: float | None = None


class PlannerKonfigurasiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kapasitas_mingguan: int
    target_distribusi: dict[str, float] | None
    porsi_eksperimen: float


# ---------------------------------------------------------------------------
# Alokasi planner
# ---------------------------------------------------------------------------

class AlokasiGenerateIn(BaseModel):
    minggu: date = Field(description="Tanggal Senin awal pekan (YYYY-MM-DD).")


class SlotOut(BaseModel):
    tanggal: str
    platform: str
    format: str
    tujuan: str
    topik: str
    hook: str
    konten_acuan_ids: list[str] = []
    target_er: list[float] = Field(description="Rentang [min, max] ±20%.")
    target_views_min: int | None = None
    target_views_max: int | None = None
    sumber_rekomendasi_id: str | None = None
    eksperimen: bool = False


class AlokasiGenerateOut(BaseModel):
    slots: list[SlotOut]
    info: dict


class AlokasiTerimaIn(BaseModel):
    slots: list[dict] = Field(description="Slot dari preview generate.")


class AlokasiTerimaOut(BaseModel):
    dibuat: int


# ---------------------------------------------------------------------------
# Ringkasan header target & realisasi
# ---------------------------------------------------------------------------

class RingkasanPlannerOut(BaseModel):
    total_rencana: int
    estimasi_views_min: int
    estimasi_views_max: int
    target_er: float | None
    label: str
    catatan: str


class RealisasiGrup(BaseModel):
    jumlah: int
    rata_er: float | None


class RealisasiOut(BaseModel):
    sesuai_rencana: RealisasiGrup
    di_luar_rencana: RealisasiGrup
    rasio: float | None
    narasi: str


# ---------------------------------------------------------------------------
# Undangan
# ---------------------------------------------------------------------------

class UndanganIn(BaseModel):
    email: str
    role: str = Field(description="admin | editor | viewer")


class UndanganOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime


class TerimaUndanganOut(BaseModel):
    organization_id: uuid.UUID
    role: str


# ---------------------------------------------------------------------------
# Ringkasan
# ---------------------------------------------------------------------------

class RingkasanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ada: bool
    id: uuid.UUID | None = None
    teks: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    created_at: datetime | None = None


# ---------------------------------------------------------------------------
# Notifikasi
# ---------------------------------------------------------------------------

class PreferensiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rekomendasi_baru: bool
    ringkasan_mingguan: bool


class PreferensiIn(BaseModel):
    rekomendasi_baru: bool | None = None
    ringkasan_mingguan: bool | None = None


# ---------------------------------------------------------------------------
# Pengaturan admin
# ---------------------------------------------------------------------------

class PengaturanItem(BaseModel):
    key: str
    label: str
    configured: bool
    updated_at: datetime | None


class PengaturanIn(BaseModel):
    key: str
    value: str | None = Field(
        default=None, description="Nilai baru; null/kosong = hapus pengaturan."
    )
