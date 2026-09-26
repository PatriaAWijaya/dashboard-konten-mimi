"""Konfigurasi worker dari environment variables.

Variabel yang didukung:
- SYNC_INTERVAL_HOURS : interval sinkronisasi akun (jam). Default: 6.
- SUMMARY_CRON        : jadwal ringkasan mingguan format crontab.
                        Default: "0 7 * * 1" (Senin 07:00).
- WORKER_TIMEZONE     : zona waktu penjadwalan. Default: "Asia/Jakarta".
- REMINDER_CRON       : jadwal pengingat membership format crontab.
                        Default: "0 8 * * *" (setiap hari 08:00).
- LOG_LEVEL           : level logging (dipakai main.py). Default: "INFO".
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("worker.config")

DEFAULT_SYNC_INTERVAL_HOURS = 6
DEFAULT_SUMMARY_CRON = "0 7 * * 1"
DEFAULT_REMINDER_CRON = "0 8 * * *"
DEFAULT_TIMEZONE = "Asia/Jakarta"


@dataclass(frozen=True)
class WorkerConfig:
    """Konfigurasi worker yang sudah tervalidasi."""

    sync_interval_hours: int = DEFAULT_SYNC_INTERVAL_HOURS
    summary_cron: str = DEFAULT_SUMMARY_CRON
    reminder_cron: str = DEFAULT_REMINDER_CRON
    timezone: str = DEFAULT_TIMEZONE


def _baca_int(nama: str, default: int) -> int:
    mentah = os.environ.get(nama)
    if mentah is None or not mentah.strip():
        return default
    try:
        nilai = int(mentah.strip())
    except ValueError:
        logger.warning("env %s=%r bukan angka, pakai default %d", nama, mentah, default)
        return default
    if nilai <= 0:
        logger.warning("env %s=%r harus > 0, pakai default %d", nama, mentah, default)
        return default
    return nilai


def load_config() -> WorkerConfig:
    """Baca konfigurasi dari environment dengan fallback aman."""
    zona = (os.environ.get("WORKER_TIMEZONE") or "").strip() or DEFAULT_TIMEZONE
    try:
        ZoneInfo(zona)
    except ZoneInfoNotFoundError:
        logger.warning("WORKER_TIMEZONE=%r tidak dikenal, pakai UTC", zona)
        zona = "UTC"
    cron = (os.environ.get("SUMMARY_CRON") or "").strip() or DEFAULT_SUMMARY_CRON
    reminder_cron = (os.environ.get("REMINDER_CRON") or "").strip() or DEFAULT_REMINDER_CRON
    return WorkerConfig(
        sync_interval_hours=_baca_int("SYNC_INTERVAL_HOURS", DEFAULT_SYNC_INTERVAL_HOURS),
        summary_cron=cron,
        reminder_cron=reminder_cron,
        timezone=zona,
    )
