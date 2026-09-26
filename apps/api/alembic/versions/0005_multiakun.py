"""Multi-akun per platform per brand + konfigurasi planner.

Revision ID: 0005_multiakun
Revises: 0004_onboarding

- connected_accounts: ganti UNIQUE(brand_id, platform)
  (uq_connected_account_brand_platform) menjadi
  UNIQUE(brand_id, platform, account_external_id)
  (uq_connected_account_brand_platform_ext) agar satu brand boleh punya
  beberapa akun per platform (batas ditegakkan di level aplikasi, bukan DB).
- Tabel baru planner_configs: konfigurasi alokasi planner per brand.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_multiakun"
down_revision = "0004_onboarding"
branch_labels = None
depends_on = None


_TENANT_USING = (
    "(organization_id::text = current_setting('app.tenant_id', true) "
    "OR current_setting('app.is_superadmin', true) = 'on')"
)


def upgrade() -> None:
    # 1. Multi-akun: longgarkan unique constraint koneksi.
    op.drop_constraint(
        "uq_connected_account_brand_platform",
        "connected_accounts",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_connected_account_brand_platform_ext",
        "connected_accounts",
        ["brand_id", "platform", "account_external_id"],
    )

    # 2. Konfigurasi planner per brand.
    op.create_table(
        "planner_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "kapasitas_mingguan", sa.Integer, nullable=False, server_default="7"
        ),
        sa.Column("target_distribusi", postgresql.JSONB, nullable=True),
        sa.Column(
            "porsi_eksperimen", sa.Float, nullable=False, server_default="0.2"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_planner_configs_org", "planner_configs", ["organization_id"])
    op.create_index("ix_planner_configs_brand", "planner_configs", ["brand_id"])

    # RLS tenant (pola sama seperti tabel Fase 2 lain).
    op.execute("ALTER TABLE planner_configs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE planner_configs FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY planner_configs_tenant ON planner_configs FOR ALL "
        f"USING ({_TENANT_USING}) WITH CHECK ({_TENANT_USING})"
    )

    # 3. planned_posts: kolom platform (nullable) agar slot alokasi yang
    #    diterima menyimpan platform target untuk ekspor CSV/PDF.
    op.add_column(
        "planned_posts", sa.Column("platform", sa.String(20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("planned_posts", "platform")
    op.execute("DROP POLICY IF EXISTS planner_configs_tenant ON planner_configs")
    op.drop_index("ix_planner_configs_brand", table_name="planner_configs")
    op.drop_index("ix_planner_configs_org", table_name="planner_configs")
    op.drop_table("planner_configs")
    op.drop_constraint(
        "uq_connected_account_brand_platform_ext",
        "connected_accounts",
        type_="unique",
    )
    # Skema lama hanya mengizinkan 1 akun per (brand, platform): bila ada
    # duplikat dari era multi-akun, pertahankan yang paling lama dibuat.
    op.execute(
        """
        DELETE FROM connected_accounts ca
        USING connected_accounts cb
        WHERE ca.brand_id = cb.brand_id
          AND ca.platform = cb.platform
          AND ca.created_at > cb.created_at
        """
    )
    op.create_unique_constraint(
        "uq_connected_account_brand_platform",
        "connected_accounts",
        ["brand_id", "platform"],
    )
