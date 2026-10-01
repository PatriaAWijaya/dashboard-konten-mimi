"""Layanan onboarding: template threshold per kategori industri, progres,
dan pratinjau kemenangan (tanpa menyimpan config).

Template threshold didefinisikan di kode (mudah diubah): tiap kategori
industri memetakan ke {tiktok_er, instagram_er, skor_menang, skor_cukup}.
Kategori "lainnya" memakai nilai default yang berlaku sekarang
(TikTok 8%, IG 5%, menang 0.7, cukup 0.4 — lihat scoring.DEFAULT_THRESHOLDS).
"""

from __future__ import annotations

import uuid
from statistics import median

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.content import Content, ContentScore, ScoreStatus
from app.models.onboarding import OnboardingProgress
from app.services.scoring import (
    DEFAULT_THRESHOLDS,
    DEFAULT_WEIGHTS,
    compute_weighted_er,
    score_content,
)

# ---------------------------------------------------------------------------
# Template threshold per kategori industri
# ---------------------------------------------------------------------------

KATEGORI_INDUSTRI = (
    "ngo/filantropi",
    "kuliner",
    "fashion",
    "edukasi",
    "kesehatan",
    "jasa",
    "lainnya",
)

KATEGORI_DEFAULT = "lainnya"

# Kunci: tiktok_er & instagram_er = ambang weighted ER minimum per platform
# (fraksi, mis. 0.08 = 8%); skor_menang / skor_cukup = ambang skor 0..1.
TEMPLATE_THRESHOLD_PER_KATEGORI: dict[str, dict[str, float]] = {
    "ngo/filantropi": {"tiktok_er": 0.06, "instagram_er": 0.04, "skor_menang": 0.60, "skor_cukup": 0.35},
    "kuliner": {"tiktok_er": 0.09, "instagram_er": 0.055, "skor_menang": 0.70, "skor_cukup": 0.40},
    "fashion": {"tiktok_er": 0.09, "instagram_er": 0.06, "skor_menang": 0.70, "skor_cukup": 0.40},
    "edukasi": {"tiktok_er": 0.07, "instagram_er": 0.045, "skor_menang": 0.65, "skor_cukup": 0.35},
    "kesehatan": {"tiktok_er": 0.07, "instagram_er": 0.045, "skor_menang": 0.65, "skor_cukup": 0.35},
    "jasa": {"tiktok_er": 0.08, "instagram_er": 0.05, "skor_menang": 0.70, "skor_cukup": 0.40},
    "lainnya": {
        "tiktok_er": float(DEFAULT_THRESHOLDS["tiktok_min_er"]),
        "instagram_er": float(DEFAULT_THRESHOLDS["instagram_min_er"]),
        "skor_menang": float(DEFAULT_THRESHOLDS["menang_score"]),
        "skor_cukup": float(DEFAULT_THRESHOLDS["cukup_score"]),
    },
}


def kategori_valid(kategori: str | None) -> bool:
    return kategori in KATEGORI_INDUSTRI


def get_template_threshold(kategori: str) -> dict[str, float]:
    """Kembalikan salinan template threshold untuk kategori (raise bila tak dikenal)."""
    if not kategori_valid(kategori):
        raise ValueError(
            f"Kategori '{kategori}' tidak dikenal. Pilih: {', '.join(KATEGORI_INDUSTRI)}."
        )
    return dict(TEMPLATE_THRESHOLD_PER_KATEGORI[kategori])


def template_untuk_brand(brand: Brand) -> dict[str, float]:
    """Template berdasarkan kategori brand; fallback ke 'lainnya'."""
    kategori = (brand.industry_category or "").strip() or KATEGORI_DEFAULT
    return dict(TEMPLATE_THRESHOLD_PER_KATEGORI.get(kategori, TEMPLATE_THRESHOLD_PER_KATEGORI[KATEGORI_DEFAULT]))


# ---------------------------------------------------------------------------
# Progres onboarding
# ---------------------------------------------------------------------------

async def get_progress(
    db: AsyncSession, user_id: uuid.UUID, brand_id: uuid.UUID
) -> OnboardingProgress | None:
    result = await db.execute(
        select(OnboardingProgress).where(
            OnboardingProgress.user_id == user_id,
            OnboardingProgress.brand_id == brand_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_progress(
    db: AsyncSession, user_id: uuid.UUID, brand_id: uuid.UUID, langkah: int
) -> OnboardingProgress:
    """Simpan langkah terakhir. Membuka kembali progres yang sempat ditutup."""
    if langkah < 0:
        raise ValueError("Langkah tidak boleh negatif.")
    progress = await get_progress(db, user_id, brand_id)
    if progress is None:
        progress = OnboardingProgress(user_id=user_id, brand_id=brand_id, langkah_terakhir=langkah)
        db.add(progress)
    else:
        progress.langkah_terakhir = langkah
        progress.ditutup = False  # progres berikutnya membuka lagi yang ditutup
    await db.flush()
    return progress


async def tandai_selesai(
    db: AsyncSession, user_id: uuid.UUID, brand_id: uuid.UUID
) -> OnboardingProgress:
    progress = await get_progress(db, user_id, brand_id)
    if progress is None:
        progress = OnboardingProgress(user_id=user_id, brand_id=brand_id)
        db.add(progress)
    progress.selesai = True
    progress.ditutup = False
    await db.flush()
    return progress


async def tutup_onboarding(
    db: AsyncSession, user_id: uuid.UUID, brand_id: uuid.UUID
) -> OnboardingProgress:
    progress = await get_progress(db, user_id, brand_id)
    if progress is None:
        progress = OnboardingProgress(user_id=user_id, brand_id=brand_id)
        db.add(progress)
    progress.ditutup = True
    await db.flush()
    return progress


# ---------------------------------------------------------------------------
# Pratinjau kemenangan (draft threshold, TANPA menyimpan config)
# ---------------------------------------------------------------------------

BATAS_KONTEN_PREVIEW = 20


async def preview_kemenangan(
    db: AsyncSession,
    *,
    brand: Brand,
    organization_id: uuid.UUID,
    draft: dict,
) -> dict:
    """Terapkan draft threshold ke 20 konten terakhir yang sudah diskors.

    Menggunakan fungsi scoring murni score_content() — config brand TIDAK
    diubah sama sekali (tidak ada tulis ke scoring_configs).
    draft: {tiktok_er, instagram_er, [skor_menang], [skor_cukup]}.
    """
    thresholds = dict(DEFAULT_THRESHOLDS)
    thresholds["tiktok_min_er"] = float(draft["tiktok_er"])
    thresholds["instagram_min_er"] = float(draft["instagram_er"])
    if draft.get("skor_menang") is not None:
        thresholds["menang_score"] = float(draft["skor_menang"])
    if draft.get("skor_cukup") is not None:
        thresholds["cukup_score"] = float(draft["skor_cukup"])

    # 20 konten terakhir yang sudah punya skor (dedup per konten, ambil yang terbaru).
    rows = (
        await db.execute(
            select(ContentScore, Content)
            .join(Content, Content.id == ContentScore.content_id)
            .where(
                ContentScore.organization_id == organization_id,
                Content.brand_id == brand.id,
            )
            .order_by(desc(Content.posted_at))
            .limit(BATAS_KONTEN_PREVIEW * 10)
        )
    ).all()
    terlihat: dict[uuid.UUID, tuple[ContentScore, Content]] = {}
    for skor, konten in rows:
        if konten.id not in terlihat:
            terlihat[konten.id] = (skor, konten)
        if len(terlihat) >= BATAS_KONTEN_PREVIEW:
            break

    # Median weighted ER per platform (pola sama seperti run_scoring).
    min_views = int(thresholds.get("min_views", 1000))
    ers_per_platform: dict[str, list[float]] = {}
    snapshot_list: list[tuple[dict, str]] = []
    for skor, konten in terlihat.values():
        snap = dict(skor.metrics_snapshot or {})
        platform = str(konten.platform or snap.get("platform") or "tiktok").lower()
        snap["platform"] = platform
        snapshot_list.append((snap, platform))
        views = int(snap.get("views") or 0)
        if views >= min_views:
            ers_per_platform.setdefault(platform, []).append(
                compute_weighted_er(
                    float(snap.get("likes") or 0),
                    float(snap.get("comments") or 0),
                    float(snap.get("shares") or 0),
                    float(snap.get("saves") or 0),
                    float(views),
                )
            )
    median_per_platform = {p: median(w) for p, w in ers_per_platform.items() if w}

    menang = 0
    per_platform: dict[str, dict[str, int]] = {}
    for snap, platform in snapshot_list:
        hasil = score_content(
            snap, DEFAULT_WEIGHTS, thresholds, median_er=median_per_platform.get(platform)
        )
        stat = per_platform.setdefault(platform, {"menang": 0, "total": 0})
        stat["total"] += 1
        if hasil["status"] == ScoreStatus.MENANG:
            menang += 1
            stat["menang"] += 1

    return {
        "menang": menang,
        "total": len(snapshot_list),
        "per_platform": {
            platform: {"menang": s["menang"], "total": s["total"]}
            for platform, s in sorted(per_platform.items())
        },
    }
