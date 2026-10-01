"""Orkestrasi OAuth & sinkronisasi konten Fase 2.

- start_oauth / handle_oauth_callback: alur OAuth PKCE per platform.
- sync_account: fetch via provider → normalize_content_row (satu pintu
  validasi yang sama dengan CSV) → upsert idempoten.

Bila kredensial admin belum lengkap, get_provider mengembalikan
MockSyncProvider. Untuk endpoint OAuth itu berarti 501 (kontrak frontend:
frontend menangkap 501 sebagai "kredensial belum disiapkan"); untuk sync
tetap jalan dengan data demo.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import encrypt_text
from app.models.brand import Brand
from app.models.content import ContentPlatform
from app.models.fase2 import (
    ConnectedAccount,
    ConnectedAccountStatus,
    OAuthState,
)
from app.models.user import User
from app.services.normalize import (
    NormalizationError,
    normalize_content_row,
    upsert_content_rows,
)
from app.services.settings import get_setting
from app.services.sync_providers import MockSyncProvider, SyncProvider, get_provider

OAUTH_STATE_EXPIRE_MINUTES = 10
SYNC_DEFAULT_SINCE_DAYS = 30


class CredentialsNotConfigured(Exception):
    """Kredensial OAuth admin belum dikonfigurasi → HTTP 501 di router."""


class AccountLimitExceeded(Exception):
    """Jumlah akun per platform per brand sudah mencapai batas → HTTP 409."""


DEFAULT_MAX_ACCOUNTS_PER_PLATFORM = 3
MAX_ACCOUNTS_SETTING_KEY = "max_accounts_per_platform"


async def get_max_accounts_per_platform(db: AsyncSession) -> int:
    """Batas akun per platform per brand dari app_settings (default 3)."""
    try:
        raw = await get_setting(db, MAX_ACCOUNTS_SETTING_KEY)
        n = int(raw)
        if n >= 1:
            return n
    except (TypeError, ValueError):
        pass
    return DEFAULT_MAX_ACCOUNTS_PER_PLATFORM


async def count_accounts(db: AsyncSession, brand_id: uuid.UUID, platform: str) -> int:
    """Jumlah ConnectedAccount untuk (brand, platform)."""
    from sqlalchemy import func as _func

    return int(
        await db.scalar(
            select(_func.count())
            .select_from(ConnectedAccount)
            .where(
                ConnectedAccount.brand_id == brand_id,
                ConnectedAccount.platform == platform,
            )
        )
        or 0
    )


async def ensure_account_capacity(db: AsyncSession, brand: Brand, platform: str) -> int:
    """Pastikan masih ada slot untuk akun baru di (brand, platform).

    Return jumlah terpakai. Raise AccountLimitExceeded bila sudah penuh
    (router mengubahnya menjadi HTTP 409).
    """
    batas = await get_max_accounts_per_platform(db)
    terpakai = await count_accounts(db, brand.id, platform)
    if terpakai >= batas:
        nama = {"tiktok": "TikTok", "instagram": "Instagram", "facebook": "Facebook"}.get(platform, platform)
        raise AccountLimitExceeded(
            f"Batas {batas} akun {nama} per brand tercapai. "
            "Hapus salah satu akun yang terhubung untuk menambah akun baru."
        )
    return terpakai


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _credential_map(db: AsyncSession) -> dict[str, str]:
    """Ambil kredensial OAuth yang ada (decrypted) sebagai dict.

    Prioritas: app_settings (diatur superadmin via /admin/pengaturan),
    lalu env (TIKTOK_CLIENT_KEY, dst.) sebagai fallback dev.
    """
    keys = (
        "tiktok_client_key",
        "tiktok_client_secret",
        "instagram_app_id",
        "instagram_app_secret",
    )
    env_fallback = {
        "tiktok_client_key": "TIKTOK_CLIENT_KEY",
        "tiktok_client_secret": "TIKTOK_CLIENT_SECRET",
        "instagram_app_id": "INSTAGRAM_APP_ID",
        "instagram_app_secret": "INSTAGRAM_APP_SECRET",
    }
    out: dict[str, str] = {}
    for k in keys:
        v = await get_setting(db, k)
        if not v:
            v = os.environ.get(env_fallback[k], "").strip() or None
        if v:
            out[k] = v
    return out


def _getter(creds: dict[str, str]) -> Callable[[str], str | None]:
    return lambda k: creds.get(k)


def _provider_nyata(
    db: AsyncSession, platform: str, creds: dict[str, str]
) -> SyncProvider:
    """Provider nyata atau raise CredentialsNotConfigured (→ 501)."""
    provider = get_provider(platform, _getter(creds))
    if isinstance(provider, MockSyncProvider):
        nama = {"tiktok": "TikTok", "instagram": "Instagram", "facebook": "Facebook"}.get(platform, platform)
        raise CredentialsNotConfigured(
            f"Kredensial {nama} belum dikonfigurasi oleh admin. "
            "Minta admin mengisi pengaturan (tiktok_client_key/secret atau "
            "instagram_app_id/secret) terlebih dahulu."
        )
    return provider


def _client_id_secret(platform: str, creds: dict[str, str]) -> tuple[str, str]:
    if platform == "tiktok":
        return creds["tiktok_client_key"], creds["tiktok_client_secret"]
    return creds["instagram_app_id"], creds["instagram_app_secret"]


def _redirect_uri() -> str:
    return f"{get_settings().API_BASE_URL.rstrip('/')}/api/v1/content/oauth/callback"


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")


def _validate_platform(platform: str) -> str:
    platform = (platform or "").strip().lower()
    if platform not in ContentPlatform.ALL:
        raise ValueError(f"Platform tidak dikenal: '{platform}'. Pilihan: tiktok, instagram, facebook.")
    return platform


# ---------------------------------------------------------------------------
# OAuth
# ---------------------------------------------------------------------------

async def start_oauth(
    db: AsyncSession,
    brand: Brand,
    platform: str,
    user: User,
    redirect_after: str | None = None,
) -> dict:
    """Mulai alur OAuth: simpan state+PKCE, kembalikan {auth_url, state}.

    Raise CredentialsNotConfigured bila kredensial admin belum lengkap
    (router mengubahnya menjadi HTTP 501).
    """
    platform = _validate_platform(platform)
    creds = await _credential_map(db)
    provider = _provider_nyata(db, platform, creds)
    client_id, _ = _client_id_secret(platform, creds)

    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    db.add(
        OAuthState(
            state=state,
            code_verifier=verifier,
            brand_id=brand.id,
            platform=platform,
            user_id=user.id,
            redirect_after=redirect_after,
            expires_at=_now() + timedelta(minutes=OAUTH_STATE_EXPIRE_MINUTES),
        )
    )
    await db.flush()

    auth_url = provider.build_authorize_url(
        client_id=client_id,
        redirect_uri=_redirect_uri(),
        state=state,
        code_challenge=_code_challenge(verifier),
    )
    return {"auth_url": auth_url, "state": state}


async def handle_oauth_callback(db: AsyncSession, code: str, state: str) -> dict:
    """Validasi state, tukar code → token, simpan connected_accounts terenkripsi.

    Return {"brand_id", "platform"}. Raise ValueError bila state tidak valid /
    kedaluwarsa; CredentialsNotConfigured bila kredensial belum lengkap.
    """
    # Callback datang tanpa sesi login (redirect browser dari provider), jadi
    # tenant belum diset: baca konteks via fungsi SECURITY DEFINER dulu.
    ctx = (
        await db.execute(
            text("SELECT * FROM public.get_oauth_state_context(:s)"), {"s": state}
        )
    ).first()
    if ctx is None:
        raise ValueError("State OAuth tidak dikenal.")
    brand_id, organization_id, platform, code_verifier, expires_at = ctx
    if expires_at < _now():
        raise ValueError("State OAuth sudah kedaluwarsa. Ulangi proses koneksi.")

    # Set tenant dari brand agar RLS (brands, connected_accounts, oauth_states) lolos.
    await db.execute(
        text("SELECT set_config('app.tenant_id', :v, false)"), {"v": str(organization_id)}
    )

    creds = await _credential_map(db)
    provider = _provider_nyata(db, platform, creds)
    client_id, client_secret = _client_id_secret(platform, creds)

    brand = await db.get(Brand, brand_id)
    if brand is None:
        raise ValueError("Brand tidak ditemukan.")

    token = await provider.exchange_code(
        code=code,
        code_verifier=code_verifier,
        redirect_uri=_redirect_uri(),
        client_id=client_id,
        client_secret=client_secret,
    )
    if not token.get("access_token"):
        raise ValueError("Provider tidak mengembalikan access_token.")

    expires_at = None
    if token.get("expires_in"):
        try:
            expires_at = _now() + timedelta(seconds=int(token["expires_in"]))
        except (TypeError, ValueError):
            expires_at = None

    account_external_id = token.get("account_external_id")
    account = await db.scalar(
        select(ConnectedAccount).where(
            ConnectedAccount.brand_id == brand.id,
            ConnectedAccount.platform == platform,
            ConnectedAccount.account_external_id == account_external_id,
        )
    )
    if account is None:
        # Akun baru: tegakkan batas multi-akun sebelum membuat baris.
        await ensure_account_capacity(db, brand, platform)
        account = ConnectedAccount(
            organization_id=brand.organization_id,
            brand_id=brand.id,
            platform=platform,
        )
        db.add(account)
    account.account_name = token.get("account_name")
    account.account_external_id = account_external_id
    account.access_token_encrypted = encrypt_text(token["access_token"])
    account.refresh_token_encrypted = (
        encrypt_text(token["refresh_token"]) if token.get("refresh_token") else None
    )
    account.token_expires_at = expires_at
    account.status = ConnectedAccountStatus.AKTIF

    st = await db.scalar(select(OAuthState).where(OAuthState.state == state))
    if st is not None:
        await db.delete(st)
    await db.flush()
    return {"brand_id": brand.id, "platform": platform}


# ---------------------------------------------------------------------------
# Sinkronisasi
# ---------------------------------------------------------------------------

async def sync_account(db: AsyncSession, account: ConnectedAccount) -> dict:
    """Sinkronisasi satu akun: fetch → normalize → upsert idempoten.

    Return {"contents_baru", "contents_diupdate"}. Bila gagal, status akun
    diset "error" dan DI-COMMIT tersendiri (tidak ikut ter-rollback pemanggil),
    lalu exception di-raise ulang (router → 502).
    """
    if account.status != ConnectedAccountStatus.AKTIF:
        raise ValueError(
            f"Akun tidak dalam status aktif (status: {account.status}). "
            "Hubungkan ulang akun bila perlu."
        )
    brand = await db.get(Brand, account.brand_id)
    if brand is None:
        raise ValueError("Brand tidak ditemukan.")

    creds = await _credential_map(db)
    provider = get_provider(account.platform, _getter(creds))
    since = (
        account.last_sync_at.date()
        if account.last_sync_at
        else date.today() - timedelta(days=SYNC_DEFAULT_SINCE_DAYS)
    )

    try:
        rows = await provider.fetch_posts(account, since)
        batch_items: list[tuple[str, dict]] = []
        for row in rows:
            try:
                normalized = normalize_content_row(account.platform, row)
            except NormalizationError:
                # Baris tak valid dari API dilewati (dicatat diam-diam).
                continue
            batch_items.append((account.platform, normalized))
        # Upsert batch: 3 roundtrip DB berapa pun jumlah baris
        # (semantik identik dengan loop per-baris: posted_at tidak
        # di-overwrite, baris duplikat dihitung sebagai update).
        baru, diupdate = await upsert_content_rows(
            db,
            brand_id=brand.id,
            organization_id=brand.organization_id,
            items=batch_items,
        )
        account.status = ConnectedAccountStatus.AKTIF
        account.last_sync_at = _now()
        await db.flush()
    except Exception:
        # Batalkan semua perubahan paruh jalan, lalu simpan status "error"
        # dalam COMMIT tersendiri. Tanpa ini, status ikut ter-rollback oleh
        # pemanggil (get_db / worker selalu rollback saat exception) sehingga
        # kegagalan tidak tercatat.
        #
        # rollback() me-recycle koneksi ke pool (SQLAlchemy 2.0); checkout
        # berikutnya bisa mendapat koneksi yang GUC RLS-nya sudah di-RESET
        # oleh request lain. Karena itu: (1) catat id/org SEBELUM rollback,
        # (2) set ulang app.tenant_id secara eksplisit, (3) pakai Core
        # update() agar tidak tergantung instance ORM yang expired.
        account_id = account.id
        organization_id = account.organization_id
        await db.rollback()
        try:
            await db.execute(
                text("SELECT set_config('app.tenant_id', :v, false)"),
                {"v": str(organization_id)},
            )
            await db.execute(
                update(ConnectedAccount)
                .where(ConnectedAccount.id == account_id)
                .values(status=ConnectedAccountStatus.ERROR)
            )
            await db.commit()
        except Exception:
            await db.rollback()
        raise
    return {"contents_baru": baru, "contents_diupdate": diupdate}
