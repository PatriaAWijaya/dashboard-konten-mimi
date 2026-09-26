"""Tes lifecycle membership & invoice via maintenance() dengan waktu simulasi."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")
from datetime import timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.models.billing import Invoice, InvoiceStatus, Membership, MembershipStatus
from app.services.maintenance import run_maintenance
from app.services.membership import ensure_membership

from .conftest import create_org_direct, create_plan_direct, create_user_direct, utcnow


async def test_membership_lifecycle_active_grace_expired(db_super):
    settings = get_settings()
    user = await create_user_direct(db_super)
    org = await create_org_direct(db_super, user)

    membership = await ensure_membership(db_super, org.id)
    t0 = utcnow()
    membership.status = MembershipStatus.ACTIVE
    membership.starts_at = t0 - timedelta(days=400)
    membership.ends_at = t0 - timedelta(days=1)  # sudah lewat kemarin
    membership.grace_ends_at = None
    await db_super.commit()

    # (b) active & now > ends_at → grace
    changed = await run_maintenance(db_super, now=t0)
    await db_super.commit()
    assert changed["memberships_graced"] >= 1

    m = (await db_super.execute(select(Membership).where(Membership.id == membership.id))).scalar_one()
    assert m.status == MembershipStatus.GRACE
    assert m.grace_ends_at is not None
    # grace_ends_at = ends_at + GRACE_PERIOD_DAYS (dari settings, bukan hardcode)
    expected_grace_end = membership.ends_at + timedelta(days=settings.GRACE_PERIOD_DAYS)
    assert abs((m.grace_ends_at - expected_grace_end).total_seconds()) < 5

    # (c) grace & now > grace_ends_at → expired
    later = m.grace_ends_at + timedelta(seconds=1)
    changed = await run_maintenance(db_super, now=later)
    await db_super.commit()
    assert changed["memberships_expired"] >= 1

    m = (await db_super.execute(select(Membership).where(Membership.id == membership.id))).scalar_one()
    assert m.status == MembershipStatus.EXPIRED


async def test_invoice_pending_expired_by_maintenance(db_super):
    from app.services.invoice import create_invoice

    user = await create_user_direct(db_super)
    org = await create_org_direct(db_super, user)
    plan = await create_plan_direct(db_super)

    t0 = utcnow()
    invoice = await create_invoice(db_super, organization_id=org.id, plan=plan, creator_user_id=user.id, now=t0)
    await db_super.commit()
    assert invoice.status == InvoiceStatus.PENDING

    # Belum kedaluwarsa → tetap pending
    await run_maintenance(db_super, now=t0 + timedelta(hours=1))
    await db_super.commit()
    inv = (await db_super.execute(select(Invoice).where(Invoice.id == invoice.id))).scalar_one()
    assert inv.status == InvoiceStatus.PENDING

    # Lewat expires_at → expired
    await run_maintenance(db_super, now=invoice.expires_at + timedelta(seconds=1))
    await db_super.commit()
    inv = (await db_super.execute(select(Invoice).where(Invoice.id == invoice.id))).scalar_one()
    assert inv.status == InvoiceStatus.EXPIRED


async def test_activate_extends_from_old_ends_at(db_super):
    from app.services.membership import activate

    settings = get_settings()
    user = await create_user_direct(db_super)
    org = await create_org_direct(db_super, user)
    plan = await create_plan_direct(db_super)

    t0 = utcnow()
    old_ends = t0 + timedelta(days=100)
    membership = await ensure_membership(db_super, org.id)
    membership.status = MembershipStatus.ACTIVE
    membership.starts_at = t0 - timedelta(days=265)
    membership.ends_at = old_ends
    await db_super.commit()

    activated = await activate(db_super, organization_id=org.id, plan_id=plan.id, now=t0)
    await db_super.commit()

    # Diperpanjang dari ends_at lama, bukan dari now.
    expected = old_ends + timedelta(days=settings.MEMBERSHIP_DURATION_DAYS)
    assert activated.status == MembershipStatus.ACTIVE
    assert abs((activated.ends_at - expected).total_seconds()) < 5
