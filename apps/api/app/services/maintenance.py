"""Maintenance periodik + lazy:

(a) invoice pending & now > expires_at → expired
(b) membership active & now > ends_at → grace (+grace_ends_at)
(c) membership grace & now > grace_ends_at → expired

Dipanggil via CLI (python -m app.cli maintenance) dan secara lazy saat
membaca invoice/membership di endpoint.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.billing import Invoice, InvoiceStatus, Membership, MembershipStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def run_maintenance(db: AsyncSession, now: datetime | None = None) -> dict[str, int]:
    """Jalankan seluruh aturan maintenance. Kembalikan jumlah baris yang diubah.

    Memakai objek ORM (bukan bulk update) agar state session selalu konsisten —
    bulk update SQLAlchemy membingungkan sinkronisasi session pada driver async.
    """
    settings = get_settings()
    now = now or _now()
    changed: dict[str, int] = {"invoices_expired": 0, "memberships_graced": 0, "memberships_expired": 0}

    invoices = (
        await db.execute(
            select(Invoice).where(Invoice.status == InvoiceStatus.PENDING, Invoice.expires_at < now)
        )
    ).scalars().all()
    for inv in invoices:
        inv.status = InvoiceStatus.EXPIRED
        changed["invoices_expired"] += 1

    memberships = (await db.execute(select(Membership))).scalars().all()
    for m in memberships:
        # (b) active & now > ends_at → grace. Masa tenggang dihitung dari ends_at.
        if m.status == MembershipStatus.ACTIVE and m.ends_at is not None and m.ends_at < now:
            m.status = MembershipStatus.GRACE
            m.grace_ends_at = m.ends_at + timedelta(days=settings.GRACE_PERIOD_DAYS)
            changed["memberships_graced"] += 1
        # (c) grace & now > grace_ends_at → expired
        if m.status == MembershipStatus.GRACE and m.grace_ends_at is not None and m.grace_ends_at < now:
            m.status = MembershipStatus.EXPIRED
            changed["memberships_expired"] += 1

    await db.flush()
    return changed
