"""Tes suitability: verdict pola format×tujuan + laporan analisa."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from datetime import date, datetime, timezone

from app.models.brand import Brand
from app.models.content import Content, ContentMetricsDaily
from app.services.scoring import run_scoring
from app.services.suitability import SUITABILITY_MATRIX, analisa_report, evaluate_suitability

from .conftest import create_org_direct, create_user_direct


def _agg(**over):
    base = {
        "format": "carousel", "tujuan": "edukasi",
        "save_rate": 0.0, "share_rate": 0.0, "comment_rate": 0.0, "er": 0.0,
        "views": 0, "reach": 0, "likes": 0, "comments": 0, "shares": 0, "saves": 0,
        "avg_watch_seconds": 0.0, "replies": 0, "sticker_taps": 0, "link_clicks": 0,
    }
    base.update(over)
    return base


def test_carousel_edukasi_save_tinggi_sesuai():
    hasil = evaluate_suitability(_agg(
        format="carousel", tujuan="edukasi", save_rate=0.05, share_rate=0.04, views=20000,
    ))
    assert hasil["verdict"] == "sesuai"
    assert hasil["diagnoses"] == []
    assert all(d["lolos"] for d in hasil["metrik_utama"])


def test_carousel_edukasi_sebagian_kurang_sesuai():
    # save_rate lolos, share_rate tidak → 1/2 < 2/3 → kurang_sesuai
    hasil = evaluate_suitability(_agg(
        format="carousel", tujuan="edukasi", save_rate=0.05, share_rate=0.002, views=20000,
    ))
    assert hasil["verdict"] == "kurang_sesuai"
    assert len(hasil["diagnoses"]) == 1
    assert hasil["diagnoses"][0]["metrik"] == "share_rate"
    assert len(hasil["suggestions"]) >= 1


def test_reels_hiburan_views_rendah_tidak_sesuai():
    hasil = evaluate_suitability(_agg(
        format="reels", tujuan="hiburan", views=500,
        avg_watch_seconds=2.0, share_rate=0.001,
    ))
    assert hasil["verdict"] == "tidak_sesuai"
    assert len(hasil["diagnoses"]) == 3
    assert len(hasil["suggestions"]) >= 1
    assert any("hook" in s for s in hasil["suggestions"])


def test_kombinasi_tak_dikenal_pakai_default():
    hasil = evaluate_suitability(_agg(
        format="live", tujuan="jualan", er=0.2, comment_rate=0.05,
        share_rate=0.05, views=30000,
    ))
    assert ("live", "jualan") not in SUITABILITY_MATRIX
    assert hasil["verdict"] == "sesuai"


async def test_analisa_report(db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner, name="Org Analisa")
    brand = Brand(organization_id=org.id, name="Brand Analisa")
    db_super.add(brand)
    await db_super.flush()

    kuat = Content(
        organization_id=org.id, brand_id=brand.id, platform="tiktok", post_id="kuat-1",
        posted_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
        format="reels", tujuan="edukasi", caption="kuat",
    )
    lemah = Content(
        organization_id=org.id, brand_id=brand.id, platform="tiktok", post_id="lemah-1",
        posted_at=datetime(2026, 9, 10, tzinfo=timezone.utc),
        format="foto", tujuan="jualan", caption="lemah",
    )
    db_super.add_all([kuat, lemah])
    await db_super.flush()
    db_super.add_all([
        ContentMetricsDaily(
            organization_id=org.id, content_id=kuat.id, date=date(2026, 9, 10),
            views=50000, reach=60000, likes=4000, comments=800,
            shares=2000, saves=2500, avg_watch_seconds=22.0,
        ),
        ContentMetricsDaily(
            organization_id=org.id, content_id=lemah.id, date=date(2026, 9, 10),
            views=1500, reach=1200, likes=10, comments=1,
            shares=0, saves=5, avg_watch_seconds=2.0, link_clicks=2,
        ),
    ])
    await db_super.commit()

    await run_scoring(db_super, brand=brand, organization_id=org.id,
                      period_start=date(2026, 9, 1), period_end=date(2026, 9, 30))

    laporan = await analisa_report(
        db_super, brand=brand, organization_id=org.id,
        period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
    )
    assert set(laporan.keys()) == {"ringkasan", "bermasalah", "rekomendasi_pola"}
    assert len(laporan["ringkasan"]) == 2
    pola = {(r["format"], r["tujuan"]): r for r in laporan["ringkasan"]}
    assert pola[("reels", "edukasi")]["dominan_status"] == "menang"
    assert pola[("foto", "jualan")]["dominan_status"] == "kurang"

    bermasalah = {b["post_id"]: b for b in laporan["bermasalah"]}
    assert "lemah-1" in bermasalah
    assert "kuat-1" not in bermasalah
    assert bermasalah["lemah-1"]["verdict"] in ("kurang_sesuai", "tidak_sesuai")
    assert len(bermasalah["lemah-1"]["diagnoses"]) >= 1
    assert len(bermasalah["lemah-1"]["suggestions"]) >= 1

    assert len(laporan["rekomendasi_pola"]) >= 1
    assert any("reels" in r and "edukasi" in r for r in laporan["rekomendasi_pola"])
