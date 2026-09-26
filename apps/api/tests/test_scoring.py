"""Tes scoring konten: determinisme, rumus WER, gerbang views, threshold platform, batas status."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from datetime import date, datetime, timezone

from sqlalchemy import func, select

from app.models.brand import Brand
from app.models.content import Content, ContentMetricsDaily, ContentScore
from app.services.scoring import (
    DEFAULT_THRESHOLDS,
    DEFAULT_WEIGHTS,
    compute_weighted_er,
    get_or_create_active_config,
    run_scoring,
    score_content,
)

from .conftest import create_org_direct, create_user_direct


def _metrics(**over):
    base = {
        "platform": "tiktok",
        "views": 10000,
        "reach": 12000,
        "likes": 500,
        "comments": 100,
        "shares": 80,
        "saves": 80,
        "avg_watch_seconds": 20.0,
        "profile_clicks": 50,
        "link_clicks": 30,
        "replies": 10,
        "sticker_taps": 5,
    }
    base.update(over)
    return base


# ------------------------------------------------------------------ murni ---


def test_wer_formula():
    # (100*1 + 10*3 + 5*5 + 5*5) / 1000 = 180/1000 = 0.18
    assert compute_weighted_er(100, 10, 5, 5, 1000) == pytest.approx(0.18)


def test_wer_views_nol():
    assert compute_weighted_er(10, 5, 2, 1, 0) == 0.0
    assert compute_weighted_er(10, 5, 2, 1, -3) == 0.0


def test_score_deterministik():
    m = _metrics()
    pertama = score_content(m, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
    kedua = score_content(m, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
    assert pertama == kedua
    assert pertama["parts"] == kedua["parts"]
    assert pertama["labels"] == kedua["labels"]


def test_gerbang_min_views():
    kurang = score_content(_metrics(views=999), DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
    assert kurang["status"] == "data_belum_cukup"
    assert kurang["score"] is None
    assert kurang["labels"] == []

    pas = score_content(_metrics(views=1000), DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
    assert pas["status"] != "data_belum_cukup"
    assert pas["score"] is not None


def test_threshold_wer_beda_platform():
    # wer = 60/1000 = 0.06 → di atas 5% (IG) tapi di bawah 8% (TikTok)
    m = _metrics(views=1000, likes=60, comments=0, shares=0, saves=0)
    ig = score_content(m | {"platform": "instagram"}, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
    tt = score_content(m | {"platform": "tiktok"}, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
    assert "wer_tinggi" in ig["labels"]
    assert "wer_tinggi" not in tt["labels"]


def test_label_wer_relatif():
    m = _metrics(views=10000, likes=1000, comments=0, shares=0, saves=0)  # wer = 0.10
    tanpa_median = score_content(m, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, median_wer=None)
    assert "wer_relatif_tinggi" not in tanpa_median["labels"]
    # 0.10 >= 1.5 * 0.05 → label muncul
    dengan_median = score_content(m, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, median_wer=0.05)
    assert "wer_relatif_tinggi" in dengan_median["labels"]
    # 0.10 < 1.5 * 0.10 → label tidak muncul
    median_tinggi = score_content(m, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS, median_wer=0.10)
    assert "wer_relatif_tinggi" not in median_tinggi["labels"]


def test_status_menang():
    m = _metrics(views=10000, likes=1000, comments=200, shares=300, saves=400,
                 avg_watch_seconds=20.0, reach=12000)
    hasil = score_content(m, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
    assert hasil["score"] == pytest.approx(1.0)
    assert hasil["status"] == "menang"
    assert len(hasil["labels"]) >= 3


def test_status_cukup():
    m = _metrics(views=5000, likes=200, comments=30, shares=40, saves=50,
                 avg_watch_seconds=8.0, reach=6000)
    hasil = score_content(m, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
    assert hasil["score"] == pytest.approx(0.6317, abs=1e-3)
    assert hasil["status"] == "cukup"


def test_status_kurang():
    m = _metrics(views=2000, likes=30, comments=2, shares=3, saves=5,
                 avg_watch_seconds=3.0, reach=1500)
    hasil = score_content(m, DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS)
    assert hasil["score"] == pytest.approx(0.2329, abs=1e-3)
    assert hasil["status"] == "kurang"


def test_menang_lewat_jumlah_label():
    # Skor < 0.7 tapi 3+ label winner → tetap 'menang' (cabang OR).
    weights = {"save_rate": 0.1, "share_rate": 0.1, "comment_rate": 0.1,
               "weighted_er": 0.1, "retensi": 0.3, "reach_abs": 0.3}
    m = _metrics(views=2000, likes=0, comments=40, shares=60, saves=80,
                 avg_watch_seconds=0.0, reach=0)
    hasil = score_content(m, weights, DEFAULT_THRESHOLDS)
    assert hasil["score"] < 0.7
    assert len(hasil["labels"]) >= 3
    assert hasil["status"] == "menang"


# --------------------------------------------------------------------- DB ---


async def _make_brand(db, org, name="Brand Skor"):
    brand = Brand(organization_id=org.id, name=name)
    db.add(brand)
    await db.flush()
    await db.commit()
    return brand


async def test_config_dibuat_sekali_dan_reproduksibel(db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner, name="Org Skor Config")
    brand = await _make_brand(db_super, org)

    c1 = await get_or_create_active_config(db_super, brand.id, org.id)
    c2 = await get_or_create_active_config(db_super, brand.id, org.id)
    assert c1.id == c2.id
    assert c1.version == 1
    assert c1.is_active is True
    assert c1.weights == DEFAULT_WEIGHTS
    assert c1.thresholds == DEFAULT_THRESHOLDS
    await db_super.commit()


async def test_run_scoring_upsert_idempoten(db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner, name="Org Skor Run")
    brand = await _make_brand(db_super, org, name="Brand Skor Run")

    def add_content(post_id, fmt="reels", tujuan="hiburan"):
        c = Content(
            organization_id=org.id, brand_id=brand.id, platform="tiktok",
            post_id=post_id, posted_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
            format=fmt, tujuan=tujuan, caption="tes",
        )
        db_super.add(c)
        return c

    c1, c2 = add_content("vid-a"), add_content("vid-b")
    await db_super.flush()
    rows = [
        # konten kuat
        ContentMetricsDaily(organization_id=org.id, content_id=c1.id, date=date(2026, 9, 10),
                            views=50000, reach=60000, likes=4000, comments=800,
                            shares=2000, saves=2500, avg_watch_seconds=22.0),
        ContentMetricsDaily(organization_id=org.id, content_id=c1.id, date=date(2026, 9, 11),
                            views=10000, reach=12000, likes=800, comments=160,
                            shares=400, saves=500, avg_watch_seconds=20.0),
        # konten lemah
        ContentMetricsDaily(organization_id=org.id, content_id=c2.id, date=date(2026, 9, 10),
                            views=1500, reach=1200, likes=10, comments=1,
                            shares=0, saves=5, avg_watch_seconds=2.0, link_clicks=2),
    ]
    db_super.add_all(rows)
    await db_super.commit()

    start, end = date(2026, 9, 1), date(2026, 9, 30)
    hasil1 = await run_scoring(db_super, brand=brand, organization_id=org.id,
                              period_start=start, period_end=end)
    assert len(hasil1) == 2
    by_post = {s.content.post_id: s for s in hasil1}
    assert by_post["vid-a"].status == "menang"
    assert by_post["vid-b"].status == "kurang"
    # snapshot = agregat SUM (views vid-a = 60000)
    assert by_post["vid-a"].metrics_snapshot["views"] == 60000

    # Dijalankan ulang → tidak duplikat, hanya update.
    hasil2 = await run_scoring(db_super, brand=brand, organization_id=org.id,
                              period_start=start, period_end=end)
    assert len(hasil2) == 2
    jumlah = await db_super.scalar(
        select(func.count()).select_from(ContentScore).where(ContentScore.organization_id == org.id)
    )
    assert jumlah == 2
