"""Router Fase 2: koneksi OAuth, sinkronisasi, planner, undangan, ringkasan,
notifikasi, dan pengaturan admin.

Konvensi mengikuti routers/content.py: org-scoped via header
X-Organization-Id + get_org_context; setiap akses brand/akun diverifikasi
milik organisasi (404 bila tidak cocok).
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import (
    get_current_user,
    get_db,
    get_org_context,
    parse_org_header,
    require_superadmin,
)
from app.core.permissions import ROLE_ADMIN, ROLE_EDITOR
from app.models.brand import Brand
from app.models.fase2 import (
    AppSetting,
    ConnectedAccount,
    Invitation,
    PlannedPost,
    PlannerConfig,
    Summary,
)
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.fase2 import (
    AlokasiGenerateIn,
    AlokasiGenerateOut,
    AlokasiTerimaIn,
    AlokasiTerimaOut,
    KoneksiOut,
    KoneksiStatusOut,
    OAuthMulaiOut,
    PengaturanIn,
    PengaturanItem,
    PlannedPostIn,
    PlannedPostOut,
    PlannedPostUpdate,
    PlannerKonfigurasiIn,
    PlannerKonfigurasiOut,
    PreferensiIn,
    PreferensiOut,
    RealisasiOut,
    RingkasanOut,
    RingkasanPlannerOut,
    SlotOut,
    SyncOut,
    TerimaUndanganOut,
    UndanganIn,
    UndanganOut,
)
from app.services import invitations as invitation_service
from app.services import planner as planner_service
from app.services import allocator as allocator_service
from app.services.notifications import get_or_create_preference
from app.services.settings import get_setting, set_setting
from app.services.summaries import get_or_generate_summary
from app.services.sync_service import (
    AccountLimitExceeded,
    CredentialsNotConfigured,
    count_accounts,
    get_max_accounts_per_platform,
    handle_oauth_callback,
    start_oauth,
    sync_account,
)

router = APIRouter(tags=["fase2"])

PLATFORM_VALID = ("tiktok", "instagram")


def _now():
    return datetime.now(timezone.utc)


async def _get_brand(db: AsyncSession, brand_id: uuid.UUID, org_id: uuid.UUID) -> Brand:
    brand = await db.get(Brand, brand_id)
    if brand is None or brand.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand tidak ditemukan.")
    return brand


async def _get_koneksi(db: AsyncSession, conn_id: uuid.UUID, org_id: uuid.UUID) -> ConnectedAccount:
    conn = await db.get(ConnectedAccount, conn_id)
    if conn is None or conn.organization_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Koneksi tidak ditemukan.")
    return conn


async def _get_planned(db: AsyncSession, post_id: uuid.UUID, org_id: uuid.UUID) -> PlannedPost:
    post = await db.get(PlannedPost, post_id)
    if post is None or post.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rencana konten tidak ditemukan."
        )
    return post


# ---------------------------------------------------------------------------
# OAuth & koneksi
# ---------------------------------------------------------------------------

@router.post(
    "/content/brands/{brand_id}/oauth/{platform}/mulai",
    response_model=OAuthMulaiOut,
)
async def oauth_mulai(
    brand_id: Annotated[uuid.UUID, Path()],
    platform: Annotated[str, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mulai koneksi OAuth → {auth_url}. 501 bila kredensial admin belum diset."""
    if platform not in PLATFORM_VALID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Platform '{platform}' tidak didukung. Pilihan: tiktok, instagram.",
        )
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    try:
        hasil = await start_oauth(db, brand, platform, user)
    except CredentialsNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    return OAuthMulaiOut(auth_url=hasil["auth_url"])


@router.get("/content/oauth/callback")
async def oauth_callback(
    db: Annotated[AsyncSession, Depends(get_db)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
):
    """Callback OAuth dari provider → redirect 302 ke frontend.

    501 (JSON, tanpa redirect) bila kredensial admin belum dikonfigurasi —
    frontend menangkap 501/503 sebagai sinyal "kredensial belum disiapkan".
    """
    settings = get_settings()
    if not code or not state:
        url = f"{settings.FRONTEND_URL}/koneksi?status=gagal"
        return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)
    try:
        hasil = await handle_oauth_callback(db, code, state)
    except CredentialsNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    except AccountLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValueError:
        url = f"{settings.FRONTEND_URL}/koneksi?status=gagal"
        return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)
    url = (
        f"{settings.FRONTEND_URL}/brand/{hasil['brand_id']}"
        f"/koneksi?status=ok&platform={hasil['platform']}"
    )
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/content/brands/{brand_id}/koneksi",
    response_model=list[KoneksiOut],
)
async def list_koneksi(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Daftar akun terhubung milik brand."""
    ctx = await get_org_context(db, user, org_id)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    rows = (
        await db.execute(
            select(ConnectedAccount)
            .where(ConnectedAccount.brand_id == brand.id)
            .order_by(ConnectedAccount.created_at.desc())
        )
    ).scalars().all()
    return [
        KoneksiOut(
            id=c.id,
            platform=c.platform,
            account_name=c.account_name,
            status=c.status,
            last_sync_at=c.last_sync_at,
            connected_at=c.created_at,
        )
        for c in rows
    ]


@router.post("/content/koneksi/{conn_id}/sync", response_model=SyncOut)
async def sync_koneksi(
    conn_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Sinkronisasi konten dari akun terhubung (min editor)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    conn = await _get_koneksi(db, conn_id, ctx.organization.id)
    try:
        hasil = await sync_account(db, conn)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — status akun sudah diset "error"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Sinkronisasi gagal: {exc}.",
        )
    return SyncOut(**hasil)


@router.delete("/content/koneksi/{conn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def hapus_koneksi(
    conn_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Putuskan koneksi akun (min admin). Token terenkripsi ikut terhapus."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_ADMIN)
    conn = await _get_koneksi(db, conn_id, ctx.organization.id)
    await db.delete(conn)
    await db.flush()
    return None


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

@router.get(
    "/content/brands/{brand_id}/planner",
    response_model=list[PlannedPostOut],
)
async def planner_list(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    bulan: Annotated[str | None, Query(description="Filter bulan: YYYY-MM.")] = None,
):
    """Daftar rencana konten brand (opsional filter bulan)."""
    ctx = await get_org_context(db, user, org_id)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    try:
        rows = await planner_service.list_planned(
            db, brand_id=brand.id, organization_id=ctx.organization.id, bulan=bulan
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return [PlannedPostOut.model_validate(r) for r in rows]


@router.post(
    "/content/brands/{brand_id}/planner",
    response_model=PlannedPostOut,
    status_code=status.HTTP_201_CREATED,
)
async def planner_create(
    brand_id: Annotated[uuid.UUID, Path()],
    data: PlannedPostIn,
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Tambah rencana konten (min editor)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    try:
        post = await planner_service.create_planned(
            db,
            brand_id=brand.id,
            organization_id=ctx.organization.id,
            created_by=user.id,
            data=data.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PlannedPostOut.model_validate(post)


@router.put("/content/planner/{post_id}", response_model=PlannedPostOut)
async def planner_update(
    post_id: Annotated[uuid.UUID, Path()],
    data: PlannedPostUpdate,
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Ubah rencana konten (min editor)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    post = await _get_planned(db, post_id, ctx.organization.id)
    try:
        post = await planner_service.update_planned(db, post=post, data=data.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PlannedPostOut.model_validate(post)


@router.delete("/content/planner/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def planner_delete(
    post_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Hapus rencana konten (min editor)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    post = await _get_planned(db, post_id, ctx.organization.id)
    await planner_service.delete_planned(db, post=post)
    return None


# ---------------------------------------------------------------------------
# Status multi-akun per platform
# ---------------------------------------------------------------------------

@router.get(
    "/content/brands/{brand_id}/koneksi/status",
    response_model=KoneksiStatusOut,
)
async def koneksi_status(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Status pemakaian slot akun per platform: {terpakai, batas, boleh_tambah}."""
    ctx = await get_org_context(db, user, org_id)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    batas = await get_max_accounts_per_platform(db)
    platforms = {}
    for platform in PLATFORM_VALID:
        terpakai = await count_accounts(db, brand.id, platform)
        platforms[platform] = {
            "terpakai": terpakai,
            "batas": batas,
            "boleh_tambah": terpakai < batas,
        }
    return KoneksiStatusOut(platforms=platforms)


# ---------------------------------------------------------------------------
# Konfigurasi planner per brand
# ---------------------------------------------------------------------------

@router.get(
    "/content/brands/{brand_id}/planner/konfigurasi",
    response_model=PlannerKonfigurasiOut,
)
async def baca_konfigurasi_planner(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Baca konfigurasi alokasi planner brand (dibuat dengan default bila belum ada)."""
    ctx = await get_org_context(db, user, org_id)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    cfg = await allocator_service.get_or_create_planner_config(
        db, brand=brand, organization_id=ctx.organization.id
    )
    return PlannerKonfigurasiOut.model_validate(cfg)


@router.put(
    "/content/brands/{brand_id}/planner/konfigurasi",
    response_model=PlannerKonfigurasiOut,
)
async def ubah_konfigurasi_planner(
    brand_id: Annotated[uuid.UUID, Path()],
    data: PlannerKonfigurasiIn,
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Ubah konfigurasi alokasi planner brand (min editor)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    cfg = await allocator_service.get_or_create_planner_config(
        db, brand=brand, organization_id=ctx.organization.id
    )
    try:
        cfg = await allocator_service.update_planner_config(
            db, config=cfg, data=data.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PlannerKonfigurasiOut.model_validate(cfg)


# ---------------------------------------------------------------------------
# Alokasi planner (generate preview + terima)
# ---------------------------------------------------------------------------

@router.post(
    "/content/brands/{brand_id}/planner/alokasi/generate",
    response_model=AlokasiGenerateOut,
)
async def alokasi_generate(
    brand_id: Annotated[uuid.UUID, Path()],
    data: AlokasiGenerateIn,
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Preview alokasi slot mingguan dari rekomendasi yang diterima (min editor).

    TANPA menyimpan apa pun — hasilnya dikembalikan untuk ditinjau.
    Deterministik: input sama -> output sama.
    """
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    try:
        hasil = await allocator_service.generate_alokasi(db, brand=brand, minggu=data.minggu)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return AlokasiGenerateOut(
        slots=[SlotOut(**s) for s in hasil["slots"]],
        info=hasil["info"],
    )


@router.post(
    "/content/brands/{brand_id}/planner/alokasi/terima",
    response_model=AlokasiTerimaOut,
)
async def alokasi_terima(
    brand_id: Annotated[uuid.UUID, Path()],
    data: AlokasiTerimaIn,
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Terima preview alokasi -> buat planned_posts berstatus 'terjadwal' (min editor)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    try:
        dibuat = await allocator_service.terima_alokasi(
            db,
            brand=brand,
            organization_id=ctx.organization.id,
            created_by=user.id,
            slots=data.slots,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return AlokasiTerimaOut(dibuat=dibuat)


# ---------------------------------------------------------------------------
# Ringkasan header target, ekspor CSV/PDF, realisasi
# ---------------------------------------------------------------------------

@router.get(
    "/content/brands/{brand_id}/planner/ringkasan",
    response_model=RingkasanPlannerOut,
)
async def planner_ringkasan(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    bulan: Annotated[str, Query(description="Bulan: YYYY-MM.")],
):
    """Header target bulan: total rencana + estimasi views (rentang) + target ER.

    Semua angka diberi label "estimasi" — bukan angka pasti.
    """
    ctx = await get_org_context(db, user, org_id)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    try:
        hasil = await allocator_service.ringkasan_planner(db, brand=brand, bulan=bulan)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return RingkasanPlannerOut(**hasil)


@router.get("/content/brands/{brand_id}/planner/export.csv")
async def planner_export_csv(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    bulan: Annotated[str, Query(description="Bulan: YYYY-MM.")],
):
    """Unduh rencana bulan sebagai CSV."""
    import csv
    import io

    from fastapi.responses import Response

    ctx = await get_org_context(db, user, org_id)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    try:
        rows = await allocator_service.daftar_rencana_bulan(db, brand=brand, bulan=bulan)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["tanggal", "platform", "format", "tujuan", "judul", "status"])
    for r in rows:
        writer.writerow(
            [r.tanggal_rencana.isoformat(), r.platform or "",
             r.format, r.tujuan, r.judul, r.status]
        )
    nama = f"planner-{bulan}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nama}"'},
    )


def _pdf_sanitize(teks: str | None) -> str:
    """fpdf2 font inti hanya latin-1: ganti karakter bermasalah."""
    t = str(teks or "")
    return (
        t.replace("—", "-")
        .replace("–", "-")
        .replace("×", "x")
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


@router.get("/content/brands/{brand_id}/planner/export.pdf")
async def planner_export_pdf(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    bulan: Annotated[str, Query(description="Bulan: YYYY-MM.")],
):
    """Unduh rencana bulan sebagai PDF (tabel sederhana + label estimasi)."""
    from fastapi.responses import Response
    from fpdf import FPDF

    ctx = await get_org_context(db, user, org_id)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    try:
        rows = await allocator_service.daftar_rencana_bulan(db, brand=brand, bulan=bulan)
        ringkasan = await allocator_service.ringkasan_planner(db, brand=brand, bulan=bulan)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _pdf_sanitize(f"Rencana Konten - {brand.name} - {bulan}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0, 7,
        _pdf_sanitize(
            f"Total rencana: {ringkasan['total_rencana']} | "
            f"Estimasi views: {ringkasan['estimasi_views_min']}-{ringkasan['estimasi_views_max']} | "
            f"Target ER: {ringkasan['target_er'] if ringkasan['target_er'] is not None else '-'}"
        ),
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 7, _pdf_sanitize(f"Label: {ringkasan['label']} - {ringkasan['catatan']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    kolom = [("Tanggal", 28), ("Platform", 26), ("Format", 26), ("Tujuan", 26), ("Judul", 120), ("Status", 28)]
    pdf.set_font("Helvetica", "B", 10)
    for judul, lebar in kolom:
        pdf.cell(lebar, 8, _pdf_sanitize(judul), border=1)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for r in rows:
        pdf.cell(kolom[0][1], 7, _pdf_sanitize(r.tanggal_rencana.isoformat()), border=1)
        pdf.cell(kolom[1][1], 7, _pdf_sanitize(r.platform or "-"), border=1)
        pdf.cell(kolom[2][1], 7, _pdf_sanitize(r.format), border=1)
        pdf.cell(kolom[3][1], 7, _pdf_sanitize(r.tujuan), border=1)
        pdf.cell(kolom[4][1], 7, _pdf_sanitize(r.judul[:70]), border=1)
        pdf.cell(kolom[5][1], 7, _pdf_sanitize(r.status), border=1)
        pdf.ln()

    nama = f"planner-{bulan}.pdf"
    return Response(
        content=bytes(pdf.output()),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nama}"'},
    )


@router.get(
    "/content/brands/{brand_id}/planner/realisasi",
    response_model=RealisasiOut,
)
async def planner_realisasi(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    bulan: Annotated[str, Query(description="Bulan: YYYY-MM.")],
):
    """Bandingkan konten terbit vs rencana bulan itu (toleransi tanggal ±3 hari).

    Narasi rasio hanya bila kedua sisi punya data; bila tidak, disampaikan
    apa adanya.
    """
    ctx = await get_org_context(db, user, org_id)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    try:
        hasil = await allocator_service.realisasi_planner(db, brand=brand, bulan=bulan)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return RealisasiOut(**hasil)


# ---------------------------------------------------------------------------
# Undangan organisasi
# ---------------------------------------------------------------------------

@router.post(
    "/organizations/{org_id}/undangan",
    response_model=UndanganOut,
    status_code=status.HTTP_201_CREATED,
)
async def buat_undangan(
    org_id: Annotated[uuid.UUID, Path()],
    data: UndanganIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Buat undangan gabung organisasi (min admin). Token dikirim terpisah."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_ADMIN)
    try:
        inv, _token = await invitation_service.create_invite(
            db, org=ctx.organization, email=data.email, role=data.role, invited_by=user
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return UndanganOut.model_validate(inv)


@router.get(
    "/organizations/{org_id}/undangan",
    response_model=list[UndanganOut],
)
async def daftar_undangan(
    org_id: Annotated[uuid.UUID, Path()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Daftar undangan pending (min admin)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_ADMIN)
    rows = await invitation_service.list_pending(db, organization_id=ctx.organization.id)
    return [UndanganOut.model_validate(r) for r in rows]


@router.delete(
    "/organizations/{org_id}/undangan/{undangan_id}",
    response_model=MessageResponse,
)
async def batalkan_undangan(
    org_id: Annotated[uuid.UUID, Path()],
    undangan_id: Annotated[uuid.UUID, Path()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Batalkan undangan pending (min admin)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_ADMIN)
    inv = await db.get(Invitation, undangan_id)
    if inv is None or inv.organization_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Undangan tidak ditemukan.")
    try:
        await invitation_service.cancel_invite(db, invitation=inv)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return MessageResponse(message="Undangan dibatalkan.")


@router.post("/undangan/{token}/terima", response_model=TerimaUndanganOut)
async def terima_undangan(
    token: Annotated[str, Path()],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Terima undangan (user wajib login; tanpa header organisasi)."""
    try:
        member = await invitation_service.accept_invite(db, token=token, user=user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return TerimaUndanganOut(organization_id=member.organization_id, role=member.role)


# ---------------------------------------------------------------------------
# Ringkasan
# ---------------------------------------------------------------------------

def _periode_minggu(minggu: date) -> tuple[date, date]:
    return minggu, minggu + timedelta(days=6)


@router.get(
    "/content/brands/{brand_id}/ringkasan",
    response_model=RingkasanOut,
    response_model_exclude_none=True,
)
async def baca_ringkasan(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    minggu: Annotated[date, Query(description="Tanggal awal minggu (YYYY-MM-DD).")],
):
    """Baca ringkasan mingguan (cached). {"ada": false} bila belum ada."""
    ctx = await get_org_context(db, user, org_id)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    awal, akhir = _periode_minggu(minggu)
    summary = await db.scalar(
        select(Summary).where(
            Summary.brand_id == brand.id,
            Summary.period_start == awal,
            Summary.period_end == akhir,
        )
    )
    if summary is None:
        return RingkasanOut(ada=False)
    return RingkasanOut(
        ada=True,
        id=summary.id,
        teks=summary.teks,
        period_start=summary.period_start,
        period_end=summary.period_end,
        created_at=summary.created_at,
    )


@router.post(
    "/content/brands/{brand_id}/ringkasan/generate",
    response_model=RingkasanOut,
)
async def generate_ringkasan(
    brand_id: Annotated[uuid.UUID, Path()],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    minggu: Annotated[date | None, Query(description="Tanggal awal minggu (YYYY-MM-DD). Default: Senin pekan berjalan.")] = None,
):
    """Generate (atau ambil dari cache) ringkasan mingguan (min editor)."""
    ctx = await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)
    brand = await _get_brand(db, brand_id, ctx.organization.id)
    if minggu is None:
        minggu = date.today() - timedelta(days=date.today().weekday())
    awal, akhir = _periode_minggu(minggu)
    summary = await get_or_generate_summary(
        db,
        brand=brand,
        organization_id=ctx.organization.id,
        period_start=awal,
        period_end=akhir,
    )
    return RingkasanOut(
        ada=True,
        id=summary.id,
        teks=summary.teks,
        period_start=summary.period_start,
        period_end=summary.period_end,
        created_at=summary.created_at,
    )


# ---------------------------------------------------------------------------
# Preferensi notifikasi (user sendiri)
# ---------------------------------------------------------------------------

@router.get("/notifikasi/preferensi", response_model=PreferensiOut)
async def baca_preferensi(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Baca preferensi notifikasi milik sendiri."""
    pref = await get_or_create_preference(db, user.id)
    return PreferensiOut(
        rekomendasi_baru=pref.rekomendasi_baru,
        ringkasan_mingguan=pref.ringkasan_mingguan,
    )


@router.put("/notifikasi/preferensi", response_model=PreferensiOut)
async def ubah_preferensi(
    data: PreferensiIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Ubah preferensi notifikasi milik sendiri."""
    pref = await get_or_create_preference(db, user.id)
    if data.rekomendasi_baru is not None:
        pref.rekomendasi_baru = data.rekomendasi_baru
    if data.ringkasan_mingguan is not None:
        pref.ringkasan_mingguan = data.ringkasan_mingguan
    await db.flush()
    return PreferensiOut(
        rekomendasi_baru=pref.rekomendasi_baru,
        ringkasan_mingguan=pref.ringkasan_mingguan,
    )


# ---------------------------------------------------------------------------
# Pengaturan admin (superadmin)
# ---------------------------------------------------------------------------

PENGATURAN_KEYS: tuple[tuple[str, str], ...] = (
    ("tiktok_client_key", "TikTok Client Key"),
    ("tiktok_client_secret", "TikTok Client Secret"),
    ("instagram_app_id", "Instagram App ID"),
    ("instagram_app_secret", "Instagram App Secret"),
    ("whatsapp_provider", "Provider WhatsApp (mis. fonnte)"),
    ("whatsapp_api_key", "WhatsApp API Key"),
    ("llm_api_key", "LLM API Key"),
    ("max_accounts_per_platform", "Batas akun per platform per brand (default 3)"),
)
_PENGATURAN_ALLOWED = {k for k, _ in PENGATURAN_KEYS}


@router.get("/admin/pengaturan", response_model=list[PengaturanItem])
async def daftar_pengaturan(
    admin: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Daftar kunci pengaturan + status terisi (superadmin). Nilai tidak dikembalikan."""
    items = []
    for key, label in PENGATURAN_KEYS:
        row = await db.get(AppSetting, key)
        items.append(
            PengaturanItem(
                key=key,
                label=label,
                configured=row is not None,
                updated_at=row.updated_at if row else None,
            )
        )
    return items


@router.put("/admin/pengaturan", response_model=MessageResponse)
async def simpan_pengaturan(
    data: PengaturanIn,
    admin: Annotated[User, Depends(require_superadmin)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Simpan pengaturan terenkripsi (superadmin). value null/kosong = hapus."""
    key = (data.key or "").strip()
    if key not in _PENGATURAN_ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kunci '{data.key}' tidak dikenal.",
        )
    await set_setting(db, key, data.value)
    if data.value:
        return MessageResponse(message=f"Pengaturan '{key}' disimpan.")
    return MessageResponse(message=f"Pengaturan '{key}' dihapus.")
