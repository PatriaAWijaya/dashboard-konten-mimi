"""Model progres onboarding per (user, brand)."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class OnboardingProgress(BaseModel):
    """Langkah onboarding terakhir yang dicapai user untuk sebuah brand."""

    __tablename__ = "onboarding_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "brand_id", name="uq_onboarding_progress_user_brand"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    langkah_terakhir: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selesai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ditutup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OnboardingProgress user={self.user_id} brand={self.brand_id} langkah={self.langkah_terakhir}>"
