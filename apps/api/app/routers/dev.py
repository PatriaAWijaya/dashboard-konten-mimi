"""Endpoint dev-only: intip token email yang 'terkirim' via ConsoleEmailService."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, parse_org_header
from app.core.security import hash_token
from app.models.tokens import EmailVerificationToken, PasswordResetToken
from app.models.user import User
from app.services.email import get_dev_outbox
from app.services.invitations import dev_lookup_token

router = APIRouter(tags=["dev"])


class InvitationTokenOut(BaseModel):
    token: str
    email: str
    expires_at: datetime | None


@router.get("/dev/undangan", response_model=InvitationTokenOut)
async def dev_undangan(
    email: Annotated[str, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Intip token plaintext undangan pending (dev only, pola /dev/email-tokens)."""
    found = dev_lookup_token(email)
    if found is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tidak ada undangan pending untuk email ini (atau server di-restart).",
        )
    return InvitationTokenOut(token=found["token"], email=email.strip().lower(), expires_at=found["expires_at"])


class EmailTokenOut(BaseModel):
    token: str
    type: str
    expires_at: datetime | None


class PasswordResetTokenOut(BaseModel):
    token: str
    expires_at: datetime | None


def _now():
    return datetime.now(timezone.utc)


@router.get("/dev/email-tokens", response_model=list[EmailTokenOut])
async def dev_email_tokens(
    email: Annotated[str, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    items = []
    for sent in get_dev_outbox():
        if sent.email.lower() != email.strip().lower() or sent.type != "verification":
            continue
        row = (
            await db.execute(
                select(EmailVerificationToken).where(
                    EmailVerificationToken.token_hash == hash_token(sent.token)
                )
            )
        ).scalar_one_or_none()
        items.append(EmailTokenOut(token=sent.token, type=sent.type, expires_at=row.expires_at if row else None))
    return items


@router.get("/dev/password-reset-tokens", response_model=list[PasswordResetTokenOut])
async def dev_password_reset_tokens(
    email: Annotated[str, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    items = []
    for sent in get_dev_outbox():
        if sent.email.lower() != email.strip().lower() or sent.type != "password_reset":
            continue
        row = (
            await db.execute(
                select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(sent.token))
            )
        ).scalar_one_or_none()
        items.append(PasswordResetTokenOut(token=sent.token, expires_at=row.expires_at if row else None))
    return items


# ---------------------------------------------------------------------------
# Koneksi mock (dev only): hubungkan akun demo tanpa OAuth asli.
# Tanpa endpoint ini, MockSyncProvider tidak bisa dicoba dari UI karena
# pembuatan ConnectedAccount hanya terjadi lewat callback OAuth (butuh
# kredensial TikTok/Meta asli). Pola sama seperti /dev/email-tokens.
# ---------------------------------------------------------------------------
class MockKoneksiIn(BaseModel):
    brand_id: uuid.UUID
    platform: str


class MockKoneksiOut(BaseModel):
    id: uuid.UUID
    platform: str
    account_name: str | None
    status: str


@router.post("/dev/koneksi/mock", response_model=MockKoneksiOut, status_code=201)
async def dev_mock_koneksi(
    data: MockKoneksiIn,
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Buat/perbarui ConnectedAccount mock untuk brand (dev only).

    Memungkinkan uji coba alur koneksi → sync dari UI tanpa kredensial
    TikTok/Meta asli. Token yang disimpan hanya string dummy terenkripsi.

    Akun diidentifikasi lewat account_external_id "mock-{platform}-001":
    pemanggilan berulang memperbarui akun yang sama (idempotent), akun mock
    dengan external id lain dianggap akun berbeda dan tunduk pada batas
    multi-akun (HTTP 409 bila penuh).
    """
    from fastapi import HTTPException, status

    from app.core.crypto import encrypt_text
    from app.core.deps import get_org_context
    from app.core.permissions import ROLE_EDITOR
    from app.models.brand import Brand
    from app.models.fase2 import ConnectedAccount, ConnectedAccountStatus
    from app.services.sync_service import AccountLimitExceeded, ensure_account_capacity

    platform = (data.platform or "").strip().lower()
    if platform not in ("tiktok", "instagram"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Platform tidak valid. Pilihan: tiktok, instagram.",
        )
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    brand = await db.get(Brand, data.brand_id)
    if brand is None or brand.organization_id != ctx.organization.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Brand tidak ditemukan."
        )

    external_id = f"mock-{platform}-001"
    account = await db.scalar(
        select(ConnectedAccount).where(
            ConnectedAccount.brand_id == brand.id,
            ConnectedAccount.platform == platform,
            ConnectedAccount.account_external_id == external_id,
        )
    )
    nama = {"tiktok": "Akun Demo TikTok (mock)", "instagram": "Akun Demo Instagram (mock)"}[platform]
    if account is None:
        try:
            await ensure_account_capacity(db, brand, platform)
        except AccountLimitExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            )
        account = ConnectedAccount(
            organization_id=ctx.organization.id,
            brand_id=brand.id,
            platform=platform,
        )
        db.add(account)
    account.account_name = nama
    account.account_external_id = external_id
    account.access_token_encrypted = encrypt_text(f"mock-access-{platform}-dev")
    account.refresh_token_encrypted = encrypt_text(f"mock-refresh-{platform}-dev")
    account.status = ConnectedAccountStatus.AKTIF
    await db.commit()
    await db.refresh(account)
    return MockKoneksiOut(
        id=account.id,
        platform=account.platform,
        account_name=account.account_name,
        status=account.status,
    )
