"""Dispatcher event domain sederhana.

Contoh: event "PembayaranLunas" dipicu saat admin menyetujui bukti pembayaran,
lalu handler di services/membership.py mengaktifkan membership.

Struktur ini siap diperluas (mis. event untuk integrasi Xendit kelak).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any], Any], Awaitable[None]]

_handlers: dict[str, list[Handler]] = {}


def on(event_name: str) -> Callable[[Handler], Handler]:
    """Decorator untuk mendaftarkan handler sebuah event."""

    def decorator(fn: Handler) -> Handler:
        _handlers.setdefault(event_name, []).append(fn)
        return fn

    return decorator


async def dispatch(event_name: str, payload: dict[str, Any], db: Any) -> None:
    """Jalankan semua handler event secara berurutan."""
    for handler in _handlers.get(event_name, []):
        try:
            await handler(payload, db)
        except Exception:
            logger.exception("Handler event %s gagal: %s", event_name, getattr(handler, "__name__", handler))
            raise


def registered_events() -> list[str]:
    return sorted(_handlers.keys())
