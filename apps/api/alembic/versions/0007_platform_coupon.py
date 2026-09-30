"""Kolom platform pada brands + tabel coupons.

Revision ID: 0007_platform_coupon
Revises: 0006_follows

- brands: tambah kolom platform (String 20, nullable) — instagram | facebook | tiktok.
  Nama tampil otomatis "[Platform] nama akun", mis. "Instagram @insanmandiri.id".
- coupons: kode kupon diskon (discount_percent, durasi hari, batas pakai).
- coupon_redemptions: riwayat penukaran kupon per organisasi.
- Seed kupon "@1717": diskon 100% selama 365 hari (akses penuh tanpa pembayaran).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid


revision = "0007_platform_coupon"
down_revision = "0006_follows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "brands",
        sa.Column("platform", sa.String(20), nullable=True),
    )

    op.create_table(
        "coupons",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("discount_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_coupons_code", "coupons", ["code"])

    op.create_table(
        "coupon_redemptions",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("coupon_id", PG_UUID(as_uuid=True), sa.ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("organization_id", PG_UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", PG_UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("coupon_id", "organization_id", name="uq_redemption_coupon_org"),
    )

    # Seed kupon "@1717": diskon 100%, berlaku 1 tahun, akses penuh tanpa pembayaran.
    op.execute(
        sa.text(
            "INSERT INTO coupons (id, code, discount_percent, duration_days, max_uses, used_count, is_active, description) "
            "VALUES (:id, '@1717', 100, 365, NULL, 0, true, 'Akses penuh 1 tahun tanpa pembayaran')"
        ).bindparams(id=uuid.uuid4())
    )


def downgrade() -> None:
    op.drop_table("coupon_redemptions")
    op.drop_index("ix_coupons_code", "coupons")
    op.drop_table("coupons")
    op.drop_column("brands", "platform")
