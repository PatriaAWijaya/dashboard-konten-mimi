"""Layanan niche finder: wawancara 8 pertanyaan -> kartu DNA brand -> saran niche.

Dipakai dari model asli app.models.content (Worker Data):
- NicheInterview: status 'berjalan'/'selesai', current_step, answers, skipped.
- BrandDNACard: version, misi, nilai_inti, kepribadian, positioning_statement,
  diferensiasi, confirmed (tanpa kolom ringkasan).
- NicheSuggestion: dna_version (wajib), name, match_percent (int 0-100),
  alasan, angles, monetisasi, persaingan, label_sumber, is_selected.

Narrative LLM untuk 'brand_dna'/'niche' tetap dipanggil sebagai bagian pipeline
(mock: gratis; provider berbayar: hasilnya bisa disimpan bila Worker Data
menambah kolom di kemudian hari).
"""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import (
    BrandDNACard,
    Content,
    ContentScore,
    InterviewStatus,
    LabelSumber,
    NicheInterview,
    NicheSuggestion,
    ScoreStatus,
)
from app.services.llm import get_llm_provider_for_db

MAX_FOLLOWUP = 2

# ---------------------------------------------------------------------------
# 8 pertanyaan wawancara
# ---------------------------------------------------------------------------

QUESTIONS: list[dict] = [
    {
        "key": "identitas",
        "pertanyaan": "Siapa Anda / brand Anda dalam satu kalimat?",
        "alasan": "Identitas yang tajam menentukan nada seluruh konten.",
        "cara_menjawab": "Sebutkan peran + bidang + untuk siapa. Satu kalimat saja.",
        "contoh": "Saya Patria, brand strategist untuk NGO dan yayasan di Indonesia.",
    },
    {
        "key": "penawaran",
        "pertanyaan": "Apa produk/jasa utama yang Anda tawarkan saat ini?",
        "alasan": "Niche harus nyambung dengan sesuatu yang bisa dijual.",
        "cara_menjawab": "Sebutkan 1-2 penawaran inti, bukan semua yang pernah dikerjakan.",
        "contoh": "Jasa konsultasi branding dan workshop strategi konten untuk yayasan.",
    },
    {
        "key": "audiens",
        "pertanyaan": "Siapa audiens spesifik yang paling ingin Anda layani?",
        "alasan": "Konten yang bicara ke semua orang tidak didengar siapa pun.",
        "cara_menjawab": "Sebutkan segmen spesifik: profesi, usia, atau komunitasnya.",
        "contoh": "Pengurus yayasan dan NGO kecil di Jawa Timur usia 30-45 tahun.",
    },
    {
        "key": "masalah",
        "pertanyaan": "Masalah terbesar apa yang dihadapi audiens tersebut?",
        "alasan": "Niche yang kuat lahir dari masalah yang nyata dan mendesak.",
        "cara_menjawab": "Ceritakan keluhan yang paling sering Anda dengar dari mereka.",
        "contoh": "Yayasan kesulitan fundraising karena brand-nya tidak dikenal donatur.",
    },
    {
        "key": "pembeda",
        "pertanyaan": "Apa yang membuat Anda berbeda dari kompetitor di bidang ini?",
        "alasan": "Diferensiasi adalah bahan bakar positioning dan konten.",
        "cara_menjawab": "Sebutkan pengalaman, metode, atau sudut pandang yang khas milik Anda.",
        "contoh": "20 tahun membangun brand NGO hingga event 17.000 anak yatim.",
    },
    {
        "key": "passion_keahlian",
        "pertanyaan": "Topik apa yang bisa Anda bahas berjam-jam tanpa bosan?",
        "alasan": "Konsistensi konten butuh topik yang Anda nikmati.",
        "cara_menjawab": "Sebutkan 1-2 topik yang Anda kuasai dan sukai.",
        "contoh": "Strategi brand dan cara mengubah donatur menjadi advokat.",
    },
    {
        "key": "bukti",
        "pertanyaan": "Bukti nyata apa yang Anda miliki (hasil, angka, testimoni)?",
        "alasan": "Bukti membangun trust lebih cepat dari sekadar klaim.",
        "cara_menjawab": "Sebutkan angka/hasil konkret. Bila belum ada, tulis 'belum ada'.",
        "contoh": "Menaikkan donasi 3x lipat untuk sebuah yayasan dalam 6 bulan.",
    },
    {
        "key": "monetisasi",
        "pertanyaan": "Bagaimana Anda ingin menghasilkan uang dari niche ini?",
        "alasan": "Model monetisasi menentukan format konten yang diprioritaskan.",
        "cara_menjawab": "Pilih: jasa, kursus, membership, afiliasi, atau sponsorship.",
        "contoh": "Membership bulanan Rp99rb + jasa konsultasi brand untuk yayasan.",
    },
]

_KEY_KE_PERTANYAAN = {q["key"]: q["pertanyaan"] for q in QUESTIONS}


# ---------------------------------------------------------------------------
# Follow-up
# ---------------------------------------------------------------------------

def needs_followup(answer: str) -> bool:
    """True bila jawaban terlalu pendek/tidak konkret dan perlu elaborasi.

    Aturan sederhana: < 20 karakter, atau < 3 kata, atau semua kata <= 4 huruf.
    """
    teks = (answer or "").strip()
    if len(teks) < 20:
        return True
    kata = teks.split()
    if len(kata) < 3:
        return True
    if all(len(k) <= 4 for k in kata):
        return True
    return False


def _followup_count(answers: dict, key: str) -> int:
    return int((answers.get("_followup") or {}).get(key, 0) or 0)


# ---------------------------------------------------------------------------
# Wawancara
# ---------------------------------------------------------------------------

async def start_interview(
    db: AsyncSession, *, brand, organization_id: uuid.UUID, user_id: uuid.UUID
) -> NicheInterview:
    """Mulai wawancara baru, atau lanjutkan yang masih 'berjalan' bila ada."""
    existing = (
        await db.execute(
            select(NicheInterview).where(
                NicheInterview.brand_id == brand.id,
                NicheInterview.status == InterviewStatus.BERJALAN,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    interview = NicheInterview(
        organization_id=organization_id,
        brand_id=brand.id,
        user_id=user_id,
        status=InterviewStatus.BERJALAN,
        current_step=0,
        answers={},
        skipped=[],
    )
    db.add(interview)
    await db.flush()
    return interview


async def save_answer(
    db: AsyncSession,
    *,
    interview: NicheInterview,
    step: int,
    answer: str | None,
    skipped: bool,
) -> dict:
    """Simpan jawaban langkah `step`.

    Return {"status": "ok"|"butuh_elaborasi", "next_step": int}.
    """
    if not (0 <= step < len(QUESTIONS)):
        raise ValueError(f"Langkah tidak valid: {step}. Rentang 0-{len(QUESTIONS) - 1}.")
    if step != interview.current_step:
        raise ValueError(
            f"Jawaban harus untuk langkah ke-{interview.current_step + 1} "
            f"(saat ini diminta langkah ke-{step + 1})."
        )
    key = QUESTIONS[step]["key"]
    answers = dict(interview.answers or {})
    daftar_lewati = list(interview.skipped or [])

    if skipped:
        if key not in daftar_lewati:
            daftar_lewati.append(key)
        answers.pop(key, None)
        interview.skipped = daftar_lewati
        interview.answers = answers
        interview.current_step = step + 1
    else:
        teks = (answer or "").strip()
        if not teks:
            raise ValueError("Jawaban tidak boleh kosong. Isi jawaban atau pilih 'lewati'.")
        if needs_followup(teks) and _followup_count(answers, key) < MAX_FOLLOWUP:
            follow = dict(answers.get("_followup") or {})
            follow[key] = _followup_count(answers, key) + 1
            answers["_followup"] = follow
            interview.answers = answers
            await db.flush()
            return {"status": "butuh_elaborasi", "next_step": step}
        answers[key] = teks
        if key in daftar_lewati:
            daftar_lewati.remove(key)
        interview.skipped = daftar_lewati
        interview.answers = answers
        interview.current_step = step + 1

    if interview.current_step >= len(QUESTIONS):
        interview.status = InterviewStatus.SELESAI
    await db.flush()
    return {"status": "ok", "next_step": interview.current_step}


# ---------------------------------------------------------------------------
# Sintesis DNA
# ---------------------------------------------------------------------------

_BELUM = "[belum diisi]"


def _ambil(answers: dict, key: str) -> str:
    return (answers.get(key) or "").strip() or _BELUM


async def synthesize_dna(
    db: AsyncSession, *, interview: NicheInterview, brand, organization_id: uuid.UUID
) -> BrandDNACard:
    """Susun kartu DNA dari jawaban wawancara (template-based dari kata user)."""
    if interview.status != InterviewStatus.SELESAI:
        raise ValueError(
            "Wawancara belum selesai. Jawab atau lewati semua 8 pertanyaan terlebih dahulu."
        )
    answers = {k: v for k, v in (interview.answers or {}).items() if k != "_followup"}
    dilewati = list(interview.skipped or [])

    # Narrative LLM sebagai bagian pipeline (hasilnya tidak disimpan:
    # model BrandDNACard tidak punya kolom ringkasan).
    await (await get_llm_provider_for_db(db)).narrate(
        "brand_dna",
        {
            "brand_name": getattr(brand, "name", ""),
            "jawaban": answers,
            "dilewati": dilewati,
            "label_pertanyaan": _KEY_KE_PERTANYAAN,
            "terjawab": len(answers),
            "total": len(QUESTIONS),
        },
    )

    identitas = _ambil(answers, "identitas")
    penawaran = _ambil(answers, "penawaran")
    audiens = _ambil(answers, "audiens")
    masalah = _ambil(answers, "masalah")
    pembeda = _ambil(answers, "pembeda")
    passion = _ambil(answers, "passion_keahlian")
    bukti = _ambil(answers, "bukti")

    versi_maks = await db.scalar(
        select(func.max(BrandDNACard.version)).where(BrandDNACard.brand_id == brand.id)
    )
    dna = BrandDNACard(
        organization_id=organization_id,
        brand_id=brand.id,
        version=int(versi_maks or 0) + 1,
        misi=f"Membantu {audiens} mengatasi {masalah} melalui {penawaran}.",
        nilai_inti=[
            f"Berdiferensiasi lewat: {pembeda}",
            f"Berakar pada keahlian & passion: {passion}",
            f"Didukung bukti nyata: {bukti}",
        ],
        kepribadian=f"Citra yang dibangun dari identitas: {identitas}",
        positioning_statement=(
            f"Untuk {audiens} yang mengalami {masalah}, "
            f"{getattr(brand, 'name', 'brand ini')} menghadirkan {penawaran} "
            f"— berbeda karena {pembeda}."
        ),
        diferensiasi=pembeda,
        confirmed=False,
    )
    db.add(dna)
    await db.flush()
    return dna


async def confirm_dna(db: AsyncSession, dna: BrandDNACard) -> BrandDNACard:
    """Tandai kartu DNA sebagai terkonfirmasi user."""
    dna.confirmed = True
    await db.flush()
    return dna


# ---------------------------------------------------------------------------
# Saran niche
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "yang", "dan", "untuk", "dengan", "dari", "ini", "itu", "adalah", "saya",
    "kami", "anda", "para", "sebuah", "dalam", "pada", "agar", "supaya",
    "karena", "sebagai", "tidak", "bisa", "dapat", "akan", "telah", "sudah",
    "lebih", "sangat", "cara", "membuat", "menjadi", "kepada", "oleh",
    "juga", "atau", "namun", "tetapi", "bagi", "tentang", "antara", "serta",
    "melalui", "mengatasi", "membantu",
    # Kata generik yang bukan topik niche (agar nama saran tidak aneh).
    "menengah", "kecil", "besar", "indonesia", "publik", "konsisten",
    "kesulitan", "dikenal", "sampai", "tanpa", "mereka", "setiap", "tahun",
    "bulan", "orang", "banyak", "utama", "baik",
    # Kata yang dipakai template nama (hindari rekursi aneh).
    "panduan", "komunitas", "studi", "kasus", "bedah", "mingguan", "pemula",
    "cuan", "ribet",
    # Kata kerja/pewatas umum yang bukan topik.
    "secara", "menyelesaikan", "masalah", "tersebut", "saling", "sedang",
    "masih", "hanya", "pernah", "sering", "selalu", "kurang", "cukup",
    "menjadi", "ialah", "yaitu", "yakni",
    "programnya", "program", "bagus", "sehingga", "acara", "kegiatan",
    "sangat", "amat",
}

_KATA_GENERIK = {"tips", "trik", "bisnis", "konten", "marketing", "jualan", "uang"}


def _kata_kunci(teks: str, batas: int = 12) -> list[str]:
    kata = re.findall(r"[a-zA-Z]{5,}", (teks or "").lower())
    unik: list[str] = []
    for k in kata:
        if k not in _STOPWORDS and k not in unik:
            unik.append(k)
        if len(unik) >= batas:
            break
    return unik


def _teks_dna(dna: BrandDNACard) -> str:
    return " ".join(
        [
            dna.misi or "",
            dna.positioning_statement or "",
            dna.diferensiasi or "",
            dna.kepribadian or "",
            " ".join(dna.nilai_inti or []),
        ]
    )


async def _pola_menang(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    """Pola (format, tujuan) yang menang 90 hari terakhir (untuk label DATA)."""
    dari = date.today() - timedelta(days=90)
    rows = (
        await db.execute(
            select(Content.format, Content.tujuan, func.count(ContentScore.id))
            .select_from(ContentScore)
            .join(Content, ContentScore.content_id == Content.id)
            .where(
                Content.brand_id == brand_id,
                ContentScore.status == ScoreStatus.MENANG,
                ContentScore.period_end >= dari,
            )
            .group_by(Content.format, Content.tujuan)
        )
    ).all()
    return [{"format": f, "tujuan": t, "n": int(n or 0)} for f, t, n in rows]


def _label_sumber(nama: str, alasan: str, monetisasi: str, pola_menang: list[dict]) -> str:
    gab = f"{nama} {alasan} {monetisasi}".lower()
    for p in pola_menang:
        if (p["format"] or "").lower() in gab or (p["tujuan"] or "").lower() in gab:
            return LabelSumber.DATA
    if re.search(r"\brp\b|\d+\s*(jt|juta|miliar|rb|ribu|x\s*lipat|%)", gab):
        return LabelSumber.KLAIM
    return LabelSumber.ESTIMASI


def _persaingan(kata: str) -> str:
    if kata.lower() in _KATA_GENERIK:
        return "tinggi"
    if " " in kata.strip() or len(kata) > 10:
        return "rendah"
    return "sedang"


def _angles(nama: str, audiens: str) -> list[str]:
    kw = nama.split(" untuk ")[0]
    aud = audiens if audiens and audiens != _BELUM else "audiens Anda"
    return [
        f"3 kesalahan {aud} dalam {kw}",
        f"Cara mulai {kw} dari nol (panduan pemula)",
        f"Studi kasus: {kw} yang berhasil",
        f"{kw} vs cara lama: mana yang lebih baik?",
        f"Panduan 7 hari menguasai {kw}",
        f"Mitos {kw} yang harus berhenti dipercaya",
        f"Tools gratis untuk {kw}",
        f"Cerita di balik {kw}: pengalaman nyata",
        f"Checklist {kw} untuk {aud}",
        f"Tanya jawab seputar {kw}",
    ]


def _bangun_kandidat(
    dna: BrandDNACard, kata_kunci: list[str], monetisasi: str, pola_menang: list[dict]
) -> list[dict]:
    teks = _teks_dna(dna).lower()
    kata_teks = set(re.findall(r"[a-z]+", teks))
    audiens = _BELUM
    m = re.search(r"membantu (.+?) mengatasi", (dna.misi or "").lower())
    if m:
        # Ambil maksimal 4 kata pertama agar nama niche tetap ringkas.
        audiens = " ".join(m.group(1).strip().split()[:4])

    pola_nama = [
        "Panduan {kw} untuk pemula",
        "{kw} untuk {aud}",
        "Studi kasus {kw}",
        "{kw} tanpa ribet",
        "Komunitas {kw}",
        "Bedah {kw} mingguan",
        "{kw} dari nol sampai cuan",
    ]
    kandidat: list[dict] = []
    dipakai: set[str] = set()
    i = 0
    while len(kandidat) < 7 and i < len(kata_kunci) + 3:
        kw = kata_kunci[i] if i < len(kata_kunci) else (kata_kunci[0] if kata_kunci else "strategi")
        nama = pola_nama[len(kandidat) % len(pola_nama)].format(kw=kw, aud=audiens)
        i += 1
        if nama.lower() in dipakai:
            continue
        dipakai.add(nama.lower())

        kunci_niche = {kw} | set(audiens.split())
        kunci_bersih = [k for k in kunci_niche if k]
        cocok = sum(1 for k in kunci_bersih if k.lower() in kata_teks)
        # Jujur & bervariasi: 35..88, bukan 95 semua.
        match = max(35, min(88, round(cocok / max(len(kunci_bersih), 1) * 100)))

        alasan = (
            f"Selaras dengan misi DNA ({(dna.misi or '')[:80]}...) dan diferensiasi "
            f"({(dna.diferensiasi or '')[:60]}...)."
        )
        kandidat.append(
            {
                "name": nama,
                "match_percent": match,
                "alasan": alasan,
                "angles": _angles(nama, audiens),
                "monetisasi": monetisasi,
                "persaingan": _persaingan(kw),
                "label_sumber": _label_sumber(nama, alasan, monetisasi, pola_menang),
            }
        )
    return kandidat[:7]


async def suggest_niches(
    db: AsyncSession, *, brand, organization_id: uuid.UUID, dna: BrandDNACard
) -> list[NicheSuggestion]:
    """Hasilkan 5-7 saran niche dari kartu DNA yang sudah dikonfirmasi."""
    if not dna.confirmed:
        raise ValueError("Konfirmasi dulu kartu DNA sebelum meminta saran niche.")

    wawancara = (
        await db.execute(
            select(NicheInterview)
            .where(
                NicheInterview.brand_id == brand.id,
                NicheInterview.status == InterviewStatus.SELESAI,
            )
            .order_by(NicheInterview.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    jawaban = {}
    if wawancara is not None:
        jawaban = {k: v for k, v in (wawancara.answers or {}).items() if k != "_followup"}
    monetisasi = (jawaban.get("monetisasi") or "").strip() or (
        "Mulai dari jasa/konsultasi, lalu kembangkan ke produk digital."
    )

    kata_kunci = _kata_kunci(_teks_dna(dna)) or ["strategi"]
    pola_menang = await _pola_menang(db, brand.id)
    kandidat = _bangun_kandidat(dna, kata_kunci, monetisasi, pola_menang)
    if len(kandidat) < 5:
        raise ValueError("Tidak cukup bahan dari DNA untuk menyusun saran niche.")

    # Narrative LLM sebagai bagian pipeline (tidak disimpan: model tidak punya kolomnya).
    await (await get_llm_provider_for_db(db)).narrate(
        "niche",
        {
            "brand_name": getattr(brand, "name", ""),
            "niches": [
                {"name": k["name"], "match_percent": k["match_percent"] / 100, "alasan": k["alasan"]}
                for k in kandidat
            ],
        },
    )

    hasil: list[NicheSuggestion] = []
    for k in kandidat:
        saran = NicheSuggestion(
            organization_id=organization_id,
            brand_id=brand.id,
            dna_version=dna.version,
            name=k["name"],
            match_percent=k["match_percent"],
            alasan=k["alasan"],
            angles=k["angles"],
            monetisasi=k["monetisasi"],
            persaingan=k["persaingan"],
            label_sumber=k["label_sumber"],
            is_selected=False,
        )
        db.add(saran)
        hasil.append(saran)
    await db.flush()
    return hasil


async def select_niches(
    db: AsyncSession, *, brand, organization_id: uuid.UUID, ids: list
) -> list[NicheSuggestion]:
    """Pilih 1-2 niche. Validasi milik brand; yang lain di-unselect."""
    if not (1 <= len(ids) <= 2):
        raise ValueError("Pilih 1-2 niche saja.")
    semua = (
        await db.execute(select(NicheSuggestion).where(NicheSuggestion.brand_id == brand.id))
    ).scalars().all()
    peta = {s.id: s for s in semua}
    for i in ids:
        if i not in peta:
            raise ValueError("Niche tidak ditemukan atau bukan milik brand ini.")
    dipilih = set(ids)
    for s in semua:
        s.is_selected = s.id in dipilih
    await db.flush()
    return [peta[i] for i in ids]
