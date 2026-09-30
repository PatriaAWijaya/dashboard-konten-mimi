"""Layanan rekomendasi konten rule-based + narasi LLM.

Prinsip "agregat dulu, narasi kemudian": semua kandidat dihitung dari agregat
rule-based per (format, tujuan); LLM hanya menerima dict agregat berisi angka
bukti (n, win_rate, avg_score, avg_wer, contoh post_id).

Dipakai dari model asli app.models.content (Worker Data):
- ContentScore tidak punya brand_id/wer: join ke Content untuk brand &
  periode; WER dihitung dari metrics_snapshot via compute_weighted_er.
- Recommendation: type, title (wajib), narrative, evidence (JSON — di sini
  format/tujuan/niche disimpan), reference_content_ids, status
  ('baru'|'diterima'|'ditolak'), period_start/end, config_version, dedup_key.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import (
    Content,
    ContentFormat,
    ContentScore,
    ContentTujuan,
    NicheSuggestion,
    Recommendation,
    RecommendationStatus,
    RecommendationType,
    ScoreStatus,
)
from app.services.llm import get_llm_provider_for_db
from app.services.notifications import notify_org
from app.services.scoring import compute_weighted_er, get_or_create_active_config
from app.services.suitability import evaluate_suitability

# Ambang rule-based (fraksi 0..1)
MIN_N_PER_POLA = 3
WIN_RATE_PERBANYAK = 0.5
WIN_RATE_KURANGI = 0.2
MAX_PERBAIKI = 3


def _batas_dt(awal: date, akhir: date) -> tuple[datetime, datetime]:
    mulai = datetime(awal.year, awal.month, awal.day, tzinfo=timezone.utc)
    selesai = datetime(akhir.year, akhir.month, akhir.day, tzinfo=timezone.utc) + timedelta(days=1)
    return mulai, selesai


async def _baris_skor(
    db: AsyncSession, brand_id: uuid.UUID, awal: date, akhir: date
) -> list[tuple]:
    """Baris (Content, ContentScore) untuk brand dalam periode."""
    mulai, selesai = _batas_dt(awal, akhir)
    return (
        await db.execute(
            select(Content, ContentScore)
            .join(ContentScore, ContentScore.content_id == Content.id)
            .where(
                Content.brand_id == brand_id,
                Content.posted_at >= mulai,
                Content.posted_at < selesai,
            )
        )
    ).all()


def _wer_snapshot(snapshot: dict | None) -> float:
    snap = snapshot or {}
    return compute_weighted_er(
        float(snap.get("likes") or 0),
        float(snap.get("comments") or 0),
        float(snap.get("shares") or 0),
        float(snap.get("saves") or 0),
        float(snap.get("views") or 0),
    )


def _agg_rates(snapshot: dict | None, fmt: str, tujuan: str) -> dict:
    """Bangun agg untuk evaluate_suitability dari metrics_snapshot."""
    snap = dict(snapshot or {})
    views = float(snap.get("views") or 0)
    agg = dict(snap)
    agg["format"] = fmt
    agg["tujuan"] = tujuan
    if views > 0:
        agg["save_rate"] = float(snap.get("saves") or 0) / views
        agg["share_rate"] = float(snap.get("shares") or 0) / views
        agg["comment_rate"] = float(snap.get("comments") or 0) / views
        agg["weighted_er"] = _wer_snapshot(snap)
    else:
        agg["save_rate"] = agg["share_rate"] = agg["comment_rate"] = agg["weighted_er"] = 0.0
    return agg


def _dedup_key(
    tipe: str, fmt: str | None, tujuan: str | None, awal: date, akhir: date,
    config_version: int, niche: str | None = None,
) -> str:
    inti = f"{tipe}:{fmt or '-'}:{tujuan or '-'}:{awal.isoformat()}:{akhir.isoformat()}:v{config_version}"
    if niche:
        inti = f"{inti}:niche:{niche}"
    return inti[:120]  # kolom dedup_key String(120)


async def _dedup_ditolak(db: AsyncSession, brand_id: uuid.UUID, dedup_key: str) -> bool:
    row = await db.scalar(
        select(func.count())
        .select_from(Recommendation)
        .where(
            Recommendation.brand_id == brand_id,
            Recommendation.dedup_key == dedup_key,
            Recommendation.status == RecommendationStatus.DITOLAK,
        )
    )
    return bool(row)


def _judul(tipe: str, fmt: str | None, tujuan: str | None, niche: str | None) -> str:
    if tipe == RecommendationType.PERBANYAK:
        return f"Perbanyak {fmt} {tujuan}"
    if tipe == RecommendationType.KURANGI:
        return f"Kurangi {fmt} {tujuan}"
    if tipe == RecommendationType.PERBAIKI:
        return f"Perbaiki {fmt} {tujuan}"
    if niche:
        return f"Coba {fmt} untuk niche {niche}"
    return f"Eksperimen {fmt} × {tujuan}"


async def generate_recommendations(
    db: AsyncSession,
    *,
    brand,
    organization_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> list[Recommendation]:
    """Hasilkan rekomendasi untuk satu brand & periode.

    Return [] bila konten unik dalam periode < 10 (API yang memberi pesan).
    """
    baris = await _baris_skor(db, brand.id, period_start, period_end)
    konten_unik = {c.id for c, _ in baris}
    n_unik = len(konten_unik)
    if n_unik < 10:
        return []

    # b. Config aktif + cache (jangan duplikat).
    config = await get_or_create_active_config(db, brand.id, organization_id)
    config_version = int(config.version or 1)
    cache = (
        await db.execute(
            select(Recommendation).where(
                Recommendation.brand_id == brand.id,
                Recommendation.period_start == period_start,
                Recommendation.period_end == period_end,
                Recommendation.config_version == config_version,
                Recommendation.status != RecommendationStatus.DITOLAK,
            )
        )
    ).scalars().all()
    if cache:
        return list(cache)

    # Agregasi per (format, tujuan) + per konten (untuk suitability).
    pola: dict[tuple[str, str], dict] = {}
    per_konten: dict[uuid.UUID, dict] = {}
    for content, skor in baris:
        key = (content.format, content.tujuan)
        p = pola.setdefault(key, {"n": set(), "menang": 0, "skor": [], "wer": []})
        p["n"].add(content.id)
        if skor.status == ScoreStatus.MENANG:
            p["menang"] += 1
        if skor.score is not None:
            p["skor"].append(float(skor.score))
        p["wer"].append(_wer_snapshot(skor.metrics_snapshot))
        kc = per_konten.setdefault(
            content.id,
            {"post_id": content.post_id, "format": content.format, "tujuan": content.tujuan,
             "statuses": [], "snapshots": []},
        )
        kc["statuses"].append(skor.status)
        kc["snapshots"].append(skor.metrics_snapshot)

    def _ringkas(p: dict) -> dict:
        n = len(p["n"])
        return {
            "n": n,
            "menang": p["menang"],
            "win_rate": (p["menang"] / n) if n else 0.0,
            "avg_score": sum(p["skor"]) / len(p["skor"]) if p["skor"] else 0.0,
            "avg_wer": sum(p["wer"]) / len(p["wer"]) if p["wer"] else 0.0,
        }

    def _contoh(key: tuple[str, str], status_utama: str | None = None, limit: int = 3) -> list[str]:
        fmt, tjn = key
        calon = [
            (c, s) for c, s in baris if c.format == fmt and c.tujuan == tjn
        ]
        if status_utama:
            calon.sort(key=lambda cs: 0 if cs[1].status == status_utama else 1)
        return [c.post_id for c, _ in calon[:limit]]

    llm = await get_llm_provider_for_db(db)
    baru: list[Recommendation] = []

    async def _simpan(
        tipe: str, fmt: str | None, tujuan: str | None, context: dict, niche: str | None = None
    ) -> None:
        key = _dedup_key(tipe, fmt, tujuan, period_start, period_end, config_version, niche)
        if await _dedup_ditolak(db, brand.id, key):
            return  # pernah ditolak user -> jangan munculkan lagi
        narrative = await llm.narrate("rekomendasi", context)
        rec = Recommendation(
            organization_id=organization_id,
            brand_id=brand.id,
            type=tipe,
            title=_judul(tipe, fmt, tujuan, niche)[:255],
            narrative=narrative,
            evidence=context,
            reference_content_ids=context.get("contoh_post_ids") or [],
            status=RecommendationStatus.BARU,
            period_start=period_start,
            period_end=period_end,
            config_version=config_version,
            dedup_key=key,
        )
        db.add(rec)
        baru.append(rec)

    def _context(tipe: str, key: tuple[str, str], r: dict, **tambahan) -> dict:
        fmt, tjn = key
        ctx = {
            "type": tipe,
            "format": fmt,
            "tujuan": tjn,
            "n": r["n"],
            "menang": r["menang"],
            "win_rate": round(r["win_rate"], 4),
            "avg_score": round(r["avg_score"], 4),
            "avg_wer": round(r["avg_wer"], 4),
            "contoh_post_ids": _contoh(key),
        }
        ctx.update(tambahan)
        return ctx

    # c1. perbanyak / kurangi dari win_rate pola.
    for key, p in pola.items():
        r = _ringkas(p)
        if r["n"] < MIN_N_PER_POLA:
            continue
        if r["win_rate"] >= WIN_RATE_PERBANYAK:
            await _simpan(
                RecommendationType.PERBANYAK, key[0], key[1],
                _context(RecommendationType.PERBANYAK, key, r,
                         contoh_post_ids=_contoh(key, ScoreStatus.MENANG)),
            )
        elif r["win_rate"] <= WIN_RATE_KURANGI:
            await _simpan(
                RecommendationType.KURANGI, key[0], key[1],
                _context(RecommendationType.KURANGI, key, r,
                         contoh_post_ids=_contoh(key, ScoreStatus.KURANG)),
            )

    # c2. perbaiki: konten 'kurang' yang verdict suitability-nya tidak_sesuai.
    grup_perbaiki: dict[tuple[str, str], dict] = {}
    for cid, kc in per_konten.items():
        if ScoreStatus.KURANG not in kc["statuses"]:
            continue
        verdict = None
        for snap in kc["snapshots"]:
            v = evaluate_suitability(_agg_rates(snap, kc["format"], kc["tujuan"]))["verdict"]
            verdict = v
            if v == "tidak_sesuai":
                break
        if verdict == "tidak_sesuai":
            g = grup_perbaiki.setdefault((kc["format"], kc["tujuan"]), {"konten": [], "verdict": verdict})
            g["konten"].append(kc["post_id"])
    for key in sorted(grup_perbaiki, key=lambda k: -len(grup_perbaiki[k]["konten"]))[:MAX_PERBAIKI]:
        r = _ringkas(pola[key])
        await _simpan(
            RecommendationType.PERBAIKI, key[0], key[1],
            _context(
                RecommendationType.PERBAIKI, key, r,
                contoh_post_ids=_contoh(key, ScoreStatus.KURANG),
                suitability_verdict="tidak_sesuai",
                pola_bermasalah=f"{key[0]}/{key[1]}",
            ),
        )

    # c3. coba_baru: dari niche terpilih, atau kombinasi yang belum pernah dicoba.
    niche_terpilih = (
        await db.execute(
            select(NicheSuggestion).where(
                NicheSuggestion.brand_id == brand.id,
                NicheSuggestion.is_selected.is_(True),
            )
        )
    ).scalars().all()
    if niche_terpilih:
        for nic in niche_terpilih:
            await _simpan(
                RecommendationType.COBA_BARU, "reels", "edukasi",
                {
                    "type": RecommendationType.COBA_BARU,
                    "format": "reels",
                    "tujuan": "edukasi",
                    "niche": nic.name,
                    "n": 0,
                    "menang": 0,
                    "win_rate": 0.0,
                    "avg_score": 0.0,
                    "avg_wer": 0.0,
                    "contoh_post_ids": [],
                    "match_percent": round(float(nic.match_percent or 0) / 100, 4),
                    "total_konten": n_unik,
                },
                niche=nic.name,
            )
    else:
        sudah_ada = set(pola.keys())
        for fmt in ContentFormat.ALL:
            for tjn in ContentTujuan.ALL:
                if (fmt, tjn) not in sudah_ada:
                    await _simpan(
                        RecommendationType.COBA_BARU, fmt, tjn,
                        {
                            "type": RecommendationType.COBA_BARU,
                            "format": fmt,
                            "tujuan": tjn,
                            "n": 0,
                            "menang": 0,
                            "win_rate": 0.0,
                            "avg_score": 0.0,
                            "avg_wer": 0.0,
                            "contoh_post_ids": [],
                            "total_konten": n_unik,
                        },
                    )
                    break
            else:
                continue
            break

    await db.flush()

    if baru:
        # Notifikasi ke semua anggota org (preferensi dicek di dalam notify()).
        # Kegagalan notifikasi tidak boleh menggagalkan generate.
        try:
            await notify_org(
                db,
                organization_id,
                "rekomendasi_baru",
                {
                    "brand_id": str(brand.id),
                    "brand_name": getattr(brand, "name", ""),
                    "jumlah": len(baru),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                },
            )
        except Exception:  # noqa: BLE001
            pass

    return baru


async def set_recommendation_status(
    db: AsyncSession, rec: Recommendation, status: str
) -> Recommendation:
    """Ubah status rekomendasi. Hanya 'diterima' / 'ditolak' yang diizinkan."""
    if status not in (RecommendationStatus.DITERIMA, RecommendationStatus.DITOLAK):
        raise ValueError(
            f"Status tidak valid: '{status}'. Pilihan: "
            f"'{RecommendationStatus.DITERIMA}', '{RecommendationStatus.DITOLAK}'."
        )
    rec.status = status
    await db.flush()
    return rec


# ---------------------------------------------------------------------------
# Rekomendasi terstruktur: Umum (akun) + Khusus (per jenis post)
# ---------------------------------------------------------------------------

# Metrik dominan per format (dari framework strategi Instagram organik).
METRIK_DOMINAN = {
    "carousel": {
        "nama": "Carousel",
        "metrik": "saves",
        "label_metrik": "Saves",
        "penjelasan": (
            "Carousel adalah mesin saves. Format ini dirancang untuk edukasi mendalam "
            "yang layak disimpan dan dibuka kembali — semakin banyak yang menyimpan, "
            "semakin kuat sinyal bahwa kontenmu bernilai."
        ),
    },
    "foto": {
        "nama": "Image",
        "metrik": "comments_shares",
        "label_metrik": "Comments & Shares",
        "penjelasan": (
            "Image mengandalkan comments dan shares. Satu gambar yang kuat harus memicu "
            "diskusi di kolom komentar atau cukup relevan untuk dibagikan ke orang lain."
        ),
    },
    "image": {
        "nama": "Image",
        "metrik": "comments_shares",
        "label_metrik": "Comments & Shares",
        "penjelasan": (
            "Image mengandalkan comments dan shares. Satu gambar yang kuat harus memicu "
            "diskusi di kolom komentar atau cukup relevan untuk dibagikan ke orang lain."
        ),
    },
    "reels": {
        "nama": "Reels",
        "metrik": "shares_comments",
        "label_metrik": "Shares & Comments",
        "penjelasan": (
            "Reels adalah mesin jangkauan. Format ini dirancang untuk menjangkau audiens "
            "baru — shares membawa penonton baru, comments menandakan kontenmu memicu "
            "reaksi."
        ),
    },
}


async def generate_rekomendasi_struktur(
    db: AsyncSession,
    *,
    brand,
    organization_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> list[Recommendation]:
    """Hasilkan rekomendasi terstruktur: Umum (akun) + Khusus (per jenis post).

    - Umum: kondisi akun secara keseluruhan + saran perbaikan dari framework.
    - Khusus: per format (Carousel, Image, Reels) + metrik dominan masing-masing.
    """
    from app.services import analisa_lanjutan as al
    from app.services.suitability import analisa_report

    # Ambil data akun & pola bermasalah.
    try:
        lanjutan = await al.analisa_lanjutan(
            db, brand=brand, organization_id=organization_id,
            period_start=period_start, period_end=period_end,
        )
    except Exception:  # noqa: BLE001
        lanjutan = {}
    try:
        suit = await analisa_report(
            db, brand=brand, organization_id=organization_id,
            period_start=period_start, period_end=period_end,
        )
    except Exception:  # noqa: BLE001
        suit = {"bermasalah": [], "ringkasan": []}

    skor_akun = (lanjutan.get("skor_akun") or {})
    nilai_skor = float(skor_akun.get("skor") or 0)
    kategori = str(skor_akun.get("kategori") or "")
    kenapa_stuck = str(lanjutan.get("kenapa_stuck") or "")

    bermasalah = suit.get("bermasalah") or []
    ringkasan = suit.get("ringkasan") or []

    total_konten = sum(int(r.get("jumlah") or 0) for r in ringkasan)
    total_bermasalah = len(bermasalah)
    persen_bermasalah = (total_bermasalah / total_konten * 100) if total_konten else 0

    # Kelompokkan bermasalah per format.
    per_format: dict[str, list] = {}
    for b in bermasalah:
        fmt = str(b.get("format") or "").lower()
        per_format.setdefault(fmt, []).append(b)
    total_per_format: dict[str, int] = {}
    for r in ringkasan:
        fmt = str(r.get("format") or "").lower()
        total_per_format[fmt] = total_per_format.get(fmt, 0) + int(r.get("jumlah") or 0)

    config = await get_or_create_active_config(db, brand.id, organization_id)
    config_version = int(config.version or 1)
    baru: list[Recommendation] = []

    async def _simpan_struktur(
        tipe: str, judul: str, narasi: str, evidence: dict,
        ref_ids: list[str] | None = None,
    ) -> None:
        key = _dedup_key(tipe, None, None, period_start, period_end, config_version, judul[:50])
        if await _dedup_ditolak(db, brand.id, key):
            return
        rec = Recommendation(
            organization_id=organization_id,
            brand_id=brand.id,
            type=tipe,
            title=judul[:255],
            narrative=narasi,
            evidence=evidence,
            reference_content_ids=ref_ids or [],
            status=RecommendationStatus.BARU,
            period_start=period_start,
            period_end=period_end,
            config_version=config_version,
            dedup_key=key,
        )
        db.add(rec)
        baru.append(rec)

    # === BAGIAN 1: REKOMENDASI UMUM (tentang akun) ===
    if nilai_skor > 0:
        if nilai_skor <= 6.0:
            saran_umum = (
                f"Skor akunmu {nilai_skor:.1f} ({kategori}) — artinya sebagian besar konten "
                f"belum bekerja optimal. Dari {total_konten} konten, {total_bermasalah} "
                f"({persen_bermasalah:.0f}%) terdeteksi bermasalah. "
                "Fokus dulu pada tiga hal: (1) buat 3 detik pertama setiap konten semenarik "
                "mungkin agar orang berhenti scroll, (2) pilih satu topik utama dan konsisten "
                "di sana agar algoritma paham siapa audiensmu, (3) posting terjadwal — akun yang "
                "aktif rutin lebih mudah terbaca polanya."
            )
        elif nilai_skor < 8.0:
            saran_umum = (
                f"Skor akunmu {nilai_skor:.1f} ({kategori}) — sudah ada fondasi yang bagus. "
                f"Dari {total_konten} konten, {total_bermasalah} masih bermasalah. "
                "Tugasmu sekarang: perbanyak pola yang sudah terbukti menang, kurangi yang "
                "tidak bekerja, dan jaga konsistensi posting agar momentum tidak putus."
            )
        else:
            saran_umum = (
                f"Skor akunmu {nilai_skor:.1f} ({kategori}) — performa sangat baik. "
                "Pertahankan polanya: lanjutkan format dan topik yang menang, uji satu-dua "
                "variasi baru setiap pekan agar tidak stagnan, dan jaga kualitas hook di "
                "3 detik pertama."
            )
        if kenapa_stuck:
            saran_umum += f" Catatan: {kenapa_stuck}"
        await _simpan_struktur(
            RecommendationType.UMUM,
            "Kondisi akun secara umum",
            saran_umum,
            {"skor": nilai_skor, "kategori": kategori,
             "total_konten": total_konten, "bermasalah": total_bermasalah},
        )

    # === Kerja engagement akun: Strategi 502 & $1.80 ===
    await _simpan_struktur(
        RecommendationType.UMUM,
        "Strategi 502: pancing algoritma ke niche target",
        (
            "Setiap kali mau posting, lakukan 50 komentar di akun-akun dengan niche "
            "yang sama dengan target audiensmu — dibagi 2 sesi: 25 komentar SEBELUM "
            "posting, 25 komentar SESUDAH posting. Tujuannya: memaksa algoritma "
            "mengenali akunmu sebagai bagian dari niche tersebut, sehingga kontenmu "
            "diuji ke audiens yang tepat (bukan orang acak). Komentar harus relevan "
            "dan bermakna — tanggapi isi postingannya, bukan sekadar emoji atau "
            "'keren bang'. Pilih akun yang audiensnya adalah calon followersmu: "
            "kompetitor se-niche, komunitas, atau kreator yang dibahas target audiensmu."
        ),
        {"strategi": "502", "komposisi": "25 sebelum + 25 sesudah posting"},
    )
    await _simpan_struktur(
        RecommendationType.UMUM,
        "Strategi 90 Komentar: bangun kehadiran harian di niche",
        (
            "Setiap hari, tinggalkan 90 komentar bermakna di postingan dalam niche-mu: "
            "cari 10 hashtag yang dipakai target audiensmu, lalu komentari 9 postingan "
            "teratas di tiap hashtag. Anggap setiap komentar sebagai investasi perhatian "
            "kecil yang dikumpulkan setiap hari. Jangan jualan di komentar orang; berikan "
            "wawasan, apresiasi spesifik, atau pertanyaan yang memancing balasan. "
            "Konsistensi di sini membangun nama akunmu di komunitas niche sebelum "
            "mereka melihat kontenmu."
        ),
        {"strategi": "90 komentar", "komposisi": "9 postingan x 10 hashtag per hari"},
    )

    # === BAGIAN 2: REKOMENDASI KHUSUS (per jenis post) ===
    for fmt_key in ("carousel", "foto", "reels"):
        info = METRIK_DOMINAN.get(fmt_key)
        if not info:
            continue
        # Cari data format (foto mencakup 'foto' & 'image').
        kunci_cari = ("foto", "image") if fmt_key == "foto" else (fmt_key,)
        items = []
        total = 0
        for k in kunci_cari:
            items.extend(per_format.get(k, []))
            total += total_per_format.get(k, 0)
        if total == 0:
            continue
        jml_masalah = len(items)
        # Hitung rata-rata metrik dominan dari contoh bermasalah (jika ada data).
        narasi = (
            f"{info['nama']}: {jml_masalah} bermasalah dari {total} post. "
            f"Metrik dominan untuk {info['nama']} adalah {info['label_metrik']}. "
            f"{info['penjelasan']} "
        )
        if jml_masalah > 0:
            if fmt_key == "carousel":
                narasi += (
                    "Agar saves naik: akhiri carousel dengan ringkasan atau checklist yang "
                    "layak di-screenshot, dan tambahkan ajakan spesifik seperti "
                    "'Simpan postingan ini'. Konten yang tidak layak disimpan tidak akan "
                    "disimpan — pastikan setiap slide memberi alasan untuk lanjut dan simpan."
                )
            elif fmt_key == "reels":
                narasi += (
                    "Agar shares dan comments naik: buka dengan pertanyaan atau pernyataan "
                    "yang memancing opini, dan tutup dengan ajakan seperti 'Tag teman yang "
                    "perlu tahu ini' atau 'Tulis pendapatmu di komentar'. Reels yang hanya "
                    "ditonton tanpa reaksi tidak akan disebar lebih luas."
                )
            else:
                narasi += (
                    "Agar comments dan shares naik: tulis caption yang mengundang cerita atau "
                    "pengalaman audiens, bukan sekadar deskripsi gambar. Ajakan seperti "
                    "'Ceritakan pengalamanmu di komentar' jauh lebih efektif daripada "
                    "caption satu baris."
                )
        else:
            narasi += (
                f"Semua {info['nama']} pada periode ini sehat — pertahankan polanya dan "
                "jadikan sebagai acuan untuk format lain."
            )
        await _simpan_struktur(
            RecommendationType.KHUSUS,
            f"Rekomendasi khusus {info['nama']}",
            narasi,
            {"format": info["nama"], "metrik_dominan": info["label_metrik"],
             "total": total, "bermasalah": jml_masalah},
            [str(b.get("post_id")) for b in items[:3] if b.get("post_id")],
        )

    await db.flush()
    return baru
