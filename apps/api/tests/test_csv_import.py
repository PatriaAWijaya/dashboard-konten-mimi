"""Tes impor CSV: idempotensi, baris rusak, kolom tak dikenal, mode auto-platform."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from sqlalchemy import func, select

from app.models.brand import Brand
from app.models.content import Content, ContentMetricsDaily
from app.services.csv_import import EXPECTED_COLUMNS, import_csv

from .conftest import create_org_direct, create_user_direct

HEADER = ",".join(EXPECTED_COLUMNS + ["kolom_aneh"])

CSV_TIKTOK = HEADER + "\n" + "\n".join([
    # 3 baris valid
    "tiktok,vid-001,https://tiktok.com/v/1,2026-09-05,reels,hiburan,Caption lucu,5000,4500,300,20,40,60,12.5,80,10,5,8,ekstra1",
    "tiktok,vid-002,https://tiktok.com/v/2,2026-09-06,foto,branding,Foto produk,8000,9000,500,30,50,70,0,120,5,0,0,ekstra2",
    "tiktok,vid-003,,2026-09-07,carousel,edukasi,Tips hemat,3000,2800,150,25,60,120,18.0,40,15,0,0,",
    # 1 tanggal salah format
    "tiktok,vid-004,https://tiktok.com/v/4,07/09/2026,reels,hiburan,Rusak tanggal,4000,3800,200,10,20,30,10.0,50,5,0,0,",
    # 1 angka negatif
    "tiktok,vid-005,https://tiktok.com/v/5,2026-09-08,reels,hiburan,Negatif,-100,3800,200,10,20,30,10.0,50,5,0,0,",
    # 1 tanpa post_id
    "tiktok,,https://tiktok.com/v/6,2026-09-09,reels,hiburan,Tanpa ID,4000,3800,200,10,20,30,10.0,50,5,0,0,",
    # 1 format tak dikenal
    "tiktok,vid-007,https://tiktok.com/v/7,2026-09-10,podcast,hiburan,Format aneh,4000,3800,200,10,20,30,10.0,50,5,0,0,",
])

CSV_AUTO = ",".join(EXPECTED_COLUMNS) + "\n" + "\n".join([
    "instagram,ig-001,https://instagram.com/p/1,2026-09-05,carousel,edukasi,Konten IG,6000,7000,400,40,80,200,15.0,90,20,0,0",
    "tiktok,tt-001,https://tiktok.com/v/9,2026-09-06,reels,hiburan,Konten TT,9000,8500,600,50,90,110,14.0,100,8,0,0",
])


async def _make_brand(db, org, name="Brand CSV"):
    brand = Brand(organization_id=org.id, name=name)
    db.add(brand)
    await db.flush()
    await db.commit()
    return brand


async def test_import_idempoten_dan_laporan_error(db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner, name="Org CSV Impor")
    brand = await _make_brand(db_super, org)

    hasil1 = await import_csv(
        db_super, brand=brand, organization_id=org.id, platform="tiktok",
        file_bytes=CSV_TIKTOK.encode("utf-8"), filename="tiktok.csv",
    )
    assert hasil1["contents_baru"] == 3
    assert hasil1["contents_diupdate"] == 0
    assert hasil1["metrics_rows"] == 3
    # 4 baris rusak dilaporkan tanpa menggagalkan impor
    assert len(hasil1["baris_gagal"]) == 4
    alasan = " | ".join(g["alasan"] for g in hasil1["baris_gagal"])
    assert "YYYY-MM-DD" in alasan
    assert "negatif" in alasan
    assert "post_id kosong" in alasan
    assert "podcast" in alasan
    # kolom tak dikenal → warning
    assert any("kolom_aneh" in w for w in hasil1["warnings"])

    n_contents = await db_super.scalar(
        select(func.count()).select_from(Content).where(Content.brand_id == brand.id)
    )
    n_metrics = await db_super.scalar(
        select(func.count()).select_from(ContentMetricsDaily)
        .where(ContentMetricsDaily.organization_id == org.id)
    )
    assert n_contents == 3
    assert n_metrics == 3

    # Upload ulang file yang sama → update, bukan duplikat.
    hasil2 = await import_csv(
        db_super, brand=brand, organization_id=org.id, platform="tiktok",
        file_bytes=CSV_TIKTOK.encode("utf-8"), filename="tiktok.csv",
    )
    assert hasil2["contents_baru"] == 0
    assert hasil2["contents_diupdate"] == 3
    assert hasil2["metrics_rows"] == 3

    n_contents2 = await db_super.scalar(
        select(func.count()).select_from(Content).where(Content.brand_id == brand.id)
    )
    n_metrics2 = await db_super.scalar(
        select(func.count()).select_from(ContentMetricsDaily)
        .where(ContentMetricsDaily.organization_id == org.id)
    )
    assert n_contents2 == n_contents
    assert n_metrics2 == n_metrics


async def test_import_auto_platform(db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner, name="Org CSV Auto")
    brand = await _make_brand(db_super, org, name="Brand CSV Auto")

    hasil = await import_csv(
        db_super, brand=brand, organization_id=org.id, platform="auto",
        file_bytes=CSV_AUTO.encode("utf-8"), filename="campuran.csv",
    )
    assert hasil["contents_baru"] == 2
    assert hasil["baris_gagal"] == []

    platforms = await db_super.scalars(
        select(Content.platform).where(Content.brand_id == brand.id).order_by(Content.platform)
    )
    assert list(platforms.all()) == ["instagram", "tiktok"]


async def test_import_platform_tidak_cocok_dilaporkan(db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner, name="Org CSV Mismatch")
    brand = await _make_brand(db_super, org, name="Brand CSV Mismatch")

    hasil = await import_csv(
        db_super, brand=brand, organization_id=org.id, platform="tiktok",
        file_bytes=CSV_AUTO.encode("utf-8"), filename="campuran.csv",
    )
    # Baris instagram ditolak karena argumen platform = tiktok.
    assert hasil["contents_baru"] == 1
    assert len(hasil["baris_gagal"]) == 1
    assert "tidak cocok" in hasil["baris_gagal"][0]["alasan"]
