"""Pengaturan global terenkripsi (app_settings).

Nilai disimpan terenkripsi Fernet. Baca memakai fungsi SECURITY DEFINER
public.get_app_setting_value() agar service backend (OAuth/sync) bisa membaca
tanpa hak superadmin; tulis langsung ke tabel (RLS: hanya superadmin).
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_text, encrypt_text
from app.models.fase2 import AppSetting

logger = logging.getLogger(__name__)


async def get_setting(db: AsyncSession, key: str) -> str | None:
    """Ambil nilai pengaturan (terdekripsi). None bila belum diset."""
    row = (
        await db.execute(
            text("SELECT public.get_app_setting_value(:k) AS v"), {"k": key}
        )
    ).first()
    encrypted = row[0] if row else None
    if not encrypted:
        return None
    try:
        return decrypt_text(encrypted)
    except ValueError:
        logger.warning("app_settings[%s] tidak bisa didekripsi (kunci salah/korup).", key)
        return None


async def set_setting(db: AsyncSession, key: str, value: str | None) -> None:
    """Simpan nilai terenkripsi. value None/kosong = hapus pengaturan."""
    if value is None or not str(value).strip():
        existing = await db.get(AppSetting, key)
        if existing is not None:
            await db.delete(existing)
            await db.flush()
        return
    encrypted = encrypt_text(str(value).strip())
    existing = await db.get(AppSetting, key)
    if existing is None:
        db.add(AppSetting(key=key, value_encrypted=encrypted))
    else:
        existing.value_encrypted = encrypted
    await db.flush()


async def is_setting_configured(db: AsyncSession, key: str) -> bool:
    return bool(await get_setting(db, key))
