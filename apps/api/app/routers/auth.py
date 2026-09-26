"""Router autentikasi & profil pengguna."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.tokens import EmailVerificationToken, PasswordResetToken, RefreshToken
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    UpdateProfileRequest,
    UserPublic,
    VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.services.audit import log_audit
from app.services.email import get_email_service

router = APIRouter(tags=["auth"])

# Hash dummy agar timing login untuk email tak dikenal mirip dengan yang dikenal.
_DUMMY_HASH = hash_password("dummy-password-yang-tidak-pernah-cocok-123")


def _now():
    return datetime.now(timezone.utc)


def _email_token_expiry() -> datetime:
    return _now() + timedelta(hours=get_settings().EMAIL_TOKEN_EXPIRE_HOURS)


async def _find_auth_row(db: AsyncSession, email: str) -> dict | None:
    """Cari user via fungsi SECURITY DEFINER (RLS membatasi SELECT langsung)."""
    result = await db.execute(
        text("SELECT * FROM public.get_user_auth_by_email(:email)"), {"email": email.strip().lower()}
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def _become(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Set konteks RLS ke user lalu muat barisnya (dipakai setelah identitas terbukti)."""
    await db.execute(text("SELECT set_config('app.user_id', :v, false)"), {"v": str(user_id)})
    user = await db.get(User, user_id)
    if user is None:  # pragma: no cover
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")
    return user


async def _revoke_all_refresh_tokens(db: AsyncSession, user_id: uuid.UUID) -> None:
    result = await db.execute(select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)))
    for rt in result.scalars().all():
        rt.revoked = True
    await db.flush()


# ---------------------------------------------------------------------------
# Registrasi & verifikasi
# ---------------------------------------------------------------------------

@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def register(
    request: Request, data: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]
):
    if await _find_auth_row(db, data.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email sudah terdaftar.")

    user = User(
        name=data.name.strip(),
        email=data.email.strip().lower(),
        password_hash=hash_password(data.password),
        whatsapp=data.whatsapp.strip() if data.whatsapp else None,
    )
    db.add(user)
    await db.flush()

    token = generate_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id, token_hash=hash_token(token), expires_at=_email_token_expiry()
        )
    )
    await db.flush()

    await get_email_service().send_verification_email(to_email=user.email, name=user.name, token=token)
    return RegisterResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        message="Pendaftaran berhasil. Silakan verifikasi email Anda.",
    )


@router.post("/auth/verify-email", response_model=MessageResponse)
@limiter.limit("30/minute")
async def verify_email(
    request: Request, data: VerifyEmailRequest, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_token(data.token))
    )
    token_row = result.scalar_one_or_none()
    if token_row is None or token_row.used_at is not None or token_row.expires_at < _now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token verifikasi tidak valid atau kedaluwarsa.",
        )
    user = await _become(db, token_row.user_id)
    user.email_verified = True
    token_row.used_at = _now()
    await db.flush()
    return MessageResponse(message="Email berhasil diverifikasi.")


# ---------------------------------------------------------------------------
# Login / refresh / logout
# ---------------------------------------------------------------------------

@router.post("/auth/login", response_model=LoginResponse)
@limiter.limit("30/minute")
async def login(
    request: Request, data: LoginRequest, db: Annotated[AsyncSession, Depends(get_db)]
):
    row = await _find_auth_row(db, data.email)
    password_ok = verify_password(data.password, row["password_hash"]) if row else verify_password(data.password, _DUMMY_HASH)
    if not row or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Email atau kata sandi salah."
        )
    if not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akun Anda dinonaktifkan. Hubungi administrator.",
        )

    user = await _become(db, row["id"])
    refresh_token, _, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_hash=hash_token(refresh_token), expires_at=expires_at))
    await db.flush()

    return LoginResponse(
        access_token=create_access_token(user.id, user.is_superadmin),
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserPublic.model_validate(user),
    )


@router.post("/auth/refresh", response_model=RefreshResponse)
async def refresh(data: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        payload = decode_token(data.refresh_token, "refresh")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(data.refresh_token))
    )
    stored = result.scalar_one_or_none()
    if (
        stored is None
        or stored.revoked
        or stored.expires_at < _now()
        or str(stored.user_id) != payload["sub"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token tidak valid atau sudah kedaluwarsa.",
        )

    user = await _become(db, stored.user_id)
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akun Anda dinonaktifkan.")

    stored.revoked = True  # rotasi: token lama hangus
    new_refresh, _, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(user_id=user.id, token_hash=hash_token(new_refresh), expires_at=expires_at))
    await db.flush()

    return RefreshResponse(
        access_token=create_access_token(user.id, user.is_superadmin),
        refresh_token=new_refresh,
        token_type="bearer",
    )


@router.post("/auth/logout", response_model=MessageResponse)
async def logout(data: LogoutRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(data.refresh_token))
    )
    stored = result.scalar_one_or_none()
    if stored is not None:
        stored.revoked = True
        await db.flush()
    return MessageResponse(message="Berhasil keluar.")


# ---------------------------------------------------------------------------
# Lupa / reset password
# ---------------------------------------------------------------------------

@router.post("/auth/forgot-password", response_model=MessageResponse)
@limiter.limit("10/minute")
async def forgot_password(
    request: Request, data: ForgotPasswordRequest, db: Annotated[AsyncSession, Depends(get_db)]
):
    # Selalu 200; jangan pernah membocorkan apakah email terdaftar / password asli.
    row = await _find_auth_row(db, data.email)
    if row:
        token = generate_token()
        db.add(
            PasswordResetToken(
                user_id=row["id"], token_hash=hash_token(token), expires_at=_email_token_expiry()
            )
        )
        await db.flush()
        await get_email_service().send_password_reset_email(
            to_email=row["email"], name=row["name"], token=token
        )
    return MessageResponse(
        message="Jika email terdaftar, tautan reset kata sandi telah dikirim ke email Anda."
    )


@router.post("/auth/reset-password", response_model=MessageResponse)
@limiter.limit("10/minute")
async def reset_password(
    request: Request, data: ResetPasswordRequest, db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(data.token))
    )
    token_row = result.scalar_one_or_none()
    if token_row is None or token_row.used_at is not None or token_row.expires_at < _now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token reset tidak valid atau kedaluwarsa.",
        )
    user = await _become(db, token_row.user_id)
    user.password_hash = hash_password(data.new_password)
    token_row.used_at = _now()
    await _revoke_all_refresh_tokens(db, user.id)
    await db.flush()
    return MessageResponse(message="Kata sandi berhasil diubah. Silakan masuk kembali.")


# ---------------------------------------------------------------------------
# Profil
# ---------------------------------------------------------------------------

@router.get("/auth/me", response_model=MeResponse)
async def get_me(user: Annotated[User, Depends(get_current_user)]):
    return MeResponse.model_validate(user)


@router.patch("/users/me", response_model=MeResponse)
async def update_profile(
    data: UpdateProfileRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    changes: dict = {}
    if data.name is not None and data.name.strip() != user.name:
        changes["name"] = {"dari": user.name, "ke": data.name.strip()}
        user.name = data.name.strip()
    if data.whatsapp is not None and (data.whatsapp.strip() or None) != user.whatsapp:
        changes["whatsapp"] = {"dari": user.whatsapp, "ke": data.whatsapp.strip() or None}
        user.whatsapp = data.whatsapp.strip() or None
    if changes:
        await log_audit(
            db,
            actor_user_id=user.id,
            action="profile_updated",
            entity_type="user",
            entity_id=user.id,
            meta=changes,
        )
        await db.flush()
    return MeResponse.model_validate(user)


@router.post("/users/me/change-password", response_model=MessageResponse)
async def change_password(
    data: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Kata sandi lama salah."
        )
    user.password_hash = hash_password(data.new_password)
    await _revoke_all_refresh_tokens(db, user.id)
    await log_audit(
        db, actor_user_id=user.id, action="password_changed", entity_type="user", entity_id=user.id
    )
    await db.flush()
    return MessageResponse(message="Kata sandi berhasil diubah. Silakan masuk kembali di perangkat lain.")
