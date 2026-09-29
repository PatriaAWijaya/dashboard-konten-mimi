"""Layanan email: ABC + implementasi console (dev) & SMTP (kerangka)."""

from __future__ import annotations

import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SentToken:
    """Catatan token yang 'dikirim' — dipakai endpoint /dev/* saat ENV=dev."""

    email: str
    token: str
    type: str  # "verification" | "password_reset"
    expires_at: datetime


# Outbox in-memory khusus dev (satu proses). Bukan untuk production.
_dev_outbox: list[SentToken] = []


def get_dev_outbox() -> list[SentToken]:
    return _dev_outbox


def clear_dev_outbox() -> None:
    _dev_outbox.clear()


class EmailService(ABC):
    @abstractmethod
    async def send_verification_email(self, *, to_email: str, name: str, token: str) -> None: ...

    @abstractmethod
    async def send_password_reset_email(self, *, to_email: str, name: str, token: str) -> None: ...


class ConsoleEmailService(EmailService):
    """Implementasi dev: cetak token ke log + simpan di outbox in-memory."""

    async def send_verification_email(self, *, to_email: str, name: str, token: str) -> None:
        settings = get_settings()
        expires_at = datetime.now(timezone.utc).replace(microsecond=0)
        logger.info("[DEV] Token verifikasi email untuk %s: %s", to_email, token)
        _dev_outbox.append(SentToken(email=to_email, token=token, type="verification", expires_at=expires_at))
        # NOTE: expires_at akurat diisi pemanggil via meta? Disederhanakan: endpoint dev
        # membaca ulang dari DB untuk expires_at yang benar. Field ini hanya penanda.

    async def send_password_reset_email(self, *, to_email: str, name: str, token: str) -> None:
        logger.info("[DEV] Token reset password untuk %s: %s", to_email, token)
        _dev_outbox.append(
            SentToken(
                email=to_email,
                token=token,
                type="password_reset",
                expires_at=datetime.now(timezone.utc),
            )
        )


class SmtpEmailService(EmailService):
    """Kerangka pengiriman via SMTP. Aktif saat ENV != dev."""

    def _send(self, to_email: str, subject: str, body: str) -> None:
        settings = get_settings()
        if not settings.SMTP_HOST:
            # SMTP belum dikonfigurasi: jangan gagalkan alur (mis. registrasi).
            # Cukup catat agar admin tahu email tidak terkirim.
            logger.warning(
                "SMTP_HOST belum dikonfigurasi; email '%s' ke %s tidak dikirim.",
                subject,
                to_email,
            )
            return
        msg = EmailMessage()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        try:
            # timeout 10 dtk: jangan biarkan koneksi SMTP yang macet
            # menggantung request (mis. registrasi) sampai proxy timeout.
            if settings.SMTP_USE_TLS:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
                    smtp.starttls()
                    if settings.SMTP_USERNAME:
                        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
                    if settings.SMTP_USERNAME:
                        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    smtp.send_message(msg)
        except Exception:
            # Email gagal terkirim (host salah, kredensial salah, dsb):
            # catat saja, jangan gagalkan alur pemanggil (registrasi dsb).
            logger.exception(
                "Gagal mengirim email '%s' ke %s via %s:%s.",
                subject,
                to_email,
                settings.SMTP_HOST,
                settings.SMTP_PORT,
            )
            return
        logger.info("Email '%s' terkirim ke %s.", subject, to_email)

    async def send_verification_email(self, *, to_email: str, name: str, token: str) -> None:
        body = (
            f"Halo {name},\n\nTerima kasih telah mendaftar di Dashboard Konten AI.\n"
            f"Gunakan token berikut untuk verifikasi email Anda (berlaku 24 jam):\n\n{token}\n"
        )
        self._send(to_email, "Verifikasi Email — Dashboard Konten AI", body)

    async def send_password_reset_email(self, *, to_email: str, name: str, token: str) -> None:
        body = (
            f"Halo {name},\n\nGunakan token berikut untuk mengatur ulang kata sandi Anda "
            f"(berlaku 24 jam):\n\n{token}\n\nAbaikan email ini bila Anda tidak memintanya.\n"
        )
        self._send(to_email, "Reset Kata Sandi — Dashboard Konten AI", body)


def get_email_service() -> EmailService:
    settings = get_settings()
    if settings.is_dev:
        return ConsoleEmailService()
    return SmtpEmailService()
