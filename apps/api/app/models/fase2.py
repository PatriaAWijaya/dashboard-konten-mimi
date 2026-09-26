"""Model Fase 2: koneksi OAuth, planner, undangan, ringkasan, notifikasi, pengaturan.

Semua tabel tenant punya organization_id agar tercakup policy RLS tenant
(kecuali oauth_states yang memakai policy via brand, notification_preferences
yang memakai policy user-sendiri, dan app_settings yang khusus superadmin).
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, BaseModel, utcnow


class ConnectedAccountStatus:
    AKTIF = "aktif"  # bisa di-sync (worker memfilter status == "aktif")
    ERROR = "error"  # sync terakhir gagal

    ALL = (AKTIF, ERROR)


class ConnectedAccount(BaseModel):
    """Akun TikTok/Instagram yang terhubung via OAuth per brand.

    Satu brand boleh punya beberapa akun per platform (batas maks ditegakkan
    di service, bukan DB; lihat sync_service.ensure_account_capacity).
    """

    __tablename__ = "connected_accounts"
    __table_args__ = (
        UniqueConstraint(
            "brand_id", "platform", "account_external_id",
            name="uq_connected_account_brand_platform_ext",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    account_external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ConnectedAccountStatus.AKTIF)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    brand: Mapped["Brand"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ConnectedAccount {self.platform}:{self.account_name}>"


class PlannerConfig(BaseModel):
    """Konfigurasi alokasi planner per brand (satu baris per brand)."""

    __tablename__ = "planner_configs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    kapasitas_mingguan: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    target_distribusi: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    porsi_eksperimen: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)

    brand: Mapped["Brand"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlannerConfig brand={self.brand_id} kapasitas={self.kapasitas_mingguan}>"


class OAuthState(BaseModel):
    """State + PKCE verifier sementara untuk alur OAuth (kedaluwarsa 10 mnt)."""

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    code_verifier: Mapped[str] = mapped_column(Text, nullable=False)
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    redirect_after: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OAuthState {self.platform}>"


class PlannedPostStatus:
    IDE = "ide"
    TERJADWAL = "terjadwal"
    TERBIT = "terbit"
    DIBATALKAN = "dibatalkan"

    ALL = (IDE, TERJADWAL, TERBIT, DIBATALKAN)


class PlannedPost(BaseModel):
    """Rencana konten (content planner) per brand."""

    __tablename__ = "planned_posts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    judul: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(20), nullable=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    tujuan: Mapped[str] = mapped_column(String(20), nullable=False)
    tanggal_rencana: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PlannedPostStatus.IDE)
    catatan: Mapped[str | None] = mapped_column(Text, nullable=True)
    rekomendasi_sumber_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    brand: Mapped["Brand"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PlannedPost {self.judul[:40]}>"


class InvitationStatus:
    PENDING = "pending"
    DITERIMA = "diterima"
    DIBATALKAN = "dibatalkan"
    KEDALUWARSA = "kedaluwarsa"

    ALL = (PENDING, DITERIMA, DIBATALKAN, KEDALUWARSA)


class Invitation(BaseModel):
    """Undangan gabung organisasi via token (token mentah tidak disimpan)."""

    __tablename__ = "invitations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=InvitationStatus.PENDING)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invitation {self.email} → {self.role}>"


class Summary(BaseModel):
    """Ringkasan naratif periode per brand (cached, unik per periode)."""

    __tablename__ = "summaries"
    __table_args__ = (
        UniqueConstraint("brand_id", "period_start", "period_end", name="uq_summary_brand_period"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    teks: Mapped[str] = mapped_column(Text, nullable=False)
    config_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    brand: Mapped["Brand"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Summary {self.brand_id} {self.period_start}..{self.period_end}>"


class NotificationLogStatus:
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"  # preferensi user off — tercatat, tidak dikirim

    ALL = (SENT, FAILED, SKIPPED)


class NotificationLog(BaseModel):
    """Jejak pengiriman notifikasi (termasuk yang di-skip karena preferensi)."""

    __tablename__ = "notification_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=True, index=True
    )
    jenis: Mapped[str] = mapped_column(String(40), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NotificationLog {self.jenis} {self.status}>"


class NotificationPreference(Base):
    """Preferensi notifikasi per user (dibuat otomatis default true)."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    rekomendasi_baru: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ringkasan_mingguan: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NotificationPreference {self.user_id}>"


class AppSetting(Base):
    """Pengaturan global terenkripsi (kredensial OAuth/LLM/WhatsApp).

    Hanya superadmin yang boleh baca/tulis langsung ke tabel ini (RLS).
    Service backend membaca nilai via fungsi SECURITY DEFINER
    public.get_app_setting_value() agar alur OAuth/sync tetap jalan untuk
    user biasa tanpa membuka tabel.
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AppSetting {self.key}>"
