"""Tes alokator deterministik, konfigurasi planner, ekspor, ringkasan, realisasi."""

import uuid
from datetime import date, datetime, timezone

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from app.core.security import create_access_token
from app.models.brand import Brand
from app.models.content import (
    Content,
    ContentScore,
    Recommendation,
    RecommendationStatus,
    RecommendationType,
    ScoreStatus,
    ScoringConfig,
)
from tests.conftest import auth_headers, create_org_direct, create_user_direct

BASE = "/api/v1"
SENIN = date(2026, 9, 7)  # Senin
assert SENIN.weekday() == 0

METRIK_MENANG = {"views": 20000, "likes": 2000, "comments": 400, "shares": 600, "saves": 800}
# WER menang = (2000 + 400*3 + 600*5 + 800*5) / 20000 = 0.51
METRIK_KURANG = {"views": 1500, "likes": 5, "comments": 0, "shares": 0, "saves": 2}
# WER kurang = (5 + 0 + 0 + 10) / 1500 = 0.01


def _headers_for(user):
    return auth_headers(create_access_token(user.id, False))


async def _seed_brand(db, *, n_reels_menang=4, n_carousel_menang=0, n_kurang=0):
    """Buat org+brand+scoring config+konten+skor langsung. Return dict."""
    owner = await create_user_direct(db)
    org = await create_org_direct(db, owner)
    brand = Brand(organization_id=org.id, name=f"Brand Alok {uuid.uuid4().hex[:6]}")
    db.add(brand)
    await db.flush()
    cfg = ScoringConfig(
        organization_id=org.id, brand_id=brand.id, version=1,
        weights={}, thresholds={},
    )
    db.add(cfg)
    await db.flush()

    contents = []
    idx = 0

    async def _konten(fmt, tjn, menang: bool, posted: datetime):
        nonlocal idx
        idx += 1
        metrik = dict(METRIK_MENANG if menang else METRIK_KURANG)
        c = Content(
            organization_id=org.id, brand_id=brand.id,
            post_id=f"post-{fmt}-{tjn}-{idx}-{uuid.uuid4().hex[:4]}",
            platform="tiktok", format=fmt, tujuan=tjn, posted_at=posted,
        )
        db.add(c)
        await db.flush()
        s = ContentScore(
            organization_id=org.id, content_id=c.id, scoring_config_id=cfg.id,
            period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
            score=1.0 if menang else 0.1,
            status=ScoreStatus.MENANG if menang else ScoreStatus.KURANG,
            labels=[], metrics_snapshot=metrik,
        )
        db.add(s)
        await db.flush()
        contents.append(c)
        return c

    for i in range(n_reels_menang):
        await _konten("reels", "edukasi", True, datetime(2026, 9, 1 + i, 12, tzinfo=timezone.utc))
    for i in range(n_carousel_menang):
        await _konten("carousel", "edukasi", True, datetime(2026, 9, 10 + i, 12, tzinfo=timezone.utc))
    for i in range(n_kurang):
        await _konten("foto", "hiburan", False, datetime(2026, 9, 20 + i, 12, tzinfo=timezone.utc))
    await db.commit()
    return {"owner": owner, "org": org, "brand": brand, "contents": contents}


async def _terima_rekomendasi(db, org, brand, fmt, tjn, avg_wer, ref_post_ids, tipe=RecommendationType.PERBANYAK):
    rec = Recommendation(
        organization_id=org.id, brand_id=brand.id, type=tipe,
        title=f"Perbanyak {fmt} {tjn}",
        narrative=f"Pola {fmt} untuk tujuan {tjn} menunjukkan performa baik. Lanjutkan dengan variasi topik.",
        evidence={
            "type": tipe, "format": fmt, "tujuan": tjn, "n": 4, "menang": 4,
            "win_rate": 1.0, "avg_score": 1.0, "avg_wer": avg_wer,
            "contoh_post_ids": ref_post_ids,
        },
        reference_content_ids=list(ref_post_ids),
        status=RecommendationStatus.DITERIMA,
        period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
        config_version=1, dedup_key=f"uji-{fmt}-{tjn}-{uuid.uuid4().hex[:6]}",
    )
    db.add(rec)
    await db.flush()
    await db.commit()
    return rec


async def _put_konfig(client, h, brand, body):
    return await client.put(
        f"{BASE}/content/brands/{brand.id}/planner/konfigurasi", headers=h, json=body
    )


# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------

async def test_konfigurasi_default_dan_update(client, db_super):
    seed = await _seed_brand(db_super)
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(seed["org"].id)

    r = await client.get(f"{BASE}/content/brands/{seed['brand'].id}/planner/konfigurasi", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kapasitas_mingguan"] == 7
    assert data["target_distribusi"] is None
    assert data["porsi_eksperimen"] == 0.2

    r = await _put_konfig(client, h, seed["brand"], {
        "kapasitas_mingguan": 10,
        "porsi_eksperimen": 0.3,
        "target_distribusi": {"reels": 2, "carousel": 2},
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kapasitas_mingguan"] == 10
    assert data["porsi_eksperimen"] == 0.3
    # dinormalisasi -> jumlah 1
    assert abs(sum(data["target_distribusi"].values()) - 1.0) < 1e-6
    assert data["target_distribusi"]["reels"] == 0.5

    # null menghapus distribusi -> fallback pola menang
    r = await _put_konfig(client, h, seed["brand"], {"target_distribusi": None})
    assert r.status_code == 200, r.text
    assert r.json()["target_distribusi"] is None

    # validasi
    r = await _put_konfig(client, h, seed["brand"], {"kapasitas_mingguan": 0})
    assert r.status_code == 400, r.text
    r = await _put_konfig(client, h, seed["brand"], {"porsi_eksperimen": 1.5})
    assert r.status_code == 400, r.text
    r = await _put_konfig(client, h, seed["brand"], {"target_distribusi": {"youtube-shorts": 1.0}})
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# Generate: deterministik, distribusi, eksperimen
# ---------------------------------------------------------------------------

async def _brand_dengan_rekomendasi(db_super):
    seed = await _seed_brand(db_super, n_reels_menang=4, n_carousel_menang=4)
    org, brand = seed["org"], seed["brand"]
    reels_ids = [c.post_id for c in seed["contents"] if c.format == "reels"]
    carousel_ids = [c.post_id for c in seed["contents"] if c.format == "carousel"]
    await _terima_rekomendasi(db_super, org, brand, "reels", "edukasi", 0.51, reels_ids)
    await _terima_rekomendasi(db_super, org, brand, "carousel", "edukasi", 0.4, carousel_ids)
    return seed


async def test_generate_deterministik(client, db_super):
    seed = await _brand_dengan_rekomendasi(db_super)
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(seed["org"].id)
    await _put_konfig(client, h, seed["brand"], {"kapasitas_mingguan": 10, "porsi_eksperimen": 0.2})

    body = {"minggu": SENIN.isoformat()}
    r1 = await client.post(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/alokasi/generate", headers=h, json=body
    )
    r2 = await client.post(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/alokasi/generate", headers=h, json=body
    )
    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text
    assert r1.json() == r2.json(), "generate harus deterministik"

    data = r1.json()
    assert data["info"]["total_slot"] == 10
    assert data["info"]["slot_eksperimen"] == 2
    assert len(data["slots"]) == 10
    # tanggal round-robin Senin..Minggu
    assert data["slots"][0]["tanggal"] == SENIN.isoformat()
    assert data["slots"][6]["tanggal"] == "2026-09-13"  # Minggu
    assert data["slots"][7]["tanggal"] == SENIN.isoformat()  # putaran kedua
    # target selalu rentang [min, max]
    for s in data["slots"]:
        assert isinstance(s["target_er"], list) and len(s["target_er"]) == 2
        assert s["target_er"][0] <= s["target_er"][1]


async def test_generate_distribusi_mengikuti_target(client, db_super):
    seed = await _brand_dengan_rekomendasi(db_super)
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(seed["org"].id)
    # semua bobot ke reels -> semua slot reguler berformat reels
    await _put_konfig(client, h, seed["brand"], {
        "kapasitas_mingguan": 6, "porsi_eksperimen": 0.0,
        "target_distribusi": {"reels": 1.0},
    })
    r = await client.post(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/alokasi/generate",
        headers=h, json={"minggu": SENIN.isoformat()},
    )
    assert r.status_code == 200, r.text
    slots = r.json()["slots"]
    assert len(slots) == 6
    assert all(s["format"] == "reels" for s in slots)
    assert all(not s["eksperimen"] for s in slots)

    # semua bobot ke carousel
    await _put_konfig(client, h, seed["brand"], {"target_distribusi": {"carousel": 1.0}})
    r = await client.post(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/alokasi/generate",
        headers=h, json={"minggu": SENIN.isoformat()},
    )
    assert r.status_code == 200, r.text
    assert all(s["format"] == "carousel" for s in r.json()["slots"])


async def test_generate_porsi_eksperimen(client, db_super):
    seed = await _brand_dengan_rekomendasi(db_super)
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(seed["org"].id)
    await _put_konfig(client, h, seed["brand"], {"kapasitas_mingguan": 10, "porsi_eksperimen": 0.2})

    r = await client.post(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/alokasi/generate",
        headers=h, json={"minggu": SENIN.isoformat()},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    eksperimen = [s for s in data["slots"] if s["eksperimen"]]
    assert len(eksperimen) == data["info"]["slot_eksperimen"] == 2
    # kombinasi format/tujuan eksperimen belum pernah dicoba brand
    dipakai = {(c.format, c.tujuan) for c in seed["contents"]}
    for s in eksperimen:
        assert (s["format"], s["tujuan"]) not in dipakai
        assert s["sumber_rekomendasi_id"] is None


async def test_generate_minggu_bukan_senin_400(client, db_super):
    seed = await _seed_brand(db_super)
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(seed["org"].id)
    r = await client.post(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/alokasi/generate",
        headers=h, json={"minggu": "2026-09-08"},  # Selasa
    )
    assert r.status_code == 400, r.text
    assert "Senin" in r.json()["detail"]


async def test_generate_tanpa_rekomendasi_tetap_jalan(client, db_super):
    seed = await _seed_brand(db_super, n_reels_menang=4)
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(seed["org"].id)
    await _put_konfig(client, h, seed["brand"], {"kapasitas_mingguan": 5, "porsi_eksperimen": 0.0})
    r = await client.post(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/alokasi/generate",
        headers=h, json={"minggu": SENIN.isoformat()},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["info"]["total_slot"] == 5
    assert all(s["format"] == "reels" for s in data["slots"])  # pola menang brand


# ---------------------------------------------------------------------------
# Terima -> planned_posts
# ---------------------------------------------------------------------------

async def test_terima_membuat_planned_posts(client, db_super):
    seed = await _brand_dengan_rekomendasi(db_super)
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(seed["org"].id)
    await _put_konfig(client, h, seed["brand"], {"kapasitas_mingguan": 8, "porsi_eksperimen": 0.25})

    rg = await client.post(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/alokasi/generate",
        headers=h, json={"minggu": SENIN.isoformat()},
    )
    assert rg.status_code == 200, rg.text
    slots = rg.json()["slots"]

    rt = await client.post(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/alokasi/terima",
        headers=h, json={"slots": slots},
    )
    assert rt.status_code == 200, rt.text
    assert rt.json()["dibuat"] == len(slots) == 8

    rl = await client.get(
        f"{BASE}/content/brands/{seed['brand'].id}/planner",
        headers=h, params={"bulan": "2026-09"},
    )
    assert rl.status_code == 200, rl.text
    rows = rl.json()
    assert len(rows) == 8
    assert all(r["status"] == "terjadwal" for r in rows)
    assert all(r["platform"] in ("tiktok", "instagram") for r in rows)


async def test_terima_slot_tidak_valid_400(client, db_super):
    seed = await _seed_brand(db_super)
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(seed["org"].id)
    r = await client.post(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/alokasi/terima",
        headers=h, json={"slots": [{"tanggal": "2026-09-07"}]},
    )
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# Ringkasan header target
# ---------------------------------------------------------------------------

async def test_ringkasan_berlabel_estimasi(client, db_super):
    seed = await _seed_brand(db_super, n_reels_menang=4)
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(seed["org"].id)
    for i in range(3):
        r = await client.post(
            f"{BASE}/content/brands/{seed['brand'].id}/planner",
            headers=h,
            json={
                "judul": f"Rencana {i}", "format": "reels", "tujuan": "edukasi",
                "tanggal_rencana": f"2026-09-{7 + i:02d}",
            },
        )
        assert r.status_code == 201, r.text

    r = await client.get(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/ringkasan",
        headers=h, params={"bulan": "2026-09"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_rencana"] == 3
    assert data["label"] == "estimasi"
    assert "bukan angka pasti" in data["catatan"]
    # rentang: semua konten menang views=20000 -> min == max == 3*20000
    assert data["estimasi_views_min"] == 60000
    assert data["estimasi_views_max"] == 60000
    assert data["estimasi_views_min"] <= data["estimasi_views_max"]
    # target ER = rata-rata WER pola menang = 0.51
    assert abs(data["target_er"] - 0.51) < 1e-6

    r = await client.get(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/ringkasan",
        headers=h, params={"bulan": "2026-13"},
    )
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# Ekspor CSV & PDF
# ---------------------------------------------------------------------------

async def test_export_csv(client, db_super):
    seed = await _seed_brand(db_super)
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(seed["org"].id)
    r = await client.post(
        f"{BASE}/content/brands/{seed['brand'].id}/planner",
        headers=h,
        json={"judul": "Judul CSV", "format": "reels", "tujuan": "edukasi",
              "tanggal_rencana": "2026-09-07", "status": "terjadwal"},
    )
    assert r.status_code == 201, r.text

    r = await client.get(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/export.csv",
        headers=h, params={"bulan": "2026-09"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert 'filename="planner-2026-09.csv"' in r.headers["content-disposition"]
    baris = r.text.strip().split("\n")
    assert baris[0] == "tanggal,platform,format,tujuan,judul,status"
    assert len(baris) == 2
    assert "2026-09-07" in baris[1] and "Judul CSV" in baris[1] and "terjadwal" in baris[1]


async def test_export_pdf(client, db_super):
    seed = await _seed_brand(db_super)
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(seed["org"].id)
    r = await client.post(
        f"{BASE}/content/brands/{seed['brand'].id}/planner",
        headers=h,
        json={"judul": "Judul PDF", "format": "reels", "tujuan": "edukasi",
              "tanggal_rencana": "2026-09-07"},
    )
    assert r.status_code == 201, r.text

    r = await client.get(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/export.pdf",
        headers=h, params={"bulan": "2026-09"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert 'filename="planner-2026-09.pdf"' in r.headers["content-disposition"]
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 500


# ---------------------------------------------------------------------------
# Realisasi
# ---------------------------------------------------------------------------

async def test_realisasi_rasio_benar(client, db_super):
    # Seed hanya konten KURANG yang tidak cocok slot (foto/hiburan, Sep 20-21).
    seed = await _seed_brand(db_super, n_reels_menang=0, n_kurang=2)
    org, brand = seed["org"], seed["brand"]
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(org.id)

    # slot rencana: 2026-09-01 reels/edukasi
    r = await client.post(
        f"{BASE}/content/brands/{brand.id}/planner",
        headers=h,
        json={"judul": "Rencana realisasi", "format": "reels", "tujuan": "edukasi",
              "tanggal_rencana": "2026-09-01", "status": "terjadwal"},
    )
    assert r.status_code == 201, r.text

    # konten sesuai rencana: 2026-09-02 (selisih 1 hari), reels/edukasi, MENANG
    # konten di luar rencana: 2026-09-20, foto/hiburan, KURANG
    from sqlalchemy import select as _select

    cfg_id = await db_super.scalar(
        _select(ScoringConfig.id).where(ScoringConfig.brand_id == brand.id)
    )

    async def _konten(post_id, fmt, tjn, posted, menang):
        c = Content(
            organization_id=org.id, brand_id=brand.id, post_id=post_id,
            platform="tiktok", format=fmt, tujuan=tjn, posted_at=posted,
        )
        db_super.add(c)
        await db_super.flush()
        db_super.add(ContentScore(
            organization_id=org.id, content_id=c.id, scoring_config_id=cfg_id,
            period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
            score=1.0 if menang else 0.1,
            status=ScoreStatus.MENANG if menang else ScoreStatus.KURANG,
            labels=[], metrics_snapshot=dict(METRIK_MENANG if menang else METRIK_KURANG),
        ))
        await db_super.flush()

    await _konten("real-sesuai-1", "reels", "edukasi",
                 datetime(2026, 9, 2, 12, tzinfo=timezone.utc), True)
    await _konten("real-luar-1", "foto", "hiburan",
                 datetime(2026, 9, 20, 12, tzinfo=timezone.utc), False)
    await db_super.commit()

    r = await client.get(
        f"{BASE}/content/brands/{brand.id}/planner/realisasi",
        headers=h, params={"bulan": "2026-09"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["sesuai_rencana"]["jumlah"] == 1
    assert abs(data["sesuai_rencana"]["rata_wer"] - 0.51) < 1e-6
    # 2 konten KURANG dari seed + 1 manual
    assert data["di_luar_rencana"]["jumlah"] == 3
    assert abs(data["di_luar_rencana"]["rata_wer"] - 0.01) < 1e-6
    assert abs(data["rasio"] - 51.0) < 1e-6
    assert data["narasi"] == "Konten sesuai rencana ER-nya 51,0× dibanding di luar rencana."


async def test_realisasi_tanpa_data_disampaikan_apa_adanya(client, db_super):
    seed = await _seed_brand(db_super)
    h = _headers_for(seed["owner"])
    h["X-Organization-Id"] = str(seed["org"].id)
    r = await client.get(
        f"{BASE}/content/brands/{seed['brand'].id}/planner/realisasi",
        headers=h, params={"bulan": "2026-08"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["sesuai_rencana"]["jumlah"] == 0
    assert data["di_luar_rencana"]["jumlah"] == 0
    assert data["rasio"] is None
    assert "Belum ada konten terbit" in data["narasi"]
