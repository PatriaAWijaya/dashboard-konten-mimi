"""Layanan email: ABC + implementasi console (dev), SMTP, & Brevo HTTP API."""

from __future__ import annotations

import json
import logging
import smtplib
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr

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


# Frontend produksi (dipakai sebagai fallback bila FRONTEND_URL belum diisi
# di environment, misalnya masih default localhost saat ENV=prod).
PROD_FRONTEND_URL = "https://dashboard-konten-mimi.vercel.app"


def verification_link(token: str) -> str:
    """Tautan verifikasi email satu-klik untuk dikirim ke pengguna."""
    settings = get_settings()
    base = (settings.FRONTEND_URL or "").strip().rstrip("/")
    if (not base or "localhost" in base or "127.0.0.1" in base) and not settings.is_dev:
        base = PROD_FRONTEND_URL
    return f"{base}/verify-email?token={token}"


def password_reset_link(token: str) -> str:
    """Tautan reset kata sandi satu-klik untuk dikirim ke pengguna."""
    settings = get_settings()
    base = (settings.FRONTEND_URL or "").strip().rstrip("/")
    if (not base or "localhost" in base or "127.0.0.1" in base) and not settings.is_dev:
        base = PROD_FRONTEND_URL
    return f"{base}/reset-password?token={token}"


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
        link = verification_link(token)
        body = (
            f"Halo {name},\n\nTerima kasih telah mendaftar di MySocial Watch.\n"
            f"Klik tautan berikut untuk memverifikasi email Anda (berlaku 15 menit):\n\n{link}\n\n"
            f"Jika tautan tidak bisa diklik, salin token berikut lalu tempel di halaman verifikasi:\n\n{token}\n"
        )
        self._send(to_email, "Verifikasi Email — MySocial Watch", body)

    async def send_password_reset_email(self, *, to_email: str, name: str, token: str) -> None:
        link = password_reset_link(token)
        body = (
            f"Halo {name},\n\nGunakan tautan berikut untuk mengatur ulang kata sandi Anda "
            f"(berlaku 24 jam):\n\n{link}\n\n"
            f"Jika tautan tidak bisa diklik, salin token berikut lalu tempel di halaman reset kata sandi:\n\n{token}\n\n"
            f"Abaikan email ini bila Anda tidak memintanya.\n"
        )
        self._send(to_email, "Reset Kata Sandi — MySocial Watch", body)


def get_email_service() -> EmailService:
    settings = get_settings()
    if settings.is_dev:
        return ConsoleEmailService()
    # Render (free tier) memblokir outbound SMTP (port 25/465/587) di level
    # jaringan -> koneksi menggantung sampai timeout. Brevo HTTP API lewat
    # port 443 tidak diblokir, jadi diprioritaskan bila API key tersedia.
    if settings.BREVO_API_KEY:
        return BrevoHttpEmailService()
    return SmtpEmailService()


class BrevoHttpEmailService(EmailService):
    """Kirim email via Brevo HTTP API (port 443).

    Dipakai di hosting yang memblokir outbound SMTP (mis. Render free tier).
    Memakai akun & sender terverifikasi Brevo yang sama dengan SMTP;
    yang dibutuhkan hanya API key (format xkeysib-...) via BREVO_API_KEY.
    """

    API_URL = "https://api.brevo.com/v3/smtp/email"

    def _send(self, to_email: str, subject: str, body: str, html: str | None = None) -> None:
        settings = get_settings()
        sender_name, sender_email = parseaddr(settings.SMTP_FROM)
        if not sender_email:
            sender_email = settings.SMTP_FROM.strip()
        payload = {
            "sender": {"name": sender_name or "MySocial Watch", "email": sender_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "textContent": body,
        }
        if html:
            payload["htmlContent"] = html
        req = urllib.request.Request(
            self.API_URL,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": settings.BREVO_API_KEY,
                # Hindari proteksi bot yang memblokir User-Agent default urllib.
                "User-Agent": "MySocialWatch/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
        except Exception:
            # Jangan gagalkan alur pemanggil (registrasi dsb); cukup catat.
            logger.exception(
                "Gagal mengirim email '%s' ke %s via Brevo HTTP API.", subject, to_email
            )
            return
        logger.info("Email '%s' terkirim ke %s via Brevo HTTP API.", subject, to_email)

    async def send_verification_email(self, *, to_email: str, name: str, token: str) -> None:
        link = verification_link(token)
        body = (
            f"Halo {name},\n\nTerima kasih telah mendaftar di MySocial Watch.\n"
            f"Klik tautan berikut untuk memverifikasi email Anda (berlaku 15 menit):\n\n{link}\n\n"
            f"Jika tautan tidak bisa diklik, salin token berikut lalu tempel di halaman verifikasi:\n\n{token}\n"
        )
        html = (
            f"<p>Halo {name},</p>"
            f"<p>Terima kasih telah mendaftar di MySocial Watch.</p>"
            f"<p><a href=\"{link}\" style=\"display:inline-block;padding:12px 24px;"
            f"background:#0f766e;color:#ffffff;text-decoration:none;border-radius:8px;\">"
            f"Verifikasi Email Saya</a></p>"
            f"<p>Atau klik tautan berikut (berlaku 15 menit):<br><a href=\"{link}\">{link}</a></p>"
            f"<p>Jika tautan tidak bisa diklik, salin token berikut lalu tempel di halaman verifikasi:<br>"
            f"<code>{token}</code></p>"
        )
        self._send(to_email, "Verifikasi Email — MySocial Watch", body, html)

    async def send_password_reset_email(self, *, to_email: str, name: str, token: str) -> None:
        link = password_reset_link(token)
        body = (
            f"Halo {name},\n\nGunakan tautan berikut untuk mengatur ulang kata sandi Anda "
            f"(berlaku 24 jam):\n\n{link}\n\n"
            f"Jika tautan tidak bisa diklik, salin token berikut lalu tempel di halaman reset kata sandi:\n\n{token}\n\n"
            f"Abaikan email ini bila Anda tidak memintanya.\n"
        )
        html = (
            f"<p>Halo {name},</p>"
            f"<p><a href=\"{link}\" style=\"display:inline-block;padding:12px 24px;"
            f"background:#0f766e;color:#ffffff;text-decoration:none;border-radius:8px;\">"
            f"Atur Ulang Kata Sandi</a></p>"
            f"<p>Atau klik tautan berikut (berlaku 24 jam):<br><a href=\"{link}\">{link}</a></p>"
            f"<p>Jika tautan tidak bisa diklik, salin token berikut lalu tempel di halaman reset kata sandi:<br>"
            f"<code>{token}</code></p>"
            f"<p>Abaikan email ini bila Anda tidak memintanya.</p>"
        )
        self._send(to_email, "Reset Kata Sandi — MySocial Watch", body, html)
