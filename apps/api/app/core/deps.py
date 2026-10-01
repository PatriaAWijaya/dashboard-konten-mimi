"""Dependencies FastAPI: sesi DB dengan RLS, user aktif, konteks organisasi."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated, AsyncIterator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import has_min_role
from app.core.security import decode_token
from app.db.session import get_session_factory
from app.models.billing import Membership
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.services.maintenance import run_maintenance


# ---------------------------------------------------------------------------
# Sesi database + RLS
# ---------------------------------------------------------------------------

async def _set_config(db: AsyncSession, key: str, value: str) -> None:
    await db.execute(text("SELECT set_config(:k, :v, false)"), {"k": key, "v": value})


async def _set_configs(db: AsyncSession, configs: dict[str, str]) -> None:
    """Set beberapa GUC dalam 1 roundtrip."""
    if not configs:
        return
    selects = ", ".join(f"set_config(:k{i}, :v{i}, false)" for i in range(len(configs)))
    params: dict = {}
    for i, (k, v) in enumerate(configs.items()):
        params[f"k{i}"] = k
        params[f"v{i}"] = v
    await db.execute(text(f"SELECT {selects}"), params)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Satu sesi per request. Set app.user_id / app.is_superadmin / app.tenant_id
    untuk Row Level Security, RESET semuanya di finally."""
    auth = request.headers.get("authorization", "")
    jwt_user_id: str | None = None
    jwt_is_sa = "off"
    if auth.lower().startswith("bearer "):
        try:
            payload = decode_token(auth[7:].strip(), "access")
            jwt_user_id = payload["sub"]
            jwt_is_sa = "on" if payload.get("sa") else "off"
        except ValueError:
            jwt_user_id = None

    session_factory = get_session_factory()
    async with session_factory() as session:
        await _set_configs(session, {
            "app.user_id": jwt_user_id or "",
            "app.is_superadmin": jwt_is_sa,
            "app.tenant_id": "",
        })
        request.state.jwt_user_id = jwt_user_id
        try:
            yield session
            # Commit SELALU: kondisi "hanya bila ada perubahan" pernah dicoba
            # (hemat 1 roundtrip) tapi salah — flush() memindahkan objek dari
            # session.new ke persistent sehingga endpoint yang flush tanpa
            # commit eksplisit (register, resend-verifikasi, dsb.) diam-diam
            # ter-rollback padahal email sudah terkirim & respons 201 sudah
            # dibuat. Jangan dioptimasi lagi.
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            # RESET harus di-commit: tanpa commit, RESET berjalan dalam
            # transaksi implisit yang di-rollback saat sesi ditutup sehingga
            # GUC bocor ke connection pool dan mencemari sesi berikutnya.
            # Digabung dalam 1 roundtrip.
            await session.execute(text("SELECT set_config('app.tenant_id', '', false), set_config('app.user_id', '', false), set_config('app.is_superadmin', 'off', false)"))
            await session.commit()


async def set_tenant(db: AsyncSession, organization_id: uuid.UUID | str) -> None:
    await _set_config(db, "app.tenant_id", str(organization_id))


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _unauthorized(detail: str = "Anda belum masuk. Silakan login terlebih dahulu.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def get_current_user(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    user_id = getattr(request.state, "jwt_user_id", None)
    if not user_id:
        raise _unauthorized()
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise _unauthorized()
    user = await db.get(User, uid)
    if user is None:
        raise _unauthorized("Sesi tidak valid. Silakan login kembali.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akun Anda dinonaktifkan. Hubungi administrator.")
    # Segarkan flag superadmin dari DB (lebih baru daripada klaim JWT).
    await _set_config(db, "app.is_superadmin", "on" if user.is_superadmin else "off")
    return user


async def require_superadmin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses ditolak: hanya superadmin.")
    return user


# ---------------------------------------------------------------------------
# Konteks organisasi (multi-tenant)
# ---------------------------------------------------------------------------

@dataclass
class OrgContext:
    organization: Organization
    member: OrganizationMember


async def get_org_context(
    db: AsyncSession,
    user: User,
    organization_id: uuid.UUID,
    min_role: str | None = None,
) -> OrgContext:
    """Validasi keanggotaan + set tenant RLS. Raise 404/403 bila tidak berhak."""
    await set_tenant(db, organization_id)

    org = await db.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisasi tidak ditemukan.")

    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Anda bukan anggota organisasi ini."
        )
    if min_role and not has_min_role(member.role, min_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Akses ditolak: butuh peran minimal '{min_role}'.",
        )
    return OrgContext(organization=org, member=member)


async def get_org_membership(db: AsyncSession, organization_id: uuid.UUID) -> Membership | None:
    """Ambil membership dengan lazy maintenance terlebih dahulu."""
    from app.services.membership import get_membership  # hindari import sirkular

    await run_maintenance(db)
    return await get_membership(db, organization_id)


def parse_org_header(x_organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None) -> uuid.UUID:
    if not x_organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header X-Organization-Id wajib disertakan.",
        )
    try:
        return uuid.UUID(x_organization_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Header X-Organization-Id tidak valid."
        )
