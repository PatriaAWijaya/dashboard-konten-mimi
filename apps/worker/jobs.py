"""Job terjadwal worker.

- sync_terjadwal   : tiap N jam, sinkronkan semua ConnectedAccount aktif.
- ringkasan_mingguan: tiap Senin 07:00, buat ringkasan minggu lalu per brand
  (membership aktif) lalu notifikasi anggota org yang preferensinya on.

Fungsi-fungsi menerima parameter `backend` (duck-typed) agar mudah diuji
dengan stub; di produksi main.py memasok RealBackend dari _backend.py.

Idempotensi:
- sync: akun yang last_sync_at-nya masih dalam interval dilewati
  (guard restart scheduler); last_sync_at hanya diupdate bila sync sukses.
- ringkasan: get_or_generate_summary bersifat cached menurut kontrak
  (aman dipanggil ulang); notifikasi dideduplikasi dalam-proses per
  (user, brand, periode) bila job dijalankan ulang untuk periode yang sama.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger("worker.jobs")

ZONA_JAKARTA = ZoneInfo("Asia/Jakarta")

JENIS_NOTIFIKASI_RINGKASAN = "ringkasan_mingguan"
JENIS_NOTIFIKASI_PENGINGAT = "pengingat_membership"
STATUS_AKUN_AKTIF = "aktif"

# H-berapa pengingat membership dikirim.
HARI_PENGINGAT_MEMBERSHIP = (30, 7, 1, 0)

# Guard dalam-proses: (user_id, brand_id, period_start, period_end) yang sudah
# dikirimi notifikasi ringkasan. Melindungi dari kirim ganda bila job
# dijalankan ulang (mis. scheduler restart) untuk periode yang sama.
_sudah_dinotifikasi: set[tuple[str, str, str, str]] = set()

# Guard dalam-proses pengingat membership: (organization_id, tanggal_kedaluwarsa).
_sudah_diingatkan_membership: set[tuple[str, str]] = set()


def reset_state() -> None:
    """Bersihkan state dalam-proses (dipakai tes)."""
    _sudah_dinotifikasi.clear()
    _sudah_diingatkan_membership.clear()


def minggu_lalu(hari_ini: date | None = None) -> tuple[date, date]:
    """Hitung periode Senin–Minggu pada minggu lalu (zona Asia/Jakarta).

    Relatif terhadap hari job berjalan, sehingga tetap benar walau job
    mundur/maju dari Senin 07:00 karena drift scheduler.
    """
    if hari_ini is None:
        hari_ini = datetime.now(ZONA_JAKARTA).date()
    senin_ini = hari_ini - timedelta(days=hari_ini.weekday())
    mulai = senin_ini - timedelta(days=7)
    selesai = mulai + timedelta(days=6)
    return mulai, selesai


async def sync_terjadwal(backend: Any, *, interval_hours: int = 6) -> dict:
    """Sinkronkan semua ConnectedAccount berstatus aktif.

    Tiap akun memakai session sendiri; error pada satu akun dicatat lalu
    lanjut ke akun berikutnya (tidak menghentikan loop).
    """
    job = "sync_terjadwal"
    logger.info("job=%s mulai interval_hours=%d", job, interval_hours)
    ok = gagal = dilewati = 0

    async with backend.open_session() as db:
        accounts = await backend.list_active_accounts(db)
    logger.info("job=%s akun_aktif=%d", job, len(accounts))

    for account in accounts:
        account_id = getattr(account, "id", "?")
        try:
            if not backend.should_sync_account(account, interval_hours):
                dilewati += 1
                logger.info("job=%s akun=%s dilewati (baru saja disync)", job, account_id)
                continue
            async with backend.open_session() as db:
                hasil = await backend.sync_account(db, account)
                await backend.mark_account_synced(db, account)
            ok += 1
            logger.info(
                "job=%s akun=%s ok baru=%s diupdate=%s",
                job,
                account_id,
                (hasil or {}).get("contents_baru"),
                (hasil or {}).get("contents_diupdate"),
            )
        except Exception:
            gagal += 1
            logger.exception("job=%s akun=%s gagal", job, account_id)

    logger.info(
        "job=%s selesai ok=%d gagal=%d dilewati=%d", job, ok, gagal, dilewati
    )
    return {"ok": ok, "gagal": gagal, "dilewati": dilewati}


async def ringkasan_mingguan(backend: Any, *, hari_ini: date | None = None) -> dict:
    """Buat ringkasan minggu lalu per brand lalu notifikasi anggota org.

    Untuk tiap brand yang membership org-nya aktif: panggil
    get_or_generate_summary (cached menurut kontrak, aman bila sudah ada),
    lalu notify tiap anggota org yang preferensinya on dengan
    jenis='ringkasan_mingguan'. Error pada satu brand tidak menghentikan
    brand lain.
    """
    job = "ringkasan_mingguan"
    mulai, selesai = minggu_lalu(hari_ini)
    logger.info("job=%s mulai periode=%s s.d. %s", job, mulai, selesai)

    llm = backend.get_llm_provider()
    brand_ok = brand_gagal = terkirim = notif_dilewati = 0

    async with backend.open_session() as db:
        targets = await backend.list_brands_with_active_membership(db)
    logger.info("job=%s brand_target=%d", job, len(targets))

    for brand, org in targets:
        brand_id = str(getattr(brand, "id", "?"))
        org_id = getattr(org, "id", None)
        try:
            async with backend.open_session() as db:
                await backend.get_or_generate_summary(
                    db, brand, org_id, mulai, selesai, llm
                )
            async with backend.open_session() as db:
                members = await backend.list_org_members(db, org_id)
            for user in members:
                user_id = str(getattr(user, "id", "?"))
                if not backend.member_wants_summary(user):
                    notif_dilewati += 1
                    continue
                kunci = (user_id, brand_id, mulai.isoformat(), selesai.isoformat())
                if kunci in _sudah_dinotifikasi:
                    notif_dilewati += 1
                    continue
                async with backend.open_session() as db:
                    await backend.notify(
                        db,
                        user,
                        JENIS_NOTIFIKASI_RINGKASAN,
                        {
                            "brand_id": brand_id,
                            "brand_name": getattr(brand, "name", ""),
                            "period_start": mulai.isoformat(),
                            "period_end": selesai.isoformat(),
                        },
                    )
                _sudah_dinotifikasi.add(kunci)
                terkirim += 1
            brand_ok += 1
            logger.info(
                "job=%s brand=%s ok anggota=%d terkirim=%d",
                job,
                getattr(brand, "name", brand_id),
                len(members),
                terkirim,
            )
        except Exception:
            brand_gagal += 1
            logger.exception("job=%s brand=%s gagal", job, brand_id)

    logger.info(
        "job=%s selesai periode=%s s.d. %s brand_ok=%d brand_gagal=%d "
        "notif_terkirim=%d notif_dilewati=%d",
        job,
        mulai,
        selesai,
        brand_ok,
        brand_gagal,
        terkirim,
        notif_dilewati,
    )
    return {
        "period_start": mulai.isoformat(),
        "period_end": selesai.isoformat(),
        "brand_ok": brand_ok,
        "brand_gagal": brand_gagal,
        "notif_terkirim": terkirim,
        "notif_dilewati": notif_dilewati,
    }


# ---------------------------------------------------------------------------
# Pengingat membership (PRD 10.8, versi mock)
# ---------------------------------------------------------------------------

async def pengingat_membership(backend: Any, *, hari_ini: date | None = None) -> dict:
    """Kirim pengingat ke org yang membership-nya kedaluwarsa H-30/H-7/H-1/H-0.

    Untuk tiap membership aktif yang tanggal kedaluwarsanya (zona Asia/Jakarta)
    jatuh tepat pada salah satu ambang: notify_org dengan jenis
    'pengingat_membership' berisi sisa hari + tanggal kedaluwarsa.
    Error pada satu org tidak menghentikan org lain. Guard dalam-proses
    mencegah kirim ganda bila job dijalankan ulang di hari yang sama.
    """
    job = "pengingat_membership"
    if hari_ini is None:
        hari_ini = datetime.now(ZONA_JAKARTA).date()
    target = {hari_ini + timedelta(days=d) for d in HARI_PENGINGAT_MEMBERSHIP}
    logger.info(
        "job=%s mulai hari_ini=%s target=%s",
        job, hari_ini, sorted(d.isoformat() for d in target),
    )

    async with backend.open_session() as db:
        rows = await backend.list_memberships_expiring(db, target)
    logger.info("job=%s kandidat=%d", job, len(rows))

    terkirim = dilewati = gagal = 0
    for membership, org in rows:
        org_id = str(getattr(org, "id", "?"))
        try:
            ends_at = getattr(membership, "ends_at", None)
            if ends_at is None:
                dilewati += 1
                continue
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
            tanggal = ends_at.astimezone(ZONA_JAKARTA).date()
            sisa_hari = (tanggal - hari_ini).days
            kunci = (org_id, tanggal.isoformat())
            if kunci in _sudah_diingatkan_membership:
                dilewati += 1
                continue
            async with backend.open_session() as db:
                await backend.notify_org(
                    db,
                    getattr(org, "id"),
                    JENIS_NOTIFIKASI_PENGINGAT,
                    {
                        "nama_organisasi": getattr(org, "name", ""),
                        "sisa_hari": sisa_hari,
                        "tanggal_kedaluwarsa": tanggal.isoformat(),
                    },
                )
            _sudah_diingatkan_membership.add(kunci)
            terkirim += 1
            logger.info(
                "job=%s org=%s sisa_hari=%d terkirim", job, getattr(org, "name", org_id), sisa_hari
            )
        except Exception:
            gagal += 1
            logger.exception("job=%s org=%s gagal", job, org_id)

    logger.info(
        "job=%s selesai terkirim=%d dilewati=%d gagal=%d",
        job, terkirim, dilewati, gagal,
    )
    return {"terkirim": terkirim, "dilewati": dilewati, "gagal": gagal}
