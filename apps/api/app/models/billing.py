import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class MembershipStatus:
    PENDING_PAYMENT = "pending_payment"
    ACTIVE = "active"
    GRACE = "grace"
    EXPIRED = "expired"
    SUSPENDED = "suspended"

    ALL = (PENDING_PAYMENT, ACTIVE, GRACE, EXPIRED, SUSPENDED)


class InvoiceStatus:
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    ALL = (PENDING, PAID, EXPIRED, CANCELLED)


class PaymentStatus:
    MENUNGGU_VERIFIKASI = "menunggu_verifikasi"
    DISETUJUI = "disetujui"
    DITOLAK = "ditolak"

    ALL = (MENUNGGU_VERIFIKASI, DISETUJUI, DITOLAK)


class MembershipPlan(BaseModel):
    """Paket membership global (bukan tenant)."""

    __tablename__ = "membership_plans"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)  # rupiah
    period_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    seats: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    features: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="plan")


class Membership(BaseModel):
    """Satu baris aktif per organisasi (di-upsert saat pembayaran lunas/perpanjangan)."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_membership_org"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("membership_plans.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=MembershipStatus.PENDING_PAYMENT)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="membership")
    plan: Mapped["MembershipPlan | None"] = relationship(back_populates="memberships")


class Invoice(BaseModel):
    __tablename__ = "invoices"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("membership_plans.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    amount_base: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unique_code: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_total: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=InvoiceStatus.PENDING)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    plan: Mapped["MembershipPlan"] = relationship()
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice")


class Payment(BaseModel):
    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)  # path relatif di STORAGE_DIR
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)  # nama asli file
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=PaymentStatus.MENUNGGU_VERIFIKASI)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")
