"""Niche Finder tanpa brand: brand_id boleh NULL.

Revision ID: 0010_niche_brand_nullable
Revises: 0009_perf_indexes

- ALTER COLUMN niche_interviews.brand_id DROP NOT NULL
  agar kuesioner Niche Finder bisa dipakai tanpa memilih brand.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0010_niche_brand_nullable"
down_revision = "0009_perf_indexes"


def upgrade() -> None:
    op.alter_column(
        "niche_interviews",
        "brand_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "niche_interviews",
        "brand_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
