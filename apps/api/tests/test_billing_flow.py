"""Tes alur billing end-to-end: invoice → bukti → approve → membership aktif."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from app.models.billing import MembershipStatus
from app.services.email import get_dev_outbox

from .conftest import auth_headers, create_plan_direct, create_user_direct


async def _register_login_verify(client, email, password="Password123", name="Billing User"):
    r = await client.post(
        "/api/v1/auth/register", json={"name": name, "email": email, "password": password}
    )
    assert r.status_code == 201, r.text
    token = [t for t in get_dev_outbox() if t.email == email and t.type == "verification"][0].token
    r = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert r.status_code == 200
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_full_billing_flow(client, db_super):
    plan = await create_plan_direct(db_super, name="Paket E2E", price=990000, seats=5)
    token = await _register_login_verify(client, "billing-e2e@example.com")

    # Buat organisasi (butuh email terverifikasi)
    r = await client.post("/api/v1/organizations", json={"name": "Org E2E"}, headers=auth_headers(token))
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]
    h = auth_headers(token, org_id)

    # Buat invoice
    r = await client.post(
        "/api/v1/billing/invoices",
        json={"organization_id": org_id, "plan_id": str(plan.id)},
        headers=h,
    )
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["status"] == "pending"
    assert inv["amount_total"] == inv["amount_base"] + inv["unique_code"]
    assert inv["bank"]["account_number"]
    invoice_id = inv["id"]

    # Upload bukti pembayaran
    files = {"file": ("bukti.jpg", b"fake-image-bytes", "image/jpeg")}
    r = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/payment-proof", files=files, headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "menunggu_verifikasi"
    payment_id = r.json()["id"]

    # Bukan superadmin → antrean admin ditolak
    r = await client.get("/api/v1/admin/payments/queue", headers=auth_headers(token))
    assert r.status_code == 403

    # Login sebagai superadmin
    admin = await create_user_direct(db_super, email="admin-e2e@example.com", is_superadmin=True)
    r = await client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": "Password123"}
    )
    assert r.status_code == 200
    admin_h = auth_headers(r.json()["access_token"])
    assert r.json()["user"]["is_superadmin"] is True

    # Antrean berisi pembayaran tadi
    r = await client.get("/api/v1/admin/payments/queue", headers=admin_h)
    assert r.status_code == 200, r.text
    queue = r.json()
    assert any(item["payment"]["id"] == payment_id for item in queue)

    # Approve → membership aktif
    r = await client.post(f"/api/v1/admin/payments/{payment_id}/approve", headers=admin_h)
    assert r.status_code == 200, r.text
    membership = r.json()["membership"]
    assert membership["status"] == MembershipStatus.ACTIVE
    assert membership["ends_at"] is not None

    # Membership terbaca aktif oleh anggota org
    r = await client.get(
        "/api/v1/billing/memberships", params={"organization_id": org_id}, headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == MembershipStatus.ACTIVE

    # Upload lagi setelah disetujui → 409
    r = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/payment-proof", files=files, headers=h
    )
    assert r.status_code == 409

    # Sekarang bisa tambah brand (membership aktif)
    r = await client.post(
        f"/api/v1/organizations/{org_id}/brands", json={"name": "Brand E2E"}, headers=auth_headers(token)
    )
    assert r.status_code == 201, r.text


async def test_brand_blocked_during_grace(client, db_super):
    from datetime import timedelta

    from sqlalchemy import select

    from app.models.billing import Membership
    from app.services.membership import ensure_membership

    from .conftest import utcnow

    plan = await create_plan_direct(db_super, name="Paket Grace", price=100000, seats=5)
    token = await _register_login_verify(client, "grace-e2e@example.com")
    r = await client.post("/api/v1/organizations", json={"name": "Org Grace"}, headers=auth_headers(token))
    org_id = r.json()["id"]
    h = auth_headers(token)

    # Set membership ke grace secara manual
    membership = await ensure_membership(db_super, org_id)
    t0 = utcnow()
    membership.status = MembershipStatus.GRACE
    membership.plan_id = plan.id
    membership.starts_at = t0 - timedelta(days=370)
    membership.ends_at = t0 - timedelta(days=5)
    membership.grace_ends_at = t0 + timedelta(days=2)
    await db_super.commit()

    # Tambah brand saat grace → 403 mode baca-saja
    r = await client.post(
        f"/api/v1/organizations/{org_id}/brands", json={"name": "Brand X"}, headers=h
    )
    assert r.status_code == 403, r.text
    assert "baca-saja" in r.json()["detail"].lower() or "mode baca" in r.json()["detail"].lower()

    # Tapi list brand masih bisa dibaca
    r = await client.get(f"/api/v1/organizations/{org_id}/brands", headers=h)
    assert r.status_code == 200, r.text
