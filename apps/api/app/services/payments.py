"""Provider pembayaran: ABC + ManualTransferProvider (fase 0).

Struktur siap ditambah provider lain (mis. XenditProvider) tanpa mengubah
kontrak endpoint: cukup buat subclass PaymentProvider baru.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.config import get_settings


@dataclass
class BankAccount:
    bank_name: str
    account_number: str
    account_name: str


class PaymentProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def get_bank_account(self) -> BankAccount:
        """Rekening tujuan untuk pembayaran manual."""
        ...

    @abstractmethod
    async def verify_payment(self, payment_id: str) -> bool:
        """Verifikasi otomatis (fase 0: selalu False → verifikasi manual oleh admin)."""
        ...


class ManualTransferProvider(PaymentProvider):
    """Fase 0: transfer bank manual + kode unik 3 digit, verifikasi oleh admin."""

    name = "manual_transfer"

    async def get_bank_account(self) -> BankAccount:
        settings = get_settings()
        return BankAccount(
            bank_name=settings.BANK_NAME,
            account_number=settings.BANK_ACCOUNT_NUMBER,
            account_name=settings.BANK_ACCOUNT_NAME,
        )

    async def verify_payment(self, payment_id: str) -> bool:
        return False


def get_payment_provider() -> PaymentProvider:
    return ManualTransferProvider()
