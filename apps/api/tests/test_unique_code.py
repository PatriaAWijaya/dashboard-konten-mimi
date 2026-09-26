"""Tes kode unik invoice: unik di antara invoice pending + retry hingga 409."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from .conftest import auth_headers, create_org_direct, create_plan_direct, create_user_direct


async def _setup_billing(client, db_super):
    user = await create_user_direct(db_super, email_verified=True)
    plan = await create_plan_direct(db_super)
    org = await create_org_direct(db_super, user)

    r = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "Password123"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return user, plan, org, auth_headers(token, org.id)


async def test_unique_code_unique_among_pending(client, db_super):
    _, plan, org, headers = await _setup_billing(client, db_super)

    totals = []
    for _ in range(50):
        r = await client.post(
            "/api/v1/billing/invoices",
            json={"organization_id": str(org.id), "plan_id": str(plan.id)},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "pending"
        assert 1 <= body["unique_code"] <= 999
        assert body["amount_total"] == body["amount_base"] + body["unique_code"]
        totals.append(body["amount_total"])

    # amount_total unik di antara invoice pending org ini
    assert len(set(totals)) == len(totals)


async def test_unique_code_exhaustion_returns_409(client, db_super, monkeypatch):
    import app.services.invoice as invoice_svc

    _, plan, org, headers = await _setup_billing(client, db_super)

    # Paksa generator selalu mengembalikan kode 1.
    monkeypatch.setattr(invoice_svc.random, "randint", lambda a, b: 1)

    r = await client.post(
        "/api/v1/billing/invoices",
        json={"organization_id": str(org.id), "plan_id": str(plan.id)},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["unique_code"] == 1

    # Invoice kedua: semua retry mentok di kode 1 → 409.
    r = await client.post(
        "/api/v1/billing/invoices",
        json={"organization_id": str(org.id), "plan_id": str(plan.id)},
        headers=headers,
    )
    assert r.status_code == 409, r.text
    assert "detail" in r.json()
