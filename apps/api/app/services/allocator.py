"""Alokator deterministik: rekomendasi diterima -> slot rencana mingguan.

Prinsip: input sama -> output sama. Tidak ada randomness, tidak ada waktu
"sekarang" di dalam perhitungan (tanggal murni dari parameter minggu).
Rekomendasi diurutkan by id; tanggal slot round-robin Senin..Minggu.

Dipakai dari model asli:
- Recommendation (status='diterima'): type, title, narrative, evidence,
  reference_content_ids.
- PlannerConfig: kapasitas_mingguan, target_distribusi, porsi_eksperimen.
- Content + ContentScore: pola menang untuk target metrik & distribusi
  default.
"""

from __future__ import annotations

import statistics
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand import Brand
from app.models.content import (
    Content,
    ContentFormat,
    ContentPlatform,
    ContentScore,
    ContentTujuan,
    Recommendation,
    RecommendationStatus,
    ScoreStatus,
)
from app.models.fase2 import PlannerConfig, PlannedPost, PlannedPostStatus
from app.services.planner import create_planned
from app.services.scoring import compute_weighted_er

KAPASITAS_MIN = 1
KAPASITAS_MAX = 50


# ---------------------------------------------------------------------------
# Konfigurasi planner
# ---------------------------------------------------------------------------

async def get_or_create_planner_config(
    db: AsyncSession, *, brand: Brand, organization_id: uuid.UUID
) -> PlannerConfig:
    """Ambil konfigurasi brand; buat dengan default bila belum ada."""
    cfg = await db.scalar(
        select(PlannerConfig).where(PlannerConfig.brand_id == brand.id)
    )
    if cfg is None:
        cfg = PlannerConfig(
            organization_id=organization_id,
            brand_id=brand.id,
            kapasitas_mingguan=7,
            target_distribusi=None,
            porsi_eksperimen=0.2,
        )
        db.add(cfg)
        await db.flush()
    return cfg


def _validasi_konfigurasi(data: dict) -> dict:
    """Validasi parsial body PUT konfigurasi. Raise ValueError bila salah."""
    bersih: dict = {}
    if "kapasitas_mingguan" in data and data.get("kapasitas_mingguan") is not None:
        try:
            kap = int(data["kapasitas_mingguan"])
        except (TypeError, ValueError) as exc:
            raise ValueError("kapasitas_mingguan harus bilangan bulat.") from exc
        if not KAPASITAS_MIN <= kap <= KAPASITAS_MAX:
            raise ValueError(
                f"kapasitas_mingguan harus antara {KAPASITAS_MIN} dan {KAPASITAS_MAX}."
            )
        bersih["kapasitas_mingguan"] = kap
    if "porsi_eksperimen" in data and data.get("porsi_eksperimen") is not None:
        try:
            porsi = float(data["porsi_eksperimen"])
        except (TypeError, ValueError) as exc:
            raise ValueError("porsi_eksperimen harus angka 0..1.") from exc
        if not 0.0 <= porsi <= 1.0:
            raise ValueError("porsi_eksperimen harus antara 0 dan 1.")
        bersih["porsi_eksperimen"] = porsi
    if "target_distribusi" in data:
        dist = data.get("target_distribusi")
        if dist is not None:
            if not isinstance(dist, dict) or not dist:
                raise ValueError("target_distribusi harus objek {format: porsi}.")
            norm: dict[str, float] = {}
            for fmt, v in dist.items():
                f = str(fmt).strip().lower()
                if f not in ContentFormat.ALL:
                    raise ValueError(f"Format '{fmt}' tidak dikenal.")
                try:
                    fv = float(v)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Porsi format '{fmt}' harus angka.") from exc
                if fv < 0:
                    raise ValueError(f"Porsi format '{fmt}' tidak boleh negatif.")
                norm[f] = fv
            total = sum(norm.values())
            if total <= 0:
                raise ValueError("Total porsi target_distribusi harus > 0.")
            # Normalisasi agar jumlah = 1 (deterministik: urut abjad).
            bersih["target_distribusi"] = {
                f: round(norm[f] / total, 4) for f in sorted(norm)
            }
        else:
            bersih["target_distribusi"] = None
    return bersih


async def update_planner_config(
    db: AsyncSession, *, config: PlannerConfig, data: dict
) -> PlannerConfig:
    bersih = _validasi_konfigurasi(data)
    for k, v in bersih.items():
        setattr(config, k, v)
    await db.flush()
    return config


# ---------------------------------------------------------------------------
# Data historis (pola menang)
# ---------------------------------------------------------------------------

async def _skor_terbaru(db: AsyncSession, brand_id: uuid.UUID) -> list[tuple[Content, ContentScore]]:
    """Skor terbaru per konten (period_end desc, created_at desc)."""
    rows = (
        await db.execute(
            select(Content, ContentScore)
            .join(ContentScore, ContentScore.content_id == Content.id)
            .where(Content.brand_id == brand_id)
            .order_by(
                Content.id.asc(),
                ContentScore.period_end.desc(),
                ContentScore.created_at.desc(),
            )
        )
    ).all()
    seen: set[uuid.UUID] = set()
    hasil: list[tuple[Content, ContentScore]] = []
    for content, skor in rows:
        if content.id in seen:
            continue
        seen.add(content.id)
        hasil.append((content, skor))
    return hasil


def _wer_dari_snapshot(snapshot: dict | None) -> float:
    snap = snapshot or {}
    return compute_weighted_er(
        float(snap.get("likes") or 0),
        float(snap.get("comments") or 0),
        float(snap.get("shares") or 0),
        float(snap.get("saves") or 0),
        float(snap.get("views") or 0),
    )


def _views_dari_snapshot(snapshot: dict | None) -> float:
    return float((snapshot or {}).get("views") or 0)


async def _pola_menang(
    db: AsyncSession, brand_id: uuid.UUID
) -> tuple[list[tuple[Content, ContentScore]], list[tuple[Content, ContentScore]]]:
    """Return (semua_skor_terbaru, yang_menang)."""
    semua = await _skor_terbaru(db, brand_id)
    menang = [(c, s) for c, s in semua if s.status == ScoreStatus.MENANG]
    return semua, menang


def _distribusi_format_menang(menang: list[tuple[Content, ContentScore]]) -> dict[str, float]:
    """Distribusi format di antara konten MENANG (fallback merata)."""
    hitung: dict[str, int] = {}
    for content, _ in menang:
        hitung[content.format] = hitung.get(content.format, 0) + 1
    total = sum(hitung.values())
    if total <= 0:
        n = len(ContentFormat.ALL)
        return {f: round(1 / n, 4) for f in sorted(ContentFormat.ALL)}
    return {f: round(hitung[f] / total, 4) for f in sorted(hitung)}


def _rentang_views(menang: list[tuple[Content, ContentScore]], fmt: str | None) -> tuple[int | None, int | None]:
    """mean ± stddev (populasi) views konten MENANG; filter format bila ada data."""
    subset = [s for c, s in menang if fmt is None or c.format == fmt]
    if not subset:
        subset = [s for _, s in menang]
    views = [_views_dari_snapshot(s.metrics_snapshot) for s in subset]
    views = [v for v in views if v > 0]
    if not views:
        return None, None
    mean = statistics.fmean(views)
    std = statistics.pstdev(views) if len(views) > 1 else 0.0
    return max(0, int(round(mean - std))), int(round(mean + std))


def _rata_wer(menang: list[tuple[Content, ContentScore]], fmt: str | None = None) -> float | None:
    wers = [
        _wer_dari_snapshot(s.metrics_snapshot)
        for c, s in menang
        if fmt is None or c.format == fmt
    ]
    if not wers:
        return None
    return round(statistics.fmean(wers), 4)


# ---------------------------------------------------------------------------
# Bangun slot
# ---------------------------------------------------------------------------

def _kalimat_pertama(teks: str | None, batas: int = 160) -> str:
    teks = (teks or "").strip().replace("\n", " ")
    if not teks:
        return ""
    for pemisah in (". ", "! ", "? ", ".\n"):
        if pemisah in teks:
            teks = teks.split(pemisah)[0]
            break
    teks = teks.rstrip(".!?")
    return teks[:batas].strip()


def _rentang_er(avg_wer: float | None) -> list[float]:
    """Rentang ±20% dari rata-rata WER (selalu rentang, bukan angka tunggal)."""
    w = max(float(avg_wer or 0.0), 0.0)
    return [round(w * 0.8, 4), round(w * 1.2, 4)]


async def _platform_untuk_rekomendasi(
    db: AsyncSession, brand_id: uuid.UUID, rec: Recommendation
) -> str:
    """Platform dominan dari konten acuan; fallback platform dominan brand."""
    ref = list(rec.reference_content_ids or [])
    if ref:
        rows = (
            await db.execute(
                select(Content.platform)
                .where(Content.brand_id == brand_id, Content.post_id.in_(ref))
                .order_by(Content.post_id.asc())
            )
        ).scalars().all()
        if rows:
            hitung: dict[str, int] = {}
            for p in rows:
                hitung[p] = hitung.get(p, 0) + 1
            return sorted(hitung, key=lambda p: (-hitung[p], p))[0]
    rows = (
        await db.execute(
            select(Content.platform, Content.id)
            .where(Content.brand_id == brand_id)
        )
    ).all()
    if rows:
        hitung = {}
        for p, _ in rows:
            hitung[p] = hitung.get(p, 0) + 1
        return sorted(hitung, key=lambda p: (-hitung[p], p))[0]
    return ContentPlatform.TIKTOK


async def _rekomendasi_diterima(db: AsyncSession, brand_id: uuid.UUID) -> list[Recommendation]:
    rows = (
        await db.execute(
            select(Recommendation)
            .where(
                Recommendation.brand_id == brand_id,
                Recommendation.status == RecommendationStatus.DITERIMA,
            )
            .order_by(Recommendation.id.asc())
        )
    ).scalars().all()
    return list(rows)


def _slot_dari_rekomendasi(
    rec: Recommendation,
    platform: str,
    tanggal: date,
    menang: list[tuple[Content, ContentScore]],
) -> dict:
    evidence = rec.evidence or {}
    fmt = str(evidence.get("format") or "reels").strip().lower()
    if fmt not in ContentFormat.ALL:
        fmt = "reels"
    tujuan = str(evidence.get("tujuan") or "edukasi").strip().lower()
    if tujuan not in ContentTujuan.ALL:
        tujuan = "edukasi"
    vmin, vmax = _rentang_views(menang, fmt)
    avg_wer = evidence.get("avg_wer")
    try:
        avg_wer = float(avg_wer) if avg_wer is not None else 0.0
    except (TypeError, ValueError):
        avg_wer = 0.0
    return {
        "tanggal": tanggal,
        "platform": platform,
        "format": fmt,
        "tujuan": tujuan,
        "topik": (rec.title or "").strip()[:255],
        "hook": _kalimat_pertama(rec.narrative),
        "konten_acuan_ids": list(rec.reference_content_ids or []),
        "target_er": _rentang_er(avg_wer),
        "target_views_min": vmin,
        "target_views_max": vmax,
        "sumber_rekomendasi_id": rec.id,
        "eksperimen": False,
    }


def _kombinasi_eksperimen(
    semua: list[tuple[Content, ContentScore]], butuh: int
) -> list[tuple[str, str]]:
    """(format, tujuan) yang belum pernah dicoba brand (urutan deterministik)."""
    dipakai = {(c.format, c.tujuan) for c, _ in semua}
    kandidat = [
        (f, t)
        for f in sorted(ContentFormat.ALL)
        for t in sorted(ContentTujuan.ALL)
        if (f, t) not in dipakai
    ]
    if not kandidat:
        # Semua kombinasi sudah dicoba: putar dari awal (tetap deterministik).
        kandidat = [(f, t) for f in sorted(ContentFormat.ALL) for t in sorted(ContentTujuan.ALL)]
    return [kandidat[i % len(kandidat)] for i in range(butuh)]


def _slot_eksperimen(
    fmt: str,
    tujuan: str,
    tanggal: date,
    menang: list[tuple[Content, ContentScore]],
) -> dict:
    vmin, vmax = _rentang_views(menang, None)
    return {
        "tanggal": tanggal,
        "platform": ContentPlatform.TIKTOK,
        "format": fmt,
        "tujuan": tujuan,
        "topik": f"Eksperimen {fmt} × {tujuan}",
        "hook": (
            "Konten uji coba: kombinasi format dan tujuan ini belum pernah "
            "diposting brand — pantau respons audiens selama 7 hari."
        ),
        "konten_acuan_ids": [],
        "target_er": _rentang_er(_rata_wer(menang)),
        "target_views_min": vmin,
        "target_views_max": vmax,
        "sumber_rekomendasi_id": None,
        "eksperimen": True,
    }


async def generate_alokasi(
    db: AsyncSession, *, brand: Brand, minggu: date
) -> dict:
    """Hasilkan preview alokasi slot untuk pekan [minggu .. minggu+6].

    TANPA menyimpan apa pun. Deterministik: input sama -> output sama.
    Raise ValueError bila minggu bukan hari Senin atau tidak ada kapasitas.
    """
    if minggu.weekday() != 0:
        raise ValueError("Parameter minggu harus tanggal hari Senin (YYYY-MM-DD).")

    cfg = await get_or_create_planner_config(
        db, brand=brand, organization_id=brand.organization_id
    )
    kapasitas = max(int(cfg.kapasitas_mingguan or 0), 0)
    if kapasitas <= 0:
        raise ValueError("kapasitas_mingguan harus >= 1 untuk membuat alokasi.")
    try:
        porsi = float(cfg.porsi_eksperimen or 0.0)
    except (TypeError, ValueError):
        porsi = 0.0
    porsi = min(max(porsi, 0.0), 1.0)

    recs = await _rekomendasi_diterima(db, brand.id)
    semua, menang = await _pola_menang(db, brand.id)

    n_eksperimen = min(kapasitas, round(kapasitas * porsi))
    n_reguler = kapasitas - n_eksperimen

    # Distribusi format target: dari konfigurasi, atau diturunkan dari
    # distribusi format di antara konten MENANG brand.
    distribusi = dict(cfg.target_distribusi or _distribusi_format_menang(menang))

    slots: list[dict] = []
    idx_tanggal = 0

    def _tanggal_berikut() -> date:
        nonlocal idx_tanggal
        tgl = minggu + timedelta(days=idx_tanggal % 7)
        idx_tanggal += 1
        return tgl

    if recs and n_reguler > 0:
        # (1-porsi) slot mengikuti pola rekomendasi yang diterima.
        # Jatah tiap rekomendasi proporsional kapasitas DAN dibobot oleh
        # target_distribusi formatnya (largest remainder; seri -> urut id).
        def _fmt_rec(rec: Recommendation) -> str:
            f = str((rec.evidence or {}).get("format") or "reels").strip().lower()
            return f if f in ContentFormat.ALL else "reels"

        bobot = [max(float(distribusi.get(_fmt_rec(r), 0.0)), 0.0) for r in recs]
        if sum(bobot) <= 0:
            bobot = [1.0] * len(recs)
        total_bobot = sum(bobot)
        kuota = [n_reguler * w / total_bobot for w in bobot]
        dasar = [int(q) for q in kuota]
        sisa = n_reguler - sum(dasar)
        # largest remainder: urut sisa desimal desc, seri -> indeks (id) kecil dulu
        urutan = sorted(range(len(recs)), key=lambda i: (-(kuota[i] - dasar[i]), i))
        jatah = list(dasar)
        for i in urutan[:sisa]:
            jatah[i] += 1
        for rec, j in zip(recs, jatah):
            if j <= 0:
                continue
            platform = await _platform_untuk_rekomendasi(db, brand.id, rec)
            for _ in range(j):
                slots.append(
                    _slot_dari_rekomendasi(rec, platform, _tanggal_berikut(), menang)
                )
    elif not recs and n_reguler > 0:
        # Tanpa rekomendasi diterima: ikuti distribusi format pola menang.
        distribusi = cfg.target_distribusi or _distribusi_format_menang(menang)
        fmts = sorted(distribusi)
        bobot = [max(float(distribusi[f]), 0.0) for f in fmts]
        total_bobot = sum(bobot) or 1.0
        tujuan_umum = "edukasi"
        # Urutan format proporsional bobot (deterministik: fmts sudah terurut).
        urutan_fmt: list[str] = []
        for f, w in zip(fmts, bobot):
            urutan_fmt.extend([f] * max(1, round(n_reguler * w / total_bobot)))
        urutan_fmt = urutan_fmt[:n_reguler]
        while len(urutan_fmt) < n_reguler:
            urutan_fmt.append(fmts[0])
        for f in urutan_fmt:
            vmin, vmax = _rentang_views(menang, f)
            slots.append(
                {
                    "tanggal": _tanggal_berikut(),
                    "platform": ContentPlatform.TIKTOK,
                    "format": f,
                    "tujuan": tujuan_umum,
                    "topik": f"Konten {f} mengikuti pola menang",
                    "hook": "Lanjutkan pola format yang terbukti menang untuk brand ini.",
                    "konten_acuan_ids": [],
                    "target_er": _rentang_er(_rata_wer(menang, f)),
                    "target_views_min": vmin,
                    "target_views_max": vmax,
                    "sumber_rekomendasi_id": None,
                    "eksperimen": False,
                }
            )

    # Slot eksperimen: format/tujuan yang belum dicoba.
    for fmt, tujuan in _kombinasi_eksperimen(semua, n_eksperimen):
        slots.append(_slot_eksperimen(fmt, tujuan, _tanggal_berikut(), menang))

    # Serialisasi id untuk JSON.
    for s in slots:
        if isinstance(s["sumber_rekomendasi_id"], uuid.UUID):
            s["sumber_rekomendasi_id"] = str(s["sumber_rekomendasi_id"])
        s["tanggal"] = s["tanggal"].isoformat()

    return {
        "slots": slots,
        "info": {"total_slot": len(slots), "slot_eksperimen": n_eksperimen},
    }


# ---------------------------------------------------------------------------
# Terima alokasi -> planned_posts
# ---------------------------------------------------------------------------

def _validasi_slot_terima(slot: dict) -> dict:
    """Validasi satu slot dari body terima. Raise ValueError bila salah."""
    if not isinstance(slot, dict):
        raise ValueError("Setiap slot harus berupa objek.")
    try:
        tanggal = slot.get("tanggal")
        if isinstance(tanggal, str):
            tanggal = date.fromisoformat(tanggal)
        if not isinstance(tanggal, date):
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise ValueError("Slot 'tanggal' harus tanggal valid (YYYY-MM-DD).") from exc
    platform = str(slot.get("platform") or "").strip().lower()
    if platform not in ContentPlatform.ALL:
        raise ValueError(f"Slot platform '{slot.get('platform')}' tidak dikenal.")
    fmt = str(slot.get("format") or "").strip().lower()
    if fmt not in ContentFormat.ALL:
        raise ValueError(f"Slot format '{slot.get('format')}' tidak dikenal.")
    tujuan = str(slot.get("tujuan") or "").strip().lower()
    if tujuan not in ContentTujuan.ALL:
        raise ValueError(f"Slot tujuan '{slot.get('tujuan')}' tidak dikenal.")
    topik = str(slot.get("topik") or slot.get("judul") or "").strip()
    if not topik:
        raise ValueError("Slot 'topik' wajib diisi.")
    hook = str(slot.get("hook") or "").strip() or None
    sumber = slot.get("sumber_rekomendasi_id")
    sumber_id = None
    if sumber not in (None, ""):
        try:
            sumber_id = uuid.UUID(str(sumber))
        except ValueError as exc:
            raise ValueError("Slot 'sumber_rekomendasi_id' tidak valid.") from exc
    return {
        "judul": topik[:255],
        "platform": platform,
        "format": fmt,
        "tujuan": tujuan,
        "tanggal_rencana": tanggal,
        "status": PlannedPostStatus.TERJADWAL,
        "catatan": f"Hook: {hook}"[:2000] if hook else None,
        "rekomendasi_sumber_id": sumber_id,
    }


async def terima_alokasi(
    db: AsyncSession,
    *,
    brand: Brand,
    organization_id: uuid.UUID,
    created_by: uuid.UUID | None,
    slots: list[dict],
) -> int:
    """Buat planned_posts (status 'terjadwal') dari slot yang diterima.

    Return jumlah yang dibuat. Raise ValueError bila ada slot tidak valid.
    """
    if not isinstance(slots, list) or not slots:
        raise ValueError("Body 'slots' harus list yang tidak kosong.")
    dibuat = 0
    for slot in slots:
        data = _validasi_slot_terima(slot)
        if data["rekomendasi_sumber_id"] is not None:
            rec = await db.get(Recommendation, data["rekomendasi_sumber_id"])
            if rec is None or rec.brand_id != brand.id:
                raise ValueError("rekomendasi sumber tidak ditemukan untuk brand ini.")
        await create_planned(
            db,
            brand_id=brand.id,
            organization_id=organization_id,
            created_by=created_by,
            data=data,
        )
        dibuat += 1
    await db.flush()
    return dibuat


# ---------------------------------------------------------------------------
# Ringkasan (header target), ekspor, realisasi
# ---------------------------------------------------------------------------

CATATAN_ESTIMASI = (
    "Estimasi dari rata-rata historis konten sejenis ± deviasi; bukan angka pasti."
)


def _rentang_bulan(bulan: str) -> tuple[date, date]:
    try:
        tahun_s, bln_s = bulan.split("-")
        awal = date(int(tahun_s), int(bln_s), 1)
    except (ValueError, AttributeError) as exc:
        raise ValueError("Parameter bulan harus format YYYY-MM.") from exc
    akhir = date(awal.year + (1 if awal.month == 12 else 0), 1 if awal.month == 12 else awal.month + 1, 1)
    return awal, akhir


async def ringkasan_planner(db: AsyncSession, *, brand: Brand, bulan: str) -> dict:
    """Header target bulan: total rencana + estimasi views + target ER.

    Semua angka estimasi diberi label "estimasi" — bukan angka pasti.
    """
    awal, akhir = _rentang_bulan(bulan)
    rencana = (
        await db.execute(
            select(PlannedPost)
            .where(
                PlannedPost.brand_id == brand.id,
                PlannedPost.tanggal_rencana >= awal,
                PlannedPost.tanggal_rencana < akhir,
                PlannedPost.status != PlannedPostStatus.DIBATALKAN,
            )
            .order_by(PlannedPost.tanggal_rencana.asc())
        )
    ).scalars().all()

    _, menang = await _pola_menang(db, brand.id)

    vmin_total = vmax_total = 0
    ada_estimasi = False
    for post in rencana:
        vmin, vmax = _rentang_views(menang, post.format)
        if vmin is None:
            vmin, vmax = _rentang_views(menang, None)
        if vmin is not None:
            ada_estimasi = True
            vmin_total += vmin
            vmax_total += vmax or vmin

    return {
        "total_rencana": len(rencana),
        "estimasi_views_min": vmin_total if ada_estimasi else 0,
        "estimasi_views_max": vmax_total if ada_estimasi else 0,
        "target_er": _rata_wer(menang),
        "label": "estimasi",
        "catatan": CATATAN_ESTIMASI,
    }


async def daftar_rencana_bulan(
    db: AsyncSession, *, brand: Brand, bulan: str
) -> list[PlannedPost]:
    """Baris rencana untuk ekspor CSV/PDF (termasuk yang dibatalkan)."""
    awal, akhir = _rentang_bulan(bulan)
    return (
        await db.execute(
            select(PlannedPost)
            .where(
                PlannedPost.brand_id == brand.id,
                PlannedPost.tanggal_rencana >= awal,
                PlannedPost.tanggal_rencana < akhir,
            )
            .order_by(PlannedPost.tanggal_rencana.asc(), PlannedPost.created_at.asc())
        )
    ).scalars().all()


async def realisasi_planner(db: AsyncSession, *, brand: Brand, bulan: str) -> dict:
    """Bandingkan konten terbit vs slot rencana bulan itu.

    Cocok bila: selisih tanggal <= 3 hari DAN format sama DAN tujuan sama.
    """
    awal, akhir = _rentang_bulan(bulan)

    rencana = (
        await db.execute(
            select(PlannedPost)
            .where(
                PlannedPost.brand_id == brand.id,
                PlannedPost.tanggal_rencana >= awal,
                PlannedPost.tanggal_rencana < akhir,
                PlannedPost.status != PlannedPostStatus.DIBATALKAN,
            )
            .order_by(PlannedPost.tanggal_rencana.asc())
        )
    ).scalars().all()

    konten = (
        await db.execute(
            select(Content)
            .where(
                Content.brand_id == brand.id,
                Content.posted_at >= awal,
                Content.posted_at < akhir,
            )
            .order_by(Content.posted_at.asc())
        )
    ).scalars().all()

    skor_map: dict[uuid.UUID, ContentScore] = {}
    for c, s in await _skor_terbaru(db, brand.id):
        skor_map[c.id] = s

    def _wer(c: Content) -> float | None:
        s = skor_map.get(c.id)
        return _wer_dari_snapshot(s.metrics_snapshot) if s else None

    def _cocok(c: Content, p: PlannedPost) -> bool:
        return (
            abs((c.posted_at.date() - p.tanggal_rencana).days) <= 3
            and c.format == p.format
            and c.tujuan == p.tujuan
        )

    terpakai: set[uuid.UUID] = set()
    sesuai: list[Content] = []
    for c in konten:
        for p in rencana:
            if p.id not in terpakai and _cocok(c, p):
                terpakai.add(p.id)
                sesuai.append(c)
                break
    id_sesuai = {c.id for c in sesuai}
    di_luar = [c for c in konten if c.id not in id_sesuai]

    def _rata(cs: list[Content]) -> float | None:
        wers = [w for w in (_wer(c) for c in cs) if w is not None]
        return round(statistics.fmean(wers), 4) if wers else None

    rata_sesuai = _rata(sesuai)
    rata_luar = _rata(di_luar)

    rasio: float | None = None
    if rata_sesuai is not None and rata_luar:
        rasio = round(rata_sesuai / rata_luar, 2)

    if sesuai and di_luar and rasio is not None:
        rasio_teks = f"{rasio:.1f}".replace(".", ",")
        narasi = (
            f"Konten sesuai rencana ER-nya {rasio_teks}× dibanding di luar rencana."
        )
    elif sesuai and not di_luar:
        narasi = (
            f"Semua {len(sesuai)} konten terbit bulan ini sesuai rencana."
        )
    elif di_luar and not sesuai:
        narasi = (
            f"Belum ada konten terbit yang sesuai rencana bulan ini; "
            f"{len(di_luar)} konten di luar rencana."
        )
    else:
        narasi = "Belum ada konten terbit pada bulan ini."

    return {
        "sesuai_rencana": {"jumlah": len(sesuai), "rata_wer": rata_sesuai},
        "di_luar_rencana": {"jumlah": len(di_luar), "rata_wer": rata_luar},
        "rasio": rasio,
        "narasi": narasi,
    }
