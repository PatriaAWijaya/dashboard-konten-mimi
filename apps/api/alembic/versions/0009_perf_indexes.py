"""Index composite untuk query dashboard/analisa yang sering dipakai.

Revision ID: 0009_perf_indexes
Revises: 0008_redemption_ts

- ix_contents_brand_posted (brand_id, posted_at): filter periode di dashboard/analisa
- ix_scores_content_period (content_id, period_end): lookup skor terbaru per konten
"""

from alembic import op


revision = "0009_perf_indexes"
down_revision = "0008_redemption_ts"


def upgrade() -> None:
    op.create_index(
        "ix_contents_brand_posted",
        "contents",
        ["brand_id", "posted_at"],
    )
    op.create_index(
        "ix_scores_content_period",
        "content_scores",
        ["content_id", "period_end"],
    )


def downgrade() -> None:
    op.drop_index("ix_scores_content_period", table_name="content_scores")
    op.drop_index("ix_contents_brand_posted", table_name="contents")
