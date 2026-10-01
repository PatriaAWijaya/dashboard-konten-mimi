"""Ringkasan naratif mingguan per brand (cached di tabel summaries).

Prinsip "agregat dulu, narasi kemudian": LLM hanya menerima dict agregat
(total konten, rata-rata skor/ER, top-3 pola format×tujuan, 3 konten
terbaik/terburuk) — tidak pernah data mentah per konten.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.content import Content, ContentScore, ScoreStatus
from app.models.fase2 import Summary
from app.services.llm import LLMProvider, get_llm_provider_for_db
from app.services.notifications import notify_org
from app.services.scoring import batas_dt, er_snapshot, get_or_create_active_config


async def _agregat(
    db: AsyncSession, brand_id: uuid.UUID, awal: date, akhir: date
) -> dict:
    mulai, selesai = batas_dt(awal, akhir)
    baris = (
        await db.execute(
            select(Content, ContentScore)
            .join(ContentScore, ContentScore.content_id == Content.id)
            .where(
                Content.brand_id == brand_id,
                Content.posted_at >= mulai,
                Content.posted_at < selesai,
            )
        )
    ).all()

    skor_list: list[float] = []
    er_list: list[float] = []
    pola: dict[tuple[str, str], dict] = {}
    per_konten: dict[str, dict] = {}
    for content, skor in baris:
        if skor.score is not None:
            skor_list.append(float(skor.score))
        er_list.append(er_snapshot(skor.metrics_snapshot))
        key = (content.format, content.tujuan)
        p = pola.setdefault(key, {"n": 0, "menang": 0})
        p["n"] += 1
        if skor.status == ScoreStatus.MENANG:
            p["menang"] += 1
        info = per_konten.setdefault(
            str(content.id), {"post_id": content.post_id, "skor": None}
        )
        if skor.score is not None and (info["skor"] is None or skor.score > info["skor"]):
            info["skor"] = float(skor.score)

    def _rata(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 4) if xs else None

    pola_top = sorted(
        (
            {
                "format": k[0],
                "tujuan": k[1],
                "n": v["n"],
                "menang": v["menang"],
                "win_rate": round(v["menang"] / v["n"], 4) if v["n"] else 0.0,
            }
            for k, v in pola.items()
        ),
        key=lambda d: (-d["win_rate"], -d["n"]),
    )[:3]

    terurut = sorted(
        (v for v in per_konten.values() if v["skor"] is not None),
        key=lambda d: d["skor"],
    )
    terbaik = [
        {"post_id": d["post_id"], "skor": round(d["skor"], 4)} for d in terurut[-3:][::-1]
    ]
    terburuk = [
        {"post_id": d["post_id"], "skor": round(d["skor"], 4)} for d in terurut[:3]
    ]

    return {
        "total_konten": len(per_konten),
        "rata_skor": _rata(skor_list),
        "rata_er": _rata(er_list),
        "pola_top3": pola_top,
        "konten_terbaik": terbaik,
        "konten_terburuk": terburuk,
    }


async def get_or_generate_summary(
    db: AsyncSession,
    *,
    brand: Brand,
    organization_id: uuid.UUID,
    period_start: date,
    period_end: date,
    llm: LLMProvider | None = None,
) -> Summary:
    """Ambil ringkasan dari cache, atau generate via LLM lalu simpan.

    Setelah generate baru, kirim notifikasi jenis 'ringkasan_mingguan' ke
    semua anggota org (preferensi dicek di dalam notify()).
    """
    cached = await db.scalar(
        select(Summary).where(
            Summary.brand_id == brand.id,
            Summary.period_start == period_start,
            Summary.period_end == period_end,
        )
    )
    if cached is not None:
        return cached

    llm = llm or await get_llm_provider_for_db(db)
    agg = await _agregat(db, brand.id, period_start, period_end)
    context = {
        "brand_name": brand.name,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        **agg,
    }
    teks = await llm.narrate("ringkasan", context)

    config = await get_or_create_active_config(db, brand.id, organization_id)
    summary = Summary(
        organization_id=organization_id,
        brand_id=brand.id,
        period_start=period_start,
        period_end=period_end,
        teks=teks,
        config_version=int(config.version or 1),
    )
    db.add(summary)
    await db.flush()

    await notify_org(
        db,
        organization_id,
        "ringkasan_mingguan",
        {
            "brand_id": str(brand.id),
            "brand_name": brand.name,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        },
    )
    return summary
