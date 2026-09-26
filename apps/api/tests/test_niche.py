"""Tes layanan niche finder dengan model ASLI (Worker Data)."""

import uuid

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from app.models.content import BrandDNACard, NicheInterview, NicheSuggestion
from app.services.niche import (
    QUESTIONS,
    confirm_dna,
    needs_followup,
    save_answer,
    select_niches,
    start_interview,
    suggest_niches,
    synthesize_dna,
)
from tests.conftest import create_user_direct
from tests.kontrak_palsu import buat_org_brand


async def _user(db):
    return await create_user_direct(db)

JAWABAN = [
    "Saya Patria, brand strategist untuk NGO dan yayasan di Indonesia.",
    "Jasa konsultasi branding dan workshop strategi konten untuk yayasan.",
    "Pengurus yayasan dan NGO kecil di Jawa Timur usia 30-45 tahun.",
    "Yayasan kesulitan fundraising karena brand-nya tidak dikenal donatur.",
    "Pengalaman 20 tahun membangun brand NGO hingga event 17.000 anak yatim.",
    "Strategi brand dan cara mengubah donatur menjadi advokat setia.",
    "Menaikkan donasi 3x lipat untuk sebuah yayasan dalam 6 bulan.",
    "Membership bulanan Rp99rb plus jasa konsultasi brand untuk yayasan.",
]


async def _wawancara_selesai(db, brand, org):
    user = await _user(db)
    interview = await start_interview(
        db, brand=brand, organization_id=org.id, user_id=user.id
    )
    for step, jawaban in enumerate(JAWABAN):
        hasil = await save_answer(
            db, interview=interview, step=step, answer=jawaban, skipped=False
        )
        assert hasil["status"] == "ok"
    assert interview.status == "selesai"
    return interview


async def test_start_interview_idempoten(db_super):
    org, brand = await buat_org_brand(db_super)
    uid = (await _user(db_super)).id
    pertama = await start_interview(db_super, brand=brand, organization_id=org.id, user_id=uid)
    assert pertama.status == "berjalan"
    assert pertama.current_step == 0
    kedua = await start_interview(db_super, brand=brand, organization_id=org.id, user_id=uid)
    assert kedua.id == pertama.id


async def test_delapan_pertanyaan_tersedia():
    assert len(QUESTIONS) == 8
    for q in QUESTIONS:
        assert q["pertanyaan"] and q["alasan"] and q["cara_menjawab"] and q["contoh"]


async def test_save_answer_butuh_elaborasi_lalu_ok(db_super):
    org, brand = await buat_org_brand(db_super)
    interview = await start_interview(
        db_super, brand=brand, organization_id=org.id, user_id=(await _user(db_super)).id
    )
    assert needs_followup("ok")
    assert needs_followup("a b c d e")
    assert not needs_followup(JAWABAN[0])

    hasil = await save_answer(db_super, interview=interview, step=0, answer="ok", skipped=False)
    assert hasil == {"status": "butuh_elaborasi", "next_step": 0}
    hasil = await save_answer(db_super, interview=interview, step=0, answer="ok", skipped=False)
    assert hasil == {"status": "butuh_elaborasi", "next_step": 0}
    # Follow-up ke-3 (melebihi MAX_FOLLOWUP=2) diterima apa adanya.
    hasil = await save_answer(db_super, interview=interview, step=0, answer="ok", skipped=False)
    assert hasil == {"status": "ok", "next_step": 1}


async def test_save_answer_skip_dan_step_salah(db_super):
    org, brand = await buat_org_brand(db_super)
    interview = await start_interview(
        db_super, brand=brand, organization_id=org.id, user_id=(await _user(db_super)).id
    )
    hasil = await save_answer(db_super, interview=interview, step=0, answer=None, skipped=True)
    assert hasil == {"status": "ok", "next_step": 1}
    assert "identitas" in (interview.skipped or [])

    try:
        await save_answer(db_super, interview=interview, step=5, answer="x", skipped=False)
    except ValueError as exc:
        assert "langkah ke-2" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("ValueError tidak terangkat untuk step salah")

    try:
        await save_answer(db_super, interview=interview, step=1, answer="   ", skipped=False)
    except ValueError as exc:
        assert "tidak boleh kosong" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("ValueError tidak terangkat untuk jawaban kosong")


async def test_synthesize_dna_dari_jawaban_user(db_super):
    org, brand = await buat_org_brand(db_super)
    interview = await _wawancara_selesai(db_super, brand, org)
    dna = await synthesize_dna(db_super, interview=interview, brand=brand, organization_id=org.id)
    assert isinstance(dna, BrandDNACard)
    assert dna.version == 1
    assert not dna.confirmed
    # Template memakai kata-kata user sendiri (bukan teks generik).
    assert "Pengurus yayasan" in dna.misi
    assert "fundraising" in dna.positioning_statement
    assert "17.000 anak yatim" in dna.diferensiasi
    assert len(dna.nilai_inti) == 3
    # Model asli tidak punya kolom ringkasan.
    assert not hasattr(dna, "ringkasan")

    dna2 = await synthesize_dna(db_super, interview=interview, brand=brand, organization_id=org.id)
    assert dna2.version == 2


async def test_synthesize_gagal_bila_belum_selesai(db_super):
    org, brand = await buat_org_brand(db_super)
    interview = await start_interview(
        db_super, brand=brand, organization_id=org.id, user_id=(await _user(db_super)).id
    )
    try:
        await synthesize_dna(db_super, interview=interview, brand=brand, organization_id=org.id)
    except ValueError as exc:
        assert "belum selesai" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("ValueError tidak terangkat")


async def test_suggest_niches_butuh_dna_terkonfirmasi(db_super):
    org, brand = await buat_org_brand(db_super)
    interview = await _wawancara_selesai(db_super, brand, org)
    dna = await synthesize_dna(db_super, interview=interview, brand=brand, organization_id=org.id)
    try:
        await suggest_niches(db_super, brand=brand, organization_id=org.id, dna=dna)
    except ValueError as exc:
        assert "Konfirmasi" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("ValueError tidak terangkat")

    await confirm_dna(db_super, dna)
    assert dna.confirmed
    saran = await suggest_niches(db_super, brand=brand, organization_id=org.id, dna=dna)
    assert 5 <= len(saran) <= 7
    for s in saran:
        assert isinstance(s, NicheSuggestion)
        assert s.dna_version == dna.version
        assert isinstance(s.match_percent, int)
        assert 35 <= s.match_percent <= 88
        assert s.label_sumber in ("DATA", "ESTIMASI", "KLAIM")
        assert len(s.angles) == 10
        assert not s.is_selected
    # Ada yang berlabel KLAIM karena jawaban menyebut angka/Rp.
    assert any(s.label_sumber == "KLAIM" for s in saran)


async def test_select_niches_satu_sampai_dua(db_super):
    org, brand = await buat_org_brand(db_super)
    interview = await _wawancara_selesai(db_super, brand, org)
    dna = await synthesize_dna(db_super, interview=interview, brand=brand, organization_id=org.id)
    await confirm_dna(db_super, dna)
    saran = await suggest_niches(db_super, brand=brand, organization_id=org.id, dna=dna)

    dipilih = await select_niches(
        db_super, brand=brand, organization_id=org.id, ids=[saran[0].id, saran[1].id]
    )
    assert len(dipilih) == 2
    assert {s.id for s in dipilih} == {saran[0].id, saran[1].id}
    assert all(s.is_selected for s in dipilih)
    assert not any(s.is_selected for s in saran[2:])

    # Pilih 3 -> ditolak; pilih milik brand lain -> ditolak.
    try:
        await select_niches(
            db_super, brand=brand, organization_id=org.id,
            ids=[saran[0].id, saran[1].id, saran[2].id],
        )
    except ValueError as exc:
        assert "1-2" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("ValueError tidak terangkat untuk 3 pilihan")

    try:
        await select_niches(
            db_super, brand=brand, organization_id=org.id, ids=[uuid.uuid4()]
        )
    except ValueError as exc:
        assert "tidak ditemukan" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("ValueError tidak terangkat untuk id asing")


async def test_interview_tersimpan_dengan_benar(db_super):
    org, brand = await buat_org_brand(db_super)
    interview = await _wawancara_selesai(db_super, brand, org)
    segar = await db_super.get(NicheInterview, interview.id)
    assert segar.status == "selesai"
    assert segar.current_step == 8
    assert segar.answers["audiens"] == JAWABAN[2]
