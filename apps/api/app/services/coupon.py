"""Layanan kupon diskon — autorisasi via kode kupon saat login.

Alur: member memasukkan kode kupon saat login → kupon divalidasi →
diskon diterapkan ke organisasi member. Nilai discount_percent bisa diubah
admin kapan saja ("ditentukan kemudian").

Kupon "@1717": discount 100% selama 365 hari → akses penuh semua fitur
tanpa pembayaran.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Coupon, CouponRedemption, MembershipPlan
from app.models.organization import OrganizationMember
from app.services.membership import ensure_membership
from app.models.billing import MembershipStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_coupon(db: AsyncSession, code: str) -> Coupon | None:
    code = (code or "").strip()
    if not code:
        return None
    result = await db.execute(select(Coupon).where(Coupon.code == code))
    return result.scalar_one_or_none()


async def validate_coupon(db: AsyncSession, code: str) -> Coupon:
    """Validasi kupon; raise 400/404 bila tidak valid."""
    coupon = await get_coupon(db, code)
    if coupon is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kode kupon tidak ditemukan.",
        )
    if not coupon.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kode kupon sudah tidak aktif.",
        )
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kode kupon sudah mencapai batas pemakaian.",
        )
    if not (0 < coupon.discount_percent <= 100):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nilai diskon kupon belum ditentukan. Hubungi administrator.",
        )
    return coupon


async def redeem_coupon(
    db: AsyncSession,
    *,
    coupon: Coupon,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> CouponRedemption:
    """Tukarkan kupon untuk satu organisasi.

    - Catat redemption (satu kupon sekali per organisasi).
    - Bila discount 100%: aktifkan membership langsung selama duration_days
      tanpa pembayaran.
    - Bila discount < 100%: redemption dicatat; diskon diterapkan saat
      pembuatan invoice berikutnya (lihat billing).
    """
    # Idempoten: bila organisasi sudah pernah menukar kupon ini, kembalikan yang ada.
    existing = await db.execute(
        select(CouponRedemption).where(
            CouponRedemption.coupon_id == coupon.id,
            CouponRedemption.organization_id == organization_id,
        )
    )
    sudah = existing.scalar_one_or_none()
    if sudah is not None:
        return sudah

    now = _now()
    expires_at = now + timedelta(days=coupon.duration_days)
    redemption = CouponRedemption(
        coupon_id=coupon.id,
        organization_id=organization_id,
        user_id=user_id,
        discount_percent=coupon.discount_percent,
        redeemed_at=now,
        expires_at=expires_at,
    )
    db.add(redemption)
    coupon.used_count = (coupon.used_count or 0) + 1

    if coupon.discount_percent >= 100:
        # Akses penuh tanpa pembayaran: aktifkan membership selama durasi kupon.
        membership = await ensure_membership(db, organization_id)
        # Pakai plan tahunan default bila ada; jika tidak, membership aktif tanpa plan.
        plan = await db.execute(
            select(MembershipPlan).order_by(MembershipPlan.price.desc()).limit(1)
        )
        plan_row = plan.scalar_one_or_none()
        if plan_row is not None:
            membership.plan_id = plan_row.id
        base = membership.ends_at if (
            membership.status in (MembershipStatus.ACTIVE, MembershipStatus.GRACE)
            and membership.ends_at is not None
            and membership.ends_at > now
        ) else now
        membership.status = MembershipStatus.ACTIVE
        membership.starts_at = membership.starts_at or now
        membership.ends_at = base + timedelta(days=coupon.duration_days)
        membership.grace_ends_at = None

    await db.flush()
    return redemption


async def redeem_coupon_for_user_orgs(
    db: AsyncSession,
    *,
    code: str,
    user_id: uuid.UUID,
) -> list[dict]:
    """Tukarkan kupon untuk semua organisasi milik user. Return ringkasan per org."""
    coupon = await validate_coupon(db, code)
    rows = (
        await db.execute(
            select(OrganizationMember.organization_id).where(
                OrganizationMember.user_id == user_id
            )
        )
    ).all()
    hasil = []
    for (org_id,) in rows:
        redemption = await redeem_coupon(
            db, coupon=coupon, organization_id=org_id, user_id=user_id
        )
        hasil.append({
            "organization_id": str(org_id),
            "discount_percent": redemption.discount_percent,
            "expires_at": redemption.expires_at.isoformat() if redemption.expires_at else None,
        })
    return hasil
