"""Tes onboarding: progres, template threshold, pratinjau kemenangan, profil,
logo, brand default otomatis, rate limit, dan security headers."""

from datetime import date, datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from sqlalchemy import func, select

from app.models.brand import Brand
from app.models.content import Content, ContentMetricsDaily
from app.models.fase2 import NotificationLog
from app.models.onboarding import OnboardingProgress
from app.services.email import get_dev_outbox
from app.services.scoring import run_scoring
from app.services import onboarding as onboarding_service

from .conftest import auth_headers, create_plan_direct, create_user_direct, utcnow

BASE = "/api/v1"

_METRIK_MENANG = {
    "views": 20000, "reach": 20000, "likes": 2000, "comments": 400,
    "shares": 600, "saves": 800, "avg_watch_seconds": 25,
    "profile_clicks": 10, "link_clicks": 5, "replies": 20, "sticker_taps": 0,
}
_METRIK_KURANG = {
    "views": 1500, "reach": 1500, "likes": 5, "comments": 0,
    "shares": 0, "saves": 2, "avg_watch_seconds": 3,
    "profile_clicks": 0, "link_clicks": 0, "replies": 0, "sticker_taps": 0,
}


async def _register_login_verify(client, email, password="Password123", name="Onboarding User"):
    r = await client.post(
        f"{BASE}/auth/register", json={"name": name, "email": email, "password": password}
    )
    assert r.status_code == 201, r.text
    token = [t for t in get_dev_outbox() if t.email == email and t.type == "verification"][0].token
    r = await client.post(f"{BASE}/auth/verify-email", json={"token": token})
    assert r.status_code == 200
    r = await client.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _setup_org_brand(client, db_super, email):
    """Register+login, buat org via API, buat brand langsung via DB."""
    token = await _register_login_verify(client, email)
    r = await client.post(
        f"{BASE}/organizations", json={"name": f"Org OB {email[:6]}"}, headers=auth_headers(token)
    )
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]
    # Buat brand langsung (bypass syarat membership aktif di endpoint publik).
    from uuid import UUID

    b = Brand(organization_id=UUID(org_id), name=f"Brand OB {email[:6]}")
    db_super.add(b)
    await db_super.commit()
    return token, org_id, str(b.id)


async def _seed_skor(db_super, org_id, brand_id):
    """Seed 10 konten (tiktok+instagram, menang+kurang) lalu jalankan scoring asli."""
    from uuid import UUID

    awal, akhir = date(2026, 9, 1), date(2026, 9, 20)
    specs = [
        ("tiktok", _METRIK_MENANG, 3),
        ("tiktok", _METRIK_KURANG, 3),
        ("instagram", _METRIK_MENANG, 2),
        ("instagram", _METRIK_KURANG, 2),
    ]
    idx = 0
    for platform, metrik, n in specs:
        for _ in range(n):
            hari = awal + timedelta(days=idx % 15)
            c = Content(
                organization_id=UUID(org_id),
                brand_id=UUID(brand_id),
                platform=platform,
                post_id=f"ob-{platform}-{idx}",
                format="reels",
                tujuan="edukasi",
                posted_at=datetime(hari.year, hari.month, hari.day, 12, 0, tzinfo=timezone.utc),
            )
            db_super.add(c)
            await db_super.flush()
            db_super.add(
                ContentMetricsDaily(organization_id=UUID(org_id), content_id=c.id, date=hari, **metrik)
            )
            idx += 1
    await db_super.flush()
    brand = await db_super.get(Brand, UUID(brand_id))
    await run_scoring(
        db_super, brand=brand, organization_id=UUID(org_id), period_start=awal, period_end=akhir
    )


# ---------------------------------------------------------------------------
# Progres: status / simpan / selesai / tutup / resume
# ---------------------------------------------------------------------------

async def test_status_progress_selesai_tutup_resume(client, db_super):
    token, org_id, brand_id = await _setup_org_brand(client, db_super, "ob-prog@example.com")
    h = auth_headers(token, org_id)

    r = await client.get(f"{BASE}/onboarding/status", params={"brand_id": brand_id}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"ada": False, "langkah_terakhir": 0, "selesai": False, "ditutup": False}

    r = await client.put(
        f"{BASE}/onboarding/progress", json={"brand_id": brand_id, "langkah": 2}, headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["ada"] is True and r.json()["langkah_terakhir"] == 2

    r = await client.post(f"{BASE}/onboarding/selesai", json={"brand_id": brand_id}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["selesai"] is True

    r = await client.post(f"{BASE}/onboarding/tutup", json={"brand_id": brand_id}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["ditutup"] is True

    # Resume: progres berikutnya membuka lagi yang ditutup.
    r = await client.put(
        f"{BASE}/onboarding/progress", json={"brand_id": brand_id, "langkah": 3}, headers=h
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ditutup"] is False and body["langkah_terakhir"] == 3
    # selesai tetap tercatat
    assert body["selesai"] is True


async def test_onboarding_butuh_auth_dan_org(client):
    r = await client.get(f"{BASE}/onboarding/status", params={"brand_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 401
    # tanpa header org
    token = await _register_login_verify(client, "ob-noorg@example.com")
    r = await client.get(
        f"{BASE}/onboarding/status",
        params={"brand_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers(token),
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Template threshold per kategori
# ---------------------------------------------------------------------------

async def test_template_threshold_semua_kategori(client, db_super):
    token, org_id, brand_id = await _setup_org_brand(client, db_super, "ob-tmpl@example.com")
    h = auth_headers(token, org_id)
    for kategori in onboarding_service.KATEGORI_INDUSTRI:
        r = await client.get(
            f"{BASE}/onboarding/template-threshold", params={"kategori": kategori}, headers=h
        )
        assert r.status_code == 200, r.text
        body = r.json()
        ekspektasi = onboarding_service.TEMPLATE_THRESHOLD_PER_KATEGORI[kategori]
        assert body["kategori"] == kategori
        for kunci in ("tiktok_er", "instagram_er", "skor_menang", "skor_cukup"):
            assert body[kunci] == pytest.approx(ekspektasi[kunci])

    # Default 'lainnya' = nilai default scoring sekarang.
    r = await client.get(
        f"{BASE}/onboarding/template-threshold", params={"kategori": "lainnya"}, headers=h
    )
    body = r.json()
    assert body["tiktok_er"] == pytest.approx(0.08)
    assert body["instagram_er"] == pytest.approx(0.05)
    assert body["skor_menang"] == pytest.approx(0.7)
    assert body["skor_cukup"] == pytest.approx(0.4)

    # Kategori tak dikenal → 400.
    r = await client.get(
        f"{BASE}/onboarding/template-threshold", params={"kategori": "kripto"}, headers=h
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Pratinjau kemenangan: draft tidak menyimpan config
# ---------------------------------------------------------------------------

async def test_preview_kemenangan_tanpa_menyimpan_config(client, db_super):
    from uuid import UUID

    from app.models.content import ScoringConfig

    token, org_id, brand_id = await _setup_org_brand(client, db_super, "ob-prev@example.com")
    h = auth_headers(token, org_id)
    await _seed_skor(db_super, org_id, brand_id)

    # Catat kondisi config SEBELUM preview.
    jml_sebelum = await db_super.scalar(
        select(func.count()).select_from(ScoringConfig).where(ScoringConfig.brand_id == UUID(brand_id))
    )
    aktif_sebelum = (
        await db_super.execute(
            select(ScoringConfig).where(
                ScoringConfig.brand_id == UUID(brand_id), ScoringConfig.is_active.is_(True)
            )
        )
    ).scalar_one()
    threshold_sebelum = dict(aktif_sebelum.thresholds)

    r = await client.post(
        f"{BASE}/onboarding/preview-kemenangan",
        json={"brand_id": brand_id, "draft": {"tiktok_er": 0.08, "instagram_er": 0.05}},
        headers=h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 10
    assert body["menang"] == 5
    assert body["per_platform"]["tiktok"] == {"menang": 3, "total": 6}
    assert body["per_platform"]["instagram"] == {"menang": 2, "total": 4}

    # BUKTI config tidak berubah: jumlah config sama, threshold aktif identik.
    jml_sesudah = await db_super.scalar(
        select(func.count()).select_from(ScoringConfig).where(ScoringConfig.brand_id == UUID(brand_id))
    )
    assert jml_sesudah == jml_sebelum
    aktif_sesudah = await db_super.get(ScoringConfig, aktif_sebelum.id)
    assert dict(aktif_sesudah.thresholds) == threshold_sebelum

    # Draft lebih longgar → semua konten yang lolos gerbang views menang.
    r = await client.post(
        f"{BASE}/onboarding/preview-kemenangan",
        json={
            "brand_id": brand_id,
            "draft": {"tiktok_er": 0.01, "instagram_er": 0.01, "skor_menang": 0.01},
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json()["menang"] == 10

    # Draft tidak valid → 422.
    r = await client.post(
        f"{BASE}/onboarding/preview-kemenangan",
        json={"brand_id": brand_id, "draft": {"tiktok_er": 1.5, "instagram_er": 0.05}},
        headers=h,
    )
    assert r.status_code == 422


async def test_preview_kemenangan_tanpa_data(client, db_super):
    token, org_id, brand_id = await _setup_org_brand(client, db_super, "ob-prev0@example.com")
    h = auth_headers(token, org_id)
    r = await client.post(
        f"{BASE}/onboarding/preview-kemenangan",
        json={"brand_id": brand_id, "draft": {"tiktok_er": 0.08, "instagram_er": 0.05}},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"menang": 0, "total": 0, "per_platform": {}}


# ---------------------------------------------------------------------------
# Profil brand & upload logo
# ---------------------------------------------------------------------------

async def test_update_profil_brand(client, db_super):
    token, org_id, brand_id = await _setup_org_brand(client, db_super, "ob-prof@example.com")
    h = auth_headers(token, org_id)

    r = await client.put(
        f"{BASE}/onboarding/brands/{brand_id}/profil",
        json={"nama": "Brand Baru", "kategori_industri": "kuliner"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["nama"] == "Brand Baru"
    assert body["kategori_industri"] == "kuliner"

    # Kategori tak dikenal → 400, nama tidak berubah.
    r = await client.put(
        f"{BASE}/onboarding/brands/{brand_id}/profil",
        json={"kategori_industri": "kripto"},
        headers=h,
    )
    assert r.status_code == 400


async def test_upload_logo_brand(client, db_super):
    from uuid import UUID

    token, org_id, brand_id = await _setup_org_brand(client, db_super, "ob-logo@example.com")
    h = auth_headers(token, org_id)

    files = {"file": ("logo.png", b"\x89PNG" + b"x" * 100, "image/png")}
    r = await client.post(f"{BASE}/onboarding/brands/{brand_id}/logo", files=files, headers=h)
    assert r.status_code == 200, r.text
    logo_url = r.json()["logo_url"]
    assert logo_url.endswith(".png")
    assert "brand_logos" in logo_url

    brand = await db_super.get(Brand, UUID(brand_id))
    assert brand.logo_url == logo_url

    # Ekstensi bukan gambar → 400.
    files = {"file": ("jahat.exe", b"MZ", "application/octet-stream")}
    r = await client.post(f"{BASE}/onboarding/brands/{brand_id}/logo", files=files, headers=h)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Brand default otomatis saat aktivasi pertama (PRD 10.5)
# ---------------------------------------------------------------------------

async def _approve_pertama(client, db_super, email, buat_brand_dulu=False):
    """Jalankan alur invoice → bukti → approve; kembalikan (org_id, payment_id)."""
    from uuid import UUID

    token = await _register_login_verify(client, email)
    r = await client.post(
        f"{BASE}/organizations", json={"name": f"Org Akt {email[:6]}"}, headers=auth_headers(token)
    )
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]
    h = auth_headers(token, org_id)

    plan = await create_plan_direct(db_super, name=f"Paket Akt {email[:6]}", price=990000, seats=5)
    r = await client.post(
        f"{BASE}/billing/invoices",
        json={"organization_id": org_id, "plan_id": str(plan.id)},
        headers=h,
    )
    assert r.status_code == 201, r.text
    invoice_id = r.json()["id"]

    files = {"file": ("bukti.jpg", b"fake-image-bytes", "image/jpeg")}
    r = await client.post(
        f"{BASE}/billing/invoices/{invoice_id}/payment-proof", files=files, headers=h
    )
    assert r.status_code == 200, r.text
    payment_id = r.json()["id"]

    if buat_brand_dulu:
        db_super.add(Brand(organization_id=UUID(org_id), name="Sudah Ada"))
        await db_super.commit()

    admin = await create_user_direct(db_super, email=f"admin-{email}", is_superadmin=True)
    r = await client.post(
        f"{BASE}/auth/login", json={"email": admin.email, "password": "Password123"}
    )
    assert r.status_code == 200
    admin_h = auth_headers(r.json()["access_token"])

    r = await client.post(f"{BASE}/admin/payments/{payment_id}/approve", headers=admin_h)
    assert r.status_code == 200, r.text
    assert r.json()["membership"]["status"] == "active"
    return org_id


async def test_brand_utama_dibuat_saat_aktivasi_pertama(client, db_super):
    import json
    from uuid import UUID

    org_id = await _approve_pertama(client, db_super, "ob-aktif@example.com")

    brands = (
        await db_super.execute(select(Brand).where(Brand.organization_id == UUID(org_id)))
    ).scalars().all()
    assert [b.name for b in brands] == ["Brand Utama"]

    # Notifikasi aktivasi terkirim (mock): ada log, berisi link login +
    # nama org + tanggal kedaluwarsa, TANPA password.
    logs = (
        await db_super.execute(
            select(NotificationLog).where(
                NotificationLog.organization_id == UUID(org_id),
                NotificationLog.jenis == "aktivasi_membership",
            )
        )
    ).scalars().all()
    assert len(logs) >= 1
    payload = logs[0].payload
    assert payload.get("login_url")
    assert payload.get("nama_organisasi")
    assert payload.get("tanggal_kedaluwarsa")
    assert "password" not in json.dumps(payload).lower()


async def test_brand_utama_tidak_duplikat_bila_sudah_ada(client, db_super):
    from uuid import UUID

    org_id = await _approve_pertama(
        client, db_super, "ob-aktif2@example.com", buat_brand_dulu=True
    )
    brands = (
        await db_super.execute(select(Brand).where(Brand.organization_id == UUID(org_id)))
    ).scalars().all()
    assert [b.name for b in brands] == ["Sudah Ada"]


# ---------------------------------------------------------------------------
# Security headers & rate limit
# ---------------------------------------------------------------------------

async def test_security_headers_ada(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("strict-transport-security", "").startswith("max-age=")
    assert r.headers.get("x-frame-options") == "DENY"
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_rate_limit_login_menolak_spam():
    """Spam login via TestClient sinkron → sebagian ditolak 429.

    TestClient menjalankan aplikasi di portal (event loop berbeda dari loop
    sesi pytest), sedangkan engine DB aplikasi terikat pada loop pemakainya.
    Karena itu engine diputus (tanpa dispose lintas-loop) sebelum & sesudah
    TestClient agar dibuat ulang di loop yang benar.
    """
    import app.db.session as _sess
    from fastapi.testclient import TestClient

    from app.core.rate_limit import limiter
    from app.main import app

    _sess._engine = None
    _sess._session_factory = None
    try:
        with TestClient(app) as c:
            hasil = []
            for _ in range(40):
                r = c.post(
                    f"{BASE}/auth/login",
                    json={"email": "spam@example.com", "password": "salah123"},
                )
                hasil.append(r)
            kode = [r.status_code for r in hasil]
        assert 429 in kode, f"tidak ada respons 429 di {sorted(set(kode))}"
        assert all(k in (401, 429) for k in kode)
        # Respons 429 tetap JSON Bahasa Indonesia + security headers.
        r429 = next(r for r in hasil if r.status_code == 429)
        assert "detail" in r429.json()
        assert r429.headers.get("x-content-type-options") == "nosniff"
    finally:
        # Kembalikan agar tes async berikutnya membuat engine di loop sesi.
        _sess._engine = None
        _sess._session_factory = None
        try:
            limiter._storage.reset()
        except Exception:
            pass
