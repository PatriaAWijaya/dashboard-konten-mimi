"""Notifikasi Fase 2: provider (mock/WhatsApp) + preferensi per user.

Kontrak worker (disepakati): SEMUA logika preferensi ada di dalam notify():
- notify() WAJIB cek notification_preferences (buat baris default true bila
  belum ada).
- Preferensi off → lewati pengiriman diam-diam TAPI tetap tulis
  notification_logs dengan status='skipped'.
- Preferensi on → kirim via provider aktif, tulis log status='sent'/'failed'.
- Return True bila terkirim, False bila tidak.

Provider aktif default = mock (tulis ke notification_logs + log). WhatsApp
dipakai bila app_settings whatsapp_provider & whatsapp_api_key terisi.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.fase2 import NotificationLog, NotificationLogStatus, NotificationPreference
from app.models.organization import OrganizationMember
from app.models.user import User
from app.services.settings import get_setting

logger = logging.getLogger(__name__)

# jenis notifikasi -> atribut preferensi
JENIS_PREFERENSI = {
    "rekomendasi_baru": "rekomendasi_baru",
    "ringkasan_mingguan": "ringkasan_mingguan",
}


class NotConfigured(Exception):
    """Layanan notifikasi belum dikonfigurasi (kredensial admin kosong)."""


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class NotificationProvider(ABC):
    channel: str = ""

    @abstractmethod
    async def send(self, *, user: User, jenis: str, payload: dict) -> dict:
        """Kirim notifikasi. Return info hasil. Raise bila gagal."""
        raise NotImplementedError


class MockNotificationProvider(NotificationProvider):
    """Provider dev: tidak mengirim ke mana-mana, hanya dicatat di log."""

    channel = "mock"

    async def send(self, *, user: User, jenis: str, payload: dict) -> dict:
        logger.info(
            "Notifikasi mock → user=%s jenis=%s payload=%s",
            user.email, jenis, {k: v for k, v in payload.items() if k != "organization_id"},
        )
        return {"ok": True, "channel": "mock"}


class WhatsAppNotificationProvider(NotificationProvider):
    """Provider WhatsApp via layanan pihak ketiga.

    Kredensial dibaca dari app_settings (whatsapp_provider, whatsapp_api_key).
    Bila tidak ada → NotConfigured. TIDAK mendaftarkan layanan apa pun;
    Patria memilih & mendaftarkan sendiri (mis. Fonnte/Wablas).
    """

    channel = "whatsapp"

    def __init__(self, *, provider_name: str, api_key: str) -> None:
        self.provider_name = provider_name.strip().lower()
        self.api_key = api_key

    async def send(self, *, user: User, jenis: str, payload: dict) -> dict:
        if not user.whatsapp:
            raise NotConfigured(
                f"User {user.email} belum mengisi nomor WhatsApp di profil."
            )
        pesan = _format_pesan(jenis, payload)
        if self.provider_name == "fonnte":
            return await self._send_fonnte(user.whatsapp, pesan)
        raise NotConfigured(
            f"Provider WhatsApp '{self.provider_name}' belum didukung. "
            "Isi app_settings 'whatsapp_provider' dengan 'fonnte' atau matikan "
            "agar kembali ke provider mock."
        )

    async def _send_fonnte(self, nomor: str, pesan: str) -> dict:
        """Kirim via Fonnte (best-effort, belum teruji tanpa API key asli)."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.fonnte.com/send",
                headers={"Authorization": self.api_key},
                data={"target": nomor, "message": pesan},
            )
        if resp.status_code != 200:
            raise RuntimeError(f"Fonnte HTTP {resp.status_code}: {resp.text[:200]}")
        return {"ok": True, "channel": "whatsapp", "provider": "fonnte"}


def _format_pesan(jenis: str, payload: dict) -> str:
    brand = payload.get("brand_name") or "brand Anda"
    if jenis == "rekomendasi_baru":
        jumlah = payload.get("jumlah", 0)
        return (
            f"MySocial Watch: {jumlah} rekomendasi baru untuk {brand} "
            f"periode {payload.get('period_start')}–{payload.get('period_end')}. "
            "Buka dashboard untuk detailnya."
        )
    if jenis == "ringkasan_mingguan":
        return (
            f"MySocial Watch: ringkasan mingguan {brand} "
            f"({payload.get('period_start')}–{payload.get('period_end')}) sudah tersedia. "
            "Buka dashboard untuk membacanya."
        )
    if jenis == "aktivasi_membership":
        return (
            f"MySocial Watch: membership {payload.get('nama_organisasi') or 'organisasi Anda'} "
            f"telah AKTIF hingga {payload.get('tanggal_kedaluwarsa')}. "
            f"Masuk di {payload.get('login_url')} untuk mulai memakai dashboard."
        )
    if jenis == "pengingat_membership":
        return (
            f"MySocial Watch: membership {payload.get('nama_organisasi') or 'organisasi Anda'} "
            f"berakhir dalam {payload.get('sisa_hari')} hari "
            f"({payload.get('tanggal_kedaluwarsa')}). Segera perpanjang agar layanan tidak terhenti."
        )
    return f"MySocial Watch: notifikasi '{jenis}' untuk {brand}."


async def get_notification_provider(db: AsyncSession) -> NotificationProvider:
    """Provider aktif: WhatsApp bila kredensial lengkap, else mock."""
    provider_name = await get_setting(db, "whatsapp_provider")
    api_key = await get_setting(db, "whatsapp_api_key")
    if provider_name and api_key:
        return WhatsAppNotificationProvider(provider_name=provider_name, api_key=api_key)
    return MockNotificationProvider()


# ---------------------------------------------------------------------------
# Preferensi
# ---------------------------------------------------------------------------

async def get_or_create_preference(db: AsyncSession, user_id: uuid.UUID) -> NotificationPreference:
    pref = await db.get(NotificationPreference, user_id)
    if pref is None:
        pref = NotificationPreference(user_id=user_id)
        db.add(pref)
        await db.flush()
    return pref


# ---------------------------------------------------------------------------
# notify(): satu pintu (dipakai service & worker)
# ---------------------------------------------------------------------------

async def notify(db: AsyncSession, user: User, jenis: str, payload: dict) -> bool:
    """Kirim notifikasi ke user sesuai preferensinya. Return True bila terkirim.

    payload wajib memuat 'organization_id' (str/UUID); 'brand_id' opsional.
    Selalu menulis baris notification_logs: 'sent' / 'failed' / 'skipped'.
    """
    org_id = payload.get("organization_id")
    if not org_id:
        raise ValueError("payload notifikasi wajib memuat 'organization_id'.")
    try:
        org_uuid = uuid.UUID(str(org_id))
    except ValueError as exc:
        raise ValueError("organization_id di payload tidak valid.") from exc
    brand_uuid = None
    if payload.get("brand_id"):
        try:
            brand_uuid = uuid.UUID(str(payload["brand_id"]))
        except ValueError as exc:
            raise ValueError("brand_id di payload tidak valid.") from exc

    pref = await get_or_create_preference(db, user.id)
    attr = JENIS_PREFERENSI.get(jenis)
    boleh_kirim = bool(getattr(pref, attr, True)) if attr else True

    log = NotificationLog(
        user_id=user.id,
        organization_id=org_uuid,
        brand_id=brand_uuid,
        jenis=jenis,
        channel="none",
        payload=dict(payload),
        status=NotificationLogStatus.SKIPPED,
    )

    if not boleh_kirim:
        # Preferensi off: lewati diam-diam, tapi tetap tercatat.
        db.add(log)
        await db.flush()
        return False

    provider = await get_notification_provider(db)
    log.channel = provider.channel
    try:
        await provider.send(user=user, jenis=jenis, payload=dict(payload))
        log.status = NotificationLogStatus.SENT
        terkirim = True
    except Exception as exc:  # noqa: BLE001 — kegagalan provider dicatat, bukan crash
        log.status = NotificationLogStatus.FAILED
        log.payload = {**dict(payload), "error": str(exc)[:500]}
        terkirim = False
    db.add(log)
    await db.flush()
    return terkirim


async def notify_org(
    db: AsyncSession, organization_id: uuid.UUID, jenis: str, payload: dict
) -> dict:
    """Kirim ke semua anggota aktif organisasi.

    Worker memanggil ini / notify() per anggota TANPA filter sendiri —
    preferensi dicek di dalam notify().
    """
    members = (
        await db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == organization_id)
            .options(selectinload(OrganizationMember.user))
        )
    ).scalars().all()
    terkirim = dilewati = gagal = 0
    for m in members:
        user = m.user
        if user is None or not user.is_active:
            continue
        try:
            ok = await notify(
                db, user, jenis, {**dict(payload), "organization_id": str(organization_id)}
            )
        except Exception:  # noqa: BLE001
            gagal += 1
            continue
        if ok:
            terkirim += 1
        else:
            dilewati += 1
    return {"terkirim": terkirim, "dilewati": dilewati, "gagal": gagal}
