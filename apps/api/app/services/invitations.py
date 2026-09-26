"""Undangan gabung organisasi via token.

KEPUTUSAN DESAIN (dicatat eksplisit sesuai brief): saat menerima undangan,
email user TIDAK wajib sama dengan email undangan — cukup token valid +
user sudah login → gabung organisasi dengan role undangan. Alasan: undangan
sering diteruskan ke email lain; keamanan dijamin oleh kerahasiaan token
32-byte yang hanya diketahui penerima. Bila di masa depan ingin diketatkan,
tambahkan pengecekan email di accept_invite.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions import VALID_ROLES, ROLE_OWNER
from app.core.security import generate_token, hash_token
from app.models.fase2 import Invitation, InvitationStatus
from app.models.organization import Organization, OrganizationMember
from app.models.user import User

INVITE_EXPIRE_DAYS = 7

# Vault dev-only: token_hash -> token plaintext (in-memory, tidak persisten).
# Diisi saat create_invite bila ENV=dev; dibaca endpoint /dev/undangan.
_DEV_TOKEN_VAULT: dict[str, str] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def dev_lookup_token(email: str) -> dict | None:
    """Kembalikan {token, expires_at} undangan pending untuk email (dev only)."""
    return _DEV_TOKEN_VAULT.get(email.strip().lower())


async def create_invite(
    db: AsyncSession,
    *,
    org: Organization,
    email: str,
    role: str,
    invited_by: User,
) -> tuple[Invitation, str]:
    """Buat undangan. Return (invitation, token_plaintext).

    token_plaintext hanya dikembalikan sekali di sini — di DB hanya
    token_hash yang disimpan.
    """
    email = email.strip().lower()
    if "@" not in email:
        raise ValueError("Alamat email tidak valid.")
    role = (role or "").strip().lower()
    if role not in VALID_ROLES or role == ROLE_OWNER:
        raise ValueError(
            f"Role undangan tidak valid: '{role}'. Pilihan: admin, editor, viewer."
        )

    # Email sudah jadi anggota?
    sudah = await db.scalar(
        select(OrganizationMember.id)
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == org.id,
            User.email == email,
        )
    )
    if sudah:
        raise ValueError("Email ini sudah menjadi anggota organisasi.")

    # Undangan pending masih aktif untuk email ini?
    aktif = await db.scalar(
        select(Invitation.id).where(
            Invitation.organization_id == org.id,
            Invitation.email == email,
            Invitation.status == InvitationStatus.PENDING,
            Invitation.expires_at > _now(),
        )
    )
    if aktif:
        raise ValueError("Undangan untuk email ini masih aktif.")

    token = generate_token()
    token_hash = hash_token(token)
    inv = Invitation(
        organization_id=org.id,
        email=email,
        role=role,
        token_hash=token_hash,
        status=InvitationStatus.PENDING,
        invited_by=invited_by.id,
        expires_at=_now() + timedelta(days=INVITE_EXPIRE_DAYS),
    )
    db.add(inv)
    await db.flush()

    if get_settings().is_dev:
        _DEV_TOKEN_VAULT[email] = {"token": token, "expires_at": inv.expires_at}
    return inv, token


async def accept_invite(db: AsyncSession, *, token: str, user: User) -> OrganizationMember:
    """Terima undangan → buat OrganizationMember. Raise ValueError bila gagal.

    Berjalan tanpa header organisasi: organisasi diambil via fungsi
    SECURITY DEFINER `get_invitation_org`, lalu tenant diset sebelum
    operasi RLS (baca undangan, cek membership, insert anggota).

    Keputusan desain: yang dibutuhkan hanyalah token undangan yang valid dan
    user yang sedang login — email user TIDAK harus sama dengan email yang
    tertulis di undangan. Undangan adalah "tiket masuk" organisasi, bukan
    verifikasi identitas email.
    """
    org_id = (
        await db.execute(
            text("SELECT public.get_invitation_org(:h)"), {"h": hash_token(token or "")}
        )
    ).scalar()
    if org_id is None:
        raise ValueError("Undangan tidak valid atau sudah dipakai.")
    await db.execute(
        text("SELECT set_config('app.tenant_id', :v, false)"), {"v": str(org_id)}
    )

    inv = await db.scalar(
        select(Invitation).where(Invitation.token_hash == hash_token(token or ""))
    )
    if inv is None or inv.status != InvitationStatus.PENDING:
        raise ValueError("Undangan tidak valid atau sudah dipakai.")
    if inv.expires_at < _now():
        inv.status = InvitationStatus.KEDALUWARSA
        await db.flush()
        raise ValueError("Undangan sudah kedaluwarsa.")

    sudah = await db.scalar(
        select(OrganizationMember.id).where(
            OrganizationMember.organization_id == inv.organization_id,
            OrganizationMember.user_id == user.id,
        )
    )
    if sudah:
        raise ValueError("Anda sudah menjadi anggota organisasi ini.")

    member = OrganizationMember(
        organization_id=inv.organization_id, user_id=user.id, role=inv.role
    )
    db.add(member)
    inv.status = InvitationStatus.DITERIMA
    await db.flush()
    return member


async def list_pending(db: AsyncSession, *, organization_id: uuid.UUID) -> list[Invitation]:
    return (
        await db.execute(
            select(Invitation)
            .where(
                Invitation.organization_id == organization_id,
                Invitation.status == InvitationStatus.PENDING,
            )
            .order_by(Invitation.created_at.desc())
        )
    ).scalars().all()


async def cancel_invite(db: AsyncSession, *, invitation: Invitation) -> Invitation:
    if invitation.status != InvitationStatus.PENDING:
        raise ValueError("Hanya undangan pending yang bisa dibatalkan.")
    invitation.status = InvitationStatus.DIBATALKAN
    await db.flush()
    return invitation
