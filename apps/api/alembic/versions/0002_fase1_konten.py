"""Tabel konten Fase 1 + Row Level Security.

Revision ID: 0002_fase1_konten
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_fase1_konten"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


_TENANT_USING = (
    "(organization_id::text = current_setting('app.tenant_id', true) "
    "OR current_setting('app.is_superadmin', true) = 'on')"
)


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def _tenant_policy(table: str) -> None:
    op.execute(
        f"CREATE POLICY {table}_tenant ON {table} FOR ALL "
        f"USING ({_TENANT_USING}) WITH CHECK ({_TENANT_USING})"
    )


_TENANT_TABLES = (
    "contents",
    "content_metrics_daily",
    "scoring_configs",
    "content_scores",
    "recommendations",
    "niche_interviews",
    "brand_dna_cards",
    "niche_suggestions",
)


def upgrade() -> None:
    # ---------------------------------------------------------------- contents
    op.create_table(
        "contents",
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
        ),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("post_id", sa.String(120), nullable=False),
        sa.Column("post_url", sa.Text, nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("tujuan", sa.String(20), nullable=False),
        sa.Column("caption", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("brand_id", "platform", "post_id", name="uq_content_brand_platform_post"),
    )
    op.create_index("ix_contents_org", "contents", ["organization_id"])
    op.create_index("ix_contents_brand", "contents", ["brand_id"])

    # ------------------------------------------------------ content_metrics_daily
    op.create_table(
        "content_metrics_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("views", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reach", sa.Integer, nullable=False, server_default="0"),
        sa.Column("likes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("comments", sa.Integer, nullable=False, server_default="0"),
        sa.Column("shares", sa.Integer, nullable=False, server_default="0"),
        sa.Column("saves", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_watch_seconds", sa.Float, nullable=False, server_default="0"),
        sa.Column("profile_clicks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("link_clicks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("replies", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sticker_taps", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("content_id", "date", name="uq_metrics_content_date"),
    )
    op.create_index("ix_content_metrics_daily_org", "content_metrics_daily", ["organization_id"])
    op.create_index("ix_content_metrics_daily_content", "content_metrics_daily", ["content_id"])
    op.create_index("ix_content_metrics_daily_date", "content_metrics_daily", ["date"])

    # ---------------------------------------------------------- scoring_configs
    op.create_table(
        "scoring_configs",
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
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("weights", postgresql.JSONB, nullable=False),
        sa.Column("thresholds", postgresql.JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("brand_id", "version", name="uq_scoring_config_brand_version"),
    )
    op.create_index("ix_scoring_configs_org", "scoring_configs", ["organization_id"])
    op.create_index("ix_scoring_configs_brand", "scoring_configs", ["brand_id"])

    # ------------------------------------------------------------ content_scores
    op.create_table(
        "content_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "content_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scoring_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scoring_configs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("labels", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("metrics_snapshot", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "content_id", "scoring_config_id", "period_start", "period_end",
            name="uq_score_content_config_period",
        ),
    )
    op.create_index("ix_content_scores_org", "content_scores", ["organization_id"])
    op.create_index("ix_content_scores_content", "content_scores", ["content_id"])

    # ---------------------------------------------------------- recommendations
    op.create_table(
        "recommendations",
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
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("narrative", sa.Text, nullable=False),
        sa.Column("evidence", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("reference_content_ids", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="baru"),
        sa.Column("period_start", sa.Date, nullable=True),
        sa.Column("period_end", sa.Date, nullable=True),
        sa.Column("config_version", sa.Integer, nullable=True),
        sa.Column("dedup_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("brand_id", "dedup_key", name="uq_recommendation_brand_dedup"),
    )
    op.create_index("ix_recommendations_org", "recommendations", ["organization_id"])
    op.create_index("ix_recommendations_brand", "recommendations", ["brand_id"])

    # ---------------------------------------------------------- niche_interviews
    op.create_table(
        "niche_interviews",
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
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("current_step", sa.Integer, nullable=False, server_default="0"),
        sa.Column("answers", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("skipped", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="berjalan"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_niche_interviews_org", "niche_interviews", ["organization_id"])
    op.create_index("ix_niche_interviews_brand", "niche_interviews", ["brand_id"])

    # ---------------------------------------------------------- brand_dna_cards
    op.create_table(
        "brand_dna_cards",
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
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("misi", sa.Text, nullable=False),
        sa.Column("nilai_inti", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("kepribadian", sa.Text, nullable=False),
        sa.Column("positioning_statement", sa.Text, nullable=False),
        sa.Column("diferensiasi", sa.Text, nullable=False),
        sa.Column("confirmed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("brand_id", "version", name="uq_dna_brand_version"),
    )
    op.create_index("ix_brand_dna_cards_org", "brand_dna_cards", ["organization_id"])
    op.create_index("ix_brand_dna_cards_brand", "brand_dna_cards", ["brand_id"])

    # -------------------------------------------------------- niche_suggestions
    op.create_table(
        "niche_suggestions",
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
        ),
        sa.Column("dna_version", sa.Integer, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("match_percent", sa.Integer, nullable=False),
        sa.Column("alasan", sa.Text, nullable=False),
        sa.Column("angles", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("monetisasi", sa.Text, nullable=False),
        sa.Column("persaingan", sa.String(40), nullable=False),
        sa.Column("label_sumber", sa.String(20), nullable=False),
        sa.Column("is_selected", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_niche_suggestions_org", "niche_suggestions", ["organization_id"])
    op.create_index("ix_niche_suggestions_brand", "niche_suggestions", ["brand_id"])

    # ------------------------------------------------------- Row Level Security
    for table in _TENANT_TABLES:
        _enable_rls(table)
        _tenant_policy(table)


def downgrade() -> None:
    for table in reversed(_TENANT_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
