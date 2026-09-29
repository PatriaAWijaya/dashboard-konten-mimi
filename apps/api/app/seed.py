"""Seed awal (idempotent): python -m app.seed

- Superadmin (SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD)
- 1 paket "Paket Tahunan"
- 1 organisasi + 1 brand contoh milik admin
"""

import asyncio
import uuid

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models.billing import MembershipPlan, MembershipStatus
from app.models.brand import Brand
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.services.membership import ensure_membership

PLAN_NAME = "Paket Tahunan"
ORG_NAME = "Organisasi Contoh"
BRAND_NAME = "Brand Contoh"


async def main() -> None:
    settings = get_settings()
    async with get_session_factory()() as session:
        await session.execute(text("SELECT set_config('app.is_superadmin', 'on', false)"))
        await session.execute(text("SELECT set_config('app.user_id', '', false)"))
        await session.execute(text("SELECT set_config('app.tenant_id', '', false)"))

        # --- Superadmin ---
        result = await session.execute(select(User).where(User.email == settings.SEED_ADMIN_EMAIL.lower()))
        admin = result.scalar_one_or_none()
        if admin is None:
            admin = User(
                name="Administrator",
                email=settings.SEED_ADMIN_EMAIL.lower(),
                password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
                is_active=True,
                is_superadmin=True,
                email_verified=True,
            )
            session.add(admin)
            await session.flush()
            print(f"Superadmin dibuat: {admin.email}")
        else:
            # SEMENTARA 2026-09-29: password admin produksi hilang (/tmp terhapus
            # sebelum sempat dicatat). Sinkronkan ulang dari SEED_ADMIN_PASSWORD
            # agar bisa login kembali, lalu password diputar manual dan blok
            # ini DIHAPUS pada commit berikutnya.
            admin.password_hash = hash_password(settings.SEED_ADMIN_PASSWORD)
            print(f"Superadmin sudah ada: {admin.email} (password di-reset sementara)")

        # --- Paket ---
        result = await session.execute(select(MembershipPlan).where(MembershipPlan.name == PLAN_NAME))
        plan = result.scalar_one_or_none()
        if plan is None:
            plan = MembershipPlan(
                name=PLAN_NAME,
                price=990000,
                period_months=12,
                seats=5,
                features=[
                    "Analisis performa konten TikTok & Instagram",
                    "Multi-brand dalam satu organisasi",
                    "Rekomendasi konten berbasis AI",
                    "Dukungan prioritas",
                ],
            )
            session.add(plan)
            await session.flush()
            print(f"Paket dibuat: {plan.name}")
        else:
            print(f"Paket sudah ada: {plan.name} (dilewati)")

        # --- Organisasi + brand contoh milik admin ---
        result = await session.execute(select(Organization).where(Organization.name == ORG_NAME))
        org = result.scalar_one_or_none()
        if org is None:
            org_id = uuid.uuid4()
            await session.execute(text("SELECT set_config('app.tenant_id', :v, false)"), {"v": str(org_id)})
            org = Organization(id=org_id, name=ORG_NAME)
            session.add(org)
            await session.flush()
            session.add(OrganizationMember(organization_id=org.id, user_id=admin.id, role="owner"))
            session.add(Brand(organization_id=org.id, name=BRAND_NAME, industry="Contoh"))
            membership = await ensure_membership(session, org.id)
            membership.status = MembershipStatus.PENDING_PAYMENT
            await session.flush()
            print(f"Organisasi contoh dibuat: {org.name}")
            await session.execute(text("SELECT set_config('app.tenant_id', '', false)"))
        else:
            print(f"Organisasi contoh sudah ada (dilewati)")

        await session.commit()
        print("Seed selesai.")


if __name__ == "__main__":
    asyncio.run(main())
