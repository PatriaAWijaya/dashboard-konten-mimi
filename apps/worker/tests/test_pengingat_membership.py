"""Tes job pengingat membership (PRD 10.8, versi mock).

Job pengingat_membership memakai backend duck-typed; StubBackend di bawah
mengimplementasikan kontrak: open_session, list_memberships_expiring,
notify_org. Kasus:
- membership H-7 terpicu (notify_org dipanggil dengan sisa_hari=7),
- membership yang tidak mendekati ambang TIDAK terpicu,
- H-30/H-1/H-0 juga terpicu,
- run ulang di hari yang sama tidak mengirim ganda (guard dalam-proses).

Jalankan dari apps/worker:
    PYTHONPATH=/home/hatch/workspace/dashboard-konten-ai/apps/api \
        ../api/.venv/bin/python -m pytest -q
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worker import jobs  # noqa: E402
from worker.jobs import pengingat_membership  # noqa: E402

ZONA = ZoneInfo("Asia/Jakarta")


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class StubBackend:
    """Backend palsu untuk kontrak pengingat membership."""

    def __init__(self, rows):
        # rows: list[(membership_ns, org_ns)]
        self.rows = rows
        self.notify_calls = []  # [(org_id, jenis, payload)]

    @asynccontextmanager
    async def open_session(self):
        yield FakeSession()

    async def list_memberships_expiring(self, db, tanggal_target):
        return [
            (m, o)
            for m, o in self.rows
            if m.ends_at.astimezone(ZONA).date() in tanggal_target
        ]

    async def notify_org(self, db, organization_id, jenis, payload):
        self.notify_calls.append((str(organization_id), jenis, payload))
        return {"terkirim": 1, "dilewati": 0, "gagal": 0}


def _membership(org_id, sisa_hari, hari_ini):
    ends = datetime(hari_ini.year, hari_ini.month, hari_ini.day, 10, 0, tzinfo=ZONA) + timedelta(
        days=sisa_hari
    )
    return SimpleNamespace(id=f"m-{org_id}", organization_id=org_id, ends_at=ends, status="active")


def _org(org_id):
    return SimpleNamespace(id=org_id, name=f"Org {org_id}")


@pytest.fixture(autouse=True)
def _reset():
    jobs.reset_state()
    yield
    jobs.reset_state()


def _hari_ini():
    return datetime.now(ZONA).date()


def test_h7_terpicu_yang_jauh_tidak():
    hari_ini = _hari_ini()
    rows = [
        (_membership("org-h7", 7, hari_ini), _org("org-h7")),
        (_membership("org-jauh", 45, hari_ini), _org("org-jauh")),
        (_membership("org-lewat", -3, hari_ini), _org("org-lewat")),
    ]
    backend = StubBackend(rows)
    hasil = __import__("asyncio").run(pengingat_membership(backend, hari_ini=hari_ini))
    assert hasil["terkirim"] == 1
    assert hasil["gagal"] == 0
    assert len(backend.notify_calls) == 1
    org_id, jenis, payload = backend.notify_calls[0]
    assert org_id == "org-h7"
    assert jenis == "pengingat_membership"
    assert payload["sisa_hari"] == 7
    assert payload["tanggal_kedaluwarsa"] == (hari_ini + timedelta(days=7)).isoformat()
    assert payload["nama_organisasi"] == "Org org-h7"


@pytest.mark.parametrize("sisa_hari", [30, 7, 1, 0])
def test_semua_ambang_terpicu(sisa_hari):
    hari_ini = _hari_ini()
    backend = StubBackend([(_membership("org-x", sisa_hari, hari_ini), _org("org-x"))])
    hasil = __import__("asyncio").run(pengingat_membership(backend, hari_ini=hari_ini))
    assert hasil["terkirim"] == 1
    _, _, payload = backend.notify_calls[0]
    assert payload["sisa_hari"] == sisa_hari


def test_tidak_kirim_ganda_di_hari_yang_sama():
    hari_ini = _hari_ini()
    backend = StubBackend([(_membership("org-x", 7, hari_ini), _org("org-x"))])
    r1 = __import__("asyncio").run(pengingat_membership(backend, hari_ini=hari_ini))
    r2 = __import__("asyncio").run(pengingat_membership(backend, hari_ini=hari_ini))
    assert r1["terkirim"] == 1
    assert r2["terkirim"] == 0
    assert r2["dilewati"] == 1
    assert len(backend.notify_calls) == 1


def test_error_satu_org_tidak_menghentikan_lain():
    hari_ini = _hari_ini()

    class BackendRusak(StubBackend):
        async def notify_org(self, db, organization_id, jenis, payload):
            if str(organization_id) == "org-rusak":
                raise RuntimeError("gagal kirim")
            return await super().notify_org(db, organization_id, jenis, payload)

    rows = [
        (_membership("org-rusak", 7, hari_ini), _org("org-rusak")),
        (_membership("org-ok", 1, hari_ini), _org("org-ok")),
    ]
    backend = BackendRusak(rows)
    hasil = __import__("asyncio").run(pengingat_membership(backend, hari_ini=hari_ini))
    assert hasil["terkirim"] == 1
    assert hasil["gagal"] == 1
    assert backend.notify_calls[0][0] == "org-ok"


def test_jadwal_pengingat_terdaftar():
    """Job pengingat_membership terjadwal harian 08:00 Asia/Jakarta."""
    from worker.config import load_config
    from worker.main import create_scheduler

    config = load_config()
    assert config.reminder_cron == "0 8 * * *"
    scheduler = create_scheduler(backend=object(), config=config)
    job = scheduler.get_job("pengingat_membership")
    assert job is not None
    assert str(job.trigger) != ""
