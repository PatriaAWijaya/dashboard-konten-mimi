"""Helper seed untuk tes integrasi Worker AI Services & API.

RIWAYAT: modul ini dulunya berisi definisi model & service PALSU (kontrak
sementara) selama Worker Data mengembangkan modul aslinya. Kini modul asli
sudah tersedia (app.models.content, app.services.scoring, csv_import,
suitability), sehingga file ini HANYA berisi helper seeding yang memakai
model & service ASLI — tanpa definisi palsu apa pun.

- buat_org_brand: buat Organization + Brand langsung.
- seed_konten_skor: buat Content + ContentMetricsDaily, lalu jalankan service
  scoring ASLI (run_scoring) agar status menang/kurang deterministik.

Profil metrik (dihitung dengan service scoring asli):
- MENANG: views=20000, reach=20000, likes=2000, comments=400, shares=600,
  saves=800, avg_watch_seconds=25  -> score 1.0 -> status 'menang'.
- KURANG: views=1500, reach=1500, likes=5, comments=0, shares=0, saves=2,
  avg_watch_seconds=3 -> score ~0.09 -> status 'kurang'.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.content import Content, ContentMetricsDaily
from app.models.organization import Organization
from app.services.scoring import run_scoring

_METRIK_MENANG = {
    "views": 20000,
    "reach": 20000,
    "likes": 2000,
    "comments": 400,
    "shares": 600,
    "saves": 800,
    "avg_watch_seconds": 25,
    "profile_clicks": 10,
    "link_clicks": 5,
    "replies": 20,
    "sticker_taps": 0,
}

_METRIK_KURANG = {
    "views": 1500,
    "reach": 1500,
    "likes": 5,
    "comments": 0,
    "shares": 0,
    "saves": 2,
    "avg_watch_seconds": 3,
    "profile_clicks": 0,
    "link_clicks": 0,
    "replies": 0,
    "sticker_taps": 0,
}


async def buat_org_brand(
    db: AsyncSession, nama_org: str = "Org Tes", nama_brand: str = "Brand Tes"
):
    """Buat Organization + Brand langsung (bypass RLS via sesi superadmin)."""
    org = Organization(id=uuid.uuid4(), name=f"{nama_org} {uuid.uuid4().hex[:6]}")
    db.add(org)
    await db.flush()
    brand = Brand(
        id=uuid.uuid4(),
        organization_id=org.id,
        name=f"{nama_brand} {uuid.uuid4().hex[:6]}",
    )
    db.add(brand)
    await db.flush()
    return org, brand


async def seed_konten_skor(
    db: AsyncSession,
    org,
    brand,
    pola: list[tuple[str, str, int, int]],
    awal: date,
    akhir: date,
):
    """Seed konten + skor memakai service scoring ASLI.

    pola: list (format, tujuan, n_menang, n_kurang). posted_at disebar merata
    di [awal, akhir]. Mengembalikan list ContentScore hasil run_scoring.
    """
    rentang = max((akhir - awal).days, 1)
    idx = 0
    for fmt, tjn, n_menang, n_kurang in pola:
        for _ in range(n_menang):
            await _satu_konten(db, org, brand, fmt, tjn, idx, _METRIK_MENANG, awal, rentang)
            idx += 1
        for _ in range(n_kurang):
            await _satu_konten(db, org, brand, fmt, tjn, idx, _METRIK_KURANG, awal, rentang)
            idx += 1
    await db.flush()
    return await run_scoring(
        db, brand=brand, organization_id=org.id, period_start=awal, period_end=akhir
    )


async def _satu_konten(db, org, brand, fmt, tjn, idx, metrik, awal, rentang):
    hari = awal + timedelta(days=idx % rentang)
    posted = datetime(hari.year, hari.month, hari.day, 12, 0, tzinfo=timezone.utc)
    c = Content(
        organization_id=org.id,
        brand_id=brand.id,
        post_id=f"p-{fmt}-{tjn}-{idx}-{uuid.uuid4().hex[:4]}",
        platform="tiktok",
        format=fmt,
        tujuan=tjn,
        posted_at=posted,
    )
    db.add(c)
    await db.flush()
    db.add(ContentMetricsDaily(organization_id=org.id, content_id=c.id, date=hari, **metrik))
