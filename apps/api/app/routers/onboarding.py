"""Router onboarding: progres per brand, template threshold per kategori
industri, pratinjau kemenangan, profil brand, dan upload logo."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import (
    OrgContext,
    get_current_user,
    get_db,
    get_org_context,
    parse_org_header,
)
from app.core.permissions import ROLE_EDITOR
from app.models.brand import Brand
from app.models.onboarding import OnboardingProgress
from app.schemas.onboarding import (
    BrandProfilOut,
    LogoOut,
    OnboardingStatusOut,
    PreviewOut,
    PreviewRequest,
    ProfilBrandRequest,
    ProgressRequest,
    SelesaiRequest,
    TemplateThresholdOut,
    TutupRequest,
)
from app.services import onboarding as onboarding_service
from app.services.storage import get_storage_service
from app.models.user import User

router = APIRouter(tags=["onboarding"])

# Ekstensi gambar yang diizinkan untuk logo brand.
_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "svg"}


async def _ctx(
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrgContext:
    return await get_org_context(db, user, org_id, min_role=ROLE_EDITOR)


async def _brand_milik_org(db: AsyncSession, ctx: OrgContext, brand_id: uuid.UUID) -> Brand:
    brand = await db.get(Brand, brand_id)
    if brand is None or brand.organization_id != ctx.organization.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Brand tidak ditemukan."
        )
    return brand


def _status_out(progress: OnboardingProgress | None) -> OnboardingStatusOut:
    if progress is None:
        return OnboardingStatusOut(ada=False, langkah_terakhir=0, selesai=False, ditutup=False)
    return OnboardingStatusOut(
        ada=True,
        langkah_terakhir=progress.langkah_terakhir,
        selesai=progress.selesai,
        ditutup=progress.ditutup,
    )


# ---------------------------------------------------------------------------
# Progres onboarding
# ---------------------------------------------------------------------------

@router.get("/onboarding/status", response_model=OnboardingStatusOut)
async def get_status(
    brand_id: Annotated[uuid.UUID, Query()],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ctx = await _ctx(user, org_id, db)
    brand = await _brand_milik_org(db, ctx, brand_id)
    progress = await onboarding_service.get_progress(db, user.id, brand.id)
    return _status_out(progress)


@router.put("/onboarding/progress", response_model=OnboardingStatusOut)
async def simpan_progress(
    data: ProgressRequest,
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ctx = await _ctx(user, org_id, db)
    brand = await _brand_milik_org(db, ctx, data.brand_id)
    progress = await onboarding_service.upsert_progress(db, user.id, brand.id, data.langkah)
    return _status_out(progress)


@router.post("/onboarding/selesai", response_model=OnboardingStatusOut)
async def tandai_selesai(
    data: SelesaiRequest,
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ctx = await _ctx(user, org_id, db)
    brand = await _brand_milik_org(db, ctx, data.brand_id)
    progress = await onboarding_service.tandai_selesai(db, user.id, brand.id)
    return _status_out(progress)


@router.post("/onboarding/tutup", response_model=OnboardingStatusOut)
async def tutup_onboarding(
    data: TutupRequest,
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ctx = await _ctx(user, org_id, db)
    brand = await _brand_milik_org(db, ctx, data.brand_id)
    progress = await onboarding_service.tutup_onboarding(db, user.id, brand.id)
    return _status_out(progress)


# ---------------------------------------------------------------------------
# Template threshold & pratinjau kemenangan
# ---------------------------------------------------------------------------

@router.get("/onboarding/template-threshold", response_model=TemplateThresholdOut)
async def template_threshold(
    kategori: Annotated[str, Query()],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await _ctx(user, org_id, db)
    try:
        template = onboarding_service.get_template_threshold(kategori.strip())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return TemplateThresholdOut(kategori=kategori.strip(), **template)


@router.post("/onboarding/preview-kemenangan", response_model=PreviewOut)
async def preview_kemenangan(
    data: PreviewRequest,
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ctx = await _ctx(user, org_id, db)
    brand = await _brand_milik_org(db, ctx, data.brand_id)
    hasil = await onboarding_service.preview_kemenangan(
        db,
        brand=brand,
        organization_id=ctx.organization.id,
        draft=data.draft.model_dump(),
    )
    return PreviewOut(**hasil)


# ---------------------------------------------------------------------------
# Profil brand & logo
# ---------------------------------------------------------------------------

@router.put("/onboarding/brands/{brand_id}/profil", response_model=BrandProfilOut)
async def update_profil_brand(
    brand_id: uuid.UUID,
    data: ProfilBrandRequest,
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ctx = await _ctx(user, org_id, db)
    brand = await _brand_milik_org(db, ctx, brand_id)
    if data.nama is not None and data.nama.strip():
        brand.name = data.nama.strip()
    if data.kategori_industri is not None:
        kategori = data.kategori_industri.strip()
        if not onboarding_service.kategori_valid(kategori):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Kategori '{kategori}' tidak dikenal. "
                    f"Pilih: {', '.join(onboarding_service.KATEGORI_INDUSTRI)}."
                ),
            )
        brand.industry_category = kategori
    await db.flush()
    return BrandProfilOut(
        id=brand.id,
        nama=brand.name,
        kategori_industri=brand.industry_category,
        logo_url=brand.logo_url,
    )


@router.post("/onboarding/brands/{brand_id}/logo", response_model=LogoOut)
async def upload_logo_brand(
    brand_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(get_current_user)],
    org_id: Annotated[uuid.UUID, Depends(parse_org_header)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ctx = await _ctx(user, org_id, db)
    brand = await _brand_milik_org(db, ctx, brand_id)

    settings = get_settings()
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _LOGO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format file tidak didukung. Gunakan: {', '.join(sorted(_LOGO_EXTENSIONS))}.",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File kosong.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ukuran file maksimal {settings.MAX_UPLOAD_MB} MB.",
        )

    storage = get_storage_service()
    rel_path = await storage.save_brand_logo(data, ext)
    # Hapus logo lama bila ada.
    if brand.logo_url:
        try:
            storage.absolute_path(brand.logo_url).unlink(missing_ok=True)
        except OSError:
            pass
    brand.logo_url = rel_path
    await db.flush()
    return LogoOut(logo_url=rel_path)
