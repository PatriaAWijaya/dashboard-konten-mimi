"""Penilaian kesesuaian format×tujuan konten (rule-based, tanpa LLM)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.content import Content, ContentMetricsDaily, ContentScore
from app.services.scoring import BASE_RATES, compute_weighted_er

# Baseline absolut untuk metrik yang bukan rate.
ABSOLUTE_BASELINES = {
    "views": 10_000,
    "reach": 10_000,
    "likes": 200,
    "comments": 50,
    "shares": 30,
    "saves": 100,
    "avg_watch_seconds": 15.0,
    "replies": 20,
    "sticker_taps": 30,
    "link_clicks": 50,
}

METRIC_LABELS = {
    "save_rate": "save rate",
    "share_rate": "share rate",
    "comment_rate": "comment rate",
    "er": "engagement rate",
    "views": "views",
    "reach": "reach",
    "likes": "likes",
    "comments": "komentar",
    "shares": "share",
    "saves": "saves",
    "avg_watch_seconds": "rata-rata durasi tonton (detik)",
    "replies": "balasan story",
    "sticker_taps": "ketukan stiker",
    "link_clicks": "klik link",
}

# (format, tujuan) → metrik utama yang menentukan keberhasilan pola tersebut.
SUITABILITY_MATRIX: dict[tuple[str, str], dict] = {
    ("carousel", "edukasi"): {
        "metrik_utama": ["save_rate", "share_rate"],
        "deskripsi": "Carousel edukasi berhasil bila orang menyimpan untuk dibaca ulang dan membagikannya.",
    },
    ("reels", "hiburan"): {
        "metrik_utama": ["views", "avg_watch_seconds", "share_rate"],
        "deskripsi": "Reels hiburan berhasil bila ditonton banyak orang sampai habis dan dibagikan.",
    },
    ("reels", "edukasi"): {
        "metrik_utama": ["save_rate", "share_rate"],
        "deskripsi": "Reels edukasi berhasil bila insight-nya disimpan dan disebar.",
    },
    ("story", "interaksi"): {
        "metrik_utama": ["replies", "sticker_taps", "link_clicks"],
        "deskripsi": "Story interaksi berhasil bila memicu balasan, ketukan stiker, dan klik.",
    },
    ("foto", "jualan"): {
        "metrik_utama": ["link_clicks", "saves"],
        "deskripsi": "Foto jualan berhasil bila mengantar klik ke link dan disimpan sebagai referensi beli.",
    },
    ("foto", "branding"): {
        "metrik_utama": ["reach", "likes"],
        "deskripsi": "Foto branding berhasil bila menjangkau banyak orang dan disukai.",
    },
    ("live", "interaksi"): {
        "metrik_utama": ["comments", "shares"],
        "deskripsi": "Live interaksi berhasil bila kolom komentar ramai dan siaran dibagikan.",
    },
    ("carousel", "jualan"): {
        "metrik_utama": ["link_clicks", "saves"],
        "deskripsi": "Carousel jualan berhasil bila mengantar klik dan disimpan sebagai bahan pertimbangan.",
    },
    ("reels", "jualan"): {
        "metrik_utama": ["link_clicks", "saves"],
        "deskripsi": "Reels jualan berhasil bila mengantar klik ke link dan disimpan calon pembeli.",
    },
}

DEFAULT_ENTRY = {
    "metrik_utama": ["er", "comment_rate", "share_rate"],
    "deskripsi": (
        "Kombinasi format×tujuan ini belum punya aturan khusus, "
        "jadi dinilai dari engagement berbobot secara umum."
    ),
}

SUGGESTION_TEMPLATES = {
    "save_rate": "Tambahkan CTA 'simpan postingan ini' dan pastikan ada insight yang layak disimpan (checklist, template, atau langkah praktis).",
    "share_rate": "Buat konten yang membuat orang ingin menandai temannya, misalnya dengan ajakan 'tag teman yang butuh info ini'.",
    "comment_rate": "Tutup caption dengan satu pertanyaan terbuka yang mudah dijawab audiens.",
    "er": "Perkuat 3 detik pertama (hook) supaya interaksi naik sebelum orang scroll lewat.",
    "views": "Perbaiki hook dan cover/thumbnail, lalu posting di jam audiens paling aktif.",
    "reach": "Dorong share ke story dan jajal kolaborasi agar jangkauan meluas.",
    "likes": "Minta like secara eksplisit di caption untuk konten yang memang disukai audiens.",
    "comments": "Pancing diskusi dengan pertanyaan yang mengundang pendapat berbeda secara sehat.",
    "shares": "Buat konten yang mewakili identitas audiens sehingga mereka bangga membagikannya.",
    "saves": "Sisipkan konten 'simpan untuk nanti': daftar, rumus, atau template siap pakai.",
    "avg_watch_seconds": "Padatkan durasi, potong bagian yang lambat, dan gunakan teks on-screen agar penonton bertahan.",
    "replies": "Gunakan stiker pertanyaan/polling di story dan balas respons audiens dengan cepat.",
    "sticker_taps": "Tempatkan stiker interaktif di awal story, bukan di akhir.",
    "link_clicks": "Perjelas ajakan klik, pastikan link berfungsi, dan tawarkan alasan kuat untuk mengklik.",
}


def _baseline_for(metric: str) -> float:
    if metric in BASE_RATES:
        return float(BASE_RATES[metric])
    return float(ABSOLUTE_BASELINES.get(metric, 1.0))


def evaluate_suitability(agg: dict) -> dict:
    """Nilai kesesuaian pola format×tujuan dari metrik agregat satu konten.

    agg: format, tujuan, save_rate, share_rate, comment_rate, er,
        views, reach, likes, comments, shares, saves, avg_watch_seconds,
        replies, sticker_taps, link_clicks.
    """
    fmt = str(agg.get("format") or "")
    tujuan = str(agg.get("tujuan") or "")
    entry = SUITABILITY_MATRIX.get((fmt, tujuan), DEFAULT_ENTRY)

    detail: list[dict] = []
    for metric in entry["metrik_utama"]:
        value = float(agg.get(metric) or 0)
        baseline = _baseline_for(metric)
        rasio = value / baseline if baseline > 0 else 0.0
        detail.append(
            {
                "metrik": metric,
                "label": METRIC_LABELS.get(metric, metric),
                "nilai": round(value, 4),
                "baseline": baseline,
                "rasio": round(rasio, 3),
                "lolos": rasio >= 1.0,
            }
        )

    n = len(detail)
    lolos_count = sum(1 for d in detail if d["lolos"])
    fraksi = lolos_count / n if n else 0.0
    if fraksi >= 2 / 3:
        verdict = "sesuai"
    elif fraksi > 0:
        verdict = "kurang_sesuai"
    else:
        verdict = "tidak_sesuai"

    diagnoses: list[dict] = []
    suggestions: list[str] = []
    for d in detail:
        if d["lolos"]:
            continue
        diagnoses.append(
            {
                "metrik": d["metrik"],
                "nilai": d["nilai"],
                "harapan": d["baseline"],
                "masalah": (
                    f"{d['label']} ({d['nilai']}) di bawah baseline ({d['baseline']}) "
                    f"untuk pola {fmt}×{tujuan}."
                ),
            }
        )
        saran = SUGGESTION_TEMPLATES.get(d["metrik"])
        if saran and saran not in suggestions:
            suggestions.append(saran)

    return {
        "format": fmt,
        "tujuan": tujuan,
        "verdict": verdict,
        "deskripsi": entry["deskripsi"],
        "metrik_utama": detail,
        "diagnoses": diagnoses,
        "suggestions": suggestions,
    }


def _rates_from_snapshot(snapshot: dict) -> dict:
    """Bangun dict agg (termasuk rates) dari metrics_snapshot ContentScore."""
    views = float(snapshot.get("views") or 0)
    agg = dict(snapshot)
    if views > 0:
        agg["save_rate"] = float(snapshot.get("saves") or 0) / views
        agg["share_rate"] = float(snapshot.get("shares") or 0) / views
        agg["comment_rate"] = float(snapshot.get("comments") or 0) / views
        agg["er"] = compute_weighted_er(
            float(snapshot.get("likes") or 0),
            float(snapshot.get("comments") or 0),
            float(snapshot.get("shares") or 0),
            float(snapshot.get("saves") or 0),
            views,
        )
    else:
        agg["save_rate"] = agg["share_rate"] = agg["comment_rate"] = agg["er"] = 0.0
    return agg


def cek_kesehatan_framework(c: Content, snapshot: dict) -> tuple[list[dict], list[str]]:
    """Cek kesehatan satu konten berdasarkan framework Strategi Instagram Organik.

    Konten dianggap "tidak sehat" (di bawah standar framework) bila:
    1. Gagal uji 200 penonton (views < 200) — terjebak "200-view jail"
       (Framework Bab 1: Initial Sample Test Group).
    2. Engagement format-spesifik di bawah 10% dari views:
       - Carousel: saves < 10% dari views (Carousel = mesin saves untuk edukasi)
       - Reels: (shares + comments) < 10% dari views (Reels = jangkauan & interaksi)
       - Image/Foto: (comments + shares) < 10% dari views
       (Framework Bab 1: Watchtime Velocity & Signals 2026 — saves, shares,
       comments adalah sinyal bermakna, bukan likes/vanity metrics).

    Returns: (diagnoses, suggestions) — list diagnosis & saran berbasis framework.
    """
    diagnoses: list[dict] = []
    suggestions: list[str] = []

    views = float(snapshot.get("views") or 0)
    comments = float(snapshot.get("comments") or 0)
    shares = float(snapshot.get("shares") or 0)
    saves = float(snapshot.get("saves") or 0)
    fmt = (c.format or "").lower()

    # 1. Uji 200 penonton.
    if views < 200:
        diagnoses.append(
            {
                "metrik": "views",
                "nilai": int(views),
                "harapan": 200,
                "masalah": (
                    f"Views ({int(views)}) di bawah 200 — konten terjebak di '200-view jail'. "
                    "Algoritma menguji "
                    "konten ke ~200 orang pertama (mayoritas non-follower); bila mereka langsung "
                    "swipe away, distribusi dihentikan."
                ),
            }
        )
        saran_hook = (
            "Perkuat Stopping Power: buat hook visual + audio + teks yang spesifik di 3 detik "
            "pertama — semakin spesifik masalah & keyword, semakin jelas algoritma mengenali "
            "audiensnya."
        )
        if saran_hook not in suggestions:
            suggestions.append(saran_hook)
        # Sudah pasti bermasalah — tidak perlu cek rasio engagement.
        return diagnoses, suggestions

    # 2. Engagement format-spesifik minimal 10% dari views.
    if fmt == "carousel":
        rasio = saves / views if views > 0 else 0
        if rasio < 0.10:
            diagnoses.append(
                {
                    "metrik": "saves",
                    "nilai": f"{int(saves)} ({rasio*100:.1f}% dari views)",
                    "harapan": "≥10% dari views",
                    "masalah": (
                        f"Carousel ini hanya menghasilkan saves {rasio*100:.1f}% dari views "
                        f"({int(saves)} saves dari {int(views)} views), di bawah standar 10%. "
                        "Carousel adalah mesin saves untuk edukasi mendalam — "
                        "bila saves rendah, konten tidak dianggap bernilai untuk disimpan."
                    ),
                }
            )
            saran = (
                "Perkuat nilai simpan Carousel: akhiri dengan ringkasan/checklist yang layak "
                "di-screenshot, tambahkan CTA spesifik 'Simpan postingan ini'."
            )
            if saran not in suggestions:
                suggestions.append(saran)
    elif fmt == "reels":
        bermakna = shares + comments
        rasio = bermakna / views if views > 0 else 0
        if rasio < 0.10:
            diagnoses.append(
                {
                    "metrik": "shares+comments",
                    "nilai": f"{int(bermakna)} ({rasio*100:.1f}% dari views)",
                    "harapan": "≥10% dari views",
                    "masalah": (
                        f"Reels ini hanya menghasilkan shares+comments {rasio*100:.1f}% dari views "
                        f"({int(bermakna)} dari {int(views)} views), di bawah standar 10%. "
                        "Reels adalah mesin jangkauan audiens baru — bila "
                        "shares & comments rendah, algoritma tidak mendapat sinyal relevansi "
                        "untuk distribusi lebih luas."
                    ),
                }
            )
            saran = (
                "Dorong shares & comments di Reels: ajukan pertanyaan yang memancing opini di "
                "caption, tambahkan CTA 'Tag teman yang perlu tahu ini' atau 'Ketik pendapatmu "
                "di komentar'."
            )
            if saran not in suggestions:
                suggestions.append(saran)
    elif fmt in ("foto", "image", "gambar"):
        bermakna = comments + shares
        rasio = bermakna / views if views > 0 else 0
        if rasio < 0.10:
            diagnoses.append(
                {
                    "metrik": "comments+shares",
                    "nilai": f"{int(bermakna)} ({rasio*100:.1f}% dari views)",
                    "harapan": "≥10% dari views",
                    "masalah": (
                        f"Image ini hanya menghasilkan comments+shares {rasio*100:.1f}% dari views "
                        f"({int(bermakna)} dari {int(views)} views), di bawah standar 10%. "
                        "Image/foto perlu memicu diskusi (comments) atau "
                        "relevansi (shares) agar dianggap bermakna oleh algoritma."
                    ),
                }
            )
            saran = (
                "Dorong comments & shares di Image: tulis caption yang mengundang cerita/pengalaman "
                "audiens, tambahkan CTA 'Ceritakan pengalamanmu di komentar' atau 'Bagikan ke "
                "teman yang membutuhkan'."
            )
            if saran not in suggestions:
                suggestions.append(saran)

    return diagnoses, suggestions


async def analisa_report(
    db: AsyncSession,
    *,
    brand: Brand,
    organization_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> dict:
    """Laporan kesesuaian pola: ringkasan per (format,tujuan), konten bermasalah, pola rekomendasi."""
    # Filter posted_at sesuai periode agar tidak memuat seluruh konten brand.
    # (ix_contents_brand_posted sudah mengindeks (brand_id, posted_at).)
    mulai_dt = datetime.combine(period_start, datetime.min.time(), tzinfo=timezone.utc)
    akhir_dt = datetime.combine(period_end, datetime.max.time(), tzinfo=timezone.utc)
    contents = list(
        (
            await db.execute(
                select(Content).where(
                    Content.brand_id == brand.id,
                    Content.organization_id == organization_id,
                    Content.posted_at >= mulai_dt,
                    Content.posted_at <= akhir_dt,
                )
            )
        )
        .scalars()
        .all()
    )
    content_ids = [c.id for c in contents]
    scores_by_content: dict[uuid.UUID, list[ContentScore]] = {}
    # Agregat metrik harian per konten sebagai fallback bila tidak ada ContentScore.
    metrics_by_content: dict[uuid.UUID, dict] = {}
    if content_ids:
        agg_rows = list(
            (
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
                    ).where(
                        ContentMetricsDaily.organization_id == organization_id,
                        ContentMetricsDaily.content_id.in_(content_ids),
                        ContentMetricsDaily.date >= period_start,
                        ContentMetricsDaily.date <= period_end,
                    ).group_by(ContentMetricsDaily.content_id)
                )
            ).all()
        )
        for r in agg_rows:
            metrics_by_content[r.content_id] = {
                "views": int(r.views or 0),
                "reach": int(r.reach or 0),
                "likes": int(r.likes or 0),
                "comments": int(r.comments or 0),
                "shares": int(r.shares or 0),
                "saves": int(r.saves or 0),
                "follows": int(r.follows or 0),
            }
    if content_ids:
        scores = list(
            (
                await db.execute(
                    select(ContentScore).where(
                        ContentScore.organization_id == organization_id,
                        ContentScore.content_id.in_(content_ids),
                        ContentScore.period_start >= period_start,
                        ContentScore.period_end <= period_end,
                    )
                )
            )
            .scalars()
            .all()
        )
        for s in scores:
            scores_by_content.setdefault(s.content_id, []).append(s)

    status_order = ["menang", "cukup", "kurang", "data_belum_cukup"]

    def dominan(statuses: list[str]) -> str | None:
        if not statuses:
            return None
        counts = {st: statuses.count(st) for st in set(statuses)}
        best = max(counts.values())
        for st in status_order:
            if counts.get(st) == best:
                return st
        return None

    # Ringkasan per pola (format, tujuan).
    groups: dict[tuple[str, str], dict] = {}
    per_content_avg: dict[uuid.UUID, float | None] = {}
    per_content_dominan: dict[uuid.UUID, str | None] = {}
    for c in contents:
        sc = scores_by_content.get(c.id, [])
        nilai = [s.score for s in sc if s.score is not None]
        avg = round(mean(nilai), 3) if nilai else None
        dom = dominan([s.status for s in sc])
        per_content_avg[c.id] = avg
        per_content_dominan[c.id] = dom
        key = (c.format, c.tujuan)
        g = groups.setdefault(key, {"jumlah": 0, "skor": [], "statuses": []})
        g["jumlah"] += 1
        if avg is not None:
            g["skor"].append(avg)
        if dom:
            g["statuses"].append(dom)

    ringkasan = []
    for (fmt, tujuan), g in sorted(groups.items()):
        ringkasan.append(
            {
                "format": fmt,
                "tujuan": tujuan,
                "jumlah": g["jumlah"],
                "rata_skor": round(mean(g["skor"]), 3) if g["skor"] else None,
                "dominan_status": dominan(g["statuses"]),
            }
        )

    # Konten bermasalah: dominan 'kurang', verdict suitability bukan 'sesuai',
    # atau di bawah standar framework Strategi Instagram Organik.
    bermasalah: list[dict] = []
    for c in contents:
        sc = scores_by_content.get(c.id, [])
        if sc:
            latest = max(sc, key=lambda s: (s.period_end, s.period_start))
            snapshot = dict(latest.metrics_snapshot or {})
            agg = _rates_from_snapshot(snapshot)
            agg["format"] = c.format
            agg["tujuan"] = c.tujuan
            hasil = evaluate_suitability(agg)
            gagal_suitability = per_content_dominan[c.id] == "kurang" or hasil["verdict"] != "sesuai"
            verdict_awal = hasil["verdict"]
            diagnosis_awal = list(hasil["diagnoses"])
            saran_awal = list(hasil["suggestions"])
        else:
            # Fallback: tanpa ContentScore, cek kesehatan framework dari metrik harian.
            snapshot = metrics_by_content.get(c.id, {})
            if not snapshot or not snapshot.get("views"):
                continue
            gagal_suitability = False
            verdict_awal = "sesuai"
            diagnosis_awal = []
            saran_awal = []
        diag_fw, saran_fw = cek_kesehatan_framework(c, snapshot)
        if gagal_suitability or diag_fw:
            verdict = verdict_awal
            if diag_fw and verdict == "sesuai":
                verdict = "tidak_sehat"
            semua_diagnosis = diagnosis_awal + diag_fw
            semua_saran = list(saran_awal)
            for s in saran_fw:
                if s not in semua_saran:
                    semua_saran.append(s)
            bermasalah.append(
                {
                    "content_id": str(c.id),
                    "post_id": c.post_id,
                    "format": c.format,
                    "tujuan": c.tujuan,
                    "verdict": verdict,
                    "diagnoses": semua_diagnosis,
                    "suggestions": semua_saran,
                }
            )

    # Rekomendasi pola dari ringkasan.
    rekomendasi_pola: list[str] = []
    terukur = [r for r in ringkasan if r["rata_skor"] is not None]
    if terukur:
        terbaik = max(terukur, key=lambda r: r["rata_skor"])
        rekomendasi_pola.append(
            f"Perbanyak pola {terbaik['format']} bertema {terbaik['tujuan']}: "
            f"rata-rata skor {terbaik['rata_skor']} tertinggi di periode ini."
        )
    for r in ringkasan:
        if r["dominan_status"] == "kurang":
            rekomendasi_pola.append(
                f"Kurangi atau rombak pola {r['format']}×{r['tujuan']} "
                f"({r['jumlah']} konten) yang dominan berstatus kurang."
            )
    if any(r["dominan_status"] == "data_belum_cukup" for r in ringkasan):
        rekomendasi_pola.append(
            "Dorong distribusi konten berstatus data_belum_cukup agar menembus "
            "1.000 views sebelum dinilai."
        )
    # Rekomendasi berbasis framework dari konten yang tidak sehat.
    jml_200jail = sum(
        1 for k in bermasalah
        for d in k["diagnoses"]
        if d.get("metrik") == "views" and isinstance(d.get("nilai"), int)
    )
    jml_tanpa_cta = sum(
        1 for k in bermasalah for d in k["diagnoses"] if d.get("metrik") == "cta"
    )
    jml_nol_bermakna = sum(
        1 for k in bermasalah for d in k["diagnoses"] if d.get("metrik") == "engagement_bermakna"
    )
    if jml_200jail:
        rekomendasi_pola.append(
            f"{jml_200jail} konten terjebak 200-view jail — audit hook 3 detik pertama semua konten "
            "baru sebelum posting."
        )
    if jml_tanpa_cta:
        rekomendasi_pola.append(
            f"{jml_tanpa_cta} konten tanpa CTA jelas — jadikan CTA spesifik sebagai checklist wajib "
            "sebelum publish."
        )
    if jml_nol_bermakna:
        rekomendasi_pola.append(
            f"{jml_nol_bermakna} konten nol engagement bermakna — terapkan filter 4 kriteria sebelum "
            "produksi: Relevan, Non-Obvious, mudah Dicerna, jarak Implementasi singkat."
        )
    if not bermasalah and ringkasan:
        rekomendasi_pola.append("Semua pola terpantau sehat — pertahankan konsistensi posting.")
    rekomendasi_pola = rekomendasi_pola[:5]

    return {
        "ringkasan": ringkasan,
        "bermasalah": bermasalah,
        "rekomendasi_pola": rekomendasi_pola,
    }
