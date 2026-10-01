"""Router admin (hanya superadmin)."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, require_superadmin
from app.core.events import dispatch
from app.models.billing import (
    Invoice,
    InvoiceStatus,
    Membership,
    Payment,
    PaymentStatus,
)
from app.models.organization import Organization
from app.models.tokens import EmailVerificationToken, RefreshToken
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.admin import (
    AdminUserOut,
    AuditLogOut,
    MembershipAdminOut,
    MembershipExtendRequest,
    PaymentQueueItem,
    QueueInvoiceMini,
    QueueOrgMini,
    QueuePaymentMini,
    QueueUserMini,
    RejectPaymentRequest,
)
from app.schemas.billing import MembershipOut
from app.schemas.common import MessageResponse
from app.services.audit import log_audit
from app.services.maintenance import run_maintenance
from app.services.membership import extend as extend_membership

router = APIRouter(tags=["admin"])


def _now():
    return datetime.now(timezone.utc)


async def _payment_with_relations(db: AsyncSession, payment_id: uuid.UUID) -> Payment | None:
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.invoice).selectinload(Invoice.plan))
        .where(Payment.id == payment_id)
    )
    return result.scalar_one_or_none()


async def _enrich_queue_item(db: AsyncSession, payment: Payment) -> PaymentQueueItem:
    invoice = payment.invoice
    org = await db.get(Organization, invoice.organization_id)
    payer = await db.get(User, payment.user_id) if payment.user_id else None
    plan_name = invoice.plan.name if invoice.plan else None
    return PaymentQueueItem(
        payment=QueuePaymentMini.model_validate(payment),
        invoice=QueueInvoiceMini(
            id=invoice.id,
            code=invoice.code,
            plan_name=plan_name,
            amount_total=invoice.amount_total,
            status=invoice.status,
            expires_at=invoice.expires_at,
        ),
        user=QueueUserMini(id=payer.id, name=payer.name, email=payer.email) if payer else None,
        organization=QueueOrgMini(id=org.id, name=org.name) if org else QueueOrgMini(id=invoice.organization_id, name="-"),
    )


# ---------------------------------------------------------------------------
# Antrean & riwayat pembayaran
# ---------------------------------------------------------------------------

@router.get("/admin/payments/queue", response_model=list[PaymentQueueItem])
async def payments_queue(
    admin: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.invoice).selectinload(Invoice.plan))
        .where(Payment.status == PaymentStatus.MENUNGGU_VERIFIKASI)
        .order_by(Payment.uploaded_at.asc())
    )
    payments = result.scalars().all()
    return [await _enrich_queue_item(db, p) for p in payments]


@router.get("/admin/payments/history", response_model=list[PaymentQueueItem])
async def payments_history(
    admin: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.invoice).selectinload(Invoice.plan))
        .order_by(desc(Payment.uploaded_at))
    )
    payments = result.scalars().all()
    return [await _enrich_queue_item(db, p) for p in payments]


@router.post("/admin/payments/{payment_id}/approve", response_model=dict)
async def approve_payment(
    payment_id: Annotated[uuid.UUID, Path()],
    admin: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    payment = await _payment_with_relations(db, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pembayaran tidak ditemukan.")
    if payment.status != PaymentStatus.MENUNGGU_VERIFIKASI:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pembayaran sudah diverifikasi (status: {payment.status}).",
        )

    await run_maintenance(db)
    invoice = payment.invoice
    if invoice.status != InvoiceStatus.PENDING or invoice.expires_at < _now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice sudah tidak berlaku (bukan pending / kedaluwarsa).",
        )

    payment.status = PaymentStatus.DISETUJUI
    payment.verified_by = admin.id
    payment.verified_at = _now()
    payment.reject_reason = None
    invoice.status = InvoiceStatus.PAID
    await db.flush()

    # Event domain → handler mengaktifkan membership 1 tahun.
    await dispatch(
        "PembayaranLunas",
        {
            "payment_id": payment.id,
            "invoice_id": invoice.id,
            "organization_id": invoice.organization_id,
            "plan_id": invoice.plan_id,
        },
        db,
    )

    await log_audit(
        db,
        actor_user_id=admin.id,
        action="payment_approved",
        entity_type="payment",
        entity_id=payment.id,
        organization_id=invoice.organization_id,
        meta={"invoice_code": invoice.code, "amount_total": invoice.amount_total},
    )
    await db.flush()

    # Ambil membership terbaru untuk respons.
    membership = (
        await db.execute(select(Membership).where(Membership.organization_id == invoice.organization_id))
    ).scalar_one()
    plan = invoice.plan
    return {
        "membership": MembershipOut(
            status=membership.status,
            starts_at=membership.starts_at,
            ends_at=membership.ends_at,
            grace_ends_at=membership.grace_ends_at,
            plan_name=plan.name if plan else None,
        ).model_dump(mode="json")
    }


@router.post("/admin/payments/{payment_id}/reject", response_model=MessageResponse)
async def reject_payment(
    payment_id: Annotated[uuid.UUID, Path()],
    data: RejectPaymentRequest,
    admin: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    payment = await _payment_with_relations(db, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pembayaran tidak ditemukan.")
    if payment.status != PaymentStatus.MENUNGGU_VERIFIKASI:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pembayaran sudah diverifikasi (status: {payment.status}).",
        )

    payment.status = PaymentStatus.DITOLAK
    payment.verified_by = admin.id
    payment.verified_at = _now()
    payment.reject_reason = data.reason.strip()

    await log_audit(
        db,
        actor_user_id=admin.id,
        action="payment_rejected",
        entity_type="payment",
        entity_id=payment.id,
        organization_id=payment.invoice.organization_id,
        meta={"reason": payment.reject_reason, "invoice_code": payment.invoice.code},
    )
    await db.flush()
    return MessageResponse(message="Bukti pembayaran ditolak.")


# ---------------------------------------------------------------------------
# Pengguna
# ---------------------------------------------------------------------------

@router.get("/admin/users", response_model=list[AdminUserOut])
async def list_users(
    admin: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).order_by(desc(User.created_at)))
    return [AdminUserOut.model_validate(u) for u in result.scalars().all()]


@router.post("/admin/users/{user_id}/suspend", response_model=MessageResponse)
async def suspend_user(
    user_id: Annotated[uuid.UUID, Path()],
    admin: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tidak ditemukan.")
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Anda tidak dapat menangguhkan akun sendiri.")
    if user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tidak dapat menangguhkan superadmin.")
    user.is_active = False
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))
    )
    for rt in result.scalars().all():
        rt.revoked = True
    await log_audit(
        db, actor_user_id=admin.id, action="user_suspended", entity_type="user", entity_id=user.id,
        meta={"email": user.email},
    )
    await db.flush()
    return MessageResponse(message="Pengguna ditangguhkan.")


@router.post("/admin/users/{user_id}/activate", response_model=MessageResponse)
async def activate_user(
    user_id: Annotated[uuid.UUID, Path()],
    admin: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tidak ditemukan.")
    user.is_active = True
    await log_audit(
        db, actor_user_id=admin.id, action="user_activated", entity_type="user", entity_id=user.id,
        meta={"email": user.email},
    )
    await db.flush()
    return MessageResponse(message="Pengguna diaktifkan kembali.")


@router.post("/admin/users/{user_id}/verify-email", response_model=MessageResponse)
async def verify_user_email_manual(
    user_id: Annotated[uuid.UUID, Path()],
    admin: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Verifikasi email user secara manual oleh superadmin.

    Dipakai sebagai jalan keluar bila alur verifikasi via email terus gagal.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pengguna tidak ditemukan.")
    if user.email_verified:
        return MessageResponse(message="Email pengguna sudah terverifikasi.")
    user.email_verified = True
    # Hanguskan token verifikasi yang belum dipakai agar tidak membingungkan.
    result = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
        )
    )
    for token in result.scalars().all():
        token.used_at = _now()
    await log_audit(
        db, actor_user_id=admin.id, action="user_email_verified_manual", entity_type="user", entity_id=user.id,
        meta={"email": user.email},
    )
    await db.flush()
    return MessageResponse(message="Email pengguna berhasil diverifikasi manual.")


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------

@router.post("/admin/memberships/{membership_id}/extend", response_model=dict)
async def extend_membership_endpoint(
    membership_id: Annotated[uuid.UUID, Path()],
    data: MembershipExtendRequest,
    admin: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    membership = await db.get(Membership, membership_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership tidak ditemukan.")
    membership = await extend_membership(db, membership=membership, months=data.months)
    await log_audit(
        db,
        actor_user_id=admin.id,
        action="membership_extended",
        entity_type="membership",
        entity_id=membership.id,
        organization_id=membership.organization_id,
        meta={"months": data.months, "ends_at": membership.ends_at.isoformat() if membership.ends_at else None},
    )
    await db.flush()
    return {"membership": MembershipAdminOut.model_validate(membership).model_dump(mode="json")}


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

@router.get("/admin/audit-logs", response_model=list[AuditLogOut])
async def list_audit_logs(
    admin: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    result = await db.execute(
        select(AuditLog, User.name)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    return [
        AuditLogOut(
            id=log.id,
            created_at=log.created_at,
            actor_name=actor_name,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            organization_id=log.organization_id,
            meta=log.meta,
        )
        for log, actor_name in result.all()
    ]
