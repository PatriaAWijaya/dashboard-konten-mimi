"""Entrypoint worker Dashboard Konten AI (Fase 2).

Jalankan dari direktori apps/worker:
    python -m worker.main

Menambahkan apps/api ke sys.path agar `from app... import ...` bekerja,
membaca konfigurasi dari env, lalu menjalankan AsyncIOScheduler dengan tiga job:
- sync_terjadwal    : tiap SYNC_INTERVAL_HOURS jam (default 6)
- ringkasan_mingguan: cron SUMMARY_CRON (default "0 7 * * 1", Senin 07:00 WIB)
- pengingat_membership: cron REMINDER_CRON (default "0 8 * * *", harian 08:00 WIB)
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from zoneinfo import ZoneInfo


def _bootstrap_sys_path() -> None:
    """Tambahkan direktori apps/api ke sys.path (layout repo & layout docker)."""
    worker_dir = Path(__file__).resolve().parent
    kandidat = [
        worker_dir.parent / "api",  # <repo>/apps/api
        worker_dir.parent.parent / "apps" / "api",  # fallback layout lain
    ]
    for path in kandidat:
        if path.is_dir() and str(path) not in sys.path:
            sys.path.insert(0, str(path))


_bootstrap_sys_path()

try:
    from worker._backend import BackendNotReadyError, RealBackend
    from worker.config import WorkerConfig, load_config
    from worker.jobs import pengingat_membership, ringkasan_mingguan, sync_terjadwal
except ImportError:  # dijalankan sebagai skrip langsung dari dalam apps/worker
    from _backend import BackendNotReadyError, RealBackend  # type: ignore[no-redef]
    from config import WorkerConfig, load_config  # type: ignore[no-redef]
    from jobs import pengingat_membership, ringkasan_mingguan, sync_terjadwal  # type: ignore[no-redef]

logger = logging.getLogger("worker.main")


def create_scheduler(backend, config: WorkerConfig):
    """Buat AsyncIOScheduler dengan kedua job terdaftar.

    Dipisah dari amain() agar bisa diuji tanpa menjalankan scheduler.
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError as exc:
        raise RuntimeError(
            "apscheduler belum terinstal — jalankan: pip install -r requirements.txt"
        ) from exc

    tz = ZoneInfo(config.timezone)
    scheduler = AsyncIOScheduler(timezone=tz)

    async def _jalan_sync():
        await sync_terjadwal(backend, interval_hours=config.sync_interval_hours)

    async def _jalan_ringkasan():
        await ringkasan_mingguan(backend)

    async def _jalan_pengingat():
        await pengingat_membership(backend)

    scheduler.add_job(
        _jalan_sync,
        trigger=IntervalTrigger(hours=config.sync_interval_hours),
        id="sync_terjadwal",
        name="Sinkronisasi akun terjadwal",
        max_instances=1,  # jangan tumpuk bila satu run belum selesai
        coalesce=True,  # gabungkan run yang terlewat menjadi satu
        misfire_grace_time=3600,
        replace_existing=True,
    )
    try:
        cron_trigger = CronTrigger.from_crontab(config.summary_cron, timezone=tz)
    except ValueError as exc:
        raise ValueError(
            f"SUMMARY_CRON tidak valid: {config.summary_cron!r} ({exc})"
        ) from exc
    scheduler.add_job(
        _jalan_ringkasan,
        trigger=cron_trigger,
        id="ringkasan_mingguan",
        name="Ringkasan mingguan",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=7200,
        replace_existing=True,
    )
    try:
        reminder_trigger = CronTrigger.from_crontab(config.reminder_cron, timezone=tz)
    except ValueError as exc:
        raise ValueError(
            f"REMINDER_CRON tidak valid: {config.reminder_cron!r} ({exc})"
        ) from exc
    scheduler.add_job(
        _jalan_pengingat,
        trigger=reminder_trigger,
        id="pengingat_membership",
        name="Pengingat kedaluwarsa membership",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=7200,
        replace_existing=True,
    )
    return scheduler


async def amain(config: WorkerConfig, backend) -> None:
    """Jalankan scheduler sampai menerima SIGINT/SIGTERM."""
    scheduler = create_scheduler(backend, config)
    scheduler.start()
    logger.info(
        "worker berjalan: sync tiap %d jam, ringkasan mingguan cron %r (%s)",
        config.sync_interval_hours,
        config.summary_cron,
        config.timezone,
    )
    for job in scheduler.get_jobs():
        logger.info("job terdaftar: id=%s trigger=%s", job.id, job.trigger)

    berhenti = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, berhenti.set)
        except (NotImplementedError, RuntimeError):
            pass  # platform tanpa signal handler (mis. Windows)
    await berhenti.wait()

    logger.info("worker menerima sinyal berhenti, menunggu job selesai...")
    scheduler.shutdown(wait=True)
    logger.info("worker berhenti.")


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    config = load_config()
    backend = RealBackend()
    try:
        backend.check_ready()
    except BackendNotReadyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        asyncio.run(amain(config, backend))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
