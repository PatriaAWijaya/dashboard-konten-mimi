"""Normalisasi baris konten (dipakai bersama CSV Fase 1 & sync provider Fase 2).

Satu-satunya tempat logika parsing/validasi baris mentah berada. csv_import.py
dan sync_service.py WAJIB memakai fungsi ini agar format data konsisten.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import (
    Content,
    ContentFormat,
    ContentMetricsDaily,
    ContentPlatform,
    ContentTujuan,
)

INT_COLUMNS = [
    "views",
    "reach",
    "likes",
    "comments",
    "shares",
    "saves",
    "profile_clicks",
    "link_clicks",
    "replies",
    "sticker_taps",
]


class NormalizationError(ValueError):
    """Baris mentah tidak valid. Pesan = alasan persis gaya impor CSV Fase 1."""


def _parse_non_negative_int(raw, col: str) -> tuple[int | None, str | None]:
    """Kembalikan (nilai, pesan_error). String kosong → 0."""
    text = (raw if raw is not None else "")
    text = str(text).strip()
    if text == "":
        return 0, None
    try:
        number = float(text.replace(",", "."))
    except ValueError:
        return None, f"kolom '{col}' berisi '{raw}' yang bukan angka"
    if not number.is_integer():
        return None, f"kolom '{col}' berisi '{raw}' yang bukan bilangan bulat"
    value = int(number)
    if value < 0:
        return None, f"kolom '{col}' berisi angka negatif ({value})"
    return value, None


def _parse_non_negative_float(raw, col: str) -> tuple[float | None, str | None]:
    text = (raw if raw is not None else "")
    text = str(text).strip()
    if text == "":
        return 0.0, None
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        return None, f"kolom '{col}' berisi '{raw}' yang bukan angka"
    if value < 0:
        return None, f"kolom '{col}' berisi angka negatif ({value})"
    return value, None


def _parse_date(raw) -> tuple:
    text = (raw if raw is not None else "")
    text = str(text).strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date(), None
    except ValueError:
        return None, f"tanggal_posting '{raw}' tidak valid (format yang benar: YYYY-MM-DD)"


def normalize_content_row(platform: str, row: dict) -> dict:
    """Normalisasi satu baris mentah menjadi dict siap insert ke Content+metrics.

    platform: platform efektif ('tiktok'/'instagram') — sudah ditentukan
        pemanggil (dari argumen upload atau kolom platform mode auto).
    row: dict kolom mentah (key = nama kolom CSV Fase 1, value = string).

    Return dict dengan key: platform, post_id, post_url, caption, tanggal
    (date), posted_at (datetime UTC), format, tujuan, views, reach, likes,
    comments, shares, saves, avg_watch_seconds, profile_clicks, link_clicks,
    replies, sticker_taps.

    Raise NormalizationError dengan pesan persis impor CSV Fase 1 bila baris
    tidak valid.
    """
    platform = (platform or "").strip().lower()
    if platform not in ContentPlatform.ALL:
        raise NormalizationError(f"platform '{platform}' tidak dikenal")

    post_id = str(row.get("post_id") or "").strip()
    if not post_id:
        raise NormalizationError("post_id kosong")

    tanggal, err = _parse_date(row.get("tanggal_posting"))
    if err:
        raise NormalizationError(err)

    fmt = str(row.get("format") or "").strip().lower()
    if fmt not in ContentFormat.ALL:
        raise NormalizationError(f"format '{row.get('format')}' tidak dikenal")

    tujuan = str(row.get("tujuan") or "").strip().lower()
    if tujuan not in ContentTujuan.ALL:
        raise NormalizationError(f"tujuan '{row.get('tujuan')}' tidak dikenal")

    numeric: dict[str, int | float] = {}
    for col in INT_COLUMNS:
        value, err = _parse_non_negative_int(row.get(col), col)
        if err:
            raise NormalizationError(err)
        numeric[col] = value  # type: ignore[assignment]
    avg_watch, err = _parse_non_negative_float(row.get("avg_watch_seconds"), "avg_watch_seconds")
    if err:
        raise NormalizationError(err)

    post_url = str(row.get("post_url") or "").strip() or None
    caption = str(row.get("caption") or "").strip() or None

    return {
        "platform": platform,
        "post_id": post_id,
        "post_url": post_url,
        "caption": caption,
        "tanggal": tanggal,
        "posted_at": datetime(tanggal.year, tanggal.month, tanggal.day, tzinfo=timezone.utc),
        "format": fmt,
        "tujuan": tujuan,
        **numeric,
        "avg_watch_seconds": avg_watch,
    }


async def upsert_content_row(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    organization_id: uuid.UUID,
    normalized: dict,
) -> tuple[Content, bool]:
    """Upsert Content (kunci brand+platform+post_id) + ContentMetricsDaily
    (kunci content+tanggal) dari dict hasil normalize_content_row.

    Return (content, True) bila Content baru dibuat, (content, False) bila
    Content sudah ada (di-update).
    """
    tanggal = normalized["tanggal"]
    content = await db.scalar(
        select(Content).where(
            Content.brand_id == brand_id,
            Content.organization_id == organization_id,
            Content.platform == normalized["platform"],
            Content.post_id == normalized["post_id"],
        )
    )
    baru = content is None
    if content is None:
        content = Content(
            organization_id=organization_id,
            brand_id=brand_id,
            platform=normalized["platform"],
            post_id=normalized["post_id"],
            post_url=normalized["post_url"],
            posted_at=normalized["posted_at"],
            format=normalized["format"],
            tujuan=normalized["tujuan"],
            caption=normalized["caption"],
        )
        db.add(content)
        await db.flush()
    else:
        # posted_at TIDAK di-overwrite: tanggal publikasi adalah fakta immutable.
        # (Sync ulang dengan data mock/API tidak boleh menggesernya.)
        content.post_url = normalized["post_url"]
        content.format = normalized["format"]
        content.tujuan = normalized["tujuan"]
        content.caption = normalized["caption"]

    metric = await db.scalar(
        select(ContentMetricsDaily).where(
            ContentMetricsDaily.content_id == content.id,
            ContentMetricsDaily.organization_id == organization_id,
            ContentMetricsDaily.date == tanggal,
        )
    )
    angka = {c: normalized[c] for c in INT_COLUMNS}
    if metric is None:
        metric = ContentMetricsDaily(
            organization_id=organization_id,
            content_id=content.id,
            date=tanggal,
            avg_watch_seconds=normalized["avg_watch_seconds"],
            **angka,
        )
        db.add(metric)
    else:
        for c in INT_COLUMNS:
            setattr(metric, c, angka[c])
        metric.avg_watch_seconds = normalized["avg_watch_seconds"]
    return content, baru
