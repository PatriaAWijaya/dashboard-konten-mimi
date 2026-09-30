import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel


class Brand(BaseModel):
    __tablename__ = "brands"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Onboarding (migrasi 0004): logo & kategori industri untuk template threshold.
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    industry_category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Platform sosial media yang dianalisa: instagram | facebook | tiktok.
    # Nama tampil otomatis: "[Platform] nama akun", mis. "Instagram @insanmandiri.id".
    platform: Mapped[str | None] = mapped_column(String(20), nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="brands")

    @property
    def display_name(self) -> str:
        """Format '[Platform] nama akun', mis. 'Instagram @insanmandiri.id'."""
        if self.platform:
            label = {"instagram": "Instagram", "facebook": "Facebook", "tiktok": "TikTok"}.get(
                self.platform.lower(), self.platform.capitalize()
            )
            return f"{label} {self.name}"
        return self.name
