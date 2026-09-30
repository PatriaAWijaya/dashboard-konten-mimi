"""Tambah created_at/updated_at ke coupon_redemptions (terlewat di 0007).

Revision ID: 0008_redemption_ts
Revises: 0007_platform_coupon

Model CouponRedemption mewarisi BaseModel yang punya created_at/updated_at
non-nullable; migrasi 0007 lupa membuat kedua kolom ini sehingga SELECT
gagal dengan UndefinedColumnError.

Catatan: ID revisi maksimal 32 karakter (kolom alembic_version.version_num
adalah varchar(32)).
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_redemption_ts"
down_revision = "0007_platform_coupon"


def upgrade() -> None:
    op.add_column(
        "coupon_redemptions",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "coupon_redemptions",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("coupon_redemptions", "updated_at")
    op.drop_column("coupon_redemptions", "created_at")
