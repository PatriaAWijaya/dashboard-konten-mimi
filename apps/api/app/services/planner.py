"""CRUD rencana konten (content planner)."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import ContentFormat, ContentPlatform, ContentTujuan
from app.models.fase2 import PlannedPost, PlannedPostStatus


def _validate(data: dict, partial: bool = False) -> dict:
    """Validasi field rencana; return dict bersih. Raise ValueError bila salah."""
    bersih: dict = {}
    if not partial or "judul" in data:
        judul = str(data.get("judul") or "").strip()
        if not judul:
            raise ValueError("Judul rencana wajib diisi.")
        bersih["judul"] = judul[:255]
    if "platform" in data and data.get("platform") not in (None, ""):
        platform = str(data.get("platform")).strip().lower()
        if platform not in ContentPlatform.ALL:
            raise ValueError(f"Platform '{data.get('platform')}' tidak dikenal.")
        bersih["platform"] = platform
    if not partial or "format" in data:
        fmt = str(data.get("format") or "").strip().lower()
        if fmt not in ContentFormat.ALL:
            raise ValueError(f"Format '{data.get('format')}' tidak dikenal.")
        bersih["format"] = fmt
    if not partial or "tujuan" in data:
        tujuan = str(data.get("tujuan") or "").strip().lower()
        if tujuan not in ContentTujuan.ALL:
            raise ValueError(f"Tujuan '{data.get('tujuan')}' tidak dikenal.")
        bersih["tujuan"] = tujuan
    if not partial or "tanggal_rencana" in data:
        tgl = data.get("tanggal_rencana")
        if not isinstance(tgl, date):
            raise ValueError("tanggal_rencana wajib tanggal valid (YYYY-MM-DD).")
        bersih["tanggal_rencana"] = tgl
    if "status" in data and data.get("status") is not None:
        status = str(data.get("status")).strip().lower()
        if status not in PlannedPostStatus.ALL:
            raise ValueError(f"Status '{data.get('status')}' tidak dikenal.")
        bersih["status"] = status
    if "catatan" in data:
        catatan = str(data.get("catatan") or "").strip()
        bersih["catatan"] = catatan or None
    if "rekomendasi_sumber_id" in data:
        rid = data.get("rekomendasi_sumber_id")
        if rid in (None, ""):
            bersih["rekomendasi_sumber_id"] = None
        else:
            try:
                bersih["rekomendasi_sumber_id"] = uuid.UUID(str(rid))
            except ValueError as exc:
                raise ValueError("rekomendasi_sumber_id tidak valid.") from exc
    return bersih


async def list_planned(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    organization_id: uuid.UUID,
    bulan: str | None = None,
) -> list[PlannedPost]:
    """Daftar rencana; bulan opsional format 'YYYY-MM'."""
    q = (
        select(PlannedPost)
        .where(
            PlannedPost.brand_id == brand_id,
            PlannedPost.organization_id == organization_id,
        )
        .order_by(PlannedPost.tanggal_rencana.asc(), PlannedPost.created_at.asc())
    )
    if bulan:
        try:
            tahun, bln = bulan.split("-")
            awal = date(int(tahun), int(bln), 1)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Parameter bulan harus format YYYY-MM.") from exc
        akhir = date(awal.year + (1 if awal.month == 12 else 0), 1 if awal.month == 12 else awal.month + 1, 1)
        q = q.where(PlannedPost.tanggal_rencana >= awal, PlannedPost.tanggal_rencana < akhir)
    return (await db.execute(q)).scalars().all()


async def create_planned(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    organization_id: uuid.UUID,
    created_by: uuid.UUID | None,
    data: dict,
) -> PlannedPost:
    bersih = _validate(data)
    post = PlannedPost(
        organization_id=organization_id,
        brand_id=brand_id,
        created_by=created_by,
        **bersih,
    )
    db.add(post)
    await db.flush()
    return post


async def update_planned(db: AsyncSession, *, post: PlannedPost, data: dict) -> PlannedPost:
    bersih = _validate(data, partial=True)
    for k, v in bersih.items():
        setattr(post, k, v)
    await db.flush()
    return post


async def delete_planned(db: AsyncSession, *, post: PlannedPost) -> None:
    await db.delete(post)
    await db.flush()
