"""Router organisasi & brand (multi-tenant)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import (
    OrgContext,
    get_current_user,
    get_db,
    get_org_context,
    get_org_membership,
    set_tenant,
)
from app.core.permissions import ROLE_ADMIN, ROLE_OWNER
from app.models.billing import Membership, MembershipStatus
from app.models.brand import Brand
from app.models.content import Content
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.schemas.organization import (
    BrandCreate,
    BrandOut,
    MemberAdd,
    MemberOut,
    MemberRoleUpdate,
    MembershipMini,
    OrganizationCreate,
    OrganizationDetail,
    OrganizationListItem,
    OrganizationOut,
)
from app.services.audit import log_audit
from app.services.membership import ensure_membership

router = APIRouter(tags=["organizations"])


def _membership_guard(membership: Membership | None, *, write: bool) -> Membership:
    """Pastikan membership mengizinkan akses. Grace = baca saja."""
    if membership is None or membership.status == MembershipStatus.PENDING_PAYMENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Membership organisasi belum aktif. Selesaikan pembayaran terlebih dahulu.",
        )
    if membership.status == MembershipStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Membership organisasi ditangguhkan. Hubungi administrator.",
        )
    if membership.status == MembershipStatus.EXPIRED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Membership organisasi sudah kedaluwarsa. Perpanjang untuk melanjutkan.",
        )
    if write and membership.status == MembershipStatus.GRACE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mode baca-saja: membership dalam masa tenggang. Perpanjang membership untuk menambah data.",
        )
    return membership


async def _ctx_with_membership(
    db: AsyncSession, user: User, org_id: uuid.UUID, min_role: str | None, *, write: bool
) -> tuple[OrgContext, Membership]:
    ctx = await get_org_context(db, user, org_id, min_role=min_role)
    membership = _membership_guard(await get_org_membership(db, org_id), write=write)
    return ctx, membership


# ---------------------------------------------------------------------------
# Organisasi
# ---------------------------------------------------------------------------

@router.post("/organizations", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    data: OrganizationCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verifikasi email Anda terlebih dahulu sebelum membuat organisasi.",
        )
    org_id = uuid.uuid4()
    # Tenant diset ke id org baru agar lolos WITH CHECK policy RLS saat INSERT.
    await set_tenant(db, org_id)
    org = Organization(id=org_id, name=data.name.strip())
    db.add(org)
    await db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=ROLE_OWNER))
    await ensure_membership(db, org.id)  # status awal: pending_payment
    await db.flush()
    return OrganizationOut.model_validate(org)


@router.get("/organizations", response_model=list[OrganizationListItem])
async def list_organizations(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(OrganizationMember, Organization, Membership)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .outerjoin(Membership, Membership.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
        .order_by(Organization.created_at.desc())
    )
    items = []
    for member, org, membership in result.all():
        items.append(
            OrganizationListItem(
                id=org.id,
                name=org.name,
                role=member.role,
                membership_status=membership.status if membership else None,
            )
        )
    return items


@router.get("/organizations/{org_id}", response_model=OrganizationDetail)
async def get_organization(
    org_id: Annotated[uuid.UUID, Path()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ctx = await get_org_context(db, user, org_id)
    membership = await get_org_membership(db, org_id)
    return OrganizationDetail(
        id=ctx.organization.id,
        name=ctx.organization.name,
        membership=MembershipMini(status=membership.status, ends_at=membership.ends_at) if membership else None,
    )


# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------

@router.post(
    "/organizations/{org_id}/brands", response_model=BrandOut, status_code=status.HTTP_201_CREATED
)
async def create_brand(
    org_id: Annotated[uuid.UUID, Path()],
    data: BrandCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ctx, _ = await _ctx_with_membership(db, user, org_id, min_role=ROLE_ADMIN, write=True)

    settings = get_settings()
    count = await db.scalar(
        select(func.count()).select_from(Brand).where(Brand.organization_id == org_id)
    )
    if (count or 0) >= settings.MAX_BRANDS_PER_ORG:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Batas maksimal {settings.MAX_BRANDS_PER_ORG} brand per organisasi tercapai.",
        )

    brand = Brand(
        organization_id=ctx.organization.id,
        name=data.name.strip(),
        industry=data.industry.strip() if data.industry else None,
        platform=data.platform,
    )
    db.add(brand)
    await db.flush()
    return BrandOut.model_validate(brand)


@router.get("/organizations/{org_id}/brands", response_model=list[BrandOut])
async def list_brands(
    org_id: Annotated[uuid.UUID, Path()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _ctx_with_membership(db, user, org_id, min_role=None, write=False)
    result = await db.execute(
        select(Brand).where(Brand.organization_id == org_id).order_by(Brand.created_at.desc())
    )
    return [BrandOut.model_validate(b) for b in result.scalars().all()]


_NAMA_BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


@router.get("/organizations/{org_id}/ringkasan-data")
async def ringkasan_data(
    org_id: Annotated[uuid.UUID, Path()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Ringkasan data konten per brand: platform, nama akun, dan daftar
    tahun-bulan yang sudah ada datanya. Dipakai dasbor untuk menampilkan
    'Data yang sudah diinput' bagi member yang sudah pernah upload."""
    await _ctx_with_membership(db, user, org_id, min_role=None, write=False)
    brands = (
        await db.execute(
            select(Brand).where(Brand.organization_id == org_id).order_by(Brand.created_at.desc())
        )
    ).scalars().all()

    hasil = []
    for b in brands:
        rows = (
            await db.execute(
                select(
                    func.extract("year", Content.posted_at).label("tahun"),
                    func.extract("month", Content.posted_at).label("bulan"),
                    func.count().label("jumlah"),
                )
                .where(
                    Content.brand_id == b.id,
                    Content.organization_id == org_id,
                    Content.posted_at.is_not(None),
                )
                .group_by("tahun", "bulan")
                .order_by("tahun", "bulan")
            )
        ).all()
        periode = []
        total = 0
        for r in rows:
            tahun, bulan, jumlah = int(r.tahun), int(r.bulan), int(r.jumlah)
            total += jumlah
            periode.append({
                "tahun": tahun,
                "bulan": bulan,
                "label": f"{_NAMA_BULAN[bulan - 1]} {tahun}",
                "jumlah_konten": jumlah,
            })
        hasil.append({
            "id": str(b.id),
            "name": b.name,
            "platform": b.platform,
            "display_name": b.display_name,
            "total_konten": total,
            "periode": periode,
        })
    return {"brands": hasil}


# ---------------------------------------------------------------------------
# Anggota
# ---------------------------------------------------------------------------

@router.get("/organizations/{org_id}/members", response_model=list[MemberOut])
async def list_members(
    org_id: Annotated[uuid.UUID, Path()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await get_org_context(db, user, org_id)
    result = await db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == org_id)
        .order_by(User.name)
    )
    return [
        MemberOut(user_id=u.id, name=u.name, email=u.email, role=m.role) for m, u in result.all()
    ]


@router.post(
    "/organizations/{org_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED
)
async def add_member(
    org_id: Annotated[uuid.UUID, Path()],
    data: MemberAdd,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from sqlalchemy import text as _text

    ctx = await get_org_context(db, user, org_id, min_role=ROLE_ADMIN)

    # Cari user via fungsi SECURITY DEFINER (RLS membatasi pencarian user lain).
    row = (
        await db.execute(
            text("SELECT * FROM public.get_user_auth_by_email(:email)"),
            {"email": data.email.strip().lower()},
        )
    ).mappings().first()
    if row is None or not row["email_verified"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pengguna tidak ditemukan atau email belum terverifikasi.",
        )
    target_id = row["id"]

    existing = await db.scalar(
        select(func.count())
        .select_from(OrganizationMember)
        .where(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == target_id)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Pengguna sudah menjadi anggota organisasi ini."
        )

    settings = get_settings()
    membership = await get_org_membership(db, org_id)
    seats = membership.plan.seats if (membership and membership.plan) else settings.DEFAULT_SEATS_NO_PLAN
    member_count = await db.scalar(
        select(func.count()).select_from(OrganizationMember).where(OrganizationMember.organization_id == org_id)
    )
    if (member_count or 0) >= seats:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Kuota anggota paket tercapai ({seats} kursi). Upgrade paket untuk menambah anggota.",
        )

    if data.role == ROLE_OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tidak dapat menambah owner baru melalui endpoint ini.",
        )

    db.add(OrganizationMember(organization_id=org_id, user_id=target_id, role=data.role))
    await log_audit(
        db,
        actor_user_id=user.id,
        action="member_added",
        entity_type="organization_member",
        entity_id=target_id,
        organization_id=org_id,
        meta={"email": row["email"], "role": data.role},
    )
    await db.flush()
    return MemberOut(user_id=target_id, name=row["name"], email=row["email"], role=data.role)


@router.put("/organizations/{org_id}/members/{member_user_id}", response_model=MemberOut)
async def update_member_role(
    org_id: Annotated[uuid.UUID, Path()],
    member_user_id: Annotated[uuid.UUID, Path()],
    data: MemberRoleUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_OWNER)

    if member_user_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Anda tidak dapat mengubah peran sendiri."
        )
    if data.role == ROLE_OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tidak dapat menetapkan peran owner melalui endpoint ini.",
        )

    result = await db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == member_user_id,
        )
    )
    found = result.first()
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anggota tidak ditemukan.")
    member, target_user = found

    old_role = member.role
    member.role = data.role
    await log_audit(
        db,
        actor_user_id=user.id,
        action="member_role_changed",
        entity_type="organization_member",
        entity_id=member_user_id,
        organization_id=org_id,
        meta={"dari": old_role, "ke": data.role},
    )
    await db.flush()
    return MemberOut(user_id=target_user.id, name=target_user.name, email=target_user.email, role=member.role)


@router.delete(
    "/organizations/{org_id}/members/{member_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    org_id: Annotated[uuid.UUID, Path()],
    member_user_id: Annotated[uuid.UUID, Path()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Keluarkan anggota dari organisasi (min admin).

    Ditolak: mengeluarkan diri sendiri; mengeluarkan owner terakhir.
    """
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_ADMIN)

    member = await db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == member_user_id,
        )
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anggota tidak ditemukan.")
    if member_user_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Anda tidak dapat mengeluarkan diri sendiri dari organisasi.",
        )
    if member.role == ROLE_OWNER:
        n_owner = await db.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.role == ROLE_OWNER,
            )
        )
        if (n_owner or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tidak dapat mengeluarkan owner terakhir organisasi.",
            )
    await log_audit(
        db,
        actor_user_id=user.id,
        action="member_removed",
        entity_type="organization_member",
        entity_id=member_user_id,
        organization_id=org_id,
        meta={"role": member.role},
    )
    await db.delete(member)
    await db.flush()
    return None
