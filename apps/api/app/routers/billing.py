"""Router billing: paket, invoice, bukti pembayaran, membership."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import (
    get_current_user,
    get_db,
    get_org_context,
    get_org_membership,
    parse_org_header,
    set_tenant,
)
from app.core.permissions import ROLE_ADMIN
from app.models.billing import Invoice, InvoiceStatus, MembershipPlan, Payment, PaymentStatus
from app.models.user import User
from app.schemas.billing import (
    BankInfo,
    InvoiceCreate,
    InvoiceCreated,
    InvoiceDetail,
    InvoiceListItem,
    MembershipOut,
    PaymentMini,
    PaymentProofOut,
    PlanOut,
)
from app.services.audit import log_audit
from app.services.invoice import create_invoice as _create_invoice
from app.services.maintenance import run_maintenance
from app.services.payments import get_payment_provider
from app.services.storage import get_storage_service

router = APIRouter(tags=["billing"])


def _now():
    return datetime.now(timezone.utc)


def _bank_info() -> BankInfo:
    settings = get_settings()
    return BankInfo(
        bank_name=settings.BANK_NAME,
        account_number=settings.BANK_ACCOUNT_NUMBER,
        account_name=settings.BANK_ACCOUNT_NAME,
    )


async def _latest_payment(db: AsyncSession, invoice_id: uuid.UUID) -> Payment | None:
    result = await db.execute(
        select(Payment).where(Payment.invoice_id == invoice_id).order_by(desc(Payment.uploaded_at)).limit(1)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Paket
# ---------------------------------------------------------------------------

@router.get("/plans", response_model=list[PlanOut])
async def list_plans(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(MembershipPlan).order_by(MembershipPlan.price))
    return [PlanOut.model_validate(p) for p in result.scalars().all()]


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

@router.post("/billing/invoices", response_model=InvoiceCreated, status_code=status.HTTP_201_CREATED)
async def create_invoice_endpoint(
    data: InvoiceCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    header_org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
):
    if header_org_id != data.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header X-Organization-Id tidak cocok dengan organization_id pada body.",
        )
    ctx = await get_org_context(db, user, data.organization_id, min_role=ROLE_ADMIN)

    plan = await db.get(MembershipPlan, data.plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paket tidak ditemukan.")

    await run_maintenance(db)
    try:
        invoice = await _create_invoice(
            db,
            organization_id=ctx.organization.id,
            plan=plan,
            creator_user_id=user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    await log_audit(
        db,
        actor_user_id=user.id,
        action="invoice_created",
        entity_type="invoice",
        entity_id=invoice.id,
        organization_id=ctx.organization.id,
        meta={"code": invoice.code, "amount_total": invoice.amount_total, "plan": plan.name},
    )
    await db.flush()

    return InvoiceCreated(
        id=invoice.id,
        code=invoice.code,
        plan_name=plan.name,
        amount_base=invoice.amount_base,
        unique_code=invoice.unique_code,
        amount_total=invoice.amount_total,
        bank=_bank_info(),
        status=invoice.status,
        expires_at=invoice.expires_at,
    )


@router.get("/billing/invoices", response_model=list[InvoiceListItem])
async def list_invoices(
    organization_id: Annotated[uuid.UUID, Query()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    header_org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
):
    if header_org_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header X-Organization-Id tidak cocok dengan organization_id pada query.",
        )
    await get_org_context(db, user, organization_id)
    await run_maintenance(db)

    result = await db.execute(
        select(Invoice, MembershipPlan.name)
        .join(MembershipPlan, MembershipPlan.id == Invoice.plan_id)
        .where(Invoice.organization_id == organization_id)
        .order_by(desc(Invoice.created_at))
    )
    return [
        InvoiceListItem(
            id=inv.id,
            code=inv.code,
            plan_name=plan_name,
            amount_total=inv.amount_total,
            status=inv.status,
            expires_at=inv.expires_at,
            created_at=inv.created_at,
        )
        for inv, plan_name in result.all()
    ]


@router.get("/billing/invoices/{invoice_id}", response_model=InvoiceDetail)
async def get_invoice_detail(
    invoice_id: Annotated[uuid.UUID, Path()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    header_org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
):
    await get_org_context(db, user, header_org_id)
    await run_maintenance(db)

    invoice = await db.get(Invoice, invoice_id, options=[selectinload(Invoice.plan)])
    if invoice is None or invoice.organization_id != header_org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice tidak ditemukan.")

    payment = await _latest_payment(db, invoice.id)
    return InvoiceDetail(
        id=invoice.id,
        code=invoice.code,
        plan_name=invoice.plan.name,
        amount_base=invoice.amount_base,
        unique_code=invoice.unique_code,
        amount_total=invoice.amount_total,
        bank=_bank_info(),
        status=invoice.status,
        expires_at=invoice.expires_at,
        created_at=invoice.created_at,
        payment=PaymentMini.model_validate(payment) if payment else None,
    )


# ---------------------------------------------------------------------------
# Bukti pembayaran
# ---------------------------------------------------------------------------

@router.post("/billing/invoices/{invoice_id}/payment-proof", response_model=PaymentProofOut)
async def upload_payment_proof(
    invoice_id: Annotated[uuid.UUID, Path()],
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    header_org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
):
    ctx = await get_org_context(db, user, header_org_id, min_role=ROLE_ADMIN)
    await run_maintenance(db)

    invoice = await db.get(Invoice, invoice_id)
    if invoice is None or invoice.organization_id != header_org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice tidak ditemukan.")
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Invoice sudah dibayar."
        )
    if invoice.status != InvoiceStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invoice berstatus '{invoice.status}', bukti pembayaran tidak dapat diunggah.",
        )
    if invoice.expires_at < _now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invoice sudah kedaluwarsa."
        )

    settings = get_settings()
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.allowed_proof_extensions_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format file tidak didukung. Gunakan: {', '.join(sorted(settings.allowed_proof_extensions_set))}.",
        )
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ukuran file maksimal {settings.MAX_UPLOAD_MB} MB.",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File kosong.")

    latest = await _latest_payment(db, invoice.id)
    if latest and latest.status == PaymentStatus.DISETUJUI:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bukti pembayaran sudah disetujui."
        )

    storage = get_storage_service()
    rel_path = await storage.save_payment_proof(data, ext)

    if latest and latest.status == PaymentStatus.MENUNGGU_VERIFIKASI:
        # Timpa bukti yang masih menunggu verifikasi.
        try:
            storage.absolute_path(latest.file_path).unlink(missing_ok=True)
        except OSError:
            pass
        latest.file_path = rel_path
        latest.file_name = filename
        latest.file_size = len(data)
        latest.mime_type = file.content_type
        latest.uploaded_at = _now()
        latest.user_id = user.id
        payment = latest
    else:
        payment = Payment(
            invoice_id=invoice.id,
            user_id=user.id,
            organization_id=ctx.organization.id,
            file_path=rel_path,
            file_name=filename,
            file_size=len(data),
            mime_type=file.content_type,
            status=PaymentStatus.MENUNGGU_VERIFIKASI,
            uploaded_at=_now(),
        )
        db.add(payment)

    await log_audit(
        db,
        actor_user_id=user.id,
        action="payment_proof_uploaded",
        entity_type="payment",
        entity_id=payment.id,
        organization_id=ctx.organization.id,
        meta={"invoice_code": invoice.code, "file_name": filename},
    )
    await db.flush()

    return PaymentProofOut(id=payment.id, status=payment.status, uploaded_at=payment.uploaded_at)


@router.get("/billing/payments/{payment_id}/file")
async def download_payment_file(
    payment_id: Annotated[uuid.UUID, Path()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    header_org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
):
    # Superadmin boleh mengunduh tanpa menjadi anggota organisasi.
    if user.is_superadmin:
        await set_tenant(db, header_org_id)
        org_id = header_org_id
    else:
        ctx = await get_org_context(db, user, header_org_id)
        org_id = ctx.organization.id
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File tidak ditemukan.")

    storage = get_storage_service()
    abs_path = storage.absolute_path(payment.file_path)
    if not abs_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File tidak ditemukan di penyimpanan.")
    return FileResponse(path=str(abs_path), filename=payment.file_name)


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------

@router.get("/billing/memberships", response_model=MembershipOut | None)
async def get_membership_info(
    organization_id: Annotated[uuid.UUID, Query()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    header_org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
):
    if header_org_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header X-Organization-Id tidak cocok dengan organization_id pada query.",
        )
    await get_org_context(db, user, organization_id)
    membership = await get_org_membership(db, organization_id)
    if membership is None:
        return None
    return MembershipOut(
        status=membership.status,
        starts_at=membership.starts_at,
        ends_at=membership.ends_at,
        grace_ends_at=membership.grace_ends_at,
        plan_name=membership.plan.name if membership.plan else None,
    )
