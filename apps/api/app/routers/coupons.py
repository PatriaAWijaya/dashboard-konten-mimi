"""Endpoint kupon diskon: validasi & penukaran."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.services.coupon import (
    redeem_coupon,
    redeem_coupon_for_user_orgs,
    validate_coupon,
)

router = APIRouter(prefix="/coupons", tags=["coupons"])


class CouponInfo(BaseModel):
    code: str
    discount_percent: int
    duration_days: int
    description: str | None


class RedeemRequest(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    organization_id: uuid.UUID | None = Field(
        default=None,
        description="Bila kosong, kupon diterapkan ke semua organisasi milik user.",
    )


@router.get("/validate", response_model=CouponInfo)
async def validate(
    code: Annotated[str, Query(min_length=1, max_length=40)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Cek apakah kode kupon valid (tanpa menukarkan)."""
    coupon = await validate_coupon(db, code)
    return CouponInfo(
        code=coupon.code,
        discount_percent=coupon.discount_percent,
        duration_days=coupon.duration_days,
        description=coupon.description,
    )


@router.post("/redeem")
async def redeem(
    data: RedeemRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Tukarkan kupon untuk organisasi (atau semua organisasi milik user)."""
    code = data.code.strip()
    if data.organization_id:
        coupon = await validate_coupon(db, code)
        redemption = await redeem_coupon(
            db, coupon=coupon, organization_id=data.organization_id, user_id=user.id
        )
        await db.commit()
        hasil = [{
            "organization_id": str(data.organization_id),
            "discount_percent": redemption.discount_percent,
            "expires_at": redemption.expires_at.isoformat() if redemption.expires_at else None,
        }]
    else:
        hasil = await redeem_coupon_for_user_orgs(db, code=code, user_id=user.id)
        await db.commit()
    return {"code": code, "applied": hasil}
