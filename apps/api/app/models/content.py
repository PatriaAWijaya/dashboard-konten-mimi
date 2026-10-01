"""Model konten Fase 1: konten, metrik harian, scoring, rekomendasi, DNA brand & niche.

Semua tabel tenant punya organization_id agar tercakup policy RLS tenant.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class ContentPlatform:
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"

    ALL = (TIKTOK, INSTAGRAM, FACEBOOK)


class ContentFormat:
    CAROUSEL = "carousel"
    REELS = "reels"
    STORY = "story"
    FOTO = "foto"
    LIVE = "live"

    ALL = (CAROUSEL, REELS, STORY, FOTO, LIVE)


class ContentTujuan:
    EDUKASI = "edukasi"
    HIBURAN = "hiburan"
    INTERAKSI = "interaksi"
    JUALAN = "jualan"
    BRANDING = "branding"
    ACCOUNT_GROWTH = "account_growth"

    ALL = (EDUKASI, HIBURAN, INTERAKSI, JUALAN, BRANDING, ACCOUNT_GROWTH)


class ScoreStatus:
    MENANG = "menang"
    CUKUP = "cukup"
    KURANG = "kurang"
    DATA_BELUM_CUKUP = "data_belum_cukup"

    ALL = (MENANG, CUKUP, KURANG, DATA_BELUM_CUKUP)


class RecommendationType:
    PERBANYAK = "perbanyak"
    PERBAIKI = "perbaiki"
    KURANGI = "kurangi"
    COBA_BARU = "coba_baru"
    UMUM = "umum"
    KHUSUS = "khusus"

    ALL = (PERBANYAK, PERBAIKI, KURANGI, COBA_BARU, UMUM, KHUSUS)


class RecommendationStatus:
    BARU = "baru"
    DITERIMA = "diterima"
    DITOLAK = "ditolak"

    ALL = (BARU, DITERIMA, DITOLAK)


class InterviewStatus:
    BERJALAN = "berjalan"
    SELESAI = "selesai"

    ALL = (BERJALAN, SELESAI)


class LabelSumber:
    DATA = "DATA"
    ESTIMASI = "ESTIMASI"
    KLAIM = "KLAIM"

    ALL = (DATA, ESTIMASI, KLAIM)


class Content(BaseModel):
    """Satu postingan konten milik sebuah brand."""

    __tablename__ = "contents"
    __table_args__ = (
        UniqueConstraint("brand_id", "platform", "post_id", name="uq_content_brand_platform_post"),
        Index("ix_contents_brand_posted", "brand_id", "posted_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    post_id: Mapped[str] = mapped_column(String(120), nullable=False)
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    tujuan: Mapped[str] = mapped_column(String(20), nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)

    brand: Mapped["Brand"] = relationship()
    metrics: Mapped[list["ContentMetricsDaily"]] = relationship(
        back_populates="content", cascade="all, delete-orphan"
    )
    scores: Mapped[list["ContentScore"]] = relationship(
        back_populates="content", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Content {self.platform}:{self.post_id}>"


class ContentMetricsDaily(BaseModel):
    """Metrik harian per konten (satu baris per konten per tanggal)."""

    __tablename__ = "content_metrics_daily"
    __table_args__ = (
        UniqueConstraint("content_id", "date", name="uq_metrics_content_date"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reach: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    saves: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    follows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_watch_seconds: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    profile_clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    link_clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    replies: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sticker_taps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    content: Mapped["Content"] = relationship(back_populates="metrics")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ContentMetricsDaily {self.content_id} {self.date}>"


class ScoringConfig(BaseModel):
    """Konfigurasi bobot & threshold scoring per brand (berversi)."""

    __tablename__ = "scoring_configs"
    __table_args__ = (
        UniqueConstraint("brand_id", "version", name="uq_scoring_config_brand_version"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    scores: Mapped[list["ContentScore"]] = relationship(
        back_populates="scoring_config", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ScoringConfig brand={self.brand_id} v{self.version}>"


class ContentScore(BaseModel):
    """Hasil scoring satu konten untuk satu periode & satu versi config."""

    __tablename__ = "content_scores"
    __table_args__ = (
        UniqueConstraint(
            "content_id", "scoring_config_id", "period_start", "period_end",
            name="uq_score_content_config_period",
        ),
        Index("ix_scores_content_period", "content_id", "period_end"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scoring_config_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("scoring_configs.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    labels: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    metrics_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    content: Mapped["Content"] = relationship(back_populates="scores")
    scoring_config: Mapped["ScoringConfig"] = relationship(back_populates="scores")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ContentScore {self.content_id} {self.status} {self.score}>"


class Recommendation(BaseModel):
    """Rekomendasi konten hasil analisis (dedup via dedup_key per brand)."""

    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("brand_id", "dedup_key", name="uq_recommendation_brand_dedup"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    reference_content_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RecommendationStatus.BARU)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    config_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dedup_key: Mapped[str] = mapped_column(String(120), nullable=False)

    brand: Mapped["Brand"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Recommendation {self.type}: {self.title[:40]}>"


class NicheInterview(BaseModel):
    """State wawancara niche per brand & user (multi-langkah)."""

    __tablename__ = "niche_interviews"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    answers: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    skipped: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=InterviewStatus.BERJALAN)

    brand: Mapped["Brand"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NicheInterview brand={self.brand_id} step={self.current_step}>"


class BrandDNACard(BaseModel):
    """Kartu DNA brand hasil wawancara niche (berversi, perlu konfirmasi)."""

    __tablename__ = "brand_dna_cards"
    __table_args__ = (
        UniqueConstraint("brand_id", "version", name="uq_dna_brand_version"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    misi: Mapped[str] = mapped_column(Text, nullable=False)
    nilai_inti: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    kepribadian: Mapped[str] = mapped_column(Text, nullable=False)
    positioning_statement: Mapped[str] = mapped_column(Text, nullable=False)
    diferensiasi: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    brand: Mapped["Brand"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BrandDNACard brand={self.brand_id} v{self.version}>"


class NicheSuggestion(BaseModel):
    """Saran niche turunan dari satu versi DNA card."""

    __tablename__ = "niche_suggestions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dna_version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    match_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    alasan: Mapped[str] = mapped_column(Text, nullable=False)
    angles: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    monetisasi: Mapped[str] = mapped_column(Text, nullable=False)
    persaingan: Mapped[str] = mapped_column(String(40), nullable=False)
    label_sumber: Mapped[str] = mapped_column(String(20), nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    brand: Mapped["Brand"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NicheSuggestion {self.name} ({self.match_percent}%)>"
