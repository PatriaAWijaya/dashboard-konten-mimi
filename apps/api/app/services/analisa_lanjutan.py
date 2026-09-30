"""Analisa lanjutan: komposisi engagement, total per format, laporan detail
per bulan (dengan deteksi CTA & kategori dari caption), skor performa akun
1-10, diagnosis kenapa akun stuck, dan saran berbasis pola winning.

Deteksi CTA & kategori bersifat HEURISTIK berbasis kata kunci Bahasa
Indonesia pada caption — dilabeli jelas di respons agar tidak dikira
hasil klasifikasi manual.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.content import Content, ContentMetricsDaily
from app.services.scoring import compute_weighted_er

# ---------------------------------------------------------------------------
# Deteksi CTA dari caption (heuristik kata kunci, Bahasa Indonesia)
# ---------------------------------------------------------------------------

# Urutan = prioritas bila beberapa pola cocok.
CTA_PATTERNS: list[tuple[str, str, tuple[str, ...]]] = [
    ("konversi", "Donasi / Beli / Daftar", ("donasi", "berdonasi", "salurkan", "sedekah", "infak", "zakat", "wakaf", "beli", "order", "checkout", "daftar", "join sekarang", "s.id/")),
    ("link_bio", "Link di bio", ("link di bio", "link pada bio", "klik link", "link bio", "bit.ly")),
    ("komentar", "Komentar", ("komen", "komentar", "kolom komentar", "tulis di bawah", "jawab di kolom")),
    ("dm", "DM / Chat", ("dm ", " dm", "direct message", "chat admin", "hubungi kami", "hubungi admin", "whatsapp")),
    ("share", "Share / Tag", ("share", "bagikan", "kirim ke teman", "tag teman", "tandai teman")),
    ("simpan", "Simpan", ("save", "simpan", "simpan dulu")),
    ("follow", "Follow", ("follow", "ikuti kami", "follow us")),
    ("like", "Like", (" like", "like ", "suka postingan", "dobel ketuk", "double tap", "ketuk dua kali")),
]

CTA_LABELS = {k: label for k, label, _ in CTA_PATTERNS}
CTA_TANPA = "tanpa_cta"
CTA_LABELS[CTA_TANPA] = "Tanpa CTA jelas"


def deteksi_cta(caption: str | None) -> list[str]:
    """Kembalikan daftar kunci CTA yang terdeteksi dari caption (bisa >1)."""
    teks = f" {(caption or '').lower()} "
    hasil: list[str] = []
    for kunci, _label, pola_list in CTA_PATTERNS:
        for pola in pola_list:
            if pola in teks:
                hasil.append(kunci)
                break
    return hasil or [CTA_TANPA]


# ---------------------------------------------------------------------------
# Deteksi kategori post dari caption (heuristik kata kunci)
# ---------------------------------------------------------------------------

KATEGORI_PATTERNS: list[tuple[str, str, tuple[str, ...]]] = [
    ("donasi_sosial", "Donasi & Aksi Sosial", ("donasi", "bantu", "salurkan", "amanah", "zakat", "infak", "sedekah", "wakaf", "korban", "bencana", "gempa", "tanggap", "penyaluran", "tersalurkan")),
    ("edukasi", "Edukasi", ("tips", "cara ", "panduan", "tutorial", "fakta", "tahukah", "pelajari", "penjelasan", "mitos", "penyebab", "manfaat")),
    ("inspirasi", "Inspirasi", ("inspirasi", "motivasi", "kisah", "cerita", "healing", "semangat", "renungan", "hikmah", "pelajaran hidup")),
    ("promo", "Promo & Giveaway", ("promo", "diskon", "gratis", "giveaway", "lomba", "hadiah", "kuis berhadiah")),
    ("interaksi", "Interaksi", ("quiz", "kuis", "polling", "menurut kamu", "setuju", "pilih mana", "tim mana", "komen ")),
    ("info_program", "Info Program", ("program", "kegiatan", "acara", "jadwal", "pengumuman", "penerima manfaat", "laporan")),
    ("hiburan", "Hiburan", ("lucu", "ngakak", "meme", "hiburan", "parodi", "kocak")),
]

KATEGORI_LABELS = {k: label for k, label, _ in KATEGORI_PATTERNS}
KATEGORI_LAIN = "lainnya"
KATEGORI_LABELS[KATEGORI_LAIN] = "Lainnya"


def deteksi_kategori(caption: str | None) -> str:
    """Kembalikan satu kunci kategori (prioritas urutan pola)."""
    teks = f" {(caption or '').lower()} "
    for kunci, _label, pola_list in KATEGORI_PATTERNS:
        for pola in pola_list:
            if pola in teks:
                return kunci
    return KATEGORI_LAIN


# ---------------------------------------------------------------------------
# Pilar konten ala framework Strategi Instagram Organik
# Edukasi → memicu saves | Hiburan/Entertain → memicu shares |
# Interaksi → mengubah penonton pasif jadi audiens aktif
# ---------------------------------------------------------------------------
PILAR_DARI_KATEGORI = {
    "edukasi": "edukasi",
    "hiburan": "hiburan",
    "inspirasi": "hiburan",
    "interaksi": "interaksi",
    "donasi_sosial": "konversi",
    "promo": "konversi",
    "info_program": "konversi",
    "lainnya": "konversi",
}
PILAR_LABELS = {
    "edukasi": "Edukasi",
    "hiburan": "Hiburan",
    "interaksi": "Interaksi",
    "konversi": "Konversi",
}

# Ambang "uji 200 orang pertama" — algoritma menguji konten pada ±200
# penonton awal; yang gagal relate berhenti di sini ("200-view jail").
AMBANG_UJI_200 = 200


def _pilar_dari_item(it: dict) -> str:
    return PILAR_DARI_KATEGORI.get(it["kategori"], "konversi")

_BULAN_SINGKAT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def _label_bulan(tahun: int, bulan: int) -> str:
    return f"{_BULAN_SINGKAT[bulan - 1]} {tahun}"


def _bulan_sebelum(tahun: int, bulan: int, geser: int) -> tuple[int, int]:
    total = (tahun * 12 + (bulan - 1)) - geser
    return total // 12, total % 12 + 1


async def _agregat_per_konten(
    db: AsyncSession,
    contents: list[Content],
    organization_id: uuid.UUID,
    mulai: date,
    selesai: date,
) -> dict[uuid.UUID, dict]:
    """Agregasi ContentMetricsDaily per content_id dalam rentang tanggal."""
    if not contents:
        return {}
    by_id = {c.id: c for c in contents}
    rows = (
        await db.execute(
            select(
                ContentMetricsDaily.content_id,
                func.sum(ContentMetricsDaily.views).label("views"),
                func.sum(ContentMetricsDaily.reach).label("reach"),
                func.sum(ContentMetricsDaily.likes).label("likes"),
                func.sum(ContentMetricsDaily.comments).label("comments"),
                func.sum(ContentMetricsDaily.shares).label("shares"),
                func.sum(ContentMetricsDaily.saves).label("saves"),
                func.sum(ContentMetricsDaily.follows).label("follows"),
            )
            .where(
                ContentMetricsDaily.organization_id == organization_id,
                ContentMetricsDaily.content_id.in_(list(by_id.keys())),
                ContentMetricsDaily.date >= mulai,
                ContentMetricsDaily.date <= selesai,
            )
            .group_by(ContentMetricsDaily.content_id)
        )
    ).all()
    hasil: dict[uuid.UUID, dict] = {}
    for r in rows:
        c = by_id[r.content_id]
        views = int(r.views or 0)
        likes = int(r.likes or 0)
        comments = int(r.comments or 0)
        shares = int(r.shares or 0)
        saves = int(r.saves or 0)
        wer = compute_weighted_er(likes, comments, shares, saves, views)
        hasil[r.content_id] = {
            "content": c,
            "views": views,
            "reach": int(r.reach or 0),
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "saves": saves,
            "follows": int(r.follows or 0),
            "engagement": likes + comments + shares + saves,
            "wer": wer,
            "cta": deteksi_cta(c.caption),
            "kategori": deteksi_kategori(c.caption),
        }
    # Konten tanpa baris metrik tetap dicatat (nol).
    for c in contents:
        if c.id not in hasil:
            hasil[c.id] = {
                "content": c, "views": 0, "reach": 0, "likes": 0,
                "comments": 0, "shares": 0, "saves": 0, "follows": 0,
                "engagement": 0, "wer": 0.0,
                "cta": deteksi_cta(c.caption), "kategori": deteksi_kategori(c.caption),
            }
    return hasil


def _grade_skor(skor: float) -> str:
    if skor >= 8:
        return "Sangat baik"
    if skor >= 6.5:
        return "Baik"
    if skor >= 5:
        return "Cukup"
    if skor >= 3.5:
        return "Kurang"
    return "Kritis"


async def analisa_lanjutan(
    db: AsyncSession,
    *,
    brand: Brand,
    organization_id: uuid.UUID,
    awal: date,
    akhir: date,
    bulan: str | None = None,
    format_filter: str | None = None,
    kategori_filter: str | None = None,
    cta_filter: str | None = None,
) -> dict:
    """Bangun seluruh paket analisa lanjutan untuk satu brand & periode."""
    mulai_dt = datetime(awal.year, awal.month, awal.day, tzinfo=timezone.utc)
    akhir_dt = datetime(akhir.year, akhir.month, akhir.day, tzinfo=timezone.utc) + timedelta(days=1)
    contents = list(
        (
            await db.execute(
                select(Content).where(
                    Content.brand_id == brand.id,
                    Content.organization_id == organization_id,
                    Content.posted_at >= mulai_dt,
                    Content.posted_at < akhir_dt,
                )
            )
        )
        .scalars()
        .all()
    )
    if not contents:
        return {"kosong": True}

    ag = await _agregat_per_konten(db, contents, organization_id, awal, akhir)
    items = list(ag.values())
    n = len(items)

    # ---- 1. Komposisi engagement (seluruh periode) ----
    tot = defaultdict(int)
    for it in items:
        for k in ("views", "reach", "likes", "comments", "saves", "shares", "follows", "engagement"):
            tot[k] += it[k]
    komposisi = {
        **{k: tot[k] for k in ("views", "reach", "likes", "comments", "saves", "shares", "follows")},
        "total_engagement": tot["engagement"],
        "jumlah_konten": n,
        "rata_engagement_per_konten": round(tot["engagement"] / n, 1) if n else 0,
        "rata_wer": round(sum(it["wer"] for it in items) / n, 4) if n else 0,
    }

    # ---- 2. Total per format ----
    per_format: dict[str, dict] = {}
    for it in items:
        f = (it["content"].format or "lainnya").lower()
        d = per_format.setdefault(
            f, {"format": f, "jumlah": 0, "views": 0, "reach": 0, "likes": 0,
                "comments": 0, "saves": 0, "shares": 0, "follows": 0,
                "total_engagement": 0, "wer_sum": 0.0})
        d["jumlah"] += 1
        for k in ("views", "reach", "likes", "comments", "saves", "shares", "follows"):
            d[k] += it[k]
        d["total_engagement"] += it["engagement"]
        d["wer_sum"] += it["wer"]
    daftar_format = []
    for f in sorted(per_format):
        d = per_format[f]
        d["rata_wer"] = round(d["wer_sum"] / d["jumlah"], 4) if d["jumlah"] else 0
        del d["wer_sum"]
        daftar_format.append(d)

    # ---- 3. Opsi filter ----
    bulan_tersedia: dict[str, str] = {}
    for it in items:
        p = it["content"].posted_at
        if p:
            kunci = f"{p.year:04d}-{p.month:02d}"
            bulan_tersedia[kunci] = _label_bulan(p.year, p.month)
    bulan_urut = sorted(bulan_tersedia)
    if bulan and bulan not in bulan_tersedia:
        bulan = None
    bulan_aktif = bulan or (bulan_urut[-1] if bulan_urut else None)

    kat_terdeteksi = sorted({it["kategori"] for it in items})
    cta_terdeteksi = sorted({c for it in items for c in it["cta"]})
    filter_options = {
        "bulan": [{"value": b, "label": bulan_tersedia[b]} for b in bulan_urut],
        "format": sorted({(it["content"].format or "lainnya").lower() for it in items}),
        "kategori": [{"value": k, "label": KATEGORI_LABELS.get(k, k)} for k in kat_terdeteksi],
        "cta": [{"value": c, "label": CTA_LABELS.get(c, c)} for c in cta_terdeteksi],
        "heuristik": ("CTA & kategori terdeteksi otomatis dari kata kunci caption "
                      "(heuristik, bukan klasifikasi manual)."),
    }

    # ---- 4. Detail per bulan ----
    detail: list[dict] = []
    if bulan_aktif:
        th, bl = int(bulan_aktif[:4]), int(bulan_aktif[5:7])
        for it in items:
            c = it["content"]
            p = c.posted_at
            if not p or p.year != th or p.month != bl:
                continue
            fmt = (c.format or "lainnya").lower()
            if format_filter and fmt != format_filter:
                continue
            if kategori_filter and it["kategori"] != kategori_filter:
                continue
            if cta_filter and cta_filter not in it["cta"]:
                continue
            detail.append({
                "content_id": str(c.id),
                "post_id": c.post_id,
                "tanggal": p.date().isoformat(),
                "format": fmt,
                "caption": c.caption or "",
                "views": it["views"], "reach": it["reach"], "likes": it["likes"],
                "comments": it["comments"], "saves": it["saves"], "shares": it["shares"],
                "follows": it["follows"], "total_engagement": it["engagement"],
                "wer": round(it["wer"], 4),
                "cta": it["cta"],
                "cta_label": [CTA_LABELS.get(x, x) for x in it["cta"]],
                "kategori": it["kategori"],
                "kategori_label": KATEGORI_LABELS.get(it["kategori"], it["kategori"]),
            })
    detail.sort(key=lambda d: (-d["total_engagement"], d["tanggal"]))

    # ---- 5. Skor akun 1-10 (selaras framework Strategi Instagram Organik) ----
    # Bab 1 (algoritma = makcomblang): yang dinilai SINYAL engagement
    # (saves, shares, comments) bukan vanity metrics (views, likes).
    avg_wer = komposisi["rata_wer"]
    tot_views = tot["views"] or 1
    sinyal_rasio = (tot["saves"] * 5 + tot["shares"] * 5 + tot["comments"] * 3) / tot_views
    komponen = []
    nilai_sinyal = min(10.0, (sinyal_rasio / 0.05) * 10)
    komponen.append({
        "nama": "Sinyal engagement bermakna", "nilai": round(nilai_sinyal, 1), "bobot": 0.35,
        "penjelasan": (f"Saves, shares & comments = {sinyal_rasio * 100:.2f}% dari views "
                       f"(skor penuh pada 5%). Algoritma membaca sinyal ini, bukan likes/views "
                       f"(vanity metrics)."),
    })
    # Bab 1: lolos uji 200 orang pertama.
    lolos_200 = sum(1 for it in items if it["views"] >= AMBANG_UJI_200)
    prop_lolos = lolos_200 / n if n else 0
    nilai_200 = min(10.0, (prop_lolos / 0.9) * 10)
    komponen.append({
        "nama": "Lolos uji 200 penonton", "nilai": round(nilai_200, 1), "bobot": 0.25,
        "penjelasan": (f"{lolos_200} dari {n} konten ({prop_lolos * 100:.0f}%) lolos uji "
                       f"200 penonton pertama (skor penuh pada ≥90%). Sisanya terjebak "
                       f"'200-view jail' — hook 3 detik tidak memenangkan strangers."),
    })
    # Bab 4: keseimbangan 3 pilar (Edukasi/Hiburan/Interaksi) + peran format.
    pilar_count = Counter(_pilar_dari_item(it) for it in items)
    tiga_pilar = ["edukasi", "hiburan", "interaksi"]
    total_tiga = sum(pilar_count.get(p, 0) for p in tiga_pilar) or 1
    share_maks_pilar = max(pilar_count.get(p, 0) / total_tiga for p in tiga_pilar)
    nilai_pilar = max(0.0, 10.0 - max(0.0, (share_maks_pilar - 0.5) * 2) * 10)
    fmt_count = Counter((it["content"].format or "lainnya").lower() for it in items)
    punya_reels = fmt_count.get("reels", 0) > 0
    punya_carousel = fmt_count.get("carousel", 0) > 0
    nilai_format = 10.0 if (punya_reels and punya_carousel) else 6.0 if (punya_reels or punya_carousel) else 3.0
    nilai_pilar_format = round((nilai_pilar * 0.6 + nilai_format * 0.4), 1)
    pilar_str = ", ".join(f"{PILAR_LABELS[p]} {pilar_count.get(p, 0)}" for p in tiga_pilar)
    komponen.append({
        "nama": "Keseimbangan pilar & format", "nilai": nilai_pilar_format, "bobot": 0.20,
        "penjelasan": (f"Pilar: {pilar_str}. Reels = jangkauan audiens baru; "
                       f"Carousel = edukasi mendalam (saves). Skor penuh bila 3 pilar seimbang "
                       f"dan Reels + Carousel sama-sama dipakai."),
    })
    # Bab 5 & 7: kekuatan CTA + konsistensi (Continue & Consistence).
    ber_cta = sum(1 for it in items if any(c != CTA_TANPA for c in it["cta"]))
    prop_cta = ber_cta / n if n else 0
    nilai_cta = min(10.0, (prop_cta / 0.8) * 10)
    hari = max((akhir - awal).days + 1, 1)
    posting_per_minggu = n / hari * 7
    nilai_vol = min(10.0, posting_per_minggu / 5 * 10)
    nilai_cta_vol = round(nilai_cta * 0.5 + nilai_vol * 0.5, 1)
    komponen.append({
        "nama": "Kekuatan CTA & konsistensi", "nilai": nilai_cta_vol, "bobot": 0.20,
        "penjelasan": (f"{ber_cta} dari {n} konten ({prop_cta * 100:.0f}%) punya CTA jelas "
                       f"(target ≥80%); {posting_per_minggu:.1f} postingan/minggu "
                       f"(target ≥5/minggu — Continue & Consistence)."),
    })
    skor = round(sum(k["nilai"] * k["bobot"] for k in komponen), 1)
    skor = max(1.0, min(10.0, skor))  # skala 1–10, min 1 untuk akun yang punya data
    skor_akun = {
        "skor": skor, "grade": _grade_skor(skor), "komponen": komponen,
        "cara_hitung": ("Skor 1–10 ala framework Strategi Instagram Organik: sinyal engagement "
                        "bermakna — saves/shares/comments, bukan vanity metrics (35%), lolos uji "
                        "200 penonton pertama (25%), keseimbangan pilar & format (20%), "
                        "kekuatan CTA & konsistensi (20%)."),
    }

    # ---- 6. Diagnosis kenapa stuck (bahasa framework: Bab 1, 4, 5, 7) ----
    diagnosis: list[dict] = []
    terjebak_200 = n - lolos_200
    prop_terjebak = terjebak_200 / n if n else 0
    if prop_terjebak >= 0.3:
        diagnosis.append({
            "tingkat": "kritis", "judul": "Terjebak 200-view jail",
            "detail": (f"{terjebak_200} dari {n} konten ({prop_terjebak * 100:.0f}%) berhenti di "
                       f"bawah {AMBANG_UJI_200} views — tidak lolos uji 200 penonton pertama. "
                       f"Algoritma (makcomblang) menilai strangers tidak relate lalu menahan distribusi. "
                       f"Perbaiki hook 3 detik pertama (Stopping Power), bukan tambah jumlah posting."),
        })
    elif prop_terjebak > 0:
        diagnosis.append({
            "tingkat": "perhatian", "judul": "Sebagian konten gagal lolos uji 200",
            "detail": (f"{terjebak_200} dari {n} konten tidak lolos uji 200 penonton pertama. "
                       f"Bedah hook konten yang lolos vs yang gagal."),
        })
    else:
        diagnosis.append({
            "tingkat": "baik", "judul": "Semua konten lolos uji 200",
            "detail": "Tidak ada konten yang terjebak 200-view jail. Hook awal bekerja untuk strangers.",
        })
    # Jebakan vanity metrics: likes/views oke tapi sinyal bermakna rendah.
    if sinyal_rasio < 0.01:
        diagnosis.append({
            "tingkat": "kritis", "judul": "Jebakan vanity metrics",
            "detail": (f"Sinyal bermakna (saves/shares/comments) hanya {sinyal_rasio * 100:.2f}% dari views. "
                       f"Konten mungkin ditonton & di-like tapi tidak dianggap PENTING oleh algoritma — "
                       f"tidak disimpan, tidak dibagikan. Fokus ke konten yang memicu save (Edukasi) "
                       f"dan share (Hiburan), bukan sekadar views."),
        })
    elif sinyal_rasio < 0.03:
        diagnosis.append({
            "tingkat": "perhatian", "judul": "Sinyal engagement belum kuat",
            "detail": (f"Sinyal bermakna {sinyal_rasio * 100:.2f}% dari views — algoritma butuh sinyal "
                       f"lebih kuat (saves, shares, comments) untuk memperluas distribusi."),
        })
    # Blended fit score: kategori terlalu menyebar → algoritma bingung memilih sampel.
    kat_count = Counter(it["kategori"] for it in items)
    kat_teratas, kat_n = kat_count.most_common(1)[0]
    if kat_n / n < 0.4 and len(kat_count) >= 4:
        diagnosis.append({
            "tingkat": "perhatian", "judul": "Blended fit score — topik gado-gado",
            "detail": (f"Kategori teratas ({KATEGORI_LABELS.get(kat_teratas, kat_teratas)}) hanya "
                       f"{kat_n / n * 100:.0f}% dari konten, tersebar ke {len(kat_count)} kategori. "
                       f"Topik yang berubah-ubah membuat algoritma bingung memilih 200 sampel awal. "
                       f"Kunci 1 niche + 3–4 pilar pendukung (Creator DNA)."),
        })
    # Pilar timpang.
    if share_maks_pilar > 0.6:
        pilar_dom, _ = Counter({p: pilar_count.get(p, 0) for p in tiga_pilar}).most_common(1)[0]
        diagnosis.append({
            "tingkat": "perhatian", "judul": f"Pilar {PILAR_LABELS[pilar_dom]} terlalu dominan",
            "detail": (f"{share_maks_pilar * 100:.0f}% konten menumpuk di satu pilar. Sinyal algoritma "
                       f"jadi timpang: Edukasi memicu saves, Hiburan memicu shares, Interaksi mengaktifkan "
                       f"penonton pasif. Seimbangkan ketiganya."),
        })
    # CTA berfriksi: dominan link-di-bio / tanpa CTA.
    cta_count = Counter(c for it in items for c in it["cta"])
    tanpa_cta_n = cta_count.get(CTA_TANPA, 0)
    link_bio_n = cta_count.get("link_bio", 0)
    if tanpa_cta_n / n > 0.5:
        diagnosis.append({
            "tingkat": "perhatian", "judul": "Mayoritas konten tanpa CTA jelas",
            "detail": (f"{tanpa_cta_n} dari {n} konten tanpa ajakan bertindak yang terdeteksi. "
                       f"90–99% audiens adalah lurkers — tanpa mekanisme pemicu, mereka tidak akan "
                       f"bergerak. Tambahkan CTA spesifik di tiap konten."),
        })
    elif link_bio_n / n > 0.4:
        diagnosis.append({
            "tingkat": "perhatian", "judul": "CTA 'link di bio' terlalu dominan",
            "detail": (f"{link_bio_n} dari {n} konten memakai CTA link di bio — CTA berfriksi tinggi: "
                       f"penonton harus buka profil → klik link → cari produk, dan algoritma membaca "
                       f"mereka meninggalkan postingan. Uji DM automation (ketik kata kunci di komentar) "
                       f"yang menjaga penonton tetap di dalam aplikasi."),
        })
    # Konsistensi (Bab 7: Continue & Consistence).
    if posting_per_minggu < 3:
        diagnosis.append({
            "tingkat": "perhatian", "judul": "Konsistensi putus — sinyal melemah",
            "detail": (f"Hanya {posting_per_minggu:.1f} postingan/minggu. Algoritma menyukai "
                       f"publishing cadence yang konsisten; account embedding melemah saat jeda panjang. "
                       f"Targetkan 3–5 postingan/minggu dengan sistem batch production."),
        })
    # Tren MoM views (tetap dipertahankan sebagai konteks).
    mom_views: list[float] = []
    if len(bulan_urut) >= 2:
        vb: dict[str, int] = defaultdict(int)
        for it in items:
            p = it["content"].posted_at
            if p:
                vb[f"{p.year:04d}-{p.month:02d}"] += it["views"]
        for i in range(1, len(bulan_urut[-4:])):
            a = bulan_urut[-4:][i - 1]
            b_ = bulan_urut[-4:][i]
            if vb.get(a, 0) > 0:
                mom_views.append((vb[b_] - vb[a]) / vb[a])
    if mom_views:
        rata_mom = sum(mom_views) / len(mom_views)
        if rata_mom < -0.1:
            diagnosis.append({
                "tingkat": "kritis", "judul": "Jangkauan menurun konsisten",
                "detail": (f"Views turun rata-rata {abs(rata_mom) * 100:.1f}% per bulan dalam "
                           f"{len(mom_views)} bulan terakhir. Pola konten saat ini kehilangan daya tarik "
                           f"atau kalah bersaing di feed."),
            })
        elif rata_mom >= 0:
            diagnosis.append({
                "tingkat": "baik", "judul": "Jangkauan tumbuh",
                "detail": f"Views naik rata-rata {rata_mom * 100:.1f}% per bulan. Momentum positif — lanjutkan pola yang bekerja.",
            })

    # ---- 7. Saran berbasis pola winning + framework (3S Power, growth loop) ----
    layak = [it for it in items if it["views"] >= 500]
    layak.sort(key=lambda x: x["wer"], reverse=True)
    topn = max(3, int(len(layak) * 0.1))
    top = layak[:topn]
    saran: list[dict] = []
    dasar = f"Berdasarkan {len(top)} konten terbaik (10% WER teratas, min. 500 views)."
    if top:
        fmt_top = Counter((it["content"].format or "lainnya").lower() for it in top)
        fmt_umum, fmt_n = fmt_top.most_common(1)[0]
        wer_fmt = sum(it["wer"] for it in top if (it["content"].format or "lainnya").lower() == fmt_umum) / fmt_n
        peran_format = {"reels": "menjangkau audiens baru (watch time & shares)",
                        "carousel": "edukasi mendalam (saves & shares)",
                        "foto": "menjangkau audiens baru"}.get(fmt_umum, "menarik perhatian")
        saran.append({
            "judul": f"Perbanyak format {fmt_umum}",
            "detail": (f"{fmt_n} dari {len(top)} konten terbaik adalah {fmt_umum} "
                       f"(rata-rata WER {wer_fmt * 100:.1f}%). Peran format ini: {peran_format}. "
                       f"Jadikan format utama minggu ini."),
            "dasar": dasar,
        })
        cta_top = Counter(c for it in top for c in it["cta"] if c != CTA_TANPA)
        if cta_top:
            cta_umum, cta_n = cta_top.most_common(1)[0]
            saran.append({
                "judul": f"CTA '{CTA_LABELS[cta_umum]}' terbukti memicu aksi",
                "detail": (f"CTA ini muncul di {cta_n} dari {len(top)} konten terbaik. "
                           f"Terapkan pola kalimat CTA yang sama di konten berikutnya — "
                           f"90–99% audiens adalah lurkers yang butuh dipicu."),
                "dasar": dasar,
            })
        kat_top = Counter(it["kategori"] for it in top)
        kat_umum, kat_n = kat_top.most_common(1)[0]
        if kat_umum != KATEGORI_LAIN:
            saran.append({
                "judul": f"Kategori '{KATEGORI_LABELS[kat_umum]}' paling resonan",
                "detail": (f"{kat_n} dari {len(top)} konten terbaik berkategori ini. "
                           f"Naikkan porsinya dalam kalender konten."),
                "dasar": dasar,
            })
        jam_top = Counter(it["content"].posted_at.hour for it in top if it["content"].posted_at)
        if jam_top:
            jam_umum, jam_n = jam_top.most_common(1)[0]
            saran.append({
                "judul": f"Jam posting terbaik sekitar pukul {jam_umum:02d}.00",
                "detail": (f"{jam_n} dari {len(top)} konten terbaik diposting di jam ini "
                           f"(WIB, sesuai waktu posting). Uji jadwalkan konten penting di jam tersebut."),
                "dasar": dasar,
            })
        # Contoh konkret: 3 teratas
        contoh = []
        for it in top[:3]:
            cap = (it["content"].caption or "").replace("\n", " ").strip()
            contoh.append({
                "post_id": it["content"].post_id,
                "caption_singkat": cap[:120] + ("…" if len(cap) > 120 else ""),
                "wer": round(it["wer"] * 100, 1),
                "format": (it["content"].format or "lainnya").lower(),
            })
        saran.append({
            "judul": "Jalankan growth loop dari 3 konten terbaik ini",
            "detail": ("Ambil 1 konten terbaik → ubah jadi Carousel 5–7 slide (pemicu saves) → "
                        "buat Story Poll tentang topiknya (relationship depth) → kembangkan jadi "
                        "Signature Series. 1 ide terbukti dilipatgandakan, bukan cari ide baru dari nol."),
            "dasar": dasar, "contoh": contoh,
        })
    else:
        saran.append({
            "judul": "Kumpulkan data dulu",
            "detail": ("Belum ada konten dengan ≥500 views untuk dianalisis polanya. "
                        "Fokus dulu menaikkan jangkauan: menangkan 3 detik pertama (Stopping Power) "
                        "dan posting konsisten 3–5x/minggu."),
            "dasar": "Data belum mencukupi.",
        })
    # Saran framework yang dipicu kondisi (bukan hanya dari top konten).
    if prop_terjebak >= 0.3:
        saran.append({
            "judul": "Terapkan 3S Power untuk lolos 200-view jail",
            "detail": ("Stopping Power: hook visual + audio + teks di 3 detik pertama, semakin spesifik "
                       "masalah & keyword semakin jelas audiensnya. Striking Power: storytelling yang "
                       "membuat audiens merasa 'ini gue banget'. Sticking Power: selalu tutup dengan "
                       "konklusi + CTA agar audiens refresh dan mau bertindak."),
            "dasar": "Framework Strategi Instagram Organik — Bab 3 (Attract).",
        })
    if share_maks_pilar > 0.6:
        pilar_lemah = [p for p in tiga_pilar if pilar_count.get(p, 0) / n < 0.2]
        pilar_lemah_str = ", ".join(PILAR_LABELS[p] for p in pilar_lemah) or "pilar yang kurang"
        saran.append({
            "judul": f"Seimbangkan pilar: tambah porsi {pilar_lemah_str}",
            "detail": ("Edukasi mendorong saves (konten dianggap penting), Hiburan mendorong shares "
                       "(kedekatan emosional), Interaksi mengubah penonton pasif jadi aktif. Pilar yang "
                       "timpang = sinyal algoritma timpang."),
            "dasar": "Framework Strategi Instagram Organik — Bab 4 (Value).",
        })
    if link_bio_n / n > 0.4:
        saran.append({
            "judul": "Uji DM automation pengganti 'link di bio'",
            "detail": ("Minta audiens ketik kata kunci di komentar (mis. 'Ketik PANDUAN'), lalu kirim "
                       "materi/link via DM otomatis. Lonjakan komentar = sinyal kuat ke algoritma, "
                       "penonton tetap di dalam aplikasi, dan Anda membangun database kontak sendiri."),
            "dasar": "Framework Strategi Instagram Organik — Bab 5 (Engagement).",
        })
    saran.append({
        "judul": "Saring ide dengan 4 kriteria sebelum produksi",
        "detail": ("1) Relevan: memecahkan masalah nyata audiens? 2) Non-obvious: ada sudut pandang baru "
                   "yang bikin 'wah, baru tahu'? 3) Mudah dicerna: bisa dipahami anak 10 tahun? "
                   "4) Aplikatif: bisa dipraktikkan <5 menit untuk quick win?"),
        "dasar": "Framework Strategi Instagram Organik — Bab 6 (Konten yang Baik).",
    })

    return {
        "kosong": False,
        "komposisi": komposisi,
        "per_format": daftar_format,
        "filter_options": filter_options,
        "bulan_aktif": bulan_aktif,
        "detail_bulanan": detail,
        "skor_akun": skor_akun,
        "diagnosis": diagnosis,
        "saran": saran,
    }
