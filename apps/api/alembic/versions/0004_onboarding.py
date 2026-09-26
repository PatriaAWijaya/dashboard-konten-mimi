"""Onboarding: kolom brand (logo, kategori industri) + tabel progres onboarding.

Revision ID: 0004_onboarding
Revises: 0003_fase2
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_onboarding"
down_revision = "0003_fase2"
branch_labels = None
depends_on = None


# Tenant dicek lewat brand pemilik (pola sama seperti oauth_states).
_BRAND_USING = (
    "(EXISTS (SELECT 1 FROM brands b WHERE b.id = onboarding_progress.brand_id "
    "AND (b.organization_id::text = current_setting('app.tenant_id', true) "
    "OR current_setting('app.is_superadmin', true) = 'on')))"
)


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    # Kolom baru di brands.
    op.add_column("brands", sa.Column("logo_url", sa.String(512), nullable=True))
    op.add_column("brands", sa.Column("industry_category", sa.String(60), nullable=True))

    # Tabel progres onboarding per (user, brand).
    op.create_table(
        "onboarding_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("langkah_terakhir", sa.Integer, nullable=False, server_default="0"),
        sa.Column("selesai", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("ditutup", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "brand_id", name="uq_onboarding_progress_user_brand"),
    )
    op.create_index("ix_onboarding_progress_user", "onboarding_progress", ["user_id"])
    op.create_index("ix_onboarding_progress_brand", "onboarding_progress", ["brand_id"])

    # Row Level Security: tenant via brand pemilik.
    _enable_rls("onboarding_progress")
    op.execute(
        "CREATE POLICY onboarding_progress_tenant ON onboarding_progress FOR ALL "
        f"USING ({_BRAND_USING}) WITH CHECK ({_BRAND_USING})"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS onboarding_progress CASCADE")
    op.drop_column("brands", "industry_category")
    op.drop_column("brands", "logo_url")
