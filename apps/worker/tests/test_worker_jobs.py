"""Tes job worker dengan STUB backend (backend Fase 2 belum dibangun).

StubBackend di bawah memakai fake async function BERNAMA SAMA dengan kontrak
backend: sync_account, get_or_generate_summary, notify, get_llm_provider.
Setiap pemanggilan dicatat sehingga tes bisa memverifikasi perilaku job:

- scheduler memanggil job yang benar dengan trigger/interval yang benar,
- error pada satu akun/brand tidak menghentikan loop,
- periode ringkasan = Senin–Minggu minggu lalu (termasuk batas bulan/tahun),
- notifikasi hanya ke anggota yang preferensinya on + tidak dobel.

Jalankan dari apps/worker:
    pytest
"""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker import jobs  # noqa: E402
from worker._backend import (  # noqa: E402
    PESAN_BACKEND_BELUM_SIAP,
    BackendNotReadyError,
    RealBackend,
)
from worker.config import WorkerConfig, load_config  # noqa: E402
from worker.jobs import minggu_lalu, ringkasan_mingguan, sync_terjadwal  # noqa: E402
from worker.main import create_scheduler  # noqa: E402


# ===================================================================== stub
class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class StubBackend:
    """Backend palsu: fungsi bernama sama seperti kontrak, mencatat pemanggilan."""

    def __init__(self):
        self.accounts = []  # SimpleNamespace(id, status, last_sync_at)
        self.brands = []  # list[(brand_ns, org_ns)]
        self.members = {}  # org_id -> [user_ns(id, notif_ringkasan_mingguan)]
        self.sync_calls = []  # [account_id]
        self.mark_calls = []  # [account_id]
        self.summary_calls = []  # [dict]
        self.notify_calls = []  # [(user_id, jenis, payload)]
        self.gagal_sync = set()  # account_id yang raise saat sync
        self.gagal_summary = set()  # brand_id yang raise saat summary
        self.llm = SimpleNamespace(nama="stub-llm")

    @asynccontextmanager
    async def open_session(self):
        yield FakeSession()

    # ---- fungsi kontrak (nama persis sama) ----
    async def sync_account(self, db, account):
        self.sync_calls.append(account.id)
        if account.id in self.gagal_sync:
            raise RuntimeError(f"sync gagal untuk {account.id}")
        return {"contents_baru": 2, "contents_diupdate": 1}

    async def get_or_generate_summary(
        self, db, brand, org_id, period_start, period_end, llm
    ):
        self.summary_calls.append(
            {
                "brand_id": brand.id,
                "org_id": org_id,
                "period_start": period_start,
                "period_end": period_end,
                "llm": llm,
            }
        )
        if brand.id in self.gagal_summary:
            raise RuntimeError(f"summary gagal untuk {brand.id}")
        return SimpleNamespace(id="summary-1")

    async def notify(self, db, user, jenis, payload):
        self.notify_calls.append((user.id, jenis, payload))

    def get_llm_provider(self):
        return self.llm

    # ---- helper internal (cerminan RealBackend, perilaku yang diuji) ----
    async def list_active_accounts(self, db):
        return [a for a in self.accounts if a.status == "aktif"]

    def should_sync_account(self, account, interval_hours):
        last = account.last_sync_at
        if last is None:
            return True
        return datetime.now(timezone.utc) - last >= timedelta(hours=interval_hours)

    async def mark_account_synced(self, db, account):
        self.mark_calls.append(account.id)
        account.last_sync_at = datetime.now(timezone.utc)

    async def list_brands_with_active_membership(self, db):
        return list(self.brands)

    async def list_org_members(self, db, org_id):
        return list(self.members.get(org_id, []))

    def member_wants_summary(self, user):
        return bool(getattr(user, "notif_ringkasan_mingguan", True))


def _akun(id_, status="aktif", last_sync_at=None):
    return SimpleNamespace(id=id_, status=status, last_sync_at=last_sync_at)


def _brand_org(brand_id, org_id, nama="Brand A"):
    return (
        SimpleNamespace(id=brand_id, name=nama),
        SimpleNamespace(id=org_id),
    )


@pytest.fixture(autouse=True)
def _bersih_state():
    jobs.reset_state()
    yield
    jobs.reset_state()


# ============================================================ periode
@pytest.mark.parametrize(
    "hari_ini, exp_mulai, exp_selesai",
    [
        # Senin 2026-09-28 -> minggu lalu 21-27 Sep 2026
        (date(2026, 9, 28), date(2026, 9, 21), date(2026, 9, 27)),
        # Batas tahun: Senin 2026-01-05 -> 29 Des 2025 - 4 Jan 2026
        (date(2026, 1, 5), date(2025, 12, 29), date(2026, 1, 4)),
        # Batas bulan: Senin 2026-03-02 -> 23 Feb - 1 Mar 2026
        (date(2026, 3, 2), date(2026, 2, 23), date(2026, 3, 1)),
        # Bukan Senin (Sabtu 2026-09-26) -> tetap minggu kalender lalu
        (date(2026, 9, 26), date(2026, 9, 14), date(2026, 9, 20)),
    ],
)
def test_minggu_lalu(hari_ini, exp_mulai, exp_selesai):
    mulai, selesai = minggu_lalu(hari_ini)
    assert (mulai, selesai) == (exp_mulai, exp_selesai)
    assert mulai.weekday() == 0  # Senin
    assert selesai.weekday() == 6  # Minggu
    assert (selesai - mulai).days == 6


# ============================================================ sync job
async def test_sync_memanggil_semua_akun_aktif():
    backend = StubBackend()
    backend.accounts = [_akun("a1"), _akun("a2"), _akun("a3")]

    hasil = await sync_terjadwal(backend, interval_hours=6)

    assert backend.sync_calls == ["a1", "a2", "a3"]
    assert backend.mark_calls == ["a1", "a2", "a3"]  # last_sync_at diupdate
    assert all(a.last_sync_at is not None for a in backend.accounts)
    assert hasil == {"ok": 3, "gagal": 0, "dilewati": 0}


async def test_sync_error_satu_akun_tidak_menghentikan_loop():
    backend = StubBackend()
    backend.accounts = [_akun("a1"), _akun("a2"), _akun("a3")]
    backend.gagal_sync = {"a2"}

    hasil = await sync_terjadwal(backend, interval_hours=6)

    assert backend.sync_calls == ["a1", "a2", "a3"]  # semua tetap dicoba
    assert backend.mark_calls == ["a1", "a3"]  # yang gagal tidak di-mark
    assert hasil == {"ok": 2, "gagal": 1, "dilewati": 0}


async def test_sync_lewati_akun_yang_baru_saja_disync():
    backend = StubBackend()
    baru = datetime.now(timezone.utc) - timedelta(hours=1)
    lama = datetime.now(timezone.utc) - timedelta(hours=10)
    backend.accounts = [
        _akun("baru", last_sync_at=baru),
        _akun("lama", last_sync_at=lama),
        _akun("pernah-tidak", last_sync_at=None),
    ]

    hasil = await sync_terjadwal(backend, interval_hours=6)

    assert backend.sync_calls == ["lama", "pernah-tidak"]
    assert hasil == {"ok": 2, "gagal": 0, "dilewati": 1}


async def test_sync_tidak_ada_akun_aktif():
    backend = StubBackend()
    hasil = await sync_terjadwal(backend, interval_hours=6)
    assert hasil == {"ok": 0, "gagal": 0, "dilewati": 0}
    assert backend.sync_calls == []


# ============================================================ scheduler
def test_scheduler_registrasi_trigger_benar():
    backend = StubBackend()
    config = WorkerConfig(
        sync_interval_hours=2, summary_cron="0 7 * * 1", timezone="Asia/Jakarta"
    )
    scheduler = create_scheduler(backend, config)

    job_sync = scheduler.get_job("sync_terjadwal")
    job_ringkas = scheduler.get_job("ringkasan_mingguan")
    assert job_sync is not None and job_ringkas is not None

    # Interval sesuai env (2 jam pada tes ini)
    assert "2:00:00" in str(job_sync.trigger)
    # Cron: Senin (1) jam 07:00, zona Asia/Jakarta
    cron_str = str(job_ringkas.trigger)
    assert "day_of_week='1'" in cron_str
    assert "hour='7'" in cron_str
    assert "minute='0'" in cron_str
    assert "Asia/Jakarta" in str(job_ringkas.trigger.timezone)

    if scheduler.running:
        scheduler.shutdown(wait=False)


async def test_scheduler_memanggil_job_stub():
    """Job yang didaftarkan scheduler benar-benar memanggil backend stub."""
    backend = StubBackend()
    backend.accounts = [_akun("a1")]
    backend.brands = [_brand_org("b1", "o1")]
    backend.members = {"o1": [SimpleNamespace(id="u1")]}
    config = WorkerConfig(timezone="Asia/Jakarta")
    scheduler = create_scheduler(backend, config)

    await scheduler.get_job("sync_terjadwal").func()
    assert backend.sync_calls == ["a1"]

    await scheduler.get_job("ringkasan_mingguan").func()
    assert len(backend.summary_calls) == 1
    assert backend.notify_calls and backend.notify_calls[0][1] == "ringkasan_mingguan"

    if scheduler.running:
        scheduler.shutdown(wait=False)


def test_scheduler_cron_tidak_valid_gagal_jelas():
    backend = StubBackend()
    config = WorkerConfig(summary_cron="bukan-cron")
    with pytest.raises(ValueError, match="SUMMARY_CRON tidak valid"):
        create_scheduler(backend, config)


# ============================================================ ringkasan
async def test_ringkasan_periode_dan_notifikasi_benar():
    backend = StubBackend()
    backend.brands = [_brand_org("b1", "o1", nama="Kopi Kita")]
    backend.members = {
        "o1": [
            SimpleNamespace(id="u1", notif_ringkasan_mingguan=True),
            SimpleNamespace(id="u2", notif_ringkasan_mingguan=False),  # pref off
        ]
    }

    hasil = await ringkasan_mingguan(backend, hari_ini=date(2026, 9, 28))

    # Periode Senin-Minggu lalu diteruskan ke summary (cached per kontrak)
    assert len(backend.summary_calls) == 1
    panggilan = backend.summary_calls[0]
    assert panggilan["period_start"] == date(2026, 9, 21)
    assert panggilan["period_end"] == date(2026, 9, 27)
    assert panggilan["org_id"] == "o1"
    assert panggilan["llm"] is backend.llm

    # Hanya anggota dengan preferensi on yang dinotifikasi
    assert len(backend.notify_calls) == 1
    user_id, jenis, payload = backend.notify_calls[0]
    assert user_id == "u1"
    assert jenis == "ringkasan_mingguan"
    assert payload["brand_id"] == "b1"
    assert payload["brand_name"] == "Kopi Kita"

    assert hasil["brand_ok"] == 1
    assert hasil["notif_terkirim"] == 1
    assert hasil["notif_dilewati"] == 1


async def test_ringkasan_idempoten_tidak_kirim_notif_ganda():
    """Job dijalankan 2x untuk periode sama -> notifikasi tidak dobel."""
    backend = StubBackend()
    backend.brands = [_brand_org("b1", "o1")]
    backend.members = {"o1": [SimpleNamespace(id="u1")]}

    await ringkasan_mingguan(backend, hari_ini=date(2026, 9, 28))
    await ringkasan_mingguan(backend, hari_ini=date(2026, 9, 28))

    # summary boleh dipanggil ulang (cached menurut kontrak), notif tidak dobel
    assert len(backend.summary_calls) == 2
    assert len(backend.notify_calls) == 1


async def test_ringkasan_error_satu_brand_tidak_menghentikan_lain():
    backend = StubBackend()
    backend.brands = [_brand_org("b1", "o1"), _brand_org("b2", "o2")]
    backend.members = {"o1": [SimpleNamespace(id="u1")], "o2": [SimpleNamespace(id="u2")]}
    backend.gagal_summary = {"b1"}

    hasil = await ringkasan_mingguan(backend, hari_ini=date(2026, 9, 28))

    assert hasil["brand_ok"] == 1
    assert hasil["brand_gagal"] == 1
    # brand b2 tetap diproses penuh
    assert any(p["brand_id"] == "b2" for p in backend.summary_calls)
    assert any(n[0] == "u2" for n in backend.notify_calls)


# ============================================================ config
def test_load_config_default():
    for var in ("SYNC_INTERVAL_HOURS", "SUMMARY_CRON", "WORKER_TIMEZONE"):
        os.environ.pop(var, None)
    config = load_config()
    assert config.sync_interval_hours == 6
    assert config.summary_cron == "0 7 * * 1"
    assert config.timezone == "Asia/Jakarta"


def test_load_config_dari_env(monkeypatch):
    monkeypatch.setenv("SYNC_INTERVAL_HOURS", "2")
    monkeypatch.setenv("SUMMARY_CRON", "30 8 * * 1")
    config = load_config()
    assert config.sync_interval_hours == 2
    assert config.summary_cron == "30 8 * * 1"


def test_load_config_tidak_valid_pakai_default(monkeypatch):
    monkeypatch.setenv("SYNC_INTERVAL_HOURS", "nol")
    assert load_config().sync_interval_hours == 6
    monkeypatch.setenv("SYNC_INTERVAL_HOURS", "-3")
    assert load_config().sync_interval_hours == 6


# ============================================================ backend belum siap
def test_backend_belum_siap_pesan_jelas(monkeypatch):
    """Bila modul app.* tidak bisa diimport, error-nya jelas (hermetik).

    Mensimulasikan kondisi "backend belum tersedia" dengan memblokir import,
    sehingga tes tidak bergantung pada keadaan environment (apakah backend
    kebetulan terinstal atau tidak).
    """
    import importlib

    import worker._backend as backend_mod

    asli_import_module = importlib.import_module

    def import_diblokir(nama, *args, **kwargs):
        if nama == "app" or nama.startswith("app."):
            raise ImportError(f"modul {nama} diblokir untuk tes ini")
        return asli_import_module(nama, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", import_diblokir)
    monkeypatch.setattr(backend_mod, "importlib", importlib)
    for nama_modul in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        monkeypatch.delitem(sys.modules, nama_modul, raising=False)

    backend = RealBackend()
    with pytest.raises(BackendNotReadyError) as excinfo:
        backend.check_ready()
    assert PESAN_BACKEND_BELUM_SIAP in str(excinfo.value)
