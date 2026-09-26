"""Enkripsi simetris (Fernet) untuk token OAuth & secret di database.

Kunci dibaca dari env FERNET_KEY (format: kunci Fernet base64, mis. hasil
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
Bila env kosong (dev), sebuah kunci sementara dibuat sekali per proses dan
peringatan jelas dicatat di log — JANGAN dipakai di produksi karena token
tidak bisa didekripsi ulang setelah restart.
"""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_dev_key: bytes | None = None


def get_fernet() -> Fernet:
    """Kembalikan Fernet dari FERNET_KEY, atau kunci dev sementara bila kosong."""
    key = (get_settings().FERNET_KEY or "").strip()
    if key:
        try:
            return Fernet(key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                "FERNET_KEY tidak valid: harus kunci Fernet base64 32-byte "
                "(buat dengan Fernet.generate_key())."
            ) from exc
    global _dev_key
    if _dev_key is None:
        _dev_key = Fernet.generate_key()
        logger.warning(
            "FERNET_KEY kosong — memakai kunci enkripsi DEV sementara. "
            "Token terenkripsi TIDAK akan bisa didekripsi setelah proses restart. "
            "Set FERNET_KEY di production!"
        )
    return Fernet(_dev_key)


def encrypt_text(plaintext: str | None) -> str | None:
    """Enkripsi string → token Fernet (str). None → None."""
    if plaintext is None:
        return None
    return get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_text(ciphertext: str | None) -> str | None:
    """Dekripsi token Fernet → string. None → None. Raise ValueError bila korup."""
    if ciphertext is None:
        return None
    try:
        return get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Data terenkripsi tidak bisa didekripsi (kunci salah atau data korup)."
        ) from exc
