"""Tes isolasi RLS: tenant A tidak bisa membaca data tenant B, dan sebaliknya."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")
import uuid

from sqlalchemy import select, text

from app.models.brand import Brand
from app.models.organization import Organization

from .conftest import _set_ctx, create_org_direct, create_user_direct


async def _brand_names_sqlalchemy(session, tenant_id: uuid.UUID) -> list[str]:
    await _set_ctx(session, user_id=str(uuid.uuid4()), is_superadmin="off", tenant_id=str(tenant_id))
    result = await session.execute(select(Brand.name).order_by(Brand.name))
    return list(result.scalars().all())


async def _brand_names_raw_sql(session, tenant_id: uuid.UUID) -> list[str]:
    await _set_ctx(session, user_id=str(uuid.uuid4()), is_superadmin="off", tenant_id=str(tenant_id))
    result = await session.execute(text("SELECT name FROM brands ORDER BY name"))
    return [row[0] for row in result.all()]


async def _org_names(session, tenant_id: uuid.UUID) -> list[str]:
    await _set_ctx(session, user_id=str(uuid.uuid4()), is_superadmin="off", tenant_id=str(tenant_id))
    result = await session.execute(select(Organization.name).order_by(Organization.name))
    return list(result.scalars().all())


async def test_rls_isolation_between_tenants(db_super, rls_session_factory):
    owner_a = await create_user_direct(db_super)
    owner_b = await create_user_direct(db_super)
    org_a = await create_org_direct(db_super, owner_a, name="Org A RLS")
    org_b = await create_org_direct(db_super, owner_b, name="Org B RLS")

    # Tambah brand di tiap org sebagai superadmin (bypass RLS).
    async with rls_session_factory() as setup:
        await _set_ctx(setup, is_superadmin="on")
        setup.add(Brand(organization_id=org_a.id, name="Brand A1"))
        setup.add(Brand(organization_id=org_a.id, name="Brand A2"))
        setup.add(Brand(organization_id=org_b.id, name="Brand B1"))
        await setup.commit()

    async with rls_session_factory() as session:
        # Tenant A → hanya data A (via SQLAlchemy maupun raw SQL)
        assert await _brand_names_sqlalchemy(session, org_a.id) == ["Brand A1", "Brand A2"]
        assert await _brand_names_raw_sql(session, org_a.id) == ["Brand A1", "Brand A2"]
        assert await _org_names(session, org_a.id) == ["Org A RLS"]

        # Tenant B → hanya data B
        assert await _brand_names_sqlalchemy(session, org_b.id) == ["Brand B1"]
        assert await _brand_names_raw_sql(session, org_b.id) == ["Brand B1"]
        assert await _org_names(session, org_b.id) == ["Org B RLS"]

        # Tanpa tenant → tidak ada data tenant yang terbaca
        await _set_ctx(session, user_id=str(uuid.uuid4()), is_superadmin="off", tenant_id="")
        result = await session.execute(select(Brand.name))
        assert list(result.scalars().all()) == []


async def test_rls_blocks_cross_tenant_write(db_super, rls_session_factory):
    owner_a = await create_user_direct(db_super)
    org_a = await create_org_direct(db_super, owner_a, name="Org A Write")

    async with rls_session_factory() as session:
        # Coba insert brand ke org A dengan tenant org lain → DITOLAK policy.
        await _set_ctx(session, user_id=str(uuid.uuid4()), is_superadmin="off", tenant_id=str(uuid.uuid4()))
        session.add(Brand(organization_id=org_a.id, name="Brand Ilegal"))
        with pytest.raises(Exception):
            await session.flush()
        await session.rollback()


async def test_rls_contents_isolation(db_super, rls_session_factory):
    """Contents milik brand org A tak terbaca dari tenant org B."""
    from datetime import datetime, timezone

    from app.models.content import Content

    owner_a = await create_user_direct(db_super)
    owner_b = await create_user_direct(db_super)
    org_a = await create_org_direct(db_super, owner_a, name="Org A Konten")
    org_b = await create_org_direct(db_super, owner_b, name="Org B Konten")

    brand_a = Brand(organization_id=org_a.id, name="Brand A Konten")
    brand_b = Brand(organization_id=org_b.id, name="Brand B Konten")
    db_super.add_all([brand_a, brand_b])
    await db_super.flush()
    await db_super.commit()

    async with rls_session_factory() as setup:
        await _set_ctx(setup, is_superadmin="on")
        setup.add(Content(
            organization_id=org_a.id, brand_id=brand_a.id, platform="tiktok",
            post_id="vid-a1", posted_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
            format="reels", tujuan="hiburan",
        ))
        setup.add(Content(
            organization_id=org_b.id, brand_id=brand_b.id, platform="tiktok",
            post_id="vid-b1", posted_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
            format="reels", tujuan="hiburan",
        ))
        await setup.commit()

    async def _post_ids(session, tenant_id: uuid.UUID) -> list[str]:
        await _set_ctx(session, user_id=str(uuid.uuid4()), is_superadmin="off", tenant_id=str(tenant_id))
        result = await session.execute(select(Content.post_id).order_by(Content.post_id))
        return list(result.scalars().all())

    async with rls_session_factory() as session:
        assert await _post_ids(session, org_a.id) == ["vid-a1"]
        assert await _post_ids(session, org_b.id) == ["vid-b1"]
