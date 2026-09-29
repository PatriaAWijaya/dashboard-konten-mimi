"""Router modul konten: upload CSV, skoring, dashboard, analisa, rekomendasi, niche.

Semua endpoint org-scoped: header X-Organization-Id + get_org_context.
Setiap akses brand diverifikasi milik organisasi (404 bila tidak cocok).
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db, get_org_context, parse_org_header
from app.core.permissions import ROLE_EDITOR, ROLE_VIEWER
from app.models.brand import Brand
from app.models.content import (
    BrandDNACard,
    Content,
    ContentScore,
    NicheInterview,
    NicheSuggestion,
    Recommendation,
)
from app.models.user import User
from app.schemas.content import (
    AnalisaOut,
    CsvFormatColumn,
    CsvUploadOut,
    DashboardKartu,
    DashboardKontenItem,
    DashboardOut,
    DashboardTren,
    DnaOut,
    GenerateOut,
    InterviewDetailOut,
    InterviewStartOut,
    JawabIn,
    JawabOut,
    NicheOut,
    NicheSaranOut,
    PeriodeIn,
    PilihNicheIn,
    RecommendationOut,
    ScoreOut,
)
from app.services.csv_import import EXPECTED_COLUMNS, import_csv
from app.services.niche import (
    QUESTIONS,
    confirm_dna,
    save_answer,
    select_niches,
    start_interview,
    suggest_niches,
    synthesize_dna,
)
from app.services.recommendations import generate_recommendations, set_recommendation_status
from app.services.scoring import compute_weighted_er, run_scoring
from app.services.suitability import analisa_report

router = APIRouter(tags=["content"])

PLATFORM_VALID = ("tiktok", "instagram")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _get_brand(db: AsyncSession, brand_id: uuid.UUID, org_id: uuid.UUID) -> Brand:
    brand = await db.get(Brand, brand_id)
    if brand is None or brand.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand tidak ditemukan.")
    return brand


async def _get_interview(db: AsyncSession, iid: uuid.UUID, org_id: uuid.UUID) -> NicheInterview:
    interview = await db.get(NicheInterview, iid)
    if interview is None or interview.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wawancara tidak ditemukan."
        )
    return interview


async def _get_recommendation(db: AsyncSession, rec_id: uuid.UUID, org_id: uuid.UUID) -> Recommendation:
    rec = await db.get(Recommendation, rec_id)
    if rec is None or rec.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rekomendasi tidak ditemukan."
        )
    return rec


def _resolve_period(data: PeriodeIn) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    if data.preset == "7d":
        return today - timedelta(days=6), today
    if data.preset == "30d":
        return today - timedelta(days=29), today
    if data.preset == "bulan_ini":
        return today.replace(day=1), today
    assert data.start and data.end
    return data.start, data.end


def _periode_dari_query(
    preset: str | None, start: date | None, end: date | None
) -> PeriodeIn | None:
    if preset is None and start is None and end is None:
        return None
    return PeriodeIn(preset=preset or "30d", start=start, end=end)


# ---------------------------------------------------------------------------
# Upload CSV & dokumentasi kolom
# ---------------------------------------------------------------------------

_COLUMN_DOCS: dict[str, tuple[str, bool]] = {
    "platform": ("Nama platform: tiktok atau instagram.", True),
    "post_id": ("ID unik postingan dari platform (mis. ID video TikTok).", False),
    "post_url": ("URL publik postingan.", False),
    "tanggal_posting": ("Tanggal publikasi (YYYY-MM-DD).", True),
    "format": ("Format konten: carousel, reels, story, foto, live.", True),
    "tujuan": ("Tujuan konten: edukasi, hiburan, interaksi, jualan, branding.", True),
    "caption": ("Teks caption postingan.", False),
    "views": ("Jumlah views/tayangan.", True),
    "reach": ("Jumlah reach.", False),
    "likes": ("Jumlah likes.", False),
    "comments": ("Jumlah komentar.", False),
    "shares": ("Jumlah share.", False),
    "saves": ("Jumlah simpanan.", False),
    "avg_watch_seconds": ("Rata-rata detik tonton.", False),
    "profile_clicks": ("Jumlah klik profil.", False),
    "link_clicks": ("Jumlah klik tautan.", False),
    "replies": ("Jumlah balasan (replies).", False),
    "sticker_taps": ("Jumlah ketukan stiker (khusus story).", False),
}


def _kolom_dokumentasi() -> list[CsvFormatColumn]:
    hasil = []
    for col in EXPECTED_COLUMNS:
        if isinstance(col, str):
            nama, deskripsi, wajib = col, *_COLUMN_DOCS.get(col, ("Kolom data konten.", False))
        else:
            nama = str(col.get("nama", col))
            deskripsi, wajib = _COLUMN_DOCS.get(nama, ("Kolom data konten.", False))
            deskripsi = col.get("deskripsi", deskripsi)
            wajib = col.get("wajib", wajib)
        hasil.append(CsvFormatColumn(nama=nama, deskripsi=deskripsi, wajib=bool(wajib)))
    return hasil


@router.get("/content/csv-format", response_model=list[CsvFormatColumn])
async def csv_format():
    """Dokumentasi kolom CSV — publik (tanpa login/organisasi) agar halaman
    upload frontend selalu menampilkan dokumentasi yang akurat."""
    return _kolom_dokumentasi()


@router.post("/content/upload", response_model=CsvUploadOut)
async def upload_csv(
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    brand_id: Annotated[str, Form(description="ID brand tujuan.")],
    platform: Annotated[str, Form(description="Platform: tiktok atau instagram.")],
    file: Annotated[UploadFile, File(description="File CSV data konten.")],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Upload file CSV metrik konten untuk satu brand."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    try:
        brand_uuid = uuid.UUID(brand_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="brand_id tidak valid.")
    brand = await _get_brand(db, brand_uuid, ctx.organization.id)

    if platform not in PLATFORM_VALID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Platform tidak valid. Pilihan: {', '.join(PLATFORM_VALID)}.",
        )
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File harus berformat .csv."
        )
    blob = await file.read()
    if len(blob) > get_settings().max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Ukuran file melebihi batas {get_settings().MAX_UPLOAD_MB} MB.",
        )
    if not blob.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File CSV kosong."
        )

    hasil = await import_csv(
        db,
        brand=brand,
        organization_id=ctx.organization.id,
        platform=platform,
        file_bytes=blob,
        filename=file.filename or "upload.csv",
    )
    kolom = [c if isinstance(c, str) else str(c.get("nama", c)) for c in EXPECTED_COLUMNS]
    return CsvUploadOut(**hasil, kolom=kolom)


# ---------------------------------------------------------------------------
# Skoring
# ---------------------------------------------------------------------------

@router.post("/content/brands/{brand_id}/score", response_model=ScoreOut)
async def score_brand(
    brand_id: Annotated[uuid.UUID, Path()],
    data: PeriodeIn,
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Jalankan skoring konten brand untuk satu periode."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    awal, akhir = _resolve_period(data)
    skor = await run_scoring(
        db, brand=brand, organization_id=ctx.organization.id,
        period_start=awal, period_end=akhir,
    )
    return ScoreOut(
        diskor=len(skor), periode={"mulai": awal.isoformat(), "selesai": akhir.isoformat()}
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/content/brands/{brand_id}/dashboard", response_model=DashboardOut)
async def brand_dashboard(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    preset: Annotated[str | None, Query(description="Preset: 7d, 30d, bulan_ini, custom.")] = "30d",
    start: Annotated[date | None, Query(description="Tanggal mulai (custom).")] = None,
    end: Annotated[date | None, Query(description="Tanggal selesai (custom).")] = None,
):
    """Dashboard agregat: kartu per platform, tren mingguan, daftar konten."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_VIEWER)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    periode = _periode_dari_query(preset, start, end) or PeriodeIn()
    awal, akhir = _resolve_period(periode)
    mulai_dt = datetime(awal.year, awal.month, awal.day, tzinfo=timezone.utc)
    selesai_dt = datetime(akhir.year, akhir.month, akhir.day, tzinfo=timezone.utc) + timedelta(days=1)

    contents = (
        await db.execute(
            select(Content)
            .where(
                Content.brand_id == brand.id,
                Content.posted_at >= mulai_dt,
                Content.posted_at < selesai_dt,
            )
            .order_by(Content.posted_at.desc())
        )
    ).scalars().all()
    cids = [c.id for c in contents]
    skor_rows = []
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
    # Skor terbaru per konten (period_end terbesar).
    skor_terbaru: dict = {}
    for s in skor_rows:
        lama = skor_terbaru.get(s.content_id)
        if lama is None or (s.period_end, s.period_start) > (lama.period_end, lama.period_start):
            skor_terbaru[s.content_id] = s

    kartu_data: dict[str, dict] = {}
    tren_data: dict[int, dict] = {}
    konten: list[DashboardKontenItem] = []
    for content in contents:
        skor = skor_terbaru.get(content.id)
        nilai_skor = float(skor.score) if skor and skor.score is not None else None
        snap = dict(skor.metrics_snapshot or {}) if skor else {}
        views = int(snap.get("views") or 0)
        wer = compute_weighted_er(
            float(snap.get("likes") or 0),
            float(snap.get("comments") or 0),
            float(snap.get("shares") or 0),
            float(snap.get("saves") or 0),
            float(views),
        )
        status_skor = skor.status if skor else "belum_diskor"

        plat = (content.platform or "lainnya").lower()
        k = kartu_data.setdefault(
            plat, {"n": 0, "skor": 0.0, "wer": 0.0, "menang": 0, "cukup": 0, "kurang": 0}
        )
        k["n"] += 1
        if nilai_skor is not None:
            k["skor"] += nilai_skor
        k["wer"] += wer
        if status_skor in ("menang", "cukup", "kurang"):
            k[status_skor] += 1

        posted = content.posted_at
        if posted:
            idx = max((posted.date() - awal).days, 0) // 7
            t = tren_data.setdefault(idx, {"n": 0, "skor": 0.0, "wer": 0.0})
            t["n"] += 1
            if nilai_skor is not None:
                t["skor"] += nilai_skor
            t["wer"] += wer

        konten.append(
            DashboardKontenItem(
                content_id=content.id,
                post_id=str(content.post_id),
                platform=content.platform,
                format=content.format,
                tujuan=content.tujuan,
                posted_at=content.posted_at,
                views=views,
                wer=round(wer, 4),
                score=nilai_skor,
                status=status_skor,
                labels=list(skor.labels or []) if skor else [],
            )
        )

    kartu = {
        plat: DashboardKartu(
            jumlah_konten=v["n"],
            rata_skor=round(v["skor"] / v["n"], 2) if v["n"] else 0.0,
            rata_wer=round(v["wer"] / v["n"], 2) if v["n"] else 0.0,
            menang=v["menang"],
            cukup=v["cukup"],
            kurang=v["kurang"],
        )
        for plat, v in kartu_data.items()
    }
    tren = [
        DashboardTren(
            label=f"W{idx + 1}",
            rata_skor=round(v["skor"] / v["n"], 2) if v["n"] else 0.0,
            rata_wer=round(v["wer"] / v["n"], 2) if v["n"] else 0.0,
        )
        for idx, v in sorted(tren_data.items())
    ]
    return DashboardOut(kartu=kartu, tren=tren, konten=konten)


# ---------------------------------------------------------------------------
# Analisa kesesuaian
# ---------------------------------------------------------------------------

@router.get("/content/brands/{brand_id}/analisa", response_model=AnalisaOut)
async def brand_analisa(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    preset: Annotated[str | None, Query(description="Preset: 7d, 30d, bulan_ini, custom.")] = "30d",
    start: Annotated[date | None, Query(description="Tanggal mulai (custom).")] = None,
    end: Annotated[date | None, Query(description="Tanggal selesai (custom).")] = None,
):
    """Laporan analisa kesesuaian pola konten (rule-based)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_VIEWER)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    periode = _periode_dari_query(preset, start, end) or PeriodeIn()
    awal, akhir = _resolve_period(periode)
    hasil = await analisa_report(
        db, brand=brand, organization_id=ctx.organization.id,
        period_start=awal, period_end=akhir,
    )
    return AnalisaOut(
        ringkasan=hasil.get("ringkasan") or [],
        bermasalah=hasil.get("bermasalah") or [],
        rekomendasi_pola=hasil.get("rekomendasi_pola") or [],
    )


# ---------------------------------------------------------------------------
# Rekomendasi
# ---------------------------------------------------------------------------

@router.get(
    "/content/brands/{brand_id}/recommendations",
    response_model=list[RecommendationOut],
)
async def list_recommendations(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    preset: Annotated[str | None, Query(description="Filter periode opsional.")] = None,
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
):
    """Daftar rekomendasi brand (opsional filter periode)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_VIEWER)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    q = select(Recommendation).where(Recommendation.brand_id == brand.id)
    periode = _periode_dari_query(preset, start, end)
    if periode is not None:
        awal, akhir = _resolve_period(periode)
        q = q.where(Recommendation.period_start == awal, Recommendation.period_end == akhir)
    rows = (await db.execute(q.order_by(Recommendation.created_at.desc()).limit(50))).scalars().all()
    return [RecommendationOut.model_validate(r) for r in rows]


@router.post(
    "/content/brands/{brand_id}/recommendations/generate",
    response_model=GenerateOut,
)
async def generate_brand_recommendations(
    brand_id: Annotated[uuid.UUID, Path()],
    data: PeriodeIn,
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Hasilkan rekomendasi baru (ada cache + anti-duplikat penolakan)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    awal, akhir = _resolve_period(data)
    hasil = await generate_recommendations(
        db, brand=brand, organization_id=ctx.organization.id,
        period_start=awal, period_end=akhir,
    )
    if not hasil:
        return GenerateOut(
            dibuat=[],
            pesan="Data belum cukup (butuh ≥10 konten per periode).",
        )
    return GenerateOut(
        dibuat=[RecommendationOut.model_validate(r) for r in hasil], pesan=None
    )


@router.post("/content/recommendations/{rec_id}/terima", response_model=RecommendationOut)
async def terima_rekomendasi(
    rec_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Tandai rekomendasi sebagai diterima."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    rec = await _get_recommendation(db, rec_id, ctx.organization.id)
    await set_recommendation_status(db, rec, "diterima")
    return RecommendationOut.model_validate(rec)


@router.post("/content/recommendations/{rec_id}/tolak", response_model=RecommendationOut)
async def tolak_rekomendasi(
    rec_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Tandai rekomendasi sebagai ditolak (tidak akan dibuat ulang)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    rec = await _get_recommendation(db, rec_id, ctx.organization.id)
    await set_recommendation_status(db, rec, "ditolak")
    return RecommendationOut.model_validate(rec)


# ---------------------------------------------------------------------------
# Niche finder
# ---------------------------------------------------------------------------

@router.post(
    "/content/brands/{brand_id}/niche/interviews",
    response_model=InterviewStartOut,
    status_code=status.HTTP_201_CREATED,
)
async def mulai_wawancara(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mulai (atau lanjutkan) wawancara niche 8 pertanyaan."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    interview = await start_interview(
        db, brand=brand, organization_id=ctx.organization.id, user_id=user.id
    )
    berikut = QUESTIONS[interview.current_step] if interview.current_step < len(QUESTIONS) else None
    return InterviewStartOut(
        id=interview.id,
        status=interview.status,
        current_step=interview.current_step,
        pertanyaan_berikut=berikut,
    )


@router.get("/content/niche/interviews/{iid}", response_model=InterviewDetailOut)
async def detail_wawancara(
    iid: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Detail wawancara + 8 pertanyaan dan panduan menjawab."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_VIEWER)
    interview = await _get_interview(db, iid, ctx.organization.id)
    answers = {k: v for k, v in (interview.answers or {}).items() if k != "_followup"}
    return InterviewDetailOut(
        id=interview.id,
        status=interview.status,
        current_step=interview.current_step,
        answers=answers,
        skipped=list(interview.skipped or []),
        questions=QUESTIONS,
    )


@router.post("/content/niche/interviews/{iid}/jawab", response_model=JawabOut)
async def jawab_wawancara(
    iid: Annotated[uuid.UUID, Path()],
    data: JawabIn,
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Simpan jawaban satu langkah (bisa dilewati; jawaban pendek diminta elaborasi)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    interview = await _get_interview(db, iid, ctx.organization.id)
    try:
        hasil = await save_answer(
            db, interview=interview, step=data.step,
            answer=data.jawaban, skipped=data.dilewati,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    berikut = QUESTIONS[hasil["next_step"]] if hasil["next_step"] < len(QUESTIONS) else None
    return JawabOut(status=hasil["status"], next_step=hasil["next_step"], pertanyaan_berikut=berikut)


@router.post("/content/niche/interviews/{iid}/sintesis", response_model=DnaOut)
async def sintesis_wawancara(
    iid: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Susun draf kartu DNA dari jawaban wawancara (perlu konfirmasi)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    interview = await _get_interview(db, iid, ctx.organization.id)
    brand = await _get_brand(db, interview.brand_id, ctx.organization.id)
    try:
        dna = await synthesize_dna(
            db, interview=interview, brand=brand, organization_id=ctx.organization.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return DnaOut.model_validate(dna)


@router.put("/content/niche/dna/{dna_id}/konfirmasi", response_model=DnaOut)
async def konfirmasi_dna(
    dna_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Konfirmasi kartu DNA brand."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    dna = await db.get(BrandDNACard, dna_id)
    if dna is None or dna.organization_id != ctx.organization.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kartu DNA tidak ditemukan."
        )
    await confirm_dna(db, dna)
    return DnaOut.model_validate(dna)


@router.get("/content/brands/{brand_id}/niche/saran", response_model=NicheSaranOut)
async def saran_niche(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Daftar saran niche; dibuat otomatis bila belum ada dan DNA sudah dikonfirmasi."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_VIEWER)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    rows = (
        await db.execute(
            select(NicheSuggestion)
            .where(NicheSuggestion.brand_id == brand.id)
            .order_by(NicheSuggestion.match_percent.desc())
        )
    ).scalars().all()
    dibuat_baru = False
    if not rows:
        dna = (
            await db.execute(
                select(BrandDNACard)
                .where(BrandDNACard.brand_id == brand.id, BrandDNACard.confirmed.is_(True))
                .order_by(BrandDNACard.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if dna is not None:
            try:
                rows = await suggest_niches(
                    db, brand=brand, organization_id=ctx.organization.id, dna=dna
                )
                dibuat_baru = True
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return NicheSaranOut(
        saran=[NicheOut.model_validate(r) for r in rows], dibuat_baru=dibuat_baru
    )


@router.post("/content/brands/{brand_id}/niche/pilih", response_model=list[NicheOut])
async def pilih_niche(
    brand_id: Annotated[uuid.UUID, Path()],
    data: PilihNicheIn,
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Pilih 1-2 niche untuk difokuskan."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    try:
        hasil = await select_niches(
            db, brand=brand, organization_id=ctx.organization.id, ids=list(data.ids)
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return [NicheOut.model_validate(r) for r in hasil]
