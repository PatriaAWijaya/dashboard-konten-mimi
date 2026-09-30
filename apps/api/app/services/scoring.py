"""Layanan scoring konten: pure functions + agregasi database.

Fungsi murni (compute_weighted_er, score_content) tidak menyentuh DB/LLM
sehingga deterministik dan mudah diuji. Bagian DB hanya agregasi & upsert.
"""

from __future__ import annotations

import uuid
from datetime import date
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import (
    Content,
    ContentMetricsDaily,
    ContentScore,
    ScoringConfig,
    ScoreStatus,
)
from app.models.brand import Brand


# Bobot default tiap komponen skor (total = 1.0).
DEFAULT_WEIGHTS = {
    "save_rate": 0.25,
    "share_rate": 0.20,
    "comment_rate": 0.15,
    "weighted_er": 0.20,
    "retensi": 0.15,
    "reach_abs": 0.05,
}

# Threshold default.
DEFAULT_THRESHOLDS = {
    "min_views": 1000,
    "tiktok_min_wer": 0.08,
    "instagram_min_wer": 0.05,
    "relative_multiplier": 1.5,
    "menang_score": 0.7,
    "cukup_score": 0.4,
    "winner_labels_for_menang": 3,
}

# Baseline wajar: komponen ternormalisasi menjadi 1.0 bila nilainya == baseline.
BASE_RATES = {
    "save_rate": 0.02,
    "share_rate": 0.015,
    "comment_rate": 0.01,
    "weighted_er": 0.06,
    "retensi": 0.5,
}

# Reach absolut yang dianggap "1.0" setelah normalisasi.
REACH_BASELINE = 10_000
# Retensi dihitung sebagai proxy: avg_watch_seconds / 30 detik, di-clamp 0..1.
RETENSI_REF_SECONDS = 30.0

_COMPONENT_KEYS = ("save_rate", "share_rate", "comment_rate", "weighted_er", "retensi", "reach_abs")


def compute_weighted_er(likes: float, comments: float, shares: float, saves: float, views: float) -> float:
    """Weighted Engagement Rate = (like*1 + comment*3 + share*5 + save*5) / views."""
    if views is None or views <= 0:
        return 0.0
    return (likes * 1 + comments * 3 + shares * 5 + saves * 5) / views


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _norm(value: float, baseline: float) -> float:
    """Normalisasi 0..1 relatif terhadap baseline (baseline → 1.0)."""
    if baseline <= 0:
        return 0.0
    return _clamp01(value / baseline)


def score_content(
    metrics: dict,
    weights: dict,
    thresholds: dict,
    median_wer: float | None = None,
) -> dict:
    """Nilai satu konten dari metrik agregatnya.

    metrics: views, reach, likes, comments, shares, saves, avg_watch_seconds,
        profile_clicks, link_clicks, replies, sticker_taps, platform.
    Mengembalikan dict: score (float|None), status, labels, parts, explanation.
    """
    views = int(metrics.get("views") or 0)
    min_views = int(thresholds.get("min_views", 1000))
    if views < min_views:
        return {
            "score": None,
            "status": ScoreStatus.DATA_BELUM_CUKUP,
            "labels": [],
            "parts": {},
            "explanation": (
                f"Views ({views}) masih di bawah ambang minimum {min_views}, "
                "jadi data belum cukup untuk dinilai."
            ),
        }

    platform = str(metrics.get("platform") or "tiktok").lower()
    likes = float(metrics.get("likes") or 0)
    comments = float(metrics.get("comments") or 0)
    shares = float(metrics.get("shares") or 0)
    saves = float(metrics.get("saves") or 0)
    reach = float(metrics.get("reach") or 0)
    avg_watch = float(metrics.get("avg_watch_seconds") or 0)

    save_rate = saves / views
    share_rate = shares / views
    comment_rate = comments / views
    wer = compute_weighted_er(likes, comments, shares, saves, views)
    retensi = _clamp01(avg_watch / RETENSI_REF_SECONDS)
    reach_ref = max(reach, float(views))

    parts = {
        "save_rate": _norm(save_rate, BASE_RATES["save_rate"]),
        "share_rate": _norm(share_rate, BASE_RATES["share_rate"]),
        "comment_rate": _norm(comment_rate, BASE_RATES["comment_rate"]),
        "weighted_er": _norm(wer, BASE_RATES["weighted_er"]),
        "retensi": _norm(retensi, BASE_RATES["retensi"]),
        "reach_abs": _norm(reach_ref, REACH_BASELINE),
    }

    total_w = sum(float(weights.get(k, 0) or 0) for k in _COMPONENT_KEYS)
    if total_w > 0:
        score = sum(float(weights.get(k, 0) or 0) * parts[k] for k in _COMPONENT_KEYS) / total_w
    else:
        score = 0.0
    score = round(score, 4)

    # Label winner (urutan deterministik).
    labels: list[str] = []
    if save_rate >= 2 * BASE_RATES["save_rate"]:
        labels.append("save_tinggi")
    if share_rate >= 2 * BASE_RATES["share_rate"]:
        labels.append("share_tinggi")
    if comment_rate >= 2 * BASE_RATES["comment_rate"]:
        labels.append("comment_tinggi")
    min_wer = float(thresholds.get(f"{platform}_min_wer", thresholds.get("tiktok_min_wer", 0.08)))
    if wer >= min_wer:
        labels.append("wer_tinggi")
    rel_mult = float(thresholds.get("relative_multiplier", 1.5))
    if median_wer is not None and median_wer > 0 and wer >= rel_mult * median_wer:
        labels.append("wer_relatif_tinggi")
    if retensi >= 2 * BASE_RATES["retensi"]:
        labels.append("retensi_tinggi")

    menang_score = float(thresholds.get("menang_score", 0.7))
    cukup_score = float(thresholds.get("cukup_score", 0.4))
    min_labels = int(thresholds.get("winner_labels_for_menang", 3))

    if score >= menang_score or len(labels) >= min_labels:
        status = ScoreStatus.MENANG
    elif score >= cukup_score:
        status = ScoreStatus.CUKUP
    else:
        status = ScoreStatus.KURANG

    top_parts = sorted(parts.items(), key=lambda kv: kv[1], reverse=True)[:2]
    top_str = ", ".join(f"{k} ({v:.2f})" for k, v in top_parts)
    label_str = ", ".join(labels) if labels else "tidak ada"
    explanation = (
        f"Konten {platform} dengan {views} views mendapat skor {score:.2f} "
        f"(status: {status}). Label pemenang: {label_str}. "
        f"Komponen terkuat: {top_str}."
    )

    return {
        "score": score,
        "status": status,
        "labels": labels,
        "parts": parts,
        "explanation": explanation,
    }


async def get_or_create_active_config(
    db: AsyncSession, brand_id: uuid.UUID, organization_id: uuid.UUID
) -> ScoringConfig:
    """Ambil config aktif brand; buat versi 1 (defaults) bila belum ada."""
    result = await db.execute(
        select(ScoringConfig)
        .where(
            ScoringConfig.brand_id == brand_id,
            ScoringConfig.organization_id == organization_id,
            ScoringConfig.is_active.is_(True),
        )
        .order_by(ScoringConfig.version.desc())
    )
    config = result.scalars().first()
    if config is not None:
        return config

    max_version = await db.scalar(
        select(func.max(ScoringConfig.version)).where(
            ScoringConfig.brand_id == brand_id,
            ScoringConfig.organization_id == organization_id,
        )
    )
    config = ScoringConfig(
        organization_id=organization_id,
        brand_id=brand_id,
        version=(max_version or 0) + 1,
        weights=dict(DEFAULT_WEIGHTS),
        thresholds=dict(DEFAULT_THRESHOLDS),
        is_active=True,
    )
    db.add(config)
    await db.flush()
    return config


async def run_scoring(
    db: AsyncSession,
    *,
    brand: Brand,
    organization_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> list[ContentScore]:
    """Agregasi metrik per konten dalam rentang tanggal lalu simpan skornya.

    Count metrics di-SUM; avg_watch_seconds di-rata-rata (mean harian).
    Upsert per unique constraint (content, config, periode) — idempoten.
    """
    config = await get_or_create_active_config(db, brand.id, organization_id)

    contents = list(
        (
            await db.execute(
                select(Content).where(
                    Content.brand_id == brand.id,
                    Content.organization_id == organization_id,
                )
            )
        )
        .scalars()
        .all()
    )
    if not contents:
        return []
    by_id = {c.id: c for c in contents}

    rows = (
        await db.execute(
            select(
                ContentMetricsDaily.content_id,
                func.sum(ContentMetricsDaily.views).label("views"),
                func.sum(ContentMetricsDaily.reach).label("reach"),
                func.sum(ContentMetricsDaily.likes).label("likes"),
                func.sum(ContentMetricsDaily.comments).label("comments"),
                func.sum(ContentMetricsDaily.shares).label("shares"),
                func.sum(ContentMetricsDaily.saves).label("saves"),
                func.avg(ContentMetricsDaily.avg_watch_seconds).label("avg_watch_seconds"),
                func.sum(ContentMetricsDaily.profile_clicks).label("profile_clicks"),
                func.sum(ContentMetricsDaily.link_clicks).label("link_clicks"),
                func.sum(ContentMetricsDaily.replies).label("replies"),
                func.sum(ContentMetricsDaily.sticker_taps).label("sticker_taps"),
            )
            .where(
                ContentMetricsDaily.organization_id == organization_id,
                ContentMetricsDaily.content_id.in_(list(by_id.keys())),
                ContentMetricsDaily.date >= period_start,
                ContentMetricsDaily.date <= period_end,
            )
            .group_by(ContentMetricsDaily.content_id)
        )
    ).all()

    min_views = int(config.thresholds.get("min_views", 1000))
    # Median weighted_er per platform dari konten yang lolos gerbang views.
    wers_by_platform: dict[str, list[float]] = {}
    agg_by_content: dict[uuid.UUID, dict] = {}
    for row in rows:
        agg = {
            "views": int(row.views or 0),
            "reach": int(row.reach or 0),
            "likes": int(row.likes or 0),
            "comments": int(row.comments or 0),
            "shares": int(row.shares or 0),
            "saves": int(row.saves or 0),
            "avg_watch_seconds": float(row.avg_watch_seconds or 0),
            "profile_clicks": int(row.profile_clicks or 0),
            "link_clicks": int(row.link_clicks or 0),
            "replies": int(row.replies or 0),
            "sticker_taps": int(row.sticker_taps or 0),
            "platform": by_id[row.content_id].platform,
        }
        agg_by_content[row.content_id] = agg
        if agg["views"] >= min_views:
            wers_by_platform.setdefault(agg["platform"], []).append(
                compute_weighted_er(agg["likes"], agg["comments"], agg["shares"], agg["saves"], agg["views"])
            )
    median_by_platform = {
        platform: median(wers) for platform, wers in wers_by_platform.items() if wers
    }

    results: list[ContentScore] = []
    # Muat skor yang sudah ada sekaligus (satu query, bukan N query).
    skor_ada = (
        (
            await db.execute(
                select(ContentScore).where(
                    ContentScore.scoring_config_id == config.id,
                    ContentScore.content_id.in_(list(agg_by_content.keys())),
                    ContentScore.period_start == period_start,
                    ContentScore.period_end == period_end,
                )
            )
        )
        .scalars()
        .all()
    )
    peta_skor: dict[uuid.UUID, ContentScore] = {s.content_id: s for s in skor_ada}
    for content_id, agg in agg_by_content.items():
        outcome = score_content(
            agg,
            config.weights,
            config.thresholds,
            median_wer=median_by_platform.get(agg["platform"]),
        )
        existing = peta_skor.get(content_id)
        if existing is None:
            existing = ContentScore(
                organization_id=organization_id,
                content_id=content_id,
                scoring_config_id=config.id,
                period_start=period_start,
                period_end=period_end,
            )
            db.add(existing)
            peta_skor[content_id] = existing
        existing.score = outcome["score"]
        existing.status = outcome["status"]
        existing.labels = outcome["labels"]
        existing.metrics_snapshot = agg
        results.append(existing)

    await db.flush()
    await db.commit()
    return results
