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
from app.models.content import Content, ContentMetricsDaily, ContentScore
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
# Agregasi
# ---------------------------------------------------------------------------

_BULAN_SINGKAT = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
BASELINE_WER_IG = 0.05  # ambang batas bawah WER Instagram yang sehat


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

    # ---- 5. Skor akun 1-10 ----
    avg_wer = komposisi["rata_wer"]
    komponen = []
    # (a) Kualitas engagement — 30%
    nilai_wer = min(10.0, (avg_wer / (BASELINE_WER_IG * 1.5)) * 10) if avg_wer > 0 else 0.0
    komponen.append({
        "nama": "Kualitas engagement", "nilai": round(nilai_wer, 1), "bobot": 0.30,
        "penjelasan": (f"Rata-rata WER {avg_wer * 100:.1f}% vs baseline sehat "
                       f"{BASELINE_WER_IG * 100:.0f}% (skor penuh pada 1,5× baseline)."),
    })
    # (b) Volume & konsistensi — 20%
    hari = max((akhir - awal).days + 1, 1)
    posting_per_minggu = n / hari * 7
    nilai_vol = min(10.0, posting_per_minggu / 5 * 10)
    komponen.append({
        "nama": "Volume & konsistensi", "nilai": round(nilai_vol, 1), "bobot": 0.20,
        "penjelasan": f"{posting_per_minggu:.1f} postingan/minggu (skor penuh pada ≥5/minggu).",
    })
    # (c) Tren pertumbuhan views — 25%
    tren_nilai, tren_jelas = 5.0, "belum cukup data bulanan untuk tren"
    if len(bulan_urut) >= 2:
        ambil = bulan_urut[-4:]  # maks 3 perbandingan MoM
        views_bulan: dict[str, int] = defaultdict(int)
        for it in items:
            p = it["content"].posted_at
            if p:
                views_bulan[f"{p.year:04d}-{p.month:02d}"] += it["views"]
        deltas = []
        for i in range(1, len(ambil)):
            sblm, skrg = views_bulan.get(ambil[i - 1], 0), views_bulan.get(ambil[i], 0)
            if sblm > 0:
                deltas.append((skrg - sblm) / sblm)
        if deltas:
            rata_delta = sum(deltas) / len(deltas)
            tren_nilai = max(0.0, min(10.0, 5 + (rata_delta / 0.2) * 5))
            arah = "naik" if rata_delta >= 0 else "turun"
            tren_jelas = (f"Views {arah} rata-rata {abs(rata_delta) * 100:.1f}% per bulan "
                          f"({len(deltas)} perbandingan terakhir).")
    komponen.append({
        "nama": "Tren pertumbuhan", "nilai": round(tren_nilai, 1), "bobot": 0.25,
        "penjelasan": tren_jelas,
    })
    # (d) Proporsi konten kuat — 25%
    cids = [c.id for c in contents]
    kuat_nilai, kuat_jelas = 0.0, "belum ada konten yang diskor"
    if cids:
        skor_rows = (
            await db.execute(
                select(ContentScore).where(
                    ContentScore.content_id.in_(cids),
                    ContentScore.period_start <= akhir,
                    ContentScore.period_end >= awal,
                )
            )
        ).scalars().all()
        terbaru: dict = {}
        for s in skor_rows:
            lama = terbaru.get(s.content_id)
            if lama is None or (s.period_end, s.period_start) > (lama.period_end, lama.period_start):
                terbaru[s.content_id] = s
        if terbaru:
            kuat = sum(1 for s in terbaru.values() if s.status in ("menang", "cukup"))
            prop = kuat / len(terbaru)
            kuat_nilai = min(10.0, prop / 0.3 * 10)
            kuat_jelas = (f"{kuat} dari {len(terbaru)} konten yang diskor berstatus "
                          f"menang/cukup ({prop * 100:.0f}%; skor penuh pada ≥30%).")
    komponen.append({
        "nama": "Proporsi konten kuat", "nilai": round(kuat_nilai, 1), "bobot": 0.25,
        "penjelasan": kuat_jelas,
    })
    skor = round(sum(k["nilai"] * k["bobot"] for k in komponen), 1)
    skor = max(1.0, min(10.0, skor))  # skala 1–10, min 1 untuk akun yang punya data
    skor_akun = {
        "skor": skor, "grade": _grade_skor(skor), "komponen": komponen,
        "cara_hitung": ("Skor 1–10 gabungan empat komponen berbobot: kualitas engagement (30%), "
                        "volume & konsistensi (20%), tren pertumbuhan (25%), proporsi konten kuat (25%)."),
    }

    # ---- 6. Diagnosis kenapa stuck ----
    diagnosis: list[dict] = []
    if avg_wer < BASELINE_WER_IG * 0.5:
        diagnosis.append({
            "tingkat": "kritis", "judul": "Engagement per tayangan terlalu rendah",
            "detail": (f"Rata-rata WER {avg_wer * 100:.1f}% — kurang dari setengah baseline sehat "
                       f"{BASELINE_WER_IG * 100:.0f}%. Artinya konten ditonton tapi tidak memicu "
                       f"aksi (like, komen, save, share). Masalahnya di hook & CTA, bukan di jangkauan."),
        })
    elif avg_wer < BASELINE_WER_IG:
        diagnosis.append({
            "tingkat": "perhatian", "judul": "Engagement di bawah baseline",
            "detail": (f"Rata-rata WER {avg_wer * 100:.1f}% masih di bawah baseline "
                       f"{BASELINE_WER_IG * 100:.0f}%. Perlu penguatan CTA dan relevansi konten."),
        })
    else:
        diagnosis.append({
            "tingkat": "baik", "judul": "Engagement di atas baseline",
            "detail": f"Rata-rata WER {avg_wer * 100:.1f}% sudah melewati baseline. Pertahankan polanya.",
        })
    # Hitung delta MoM views untuk diagnosis.
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
        elif rata_mom < 0:
            diagnosis.append({
                "tingkat": "perhatian", "judul": "Jangkauan cenderung turun",
                "detail": f"Views turun rata-rata {abs(rata_mom) * 100:.1f}% per bulan. Waspadai sebelum makin dalam.",
            })
        else:
            diagnosis.append({
                "tingkat": "baik", "judul": "Jangkauan tumbuh",
                "detail": f"Views naik rata-rata {rata_mom * 100:.1f}% per bulan. Momentum positif.",
            })
    if kuat_jelas.startswith("0 dari") or "0 dari" in kuat_jelas:
        diagnosis.append({
            "tingkat": "kritis", "judul": "Belum ada pola winning yang lolos ambang",
            "detail": ("Tidak satu pun konten berstatus menang/cukup — semua di bawah ambang skor. "
                        "Akun belum menemukan formula yang terbukti bekerja; saran di bawah memakai "
                        "10% konten terbaik relatif sebagai acuan sementara."),
        })
    if posting_per_minggu < 2:
        diagnosis.append({
            "tingkat": "perhatian", "judul": "Frekuensi posting rendah",
            "detail": (f"Hanya {posting_per_minggu:.1f} postingan/minggu. Algoritma dan audiens butuh "
                        "keteraturan — targetkan minimal 3–5 postingan/minggu."),
        })

    # ---- 7. Saran berbasis pola winning (10% WER teratas, min 3 konten) ----
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
        saran.append({
            "judul": f"Perbanyak format {fmt_umum}",
            "detail": (f"{fmt_n} dari {len(top)} konten terbaik adalah {fmt_umum} "
                       f"(rata-rata WER {wer_fmt * 100:.1f}%). Jadikan format utama minggu ini."),
            "dasar": dasar,
        })
        cta_top = Counter(c for it in top for c in it["cta"] if c != CTA_TANPA)
        if cta_top:
            cta_umum, cta_n = cta_top.most_common(1)[0]
            saran.append({
                "judul": f"CTA '{CTA_LABELS[cta_umum]}' terbukti memicu aksi",
                "detail": (f"CTA ini muncul di {cta_n} dari {len(top)} konten terbaik. "
                           f"Terapkan pola kalimat CTA yang sama di konten berikutnya."),
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
            "judul": "Replikasi 3 konten terbaik ini",
            "detail": "Bedah dan tiru struktur hook, isi, dan CTA dari tiga konten dengan WER tertinggi.",
            "dasar": dasar, "contoh": contoh,
        })
    else:
        saran.append({
            "judul": "Kumpulkan data dulu",
            "detail": ("Belum ada konten dengan ≥500 views untuk dianalisis polanya. "
                        "Fokus dulu menaikkan jangkauan: perbaiki hook 3 detik pertama dan posting konsisten."),
            "dasar": "Data belum mencukupi.",
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
