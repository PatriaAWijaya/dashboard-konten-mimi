"""Tes layanan rekomendasi dengan model & service ASLI (Worker Data)."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from datetime import date, timedelta

from sqlalchemy import func, select

from app.models.content import NicheSuggestion, Recommendation
from app.services.recommendations import generate_recommendations, set_recommendation_status
from tests.kontrak_palsu import buat_org_brand, seed_konten_skor


def _periode():
    akhir = date.today()
    return akhir - timedelta(days=29), akhir


def _tipe(rec):
    """(type, format, tujuan) dibaca dari evidence (kolom format/tujuan/niche tidak ada)."""
    ev = rec.evidence or {}
    return rec.type, ev.get("format"), ev.get("tujuan")


async def _brand_12(db):
    """Brand dengan 12 konten terskor via service scoring asli."""
    org, brand = await buat_org_brand(db)
    awal, akhir = _periode()
    await seed_konten_skor(
        db, org, brand,
        [("reels", "edukasi", 3, 2), ("carousel", "jualan", 0, 4), ("foto", "hiburan", 1, 2)],
        awal, akhir,
    )
    return org, brand, awal, akhir


async def test_data_kurang_dari_10_return_kosong(db_super):
    org, brand = await buat_org_brand(db_super)
    awal, akhir = _periode()
    await seed_konten_skor(db_super, org, brand, [("reels", "edukasi", 3, 2)], awal, akhir)
    hasil = await generate_recommendations(
        db_super, brand=brand, organization_id=org.id, period_start=awal, period_end=akhir
    )
    assert hasil == []


async def test_generate_menghasilkan_kandidat_rule_based(db_super):
    org, brand, awal, akhir = await _brand_12(db_super)
    hasil = await generate_recommendations(
        db_super, brand=brand, organization_id=org.id, period_start=awal, period_end=akhir
    )
    tipe = {_tipe(r) for r in hasil}
    # reels/edukasi: 3/5 menang -> perbanyak; carousel/jualan: 0/4 -> kurangi
    assert ("perbanyak", "reels", "edukasi") in tipe
    assert ("kurangi", "carousel", "jualan") in tipe
    # carousel/jualan: verdict suitability tidak_sesuai + ada 'kurang' -> perbaiki
    assert ("perbaiki", "carousel", "jualan") in tipe
    # tidak ada niche terpilih -> 1 coba_baru kombinasi belum dicoba
    assert sum(1 for r in hasil if r.type == "coba_baru") == 1
    for r in hasil:
        assert r.title and len(r.title) > 5
        assert len(r.dedup_key) <= 120
        assert r.status == "baru"
        assert r.narrative and len(r.narrative) > 20
        assert "win_rate" in (r.evidence or {})
        assert isinstance(r.reference_content_ids, list)

    # Narasi mock LLM mencantumkan angka bukti (agregat, bukan data mentah).
    perbanyak = next(r for r in hasil if r.type == "perbanyak")
    assert "60,0%" in perbanyak.narrative  # win_rate 3/5
    assert str(perbanyak.evidence["n"]) in perbanyak.narrative


async def test_generate_cache_tidak_menduplikat(db_super):
    org, brand, awal, akhir = await _brand_12(db_super)
    pertama = await generate_recommendations(
        db_super, brand=brand, organization_id=org.id, period_start=awal, period_end=akhir
    )
    kedua = await generate_recommendations(
        db_super, brand=brand, organization_id=org.id, period_start=awal, period_end=akhir
    )
    assert {r.id for r in pertama} == {r.id for r in kedua}
    total = await db_super.scalar(
        select(func.count()).select_from(Recommendation).where(Recommendation.brand_id == brand.id)
    )
    assert total == len(pertama)


async def test_dedup_ditolak_tidak_muncul_lagi(db_super):
    org, brand, awal, akhir = await _brand_12(db_super)
    hasil = await generate_recommendations(
        db_super, brand=brand, organization_id=org.id, period_start=awal, period_end=akhir
    )
    kurangi = next(r for r in hasil if r.type == "kurangi")
    await set_recommendation_status(db_super, kurangi, "ditolak")
    await db_super.commit()

    segar = await generate_recommendations(
        db_super, brand=brand, organization_id=org.id, period_start=awal, period_end=akhir
    )
    assert all(r.status != "ditolak" for r in segar)
    assert ("kurangi", "carousel", "jualan") not in {_tipe(r) for r in segar}


async def test_set_recommendation_status_valid_dan_invalid(db_super):
    org, brand, awal, akhir = await _brand_12(db_super)
    hasil = await generate_recommendations(
        db_super, brand=brand, organization_id=org.id, period_start=awal, period_end=akhir
    )
    rec = hasil[0]
    await set_recommendation_status(db_super, rec, "diterima")
    assert rec.status == "diterima"
    try:
        await set_recommendation_status(db_super, rec, "ngawur")
    except ValueError as exc:
        assert "tidak valid" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("ValueError tidak terangkat untuk status invalid")


async def test_niche_terpilih_jadi_coba_baru(db_super):
    org, brand, awal, akhir = await _brand_12(db_super)
    db_super.add(
        NicheSuggestion(
            organization_id=org.id,
            brand_id=brand.id,
            dna_version=1,
            name="Panduan branding untuk yayasan",
            match_percent=80,
            alasan="Selaras dengan DNA.",
            angles=["a1", "a2"],
            monetisasi="Jasa konsultasi.",
            persaingan="rendah",
            label_sumber="ESTIMASI",
            is_selected=True,
        )
    )
    await db_super.flush()
    hasil = await generate_recommendations(
        db_super, brand=brand, organization_id=org.id, period_start=awal, period_end=akhir
    )
    coba = [r for r in hasil if r.type == "coba_baru"]
    assert len(coba) == 1
    assert coba[0].evidence.get("niche") == "Panduan branding untuk yayasan"
    assert "Panduan branding untuk yayasan" in coba[0].title
