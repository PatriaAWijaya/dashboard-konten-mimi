"""Impor CSV metrik konten: parse, validasi, upsert idempoten.

Normalisasi tiap baris memakai app.services.normalize.normalize_content_row
(fungsi bersama dengan sync provider Fase 2) agar perilaku identik.
"""

from __future__ import annotations

import csv
import io
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.content import ContentPlatform
from app.services.normalize import (
    INT_COLUMNS,
    NormalizationError,
    normalize_content_row,
    upsert_content_row,
)

EXPECTED_COLUMNS = [
    "platform",
    "post_id",
    "post_url",
    "tanggal_posting",
    "format",
    "tujuan",
    "caption",
    "views",
    "reach",
    "likes",
    "comments",
    "shares",
    "saves",
    "avg_watch_seconds",
    "profile_clicks",
    "link_clicks",
    "replies",
    "sticker_taps",
]

AUTO_PLATFORM = "auto"


async def import_csv(
    db: AsyncSession,
    *,
    brand: Brand,
    organization_id: uuid.UUID,
    platform: str,
    file_bytes: bytes,
    filename: str,
) -> dict:
    """Impor satu file CSV metrik konten untuk sebuah brand.

    platform: 'tiktok'/'instagram', atau 'auto' (ambil dari kolom platform).
    Upsert Content (brand+platform+post_id) lalu upsert ContentMetricsDaily
    (content_id + tanggal_posting). Idempoten: upload ulang file yang sama
    hanya meng-update, tidak menduplikasi.
    "baris" pada baris_gagal = nomor baris di file (baris 1 = header).
    """
    platform_arg = (platform or "").strip().lower()
    if platform_arg != AUTO_PLATFORM and platform_arg not in ContentPlatform.ALL:
        raise ValueError(f"platform argumen '{platform}' tidak dikenal")

    text = file_bytes.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=[",", ";"])
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    header = [(h or "").strip() for h in (reader.fieldnames or [])]

    warnings: list[str] = []
    unknown_cols = [h for h in header if h and h not in EXPECTED_COLUMNS]
    if unknown_cols:
        warnings.append(f"Kolom tak dikenal diabaikan: {', '.join(unknown_cols)}")

    contents_baru = 0
    contents_diupdate = 0
    metrics_rows = 0
    baris_gagal: list[dict] = []

    try:
        for line_no, raw_row in enumerate(reader, start=2):
            row = {(k or "").strip(): (v or "") for k, v in raw_row.items()}

            # --- platform (ditentukan di sini, dinormalisasi di normalize.py) ---
            col_platform = (row.get("platform") or "").strip().lower()
            if platform_arg == AUTO_PLATFORM:
                if not col_platform:
                    baris_gagal.append({"baris": line_no, "alasan": "kolom platform kosong"})
                    continue
                row_platform = col_platform
            else:
                if col_platform and col_platform != platform_arg:
                    baris_gagal.append(
                        {
                            "baris": line_no,
                            "alasan": f"platform baris '{col_platform}' tidak cocok dengan '{platform_arg}'",
                        }
                    )
                    continue
                row_platform = platform_arg

            try:
                normalized = normalize_content_row(row_platform, row)
            except NormalizationError as exc:
                baris_gagal.append({"baris": line_no, "alasan": str(exc)})
                continue

            _, baru = await upsert_content_row(
                db,
                brand_id=brand.id,
                organization_id=organization_id,
                normalized=normalized,
            )
            if baru:
                contents_baru += 1
            else:
                contents_diupdate += 1
            metrics_rows += 1

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {
        "contents_baru": contents_baru,
        "contents_diupdate": contents_diupdate,
        "metrics_rows": metrics_rows,
        "baris_gagal": baris_gagal,
        "warnings": warnings,
    }
