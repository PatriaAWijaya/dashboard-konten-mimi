"""Layanan Niche Finder: kuesioner 11 kartu -> laporan strategi 13 bagian + skor kekuatan niche.

Framework diadaptasi dari pola niche-generator (kuesioner kartu interaktif):
- 11 kartu: tujuan (bercabang) -> topik -> pengalaman+bukti -> target audiens
  -> dikenal untuk -> harapan perubahan -> kreator inspirasi -> kata persona
  -> platform -> pantangan -> audiens Inggris.
  (Kartu email & pembayaran dilewati: aplikasi ini membership-based, tanpa payment gate.)
- Laporan 13 bagian, template-based dari jawaban + data performa nyata brand
  (untuk tujuan pivot/tajamkan; untuk bikin_baru menjadi fondasi awal).
- Skor kekuatan niche: 5 dimensi, masing-masing 1-3, total -> grade A/B/C/D.

Dipakai dari model app.models.content (Worker Data):
- NicheInterview: status 'berjalan'/'selesai', current_step, answers (JSONB), skipped.

Narrative LLM untuk 'niche' tetap dipanggil sebagai bagian pipeline
(mock: gratis; hasilnya tidak disimpan, mengikuti pola sebelumnya).
"""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import (
    Content,
    ContentScore,
    InterviewStatus,
    NicheInterview,
    ScoreStatus,
)
from app.services.llm import get_llm_provider_for_db

MAX_FOLLOWUP = 2

# ---------------------------------------------------------------------------
# 11 kartu kuesioner
# ---------------------------------------------------------------------------
# tipe: pilihan_tunggal | pilihan_ganda | teks | teks_ganda | kreator | kata
# Bentuk jawaban tersimpan (answers[key]):
#   tujuan:            {"pilihan": "bikin_baru"}
#   topik:             {"utama": str, "side_2": str, "side_3": str}
#   pengalaman:        {"terpilih": [value], "bukti": {value: str}}
#   target_audiens:    {"teks": str}
#   dikenal_untuk:     {"teks": str}
#   harapan_perubahan: {"teks": str}
#   kreator_inspirasi: [{"username": str, "alasan": str}]
#   kata_persona:      [str]
#   platform:          {"terpilih": [value]}
#   pantangan:         {"teks": str}
#   audiens_inggris:   {"pilihan": "ya"|"tidak"}

QUESTIONS: list[dict] = [
    {
        "key": "tujuan",
        "nomor": 1,
        "tipe": "pilihan_tunggal",
        "pertanyaan": "Pilih 1 tujuan kamu",
        "subteks": "Tujuan menentukan arah seluruh rekomendasi di laporan.",
        "wajib": True,
        "alasan": "Akun baru butuh fondasi niche; akun lama butuh analisa data performa.",
        "opsi": [
            {
                "value": "bikin_baru",
                "judul": "Bikin akun baru",
                "deskripsi": "Temukan niche dari topik, pengalaman, dan orang yang paling ingin kamu bantu.",
            },
            {
                "value": "pivot",
                "judul": "Pivot atau re-branding",
                "deskripsi": "Analisa akunmu saat ini, lalu temukan arah niche baru yang paling sesuai.",
            },
            {
                "value": "tajamkan",
                "judul": "Tajamkan niche sekarang",
                "deskripsi": "Cari sub-niche, audiens, dan masalah paling kuat dari pola konten yang sudah terbukti.",
            },
        ],
    },
    {
        "key": "topik",
        "nomor": 2,
        "tipe": "teks_ganda",
        "pertanyaan": "Topik apa yang ingin kamu bahas di kontenmu?",
        "wajib": True,
        "alasan": "Satu topik utama yang tajam mengalahkan tiga topik yang tanggung.",
        "contoh": "Topik utama: strategi branding yayasan agar dilirik donatur.",
        "fields": [
            {
                "key": "utama",
                "label": "1 · Topik utama",
                "wajib": True,
                "placeholder": "mis. tips konten TikTok untuk UMKM pemula",
                "contoh": "",
            },
            {
                "key": "side_2",
                "label": "2 · Side topic",
                "wajib": False,
                "placeholder": "Topik pendukung (opsional)",
                "contoh": "",
            },
            {
                "key": "side_3",
                "label": "3 · Side topic",
                "wajib": False,
                "placeholder": "Topik pendukung lain (opsional)",
                "contoh": "",
            },
        ],
    },
    {
        "key": "pengalaman",
        "nomor": 3,
        "tipe": "pilihan_ganda",
        "pertanyaan": "Di topik yang kamu sebutkan, kamu punya pengalaman apa?",
        "subteks": "Pilih minimal 1. Setiap pilihan wajib disertai bukti singkat.",
        "wajib": True,
        "min_pilih": 1,
        "alasan": "Kredibilitas niche dibangun dari bukti nyata, bukan sekadar klaim.",
        "contoh": "Contoh bukti: Aku pernah bantu teman jualan lewat live dan ngerti tantangan UMKM pemula.",
        "label_bukti": "Ceritakan bukti singkat",
        "placeholder_bukti": "Pengalaman, contoh, hasil, atau kenapa ini nyambung dengan topikmu…",
        "opsi": [
            {
                "value": "pengalaman",
                "judul": "Pengalaman",
                "deskripsi": "Hal berat yang pernah kamu lewati, atau orang sering minta bantuanmu soal ini.",
            },
            {
                "value": "pencapaian",
                "judul": "Pencapaian",
                "deskripsi": "Hasil nyata yang pernah kamu raih di topik ini.",
            },
            {
                "value": "passion",
                "judul": "Passion / hobi",
                "deskripsi": "Hal yang terakhir kamu cari di TikTok/YouTube murni karena penasaran.",
            },
            {
                "value": "masalah",
                "judul": "Masalah / keresahan",
                "deskripsi": "Hal yang bikin kamu gemas kalau orang menjelaskannya dengan salah.",
            },
        ],
    },
    {
        "key": "target_audiens",
        "nomor": 4,
        "tipe": "teks",
        "pertanyaan": "Orang seperti apa yang ingin kamu targetkan?",
        "wajib": True,
        "alasan": "Konten yang bicara ke semua orang tidak didengar siapa pun.",
        "cara_menjawab": "Sebutkan ciri spesifik: profesi, usia, kondisi, atau komunitasnya.",
        "placeholder": "Contoh: fresh graduate yang baru masuk dunia kerja",
        "contoh": "Pengurus yayasan kecil di Jawa Timur, usia 30–45 tahun, pegang HP Android.",
    },
    {
        "key": "dikenal_untuk",
        "nomor": 5,
        "tipe": "teks",
        "pertanyaan": "Biasanya orang cari kamu untuk hal apa?",
        "subteks": "Atau: teman-teman ingat kamu jago di bidang apa?",
        "wajib": True,
        "alasan": "Reputasi yang sudah ada adalah modal niche yang paling murah.",
        "placeholder": "Contoh: dimintai tolong bikin desain presentasi yang rapi",
        "contoh": "Sering diminta jadi MC acara komunitas dan bikin rundown acara.",
    },
    {
        "key": "harapan_perubahan",
        "nomor": 6,
        "tipe": "teks",
        "pertanyaan": "Kalau orang follow kamu, perubahan apa yang kamu harapkan terjadi?",
        "subteks": "Opsional, tapi makin jelas harapanmu, makin tajam rekomendasinya.",
        "wajib": False,
        "alasan": "Niche yang kuat menjanjikan transformasi yang jelas bagi audiens.",
        "placeholder": "Contoh: jadi lebih pede tampil di depan kamera",
    },
    {
        "key": "kreator_inspirasi",
        "nomor": 7,
        "tipe": "kreator",
        "pertanyaan": "Sebutkan kreator atau akun yang jadi inspirasi kamu",
        "subteks": "Minimal 1, maksimal 3. Tulis username (tanpa @) dan kenapa kamu suka.",
        "wajib": True,
        "min_slot": 1,
        "maks_slot": 3,
        "alasan": "Gaya kreator favoritmu adalah petunjuk selera audiens yang ingin kamu tarik.",
        "contoh": "Hook-nya jelas, gaya ngomongnya santai, dan cara jualannya nggak maksa.",
        "placeholder_username": "username (tanpa @), mis. karyakreatifid",
        "placeholder_alasan": "Kenapa kamu suka gaya kontennya…",
    },
    {
        "key": "kata_persona",
        "nomor": 8,
        "tipe": "kata",
        "pertanyaan": "Kamu ingin dikenal sebagai orang yang seperti apa?",
        "subteks": "Tulis 1–3 kata sifat, satu kata per kotak. Minimal 1 kata.",
        "wajib": True,
        "min_kata": 1,
        "maks_kata": 3,
        "alasan": "Persona yang konsisten bikin audiens mudah mengingat dan merekomendasikanmu.",
        "contoh": "praktis, hangat, punya bukti",
    },
    {
        "key": "platform",
        "nomor": 9,
        "tipe": "pilihan_ganda",
        "pertanyaan": "Kamu bakal ngonten di platform apa?",
        "subteks": "Boleh pilih dua-duanya.",
        "wajib": True,
        "min_pilih": 1,
        "alasan": "Format dan gaya konten mengikuti kebiasaan tiap platform.",
        "opsi": [
            {
                "value": "instagram",
                "judul": "Instagram",
                "deskripsi": "Feed, Reels, Stories, bio.",
            },
            {
                "value": "tiktok",
                "judul": "TikTok",
                "deskripsi": "Short video, hooks, trends.",
            },
        ],
    },
    {
        "key": "pantangan",
        "nomor": 10,
        "tipe": "teks",
        "pertanyaan": "Apa hal yang kamu tidak mau ada dalam kontenmu?",
        "wajib": False,
        "alasan": "Batasan yang jelas menjaga konsistensi persona dan kepercayaan audiens.",
        "placeholder": "Misal: kata gue/lo, hard selling, flexing, kata kasar, muncul muka",
    },
    {
        "key": "audiens_inggris",
        "nomor": 11,
        "tipe": "pilihan_tunggal",
        "pertanyaan": "Mau sekalian jangkau audiens berbahasa Inggris (market global)?",
        "subteks": (
            "Opsional. Kalau iya, kami tambahkan referensi kreator global + ide konten "
            "bilingual sebagai pelengkap."
        ),
        "wajib": False,
        "alasan": "Yang works untuk audiens berbahasa Inggris belum tentu seefektif itu untuk audiens Indonesia.",
        "opsi": [
            {
                "value": "ya",
                "judul": "Iya, sekalian",
                "deskripsi": "Tambah referensi kreator global + ide konten bilingual.",
            },
            {
                "value": "tidak",
                "judul": "Nggak, fokus Indonesia dulu",
                "deskripsi": "Fokus penuh ke audiens Indonesia.",
            },
        ],
    },
]

_KEY_KE_KARTU = {q["key"]: q for q in QUESTIONS}
_TUJUAN_LABEL = {
    "bikin_baru": "Bikin akun baru",
    "pivot": "Pivot atau re-branding",
    "tajamkan": "Tajamkan niche sekarang",
}


# ---------------------------------------------------------------------------
# Validasi jawaban
# ---------------------------------------------------------------------------

# Key jawaban dari format wawancara lama (8 pertanyaan DNA) — dipakai untuk
# mendeteksi interview yang masih memakai skema lama di database produksi.
LEGACY_ANSWER_KEYS = frozenset(
    {"misi", "audiens", "nilai", "kepribadian", "keunggulan", "monetisasi", "batasan"}
)


def _is_legacy_schema(answers: Any) -> bool:
    return isinstance(answers, dict) and any(
        k in answers for k in LEGACY_ANSWER_KEYS
    )


def _str(x: Any) -> str:
    return (x or "").strip() if isinstance(x, str) else ""


def validasi_jawaban(kartu: dict, jawaban: Any) -> str | None:
    """Kembalikan pesan error bila jawaban tidak valid, atau None bila valid."""
    tipe = kartu["tipe"]
    wajib = kartu.get("wajib", False)
    kosong = jawaban is None or jawaban == {} or jawaban == [] or jawaban == ""

    if kosong:
        return None if not wajib else "Kartu ini wajib diisi."

    if tipe == "pilihan_tunggal":
        pilihan = jawaban.get("pilihan") if isinstance(jawaban, dict) else None
        nilai_valid = {o["value"] for o in kartu.get("opsi", [])}
        if not pilihan:
            return None if not wajib else "Pilih salah satu opsi."
        if pilihan not in nilai_valid:
            return "Pilihan tidak dikenal."
        return None

    if tipe == "pilihan_ganda":
        terpilih = jawaban.get("terpilih") if isinstance(jawaban, dict) else None
        terpilih = [t for t in (terpilih or []) if t]
        nilai_valid = {o["value"] for o in kartu.get("opsi", [])}
        min_pilih = int(kartu.get("min_pilih", 1))
        if not terpilih:
            return None if not wajib else f"Pilih minimal {min_pilih} opsi."
        if len(terpilih) < min_pilih:
            return f"Pilih minimal {min_pilih} opsi."
        if any(t not in nilai_valid for t in terpilih):
            return "Ada pilihan yang tidak dikenal."
        if kartu["key"] == "pengalaman":
            bukti = jawaban.get("bukti") if isinstance(jawaban, dict) else {}
            for t in terpilih:
                b = _str((bukti or {}).get(t))
                if len(b) < 10:
                    label = next(o["judul"] for o in kartu["opsi"] if o["value"] == t)
                    return f"Isi bukti singkat untuk '{label}' (minimal 10 karakter)."
        return None

    if tipe == "teks":
        teks = jawaban.get("teks") if isinstance(jawaban, dict) else (_str(jawaban))
        if not teks:
            return None if not wajib else "Jawaban tidak boleh kosong."
        return None

    if tipe == "teks_ganda":
        data = jawaban if isinstance(jawaban, dict) else {}
        for f in kartu.get("fields", []):
            nilai = _str(data.get(f["key"]))
            if f.get("wajib") and not nilai:
                return f"Isi '{f['label']}'."
        if wajib and not _str(data.get("utama")):
            return "Isi topik utama."
        return None

    if tipe == "kreator":
        daftar = jawaban if isinstance(jawaban, list) else []
        terisi = [s for s in daftar if isinstance(s, dict) and _str(s.get("username"))]
        min_slot = int(kartu.get("min_slot", 1))
        if len(terisi) < min_slot:
            return None if not wajib else f"Isi minimal {min_slot} kreator inspirasi."
        for s in terisi:
            if not re.match(r"^[A-Za-z0-9._]{1,30}$", _str(s.get("username"))):
                return f"Username '{s.get('username')}' tidak valid (tanpa @, huruf/angka/titik/underscore)."
        return None

    if tipe == "kata":
        daftar = [k.strip() for k in (jawaban if isinstance(jawaban, list) else []) if _str(k)]
        min_kata = int(kartu.get("min_kata", 1))
        if len(daftar) < min_kata:
            return None if not wajib else f"Tulis minimal {min_kata} kata."
        return None

    return f"Tipe kartu tidak dikenal: {tipe}."


def _normalisasi_jawaban(kartu: dict, jawaban: Any) -> Any:
    """Rapikan jawaban sebelum disimpan (buang slot/kata kosong)."""
    tipe = kartu["tipe"]
    if tipe == "kreator" and isinstance(jawaban, list):
        return [
            {"username": _str(s.get("username")), "alasan": _str(s.get("alasan"))}
            for s in jawaban
            if isinstance(s, dict) and _str(s.get("username"))
        ][: int(kartu.get("maks_slot", 3))]
    if tipe == "kata" and isinstance(jawaban, list):
        return [_str(k) for k in jawaban if _str(k)][: int(kartu.get("maks_kata", 3))]
    if tipe == "pilihan_ganda" and isinstance(jawaban, dict):
        terpilih = [t for t in (jawaban.get("terpilih") or []) if t]
        bukti = {
            t: _str(v)
            for t, v in ((jawaban.get("bukti") or {}).items())
            if t in terpilih and _str(v)
        }
        return {"terpilih": terpilih, "bukti": bukti}
    if tipe == "teks_ganda" and isinstance(jawaban, dict):
        return {f["key"]: _str(jawaban.get(f["key"])) for f in kartu.get("fields", [])}
    if tipe == "teks" and isinstance(jawaban, dict):
        return {"teks": _str(jawaban.get("teks"))}
    if tipe == "teks" and isinstance(jawaban, str):
        return {"teks": _str(jawaban)}
    if tipe == "pilihan_tunggal" and isinstance(jawaban, dict):
        return {"pilihan": _str(jawaban.get("pilihan"))}
    return jawaban


# ---------------------------------------------------------------------------
# Follow-up (elaborasi jawaban teks yang terlalu pendek)
# ---------------------------------------------------------------------------

def needs_followup(teks: str) -> bool:
    """True bila jawaban teks terlalu pendek/tidak konkret dan perlu elaborasi."""
    t = (teks or "").strip()
    if len(t) < 20:
        return True
    kata = t.split()
    if len(kata) < 3:
        return True
    if all(len(k) <= 4 for k in kata):
        return True
    return False


def _followup_count(answers: dict, key: str) -> int:
    return int((answers.get("_followup") or {}).get(key, 0) or 0)


def _teks_untuk_followup(kartu: dict, jawaban: Any) -> str:
    if kartu["tipe"] == "teks":
        return _str(jawaban.get("teks")) if isinstance(jawaban, dict) else _str(jawaban)
    if kartu["tipe"] == "teks_ganda":
        return _str(jawaban.get("utama")) if isinstance(jawaban, dict) else ""
    return ""


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
        if _is_legacy_schema(existing.answers):
            # Interview lama masih memakai format 8 pertanyaan DNA yang sudah
            # dihapus — reset otomatis ke format 11 kartu yang baru.
            await reset_interview(db, interview=existing)
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


async def reset_interview(db: AsyncSession, *, interview: NicheInterview) -> NicheInterview:
    """Mulai ulang wawancara dari kartu pertama (jawaban lama dibuang)."""
    interview.status = InterviewStatus.BERJALAN
    interview.current_step = 0
    interview.answers = {}
    interview.skipped = []
    await db.flush()
    return interview


async def save_answer(
    db: AsyncSession,
    *,
    interview: NicheInterview,
    step: int,
    jawaban: Any,
    dilewati: bool,
) -> dict:
    """Simpan jawaban langkah `step` (jawaban terstruktur sesuai tipe kartu).

    Return {"status": "ok"|"butuh_elaborasi", "next_step": int}.
    """
    if not (0 <= step < len(QUESTIONS)):
        raise ValueError(f"Langkah tidak valid: {step}. Rentang 0-{len(QUESTIONS) - 1}.")
    if step != interview.current_step:
        raise ValueError(
            f"Jawaban harus untuk kartu ke-{interview.current_step + 1} "
            f"(saat ini diminta kartu ke-{step + 1})."
        )
    kartu = QUESTIONS[step]
    key = kartu["key"]
    answers = dict(interview.answers or {})
    daftar_lewati = list(interview.skipped or [])

    if dilewati:
        if kartu.get("wajib"):
            raise ValueError("Kartu ini wajib diisi dan tidak bisa dilewati.")
        if key not in daftar_lewati:
            daftar_lewati.append(key)
        answers.pop(key, None)
        interview.skipped = daftar_lewati
        interview.answers = answers
        interview.current_step = step + 1
    else:
        error = validasi_jawaban(kartu, jawaban)
        if error:
            raise ValueError(error)
        bersih = _normalisasi_jawaban(kartu, jawaban)
        teks = _teks_untuk_followup(kartu, bersih)
        if (
            teks
            and kartu.get("wajib")
            and kartu["tipe"] in ("teks", "teks_ganda")
            and needs_followup(teks)
            and _followup_count(answers, key) < MAX_FOLLOWUP
        ):
            follow = dict(answers.get("_followup") or {})
            follow[key] = _followup_count(answers, key) + 1
            answers["_followup"] = follow
            answers[key] = bersih  # simpan draf
            interview.answers = answers
            await db.flush()
            return {"status": "butuh_elaborasi", "next_step": step}
        answers[key] = bersih
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
# Skor kekuatan niche (5 dimensi x/3 -> grade)
# ---------------------------------------------------------------------------

_STOPWORDS_SKOR = {
    "yang", "dan", "untuk", "dengan", "dari", "ini", "itu", "adalah", "saya",
    "kami", "anda", "para", "sebuah", "dalam", "pada", "agar", "supaya",
    "karena", "sebagai", "tidak", "bisa", "dapat", "akan", "telah", "sudah",
    "lebih", "sangat", "cara", "membuat", "menjadi", "kepada", "oleh",
    "juga", "atau", "bagi", "tentang", "ingin", "ingin", "supaya",
}

_PENANDA_SPESIFIK = {
    "tahun", "umkm", "yayasan", "pemilik", "founder", "ibu", "bapak",
    "mahasiswa", "pelajar", "karyawan", "fresh", "graduate", "pemula",
    "jakarta", "surabaya", "bandung", "medan", "jawa", "kalimantan",
    "sulawesi", "sumatera", "bali", "kota", "desa", "online", "muslim",
    "muslimah", "gen", "milenial", "genz", "komunitas", "pelaku",
    "pengusaha", "freelance", "konten", "kreator", "affiliate", "reseller",
    "dropship", "kuliner", "fashion", "skincare", "kecantikan", "kesehatan",
    "keuangan", "investasi", "saham", "kripto", "properti",
}


def _kata_kunci_skor(teks: str) -> set[str]:
    return {
        k for k in re.findall(r"[a-zA-Z]{5,}", (teks or "").lower())
        if k not in _STOPWORDS_SKOR
    }


def _teks_jawaban(answers: dict, key: str) -> str:
    v = answers.get(key)
    if isinstance(v, dict):
        return _str(v.get("teks"))
    return _str(v)


def skor_kekuatan_niche(answers: dict) -> dict:
    """Nilai 5 dimensi (1-3 tiap dimensi) -> total & grade A/B/C/D.

    Aturan jujur dari kelengkapan jawaban: jawaban kosong/tipis tidak bisa
    dapat skor tinggi.
    """
    dimensi: list[dict] = []

    # 1. Spesifik — seberapa tajam target audiens.
    aud = _teks_jawaban(answers, "target_audiens")
    kata_aud = aud.split()
    n_penanda = sum(1 for p in _PENANDA_SPESIFIK if p in aud.lower())
    if re.search(r"\d", aud):
        n_penanda += 1
    if len(kata_aud) >= 6 and n_penanda >= 2:
        s, als = 3, "Target audiens spesifik: detail + penanda jelas (profesi/usia/angka)."
    elif len(kata_aud) >= 4 or n_penanda >= 1:
        s, als = 2, "Target audiens cukup jelas, tapi bisa dipertajam lagi."
    else:
        s, als = 1, "Target audiens masih terlalu umum atau belum diisi."
    dimensi.append({"key": "spesifik", "label": "Spesifik", "skor": s, "maksimal": 3, "alasan": als})

    # 2. Kredibilitas — bukti pengalaman.
    peng = answers.get("pengalaman") if isinstance(answers.get("pengalaman"), dict) else {}
    terpilih = peng.get("terpilih") or []
    bukti = peng.get("bukti") or {}
    bukti_ok = [t for t in terpilih if len(_str(bukti.get(t))) >= 30]
    bukti_cukup = [t for t in terpilih if len(_str(bukti.get(t))) >= 20]
    if len(bukti_ok) >= 2:
        s, als = 3, "Punya 2+ bukti pengalaman yang konkret dan detail."
    elif len(bukti_cukup) >= 1:
        s, als = 2, "Ada bukti pengalaman, tapi bisa diperkuat dengan angka/hasil."
    else:
        s, als = 1, "Bukti pengalaman masih tipis — kredibilitas perlu dibangun."
    dimensi.append({"key": "kredibilitas", "label": "Kredibilitas", "skor": s, "maksimal": 3, "alasan": als})

    # 3. Cocok pasar — keselarasan topik utama dengan reputasi yang sudah ada.
    topik = answers.get("topik") if isinstance(answers.get("topik"), dict) else {}
    utama = _str(topik.get("utama"))
    dikenal = _teks_jawaban(answers, "dikenal_untuk")
    irisan = _kata_kunci_skor(utama) & _kata_kunci_skor(dikenal)
    if len(irisan) >= 3:
        s, als = 3, "Topik selaras kuat dengan reputasi yang sudah dikenal orang."
    elif len(irisan) >= 1:
        s, als = 2, "Topik dan reputasi cukup nyambung."
    else:
        s, als = 1, "Topik dan reputasi belum terlihat nyambung — butuh jembatan narasi."
    dimensi.append({"key": "cocok_pasar", "label": "Cocok pasar", "skor": s, "maksimal": 3, "alasan": als})

    # 4. Pembeda — keunikan persona + pengalaman.
    kata = [_str(k) for k in (answers.get("kata_persona") or []) if _str(k)]
    unik = len({k.lower() for k in kata})
    if unik >= 2 and any(t in ("pencapaian", "pengalaman") for t in terpilih):
        s, als = 3, "Persona jelas dan didukung pengalaman/pencapaian yang membedakan."
    elif unik >= 1:
        s, als = 2, "Ada persona, tapi pembeda dari kreator lain belum tajam."
    else:
        s, als = 1, "Persona belum terdefinisi — sulit dibedakan dari kreator lain."
    dimensi.append({"key": "pembeda", "label": "Pembeda", "skor": s, "maksimal": 3, "alasan": als})

    # 5. Tahan lama — motivasi jangka panjang.
    harapan = _teks_jawaban(answers, "harapan_perubahan")
    ada_harapan = len(harapan) >= 20
    ada_passion = "passion" in terpilih
    if ada_harapan and ada_passion:
        s, als = 3, "Motivasi jelas + topik yang dinikmati — fondasi konsistensi kuat."
    elif ada_harapan or ada_passion:
        s, als = 2, "Ada motivasi atau passion, tapi belum keduanya."
    else:
        s, als = 1, "Motivasi jangka panjang belum jelas — rawan berhenti di tengah jalan."
    dimensi.append({"key": "tahan_lama", "label": "Tahan lama", "skor": s, "maksimal": 3, "alasan": als})

    total = sum(d["skor"] for d in dimensi)
    grade = "A" if total >= 13 else "B" if total >= 10 else "C" if total >= 7 else "D"
    ringkasan = {
        "A": "Niche sangat kuat — siap dieksekusi agresif.",
        "B": "Niche kuat dengan sedikit catatan perbaikan.",
        "C": "Niche cukup — pertajam 1-2 dimensi terlemah dulu.",
        "D": "Niche masih lemah — lengkapi jawaban dan ulangi kuesioner.",
    }[grade]
    return {
        "dimensi": dimensi,
        "total": total,
        "maksimal": 15,
        "grade": grade,
        "ringkasan": ringkasan,
    }


# ---------------------------------------------------------------------------
# Data performa brand (untuk tujuan pivot/tajamkan)
# ---------------------------------------------------------------------------

async def _ringkasan_performa(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Ringkasan performa 90 hari terakhir dari ContentScore (label DATA)."""
    dari = date.today() - timedelta(days=90)
    total = await db.scalar(
        select(func.count(ContentScore.id))
        .select_from(ContentScore)
        .join(Content, ContentScore.content_id == Content.id)
        .where(Content.brand_id == brand_id, ContentScore.period_end >= dari)
    )
    menang = await db.scalar(
        select(func.count(ContentScore.id))
        .select_from(ContentScore)
        .join(Content, ContentScore.content_id == Content.id)
        .where(
            Content.brand_id == brand_id,
            ContentScore.status == ScoreStatus.MENANG,
            ContentScore.period_end >= dari,
        )
    )
    pola_rows = (
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
            .order_by(func.count(ContentScore.id).desc())
            .limit(5)
        )
    ).all()
    pola = [
        {"format": f or "-", "tujuan": t or "-", "jumlah_menang": int(n or 0)}
        for f, t, n in pola_rows
    ]
    return {
        "total_konten": int(total or 0),
        "konten_menang": int(menang or 0),
        "pola_menang": pola,
        "ada_data": bool(total),
    }


# ---------------------------------------------------------------------------
# Laporan 13 bagian
# ---------------------------------------------------------------------------

_BELUM = "[belum diisi]"


def _ambil_teks(answers: dict, key: str) -> str:
    return _teks_jawaban(answers, key) or _BELUM


def _tujuan(answers: dict) -> str:
    t = answers.get("tujuan")
    pilihan = t.get("pilihan") if isinstance(t, dict) else None
    return pilihan if pilihan in _TUJUAN_LABEL else "bikin_baru"


def _topik_utama(answers: dict) -> str:
    t = answers.get("topik") if isinstance(answers.get("topik"), dict) else {}
    return _str(t.get("utama")) or _BELUM


def _side_topics(answers: dict) -> list[str]:
    t = answers.get("topik") if isinstance(answers.get("topik"), dict) else {}
    return [_str(t.get("side_2")), _str(t.get("side_3"))]


def _platforms(answers: dict) -> list[str]:
    p = answers.get("platform") if isinstance(answers.get("platform"), dict) else {}
    label = {"instagram": "Instagram", "tiktok": "TikTok"}
    return [label[x] for x in (p.get("terpilih") or []) if x in label]


def _kreator_usernames(answers: dict) -> list[str]:
    daftar = answers.get("kreator_inspirasi") or []
    return [_str(s.get("username")) for s in daftar if isinstance(s, dict) and _str(s.get("username"))]


def _niche_oneliner(answers: dict) -> str:
    return f"{_topik_utama(answers)} untuk {_ambil_teks(answers, 'target_audiens')}"


def _bagian_ringkasan(answers: dict, skor: dict) -> dict:
    terjawab = sum(1 for q in QUESTIONS if answers.get(q["key"]))
    return {
        "judul": "Ringkasan",
        "niche_utama": _niche_oneliner(answers),
        "grade": skor["grade"],
        "total_skor": skor["total"],
        "kalimat": (
            f"Berdasarkan {terjawab} dari {len(QUESTIONS)} kartu yang terisi, "
            f"niche kamu terumuskan sebagai: {_niche_oneliner(answers)}. "
            f"Kekuatan niche: {skor['total']}/15 (grade {skor['grade']}) — {skor['ringkasan']}"
        ),
        "disclaimer": (
            "Laporan ini disusun dari jawaban kuesionermu dan "
            "(bila relevan) data performa brand-mu. Ini panduan strategi, "
            "bukan jaminan hasil — eksekusi dan konsistensi tetap menentukan."
        ),
    }


def _bagian_temuan_akun(answers: dict, performa: dict | None) -> dict:
    tujuan = _tujuan(answers)
    if performa and performa.get("ada_data"):
        pola = performa["pola_menang"]
        narasi = (
            f"Dalam 90 hari terakhir ada {performa['total_konten']} konten dinilai, "
            f"{performa['konten_menang']} di antaranya berstatus menang. "
        )
        if pola:
            p0 = pola[0]
            narasi += (
                f"Pola paling menang: format {p0['format']} untuk tujuan {p0['tujuan']} "
                f"({p0['jumlah_menang']} konten menang)."
            )
        else:
            narasi += "Belum ada pola menang yang konsisten — ini justru alasan kuat untuk pivot/tajamkan."
        return {
            "judul": "Temuan akun",
            "mode": "data",
            "sumber": "DATA",
            "total_konten": performa["total_konten"],
            "konten_menang": performa["konten_menang"],
            "pola_menang": pola,
            "narasi": narasi,
            "yang_dihentikan": (
                "Format/tujuan yang tidak pernah menang dalam 90 hari layak dikurangi "
                "porsinya atau dihentikan sementara."
            ),
        }
    if tujuan == "bikin_baru":
        narasi = (
            "Kamu memilih bikin akun baru, jadi bagian ini adalah fondasi awal — "
            "belum ada data performa. Setelah 30 hari konsisten posting, kembali ke "
            "Niche Finder dengan tujuan 'Tajamkan niche' agar rekomendasi memakai data nyatamu."
        )
    else:
        narasi = (
            "Belum ada data performa yang cukup untuk dianalisa "
            "(butuh minimal beberapa konten yang sudah dinilai). "
            "Sementara itu, fondasi di bawah disusun dari jawaban kuesionermu."
        )
    return {
        "judul": "Temuan akun",
        "mode": "fondasi",
        "sumber": "ESTIMASI",
        "narasi": narasi,
        "yang_dilacak": [
            "Format konten (Reels/carousel/foto) vs engagement rate",
            "Topik mana yang paling sering menang",
            "Jam posting vs performa",
        ],
    }


def _bagian_pengemasan(answers: dict) -> dict:
    kreator = answers.get("kreator_inspirasi") or []
    inspirasi = "; ".join(
        f"@{_str(s.get('username'))} ({_str(s.get('alasan'))[:60]})"
        for s in kreator
        if isinstance(s, dict) and _str(s.get("username"))
    ) or _BELUM
    kata = [_str(k) for k in (answers.get("kata_persona") or []) if _str(k)]
    persona = ", ".join(kata) if kata else _BELUM
    pantangan = _teks_jawaban(answers, "pantangan")
    platforms = _platforms(answers)
    return {
        "judul": "Pengemasan konten",
        "hook": [
            "Buka dengan masalah audiens, bukan dengan perkenalan diri.",
            f"Pakai sudut pandang persona kamu: {persona}.",
            "3 detik pertama menentukan — tulis hook dulu sebelum isi.",
        ],
        "cta": [
            "Akhiri dengan 1 ajakan jelas: simpan, komen, atau follow.",
            "CTA yang selaras dengan harapan perubahanmu bekerja paling baik.",
        ],
        "optimasi": [
            f"Platform fokus: {', '.join(platforms) if platforms else _BELUM}.",
            "Konsisten format 30 hari sebelum menilai — jangan ganti gaya tiap minggu.",
            "Pelajari pola hook kreator inspirasimu, tiru strukturnya bukan isinya.",
        ],
        "inspirasi_gaya": inspirasi,
        "pantangan": pantangan if pantangan else "Belum ditentukan — tetapkan agar persona konsisten.",
    }


def _bagian_target_market(answers: dict) -> dict:
    masalah = _teks_jawaban(answers, "dikenal_untuk")
    masalah_txt = (
        f"Mereka butuh bantuan soal: {masalah}."
        if masalah
        else "Masalah spesifik mereka belum terpetakan — gali dari komentar/DM."
    )
    tujuan_mereka = _teks_jawaban(answers, "harapan_perubahan") or (
        "Belum dirumuskan — tentukan transformasi yang kamu janjikan."
    )
    return {
        "judul": "Target market",
        "kalimat_niche": _niche_oneliner(answers),
        "siapa": _ambil_teks(answers, "target_audiens"),
        "masalah_mereka": masalah_txt,
        "tujuan_mereka": tujuan_mereka,
    }


def _bagian_positioning(answers: dict) -> dict:
    kata = [_str(k) for k in (answers.get("kata_persona") or []) if _str(k)]
    while len(kata) < 3:
        kata.append(["tulus", "konsisten", "berani"][len(kata) % 3])
    kata = kata[:3]
    peng = answers.get("pengalaman") if isinstance(answers.get("pengalaman"), dict) else {}
    bukti = peng.get("bukti") or {}
    pembeda_txt = _str(next(iter(bukti.values()), "")) or _teks_jawaban(answers, "dikenal_untuk")
    if not pembeda_txt:
        pembeda_txt = "pengalaman dan sudut pandang personalmu"
    risiko_map = [
        "Terlalu generik bila tidak didukung bukti konkret di konten.",
        "Bisa terasa menggurui bila nada tidak dijaga tetap hangat.",
        "Butuh konsistensi lama sebelum audiens benar-benar percaya.",
    ]
    opsi = []
    for i, k in enumerate(kata):
        opsi.append(
            {
                "nama": f"Si {k.title()}",
                "deskripsi": (
                    f"Dikenal sebagai sosok yang {k} dalam membahas "
                    f"{_topik_utama(answers)} untuk {_ambil_teks(answers, 'target_audiens')}."
                ),
                "pembeda": f"Pembeda kamu: {pembeda_txt[:120]}",
                "risiko": risiko_map[i % len(risiko_map)],
            }
        )
    return {"judul": "Positioning", "opsi": opsi}


def _bagian_strategi_transisi(answers: dict) -> dict:
    tujuan = _tujuan(answers)
    if tujuan == "pivot":
        return {
            "judul": "Strategi transisi",
            "nama": "Refocus bertahap",
            "kenapa_cocok": "Audiens lama butuh waktu beradaptasi — pivot mendadak bikin unfollow massal.",
            "cara_jalan": [
                "Minggu 1-2: campur 50% konten lama + 50% arah baru sebagai 'jembatan'.",
                "Minggu 3-4: naikkan porsi arah baru ke 70%, umumkan perubahan positioning.",
                "Bulan ke-2: full arah baru; arsipkan konten lama yang tidak relevan.",
            ],
            "yang_perlu_diwaspadai": [
                "Penurunan engagement sementara itu normal — jangan panik dan balik arah.",
                "Sampaikan alasan pivot secara jujur ke audiens setia.",
            ],
        }
    if tujuan == "tajamkan":
        return {
            "judul": "Strategi transisi",
            "nama": "Pertajam yang sudah jalan",
            "kenapa_cocok": "Kamu sudah punya pola yang terbukti — tugasnya memfokuskan, bukan mengulang dari nol.",
            "cara_jalan": [
                "Petakan 3-5 konten dengan performa terbaik 90 hari terakhir.",
                "Cari benang merahnya: topik, format, dan hook yang berulang.",
                "Naikkan porsi pola winning jadi 60% dari jadwal posting.",
                "Sisakan 25% untuk eksperimen sub-niche baru.",
            ],
            "yang_perlu_diwaspadai": [
                "Jangan tajamkan sampai terlalu sempit hingga kehabisan ide.",
                "Eksperimen tetap perlu — algoritma dan selera berubah.",
            ],
        }
    return {
        "judul": "Strategi transisi",
        "nama": "Fondasi dari nol",
        "kenapa_cocok": "Akun baru menang lewat kejelasan, bukan lewat kuantitas.",
        "cara_jalan": [
            "Tetapkan 1 topik utama dan posting hanya seputar itu selama 30 hari.",
            "Bangun 9-12 konten fondasi (jawaban atas pertanyaan paling umum audiens).",
            "Optimasi bio sebelum posting pertama — profil adalah landing page-mu.",
        ],
        "yang_perlu_diwaspadai": [
            "Jangan ganti niche sebelum 30 hari konsisten — data belum cukup.",
            "Hindari ikut semua tren; tren hanya bumbu, bukan menu utama.",
        ],
    }


def _bagian_pilar(answers: dict) -> dict:
    tujuan = _tujuan(answers)
    utama = _topik_utama(answers)
    side = [s for s in _side_topics(answers) if s]
    side_txt = " & ".join(side) if side else "topik pendukung pilihanmu"
    if tujuan == "pivot":
        fase, mix = "Fase Transisi", [
            {"nama": f"Arah baru: {utama}", "porsi": 40, "keterangan": "Konten positioning baru."},
            {"nama": "Konten jembatan", "porsi": 30, "keterangan": "Menghubungkan topik lama ke arah baru."},
            {"nama": "Pola yang sudah terbukti", "porsi": 30, "keterangan": "Format/topik lama yang masih menang."},
        ]
    elif tujuan == "tajamkan":
        fase, mix = "Fase B · Bangun Identitas", [
            {"nama": f"Pola winning: {utama}", "porsi": 60, "keterangan": "Perbanyak yang terbukti berhasil."},
            {"nama": "Eksperimen sub-niche", "porsi": 25, "keterangan": f"Coba angle baru di sekitar {side_txt}."},
            {"nama": "Personal / behind the scenes", "porsi": 15, "keterangan": "Bangun kedekatan personal."},
        ]
    else:
        fase, mix = "Fase A · Validasi Awal", [
            {"nama": f"Topik utama: {utama}", "porsi": 50, "keterangan": "Fondasi niche — jawaban atas masalah audiens."},
            {"nama": f"Topik luas: {side_txt}", "porsi": 20, "keterangan": "Jangkau audiens baru yang beririsan."},
            {"nama": "Personal life", "porsi": 30, "keterangan": "Cerita personal agar audiens merasa dekat."},
        ]
    return {"judul": "Pilar konten", "fase": fase, "mix": mix}


def _bagian_ide(answers: dict) -> dict:
    utama = _topik_utama(answers)
    aud = _ambil_teks(answers, "target_audiens")
    kata = [_str(k) for k in (answers.get("kata_persona") or []) if _str(k)]
    persona = kata[0] if kata else "autentik"
    platforms = _platforms(answers)
    fmt = "Reels/TikTok 30 detik" if platforms else "Video pendek 30 detik"
    inggris = answers.get("audiens_inggris")
    bilingual = isinstance(inggris, dict) and inggris.get("pilihan") == "ya"
    ide = [
        {
            "judul": f"3 kesalahan {aud} soal {utama}",
            "hook": f"Stop lakukan ini kalau kamu {aud}…",
            "format": fmt,
            "cta": "Simpan buat dibaca ulang besok pagi.",
            "tips": f"Sampaikan dengan gaya {persona}; satu kesalahan satu contoh nyata.",
        },
        {
            "judul": f"Cara mulai {utama} dari nol",
            "hook": f"Panduan {utama} buat pemula — tanpa ribet.",
            "format": fmt,
            "cta": "Follow biar nggak ketinggalan part 2.",
            "tips": "Pecah jadi 3 part agar audiens menantikan lanjutan.",
        },
        {
            "judul": f"Mitos {utama} yang harus berhenti dipercaya",
            "hook": f"Jangan percaya mitos {utama} ini…",
            "format": fmt,
            "cta": "Komen 'setuju' kalau kamu pernah kena mitos ini.",
            "tips": "Mitos memancing debat sehat = engagement naik.",
        },
        {
            "judul": f"Studi kasus nyata: {utama}",
            "hook": "Ini yang terjadi waktu aku coba…",
            "format": fmt,
            "cta": "Share ke teman yang butuh ini.",
            "tips": "Pakai bukti dari kartu pengalamanmu agar kredibel.",
        },
        {
            "judul": f"Checklist {utama} untuk {aud}",
            "hook": f"Checklist wajib sebelum kamu mulai {utama}.",
            "format": "Carousel / thread",
            "cta": "Simpan checklist ini.",
            "tips": "Konten checklist paling sering disimpan — bagus untuk reach.",
        },
        {
            "judul": f"Tanya jawab seputar {utama}",
            "hook": f"Pertanyaan yang paling sering masuk soal {utama}…",
            "format": fmt,
            "cta": "Tulis pertanyaanmu di komen buat dibahas next.",
            "tips": "Ambil pertanyaan dari DM/komentar asli audiensmu.",
        },
    ]
    if bilingual:
        ide.append(
            {
                "judul": f"{utama} — versi bilingual",
                "hook": "Same tips, in English — buat audiens global.",
                "format": fmt,
                "cta": "Share to your English-speaking friends.",
                "tips": "Subtitle Inggris cukup; tidak perlu dubbing ulang.",
            }
        )
    return {"judul": "Ide siap posting", "ide": ide[:7]}


def _bagian_bio(answers: dict) -> dict:
    utama = _topik_utama(answers)
    aud = _ambil_teks(answers, "target_audiens")
    dikenal = _teks_jawaban(answers, "dikenal_untuk")
    kredibilitas = dikenal if dikenal else "berbagi dari pengalaman nyata"
    harapan = _teks_jawaban(answers, "harapan_perubahan")
    cta = f"Bantu kamu {harapan}" if harapan else "Follow untuk tips rutin"
    opsi = [
        {
            "nama": "Bio A · To the point",
            "baris": [
                f"Bantu {aud}",
                f" Lewat {utama}",
                "👇 Mulai dari sini",
            ],
            "nada": "Langsung, jelas, tanpa basa-basi.",
        },
        {
            "nama": "Bio B · Kredibilitas dulu",
            "baris": [
                f"{kredibilitas[:60]}",
                f"Fokus: {utama}",
                "👇 Konten baru tiap hari",
            ],
            "nada": "Membangun trust lewat bukti.",
        },
        {
            "nama": "Bio C · Ajakan personal",
            "baris": [
                f"Cerita & strategi {utama}",
                f"Buat {aud}",
                f"👇 {cta[:60]}",
            ],
            "nada": "Hangat dan personal.",
        },
    ]
    return {
        "judul": "Opsi bio",
        "catatan": "Struktur bio yang baik: A = value proposition, B = kredibilitas, C = call to action.",
        "opsi": opsi,
    }


def _bagian_swot(answers: dict, skor: dict) -> dict:
    peng = answers.get("pengalaman") if isinstance(answers.get("pengalaman"), dict) else {}
    label_peng = {
        "pengalaman": "pengalaman", "pencapaian": "pencapaian",
        "passion": "passion", "masalah": "kepekaan masalah",
    }
    kekuatan = [
        f"Punya {label_peng.get(t, t)} di topik ini" for t in (peng.get("terpilih") or [])
    ] or ["Belum teridentifikasi — gali lagi pengalamanmu."]
    kelemahan = []
    for d in skor["dimensi"]:
        if d["skor"] <= 1:
            kelemahan.append(f"Dimensi '{d['label']}' lemah: {d['alasan']}")
    if not kelemahan:
        kelemahan = ["Belum ada kelemahan menonjol dari jawaban."]
    inggris = answers.get("audiens_inggris")
    peluang = ["Audiens Indonesia yang haus konten praktis dan jujur."]
    if isinstance(inggris, dict) and inggris.get("pilihan") == "ya":
        peluang.append("Market global berbahasa Inggris sebagai kanal pertumbuhan kedua.")
    if _tujuan(answers) == "pivot":
        peluang.append("Data performa lama bisa dipakai untuk validasi arah baru.")
    ancaman = [
        "Kreator se-topik dengan modal dan tim lebih besar.",
        "Perubahan algoritma platform.",
        "Kehabisan ide bila tidak punya sistem bank ide.",
    ]
    return {
        "judul": "SWOT",
        "kekuatan": kekuatan,
        "kelemahan": kelemahan,
        "peluang": peluang,
        "ancaman": ancaman,
    }


def _bagian_minggu_pertama(answers: dict) -> dict:
    utama = _topik_utama(answers)
    return {
        "judul": "Minggu pertama",
        "aksi": [
            {
                "judul": "Pasang bio baru",
                "detail": "Pilih salah satu dari 3 opsi bio di laporan ini dan pasang hari ini juga.",
                "level": "Gampang",
            },
            {
                "judul": f"Posting 3 konten pilar '{utama}'",
                "detail": "Ambil 3 ide dari daftar ide siap posting. Satu format, satu gaya — jangan ganti-ganti dulu.",
                "level": "Sedang",
            },
            {
                "judul": "Riset 5 kreator se-niche",
                "detail": "Catat 3 hook terbaik dari tiap kreator inspirasimu. Tiru strukturnya, bukan isinya.",
                "level": "Gampang",
            },
        ],
    }


def _bagian_kesimpulan(answers: dict, skor: dict) -> dict:
    tujuan = _tujuan(answers)
    arah = {
        "bikin_baru": "Fokus 30 hari pertama: validasi 1 topik utama dengan posting konsisten.",
        "pivot": "Fokus 30 hari pertama: transisi bertahap 50/50 lalu naikkan porsi arah baru.",
        "tajamkan": "Fokus 30 hari pertama: perbanyak pola winning hingga 60% jadwal posting.",
    }[tujuan]
    return {
        "judul": "Kesimpulan",
        "niche": _niche_oneliner(answers),
        "grade": f"{skor['grade']} ({skor['total']}/15)",
        "arah_selanjutnya": arah,
        "langkah_pertama": "Pasang bio baru hari ini, lalu posting konten pertama dari daftar ide siap posting.",
    }


async def generate_laporan(
    db: AsyncSession, *, interview: NicheInterview, brand, organization_id: uuid.UUID
) -> dict:
    """Susun laporan strategi niche 13 bagian dari jawaban kuesioner.

    Template-based dari kata user + data performa nyata (untuk pivot/tajamkan).
    """
    if interview.status != InterviewStatus.SELESAI:
        raise ValueError(
            "Kuesioner belum selesai. Jawab semua 11 kartu terlebih dahulu."
        )
    answers = {k: v for k, v in (interview.answers or {}).items() if k != "_followup"}
    dilewati = list(interview.skipped or [])
    tujuan = _tujuan(answers)

    # Narrative LLM sebagai bagian pipeline (hasilnya tidak disimpan,
    # mengikuti pola synthesize_dna/suggest_niches sebelumnya).
    await (await get_llm_provider_for_db(db)).narrate(
        "niche",
        {
            "brand_name": getattr(brand, "name", ""),
            "tujuan": tujuan,
            "jawaban": answers,
            "dilewati": dilewati,
            "terjawab": len(answers),
            "total": len(QUESTIONS),
        },
    )

    skor = skor_kekuatan_niche(answers)
    performa = (
        await _ringkasan_performa(db, brand.id)
        if tujuan in ("pivot", "tajamkan")
        else None
    )

    swot = _bagian_swot(answers, skor)
    if dilewati:
        label_lewat = [_KEY_KE_KARTU[k]["pertanyaan"] for k in dilewati if k in _KEY_KE_KARTU]
        if label_lewat:
            swot["kelemahan"].append(
                "Kartu yang dilewati: " + "; ".join(label_lewat) + ". Mengisinya menajamkan laporan."
            )

    bagian = {
        "ringkasan": _bagian_ringkasan(answers, skor),
        "temuan_akun": _bagian_temuan_akun(answers, performa),
        "pengemasan_konten": _bagian_pengemasan(answers),
        "target_market": _bagian_target_market(answers),
        "positioning": _bagian_positioning(answers),
        "strategi_transisi": _bagian_strategi_transisi(answers),
        "pilar_konten": _bagian_pilar(answers),
        "ide_siap_posting": _bagian_ide(answers),
        "opsi_bio": _bagian_bio(answers),
        "kekuatan_niche": {
            "judul": "Kekuatan niche",
            "dimensi": skor["dimensi"],
            "total": skor["total"],
            "maksimal": skor["maksimal"],
            "grade": skor["grade"],
            "ringkasan": skor["ringkasan"],
        },
        "swot": swot,
        "minggu_pertama": _bagian_minggu_pertama(answers),
        "kesimpulan": _bagian_kesimpulan(answers, skor),
    }

    return {
        "tujuan": tujuan,
        "tujuan_label": _TUJUAN_LABEL[tujuan],
        "dibuat_pada": date.today().isoformat(),
        "brand": {"id": str(getattr(brand, "id", "")), "nama": getattr(brand, "name", "")},
        "kartu_terjawab": len(answers),
        "kartu_total": len(QUESTIONS),
        "kartu_dilewati": dilewati,
        "bagian": bagian,
        "skor": skor,
    }
