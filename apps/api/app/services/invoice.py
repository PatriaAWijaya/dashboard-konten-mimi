"""Layanan invoice: pembuatan dengan kode unik 3 digit yang unik antar invoice pending."""

import random
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.billing import Invoice, InvoiceStatus, MembershipPlan


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_invoice_code() -> str:
    date_part = _now().strftime("%Y%m%d")
    rand_part = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"INV-{date_part}-{rand_part}"


async def _unique_code_taken(db: AsyncSession, code: int) -> bool:
    """Cek global via fungsi SECURITY DEFINER (RLS membatasi SELECT biasa ke tenant)."""
    result = await db.execute(
        text("SELECT public.pending_invoice_unique_code_exists(:code)"), {"code": code}
    )
    return bool(result.scalar())


async def generate_unique_code(db: AsyncSession) -> int:
    """Acak kode 1..999 yang belum dipakai invoice pending lain.

    Retry maksimal UNIQUE_CODE_MAX_RETRIES kali, lalu raise LookupError (→ 409).
    """
    settings = get_settings()
    for _ in range(settings.UNIQUE_CODE_MAX_RETRIES):
        code = random.randint(settings.UNIQUE_CODE_MIN, settings.UNIQUE_CODE_MAX)
        if not await _unique_code_taken(db, code):
            return code
    raise LookupError("Kode unik habis, silakan coba lagi.")


async def create_invoice(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    plan: MembershipPlan,
    creator_user_id: uuid.UUID | None,
    now: datetime | None = None,
) -> Invoice:
    settings = get_settings()
    now = now or _now()

    # Coba beberapa kali bila kode invoice bentrok (unique constraint) atau
    # kode unik bentrok karena race condition (partial unique index).
    attempts = settings.UNIQUE_CODE_MAX_RETRIES
    last_error: Exception | None = None
    for _ in range(attempts):
        unique_code = await generate_unique_code(db)
        invoice = Invoice(
            organization_id=organization_id,
            plan_id=plan.id,
            user_id=creator_user_id,
            code=generate_invoice_code(),
            amount_base=plan.price,
            unique_code=unique_code,
            amount_total=plan.price + unique_code,
            status=InvoiceStatus.PENDING,
            expires_at=now + timedelta(hours=settings.INVOICE_EXPIRY_HOURS),
        )
        try:
            async with db.begin_nested():
                db.add(invoice)
                await db.flush()
            return invoice
        except IntegrityError as exc:
            last_error = exc
            continue
    raise LookupError(f"Gagal membuat invoice setelah {attempts} percobaan.") from last_error
