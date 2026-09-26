"""Layanan membership: aktivasi (via event PembayaranLunas), perpanjangan, dan baca."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.events import on
from app.models.billing import Membership, MembershipStatus
from app.models.brand import Brand
from app.models.organization import Organization
from app.services.notifications import notify_org

# Nama brand otomatis saat membership pertama kali aktif (PRD 10.5).
NAMA_BRAND_UTAMA = "Brand Utama"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_membership(db: AsyncSession, organization_id: uuid.UUID) -> Membership | None:
    result = await db.execute(
        select(Membership)
        .options(selectinload(Membership.plan))
        .where(Membership.organization_id == organization_id)
    )
    return result.scalar_one_or_none()


async def ensure_membership(db: AsyncSession, organization_id: uuid.UUID) -> Membership:
    membership = await get_membership(db, organization_id)
    if membership is None:
        membership = Membership(organization_id=organization_id, status=MembershipStatus.PENDING_PAYMENT)
        db.add(membership)
        await db.flush()
    return membership


async def activate(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    plan_id: uuid.UUID,
    now: datetime | None = None,
) -> Membership:
    """Aktifkan membership 1 tahun. Bila membership lama masih active/grace dan
    ends_at > now, perpanjang dari ends_at lama (tidak memotong sisa waktu)."""
    settings = get_settings()
    now = now or _now()
    membership = await ensure_membership(db, organization_id)

    duration = timedelta(days=settings.MEMBERSHIP_DURATION_DAYS)
    if (
        membership.status in (MembershipStatus.ACTIVE, MembershipStatus.GRACE)
        and membership.ends_at is not None
        and membership.ends_at > now
    ):
        base = membership.ends_at
        starts_at = membership.starts_at or now
    else:
        base = now
        starts_at = now

    membership.plan_id = plan_id
    membership.status = MembershipStatus.ACTIVE
    membership.starts_at = starts_at
    membership.ends_at = base + duration
    membership.grace_ends_at = None
    await db.flush()
    return membership


async def extend(
    db: AsyncSession,
    *,
    membership: Membership,
    months: int,
    now: datetime | None = None,
) -> Membership:
    """Perpanjang dari ends_at lama bila masih berlaku, jika tidak dari now."""
    settings = get_settings()
    now = now or _now()
    # Proporsional terhadap durasi standar (12 bulan = MEMBERSHIP_DURATION_DAYS hari).
    extra_days = round(months / 12 * settings.MEMBERSHIP_DURATION_DAYS)
    base = membership.ends_at if (membership.ends_at and membership.ends_at > now) else now
    membership.status = MembershipStatus.ACTIVE
    membership.starts_at = membership.starts_at or now
    membership.ends_at = base + timedelta(days=extra_days)
    membership.grace_ends_at = None
    await db.flush()
    return membership


@on("PembayaranLunas")
async def handle_pembayaran_lunas(payload: dict, db: AsyncSession) -> None:
    """Handler event domain PembayaranLunas → aktifkan membership organisasi.

    Bila ini aktivasi PERTAMA (sebelumnya belum pernah aktif): buatkan brand
    "Brand Utama" bila organisasi belum punya brand, lalu kirim notifikasi
    aktivasi (berisi link login, nama organisasi, tanggal kedaluwarsa —
    TIDAK PERNAH password) ke semua anggota organisasi.
    """
    organization_id = payload["organization_id"]
    sebelum = await get_membership(db, organization_id)
    pertama_kali = sebelum is None or sebelum.status == MembershipStatus.PENDING_PAYMENT

    membership = await activate(
        db,
        organization_id=organization_id,
        plan_id=payload["plan_id"],
    )

    if membership.status != MembershipStatus.ACTIVE or not pertama_kali:
        return

    await _pastikan_brand_utama(db, organization_id)

    settings = get_settings()
    org = await db.get(Organization, organization_id)
    await notify_org(
        db,
        organization_id,
        "aktivasi_membership",
        {
            "nama_organisasi": org.name if org else "",
            "login_url": settings.FRONTEND_URL,
            "tanggal_kedaluwarsa": membership.ends_at.isoformat() if membership.ends_at else "",
            "nama_plan": payload.get("plan_name") or "",
        },
    )


async def _pastikan_brand_utama(db: AsyncSession, organization_id: uuid.UUID) -> Brand | None:
    """Buatkan brand 'Brand Utama' bila organisasi belum punya brand sama sekali.

    Return brand yang dibuat, atau None bila organisasi sudah punya brand.
    """
    sudah_ada = await db.scalar(
        select(Brand).where(Brand.organization_id == organization_id).limit(1)
    )
    if sudah_ada is not None:
        return None
    brand = Brand(organization_id=organization_id, name=NAMA_BRAND_UTAMA)
    db.add(brand)
    await db.flush()
    return brand
