"""Impor CSV metrik konten: parse, validasi, upsert idempoten.

Normalisasi tiap baris memakai app.services.normalize.normalize_content_row
(fungsi bersama dengan sync provider Fase 2) agar perilaku identik.

Selain format kolom aplikasi (platform, post_id, ...), importer juga
menerima FORMAT EXPORT NATIVE META (TikTok/Instagram) apa adanya — kolom
seperti "Post ID", "Publish time", "Post type", Views/Reach/Likes/...
dipetakan otomatis, termasuk deteksi platform dari kolom "Post type"
("IG reel" -> instagram/reels, dst.).
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.content import ContentPlatform, ContentTujuan
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


# ---------------------------------------------------------------------------
# Dukungan format export native Meta (TikTok / Instagram)
# ---------------------------------------------------------------------------
# Contoh header export Meta:
# "Post ID","Account ID","Account username","Account name",Description,
# "Duration (sec)","Publish time",Permalink,"Post type","Data comment",
# Date,Views,Reach,Likes,Shares,Follows,Comments,Saves

_META_COLUMN_MAP = {
    "post id": "post_id",
    "permalink": "post_url",
    "description": "caption",
    "views": "views",
    "reach": "reach",
    "likes": "likes",
    "comments": "comments",
    "shares": "shares",
    "saves": "saves",
}

_META_POST_TYPE_FORMAT = {
    "carousel": "carousel",
    "reel": "reels",
    "reels": "reels",
    "image": "foto",
    "photo": "foto",
    "story": "story",
    "video": "reels",  # video native TikTok dipetakan ke bucket video vertikal
    "live": "live",
}

_META_TANGGAL_POLAS = (
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
)


def _is_meta_header(header: list[str]) -> bool:
    """Deteksi header export native Meta dari nama kolom kuncinya."""
    norm = {(h or "").strip().lower() for h in header}
    return "post id" in norm and "publish time" in norm


def _meta_platform_dan_format(post_type: str) -> tuple[str | None, str | None]:
    """Deteksi (platform, format) dari kolom 'Post type' export Meta.

    Contoh: 'IG carousel' -> ('instagram', 'carousel'),
    'IG reel' -> ('instagram', 'reels'), 'TT video' -> ('tiktok', 'reels').
    """
    t = (post_type or "").strip().lower()
    if t.startswith("ig "):
        platform: str | None = "instagram"
    elif t.startswith("tt "):
        platform = "tiktok"
    else:
        return None, None
    jenis = t.split(" ", 1)[1].strip() if " " in t else ""
    return platform, _META_POST_TYPE_FORMAT.get(jenis)


def _meta_tanggal(publish_time: str) -> str | None:
    """Ubah 'Publish time' Meta menjadi YYYY-MM-DD. None bila tak dikenali."""
    teks = (publish_time or "").strip()
    for pola in _META_TANGGAL_POLAS:
        try:
            return datetime.strptime(teks, pola).date().isoformat()
        except ValueError:
            continue
    return None


def _remap_meta_row(row: dict) -> tuple[dict, str | None, str | None]:
    """Petakan satu baris export Meta ke nama kolom internal.

    Return (baris_terpetakan, platform_terdeteksi, pesan_error).
    """
    bawah = {(k or "").strip().lower(): (v or "") for k, v in row.items()}
    mapped: dict = {}
    for meta_col, internal in _META_COLUMN_MAP.items():
        if bawah.get(meta_col):
            mapped[internal] = bawah[meta_col].strip()

    publish_time = bawah.get("publish time", "").strip()
    tanggal = _meta_tanggal(publish_time)
    if not tanggal:
        return {}, None, f"kolom 'Publish time' ('{publish_time}') tidak dikenali"
    mapped["tanggal_posting"] = tanggal

    platform_det, fmt = _meta_platform_dan_format(bawah.get("post type", ""))
    if fmt:
        mapped["format"] = fmt
    else:
        return {}, None, f"kolom 'Post type' ('{bawah.get('post type', '')}') tidak dikenali"

    if not mapped.get("post_id"):
        return {}, None, "kolom 'Post ID' kosong"
    return mapped, platform_det, None


async def import_csv(
    db: AsyncSession,
    *,
    brand: Brand,
    organization_id: uuid.UUID,
    platform: str,
    file_bytes: bytes,
    filename: str,
    tujuan_default: str = ContentTujuan.BRANDING,
) -> dict:
    """Impor satu file CSV metrik konten untuk sebuah brand.

    platform: 'tiktok'/'instagram', atau 'auto' (ambil dari kolom platform).
    tujuan_default: dipakai bila baris tidak punya kolom tujuan
        (mis. file export native Meta yang memang tidak punya kolom ini).
    Upsert Content (brand+platform+post_id) lalu upsert ContentMetricsDaily
    (content_id + tanggal_posting). Idempoten: upload ulang file yang sama
    hanya meng-update, tidak menduplikasi.
    "baris" pada baris_gagal = nomor baris di file (baris 1 = header).
    """
    platform_arg = (platform or "").strip().lower()
    if platform_arg != AUTO_PLATFORM and platform_arg not in ContentPlatform.ALL:
        raise ValueError(f"platform argumen '{platform}' tidak dikenal")
    tujuan_def = (tujuan_default or "").strip().lower() or ContentTujuan.BRANDING
    if tujuan_def not in ContentTujuan.ALL:
        raise ValueError(f"tujuan_default '{tujuan_default}' tidak dikenal")

    text = file_bytes.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=[",", ";"])
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    header = [(h or "").strip() for h in (reader.fieldnames or [])]

    warnings: list[str] = []
    meta_mode = _is_meta_header(header)
    if meta_mode:
        warnings.append(
            "Format export Meta terdeteksi — kolom dipetakan otomatis "
            "(Post ID, Publish time, Post type, Views/Reach/Likes/...), "
            "platform dideteksi dari kolom 'Post type'."
        )
    else:
        unknown_cols = [h for h in header if h and h not in EXPECTED_COLUMNS]
        if unknown_cols:
            warnings.append(f"Kolom tak dikenal diabaikan: {', '.join(unknown_cols)}")

    contents_baru = 0
    contents_diupdate = 0
    metrics_rows = 0
    baris_gagal: list[dict] = []
    peringatan_platform_diberi = False

    try:
        for line_no, raw_row in enumerate(reader, start=2):
            row = {(k or "").strip(): (v or "") for k, v in raw_row.items()}

            if meta_mode:
                # --- mode export Meta: kolom dipetakan otomatis ---
                mapped, platform_det, err = _remap_meta_row(row)
                if err:
                    baris_gagal.append({"baris": line_no, "alasan": err})
                    continue
                if platform_det:
                    if (
                        platform_arg != AUTO_PLATFORM
                        and platform_det != platform_arg
                        and not peringatan_platform_diberi
                    ):
                        warnings.append(
                            f"Platform file terdeteksi '{platform_det}' dari kolom "
                            f"'Post type' (pilihan form: '{platform_arg}') — memakai "
                            f"hasil deteksi file."
                        )
                        peringatan_platform_diberi = True
                    row_platform = platform_det
                elif platform_arg == AUTO_PLATFORM:
                    baris_gagal.append(
                        {
                            "baris": line_no,
                            "alasan": "platform tidak terdeteksi dari kolom 'Post type'",
                        }
                    )
                    continue
                else:
                    row_platform = platform_arg
                row = mapped
            else:
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

            # Tujuan: isi default bila CSV tidak punya kolom tujuan (kasus export Meta).
            if not (row.get("tujuan") or "").strip():
                row["tujuan"] = tujuan_def

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
