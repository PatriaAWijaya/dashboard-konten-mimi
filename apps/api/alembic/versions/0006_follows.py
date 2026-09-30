"""Kolom follows pada metrik harian konten.

Revision ID: 0006_follows
Revises: 0005_multiakun

- content_metrics_daily: tambah kolom follows (Integer, default 0, not null)
  agar metrik "Follows" dari export Meta ikut tersimpan dan bisa dianalisa.
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_follows"
down_revision = "0005_multiakun"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "content_metrics_daily",
        sa.Column("follows", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("content_metrics_daily", "follows")
