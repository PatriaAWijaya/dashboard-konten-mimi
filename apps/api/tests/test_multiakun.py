"""Tes multi-akun: batas 3 akun per platform per brand (configurable)."""

import uuid
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.brand import Brand
from app.models.fase2 import ConnectedAccount, ConnectedAccountStatus
from app.services.settings import set_setting
from tests.conftest import auth_headers, create_org_direct, create_user_direct

BASE = "/api/v1"


def _now():
    return datetime.now(timezone.utc)


async def _brand(db, org, name="Brand MA"):
    brand = Brand(organization_id=org.id, name=f"{name} {uuid.uuid4().hex[:6]}")
    db.add(brand)
    await db.flush()
    await db.commit()
    return brand


def _headers_for(user):
    return auth_headers(create_access_token(user.id, False))


async def _tambah_akun(db, org, brand, platform, ext_id, nama=None):
    acc = ConnectedAccount(
        organization_id=org.id,
        brand_id=brand.id,
        platform=platform,
        account_name=nama or f"Akun {ext_id}",
        account_external_id=ext_id,
        status=ConnectedAccountStatus.AKTIF,
    )
    db.add(acc)
    await db.flush()
    await db.commit()
    return acc


async def test_multiakun_akun_keempat_ditolak_409(client, db_super):
    """3 akun TikTok terhubung -> akun mock ke-4 ditolak 409."""
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    brand = await _brand(db_super, org)
    for i in range(3):
        await _tambah_akun(db_super, org, brand, "tiktok", f"tt-ext-{i}")

    h = _headers_for(owner)
    h["X-Organization-Id"] = str(org.id)
    r = await client.post(
        f"{BASE}/dev/koneksi/mock",
        headers=h,
        json={"brand_id": str(brand.id), "platform": "tiktok"},
    )
    assert r.status_code == 409, r.text
    assert "Batas 3 akun TikTok per brand tercapai" in r.json()["detail"]

    # instagram tidak terpengaruh batas tiktok
    r2 = await client.post(
        f"{BASE}/dev/koneksi/mock",
        headers=h,
        json={"brand_id": str(brand.id), "platform": "instagram"},
    )
    assert r2.status_code == 201, r2.text


async def test_multiakun_mock_endpoint_menolak_saat_penuh(client, db_super):
    """Mock endpoint menghitung akun existing; update akun mock yang sama tetap boleh."""
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    brand = await _brand(db_super, org)
    await _tambah_akun(db_super, org, brand, "tiktok", "tt-ext-a")
    await _tambah_akun(db_super, org, brand, "tiktok", "tt-ext-b")

    h = _headers_for(owner)
    h["X-Organization-Id"] = str(org.id)

    # slot masih ada (2/3) -> mock berhasil membuat akun ke-3
    r = await client.post(
        f"{BASE}/dev/koneksi/mock",
        headers=h,
        json={"brand_id": str(brand.id), "platform": "tiktok"},
    )
    assert r.status_code == 201, r.text
    mock_id = r.json()["id"]

    # akun mock yang sama dipanggil lagi -> update, bukan 409 (idempotent)
    r2 = await client.post(
        f"{BASE}/dev/koneksi/mock",
        headers=h,
        json={"brand_id": str(brand.id), "platform": "tiktok"},
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["id"] == mock_id

    # hapus satu akun manual -> slot kosong lagi -> mock tetap 201 (update)
    acc = await db_super.scalar(
        select(ConnectedAccount).where(ConnectedAccount.account_external_id == "tt-ext-a")
    )
    await db_super.delete(acc)
    await db_super.commit()
    r3 = await client.post(
        f"{BASE}/dev/koneksi/mock",
        headers=h,
        json={"brand_id": str(brand.id), "platform": "tiktok"},
    )
    assert r3.status_code == 201, r3.text
    assert r3.json()["id"] == mock_id


async def test_multiakun_batas_configurable_via_setting(client, db_super):
    """app_settings max_accounts_per_platform mengubah batas (lalu dibersihkan)."""
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    brand = await _brand(db_super, org)
    await set_setting(db_super, "max_accounts_per_platform", "1")
    await db_super.commit()
    try:
        await _tambah_akun(db_super, org, brand, "instagram", "ig-ext-1")

        h = _headers_for(owner)
        h["X-Organization-Id"] = str(org.id)
        r = await client.post(
            f"{BASE}/dev/koneksi/mock",
            headers=h,
            json={"brand_id": str(brand.id), "platform": "instagram"},
        )
        assert r.status_code == 409, r.text
        assert "Batas 1 akun Instagram per brand tercapai" in r.json()["detail"]
    finally:
        await set_setting(db_super, "max_accounts_per_platform", None)
        await db_super.commit()


async def test_koneksi_status_endpoint(client, db_super):
    """GET .../koneksi/status -> {platforms:{tiktok:{terpakai,batas,boleh_tambah},...}}."""
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    brand = await _brand(db_super, org)
    await _tambah_akun(db_super, org, brand, "tiktok", "tt-x-1")
    await _tambah_akun(db_super, org, brand, "tiktok", "tt-x-2")
    await _tambah_akun(db_super, org, brand, "tiktok", "tt-x-3")
    await _tambah_akun(db_super, org, brand, "instagram", "ig-x-1")

    h = _headers_for(owner)
    h["X-Organization-Id"] = str(org.id)
    r = await client.get(f"{BASE}/content/brands/{brand.id}/koneksi/status", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()["platforms"]
    assert data["tiktok"] == {"terpakai": 3, "batas": 3, "boleh_tambah": False}
    assert data["instagram"] == {"terpakai": 1, "batas": 3, "boleh_tambah": True}


async def test_koneksi_status_brand_lain_404(client, db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    owner2 = await create_user_direct(db_super)
    org2 = await create_org_direct(db_super, owner2)
    brand2 = await _brand(db_super, org2)

    h = _headers_for(owner)
    h["X-Organization-Id"] = str(org.id)
    r = await client.get(f"{BASE}/content/brands/{brand2.id}/koneksi/status", headers=h)
    assert r.status_code == 404, r.text
