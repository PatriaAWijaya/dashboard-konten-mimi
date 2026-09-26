"""Tes auth dasar: register → verify → login → refresh."""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from app.services.email import get_dev_outbox

from .conftest import auth_headers


async def test_register_verify_login_refresh(client):
    email = "authflow@example.com"
    password = "Password123"

    # register → 201
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": "Auth Flow", "email": email, "password": password, "whatsapp": "08123456789"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == email
    assert "message" in body

    # login DIIZINKAN walau email belum verifikasi
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    tokens = r.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["user"]["email"] == email

    # ambil token verifikasi dari outbox dev
    outbox = [t for t in get_dev_outbox() if t.email == email and t.type == "verification"]
    assert len(outbox) == 1
    r = await client.post("/api/v1/auth/verify-email", json={"token": outbox[0].token})
    assert r.status_code == 200, r.text

    # /auth/me menunjukkan email_verified = true
    r = await client.get("/api/v1/auth/me", headers=auth_headers(tokens["access_token"]))
    assert r.status_code == 200, r.text
    assert r.json()["email_verified"] is True

    # refresh → token baru; token lama hangus (rotasi)
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200, r.text
    new_tokens = r.json()
    # Refresh token selalu berbeda (jti unik) — rotasi terbukti.
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401, r.text

    # password salah → 401 dengan format {"detail"}
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "Salah1234"})
    assert r.status_code == 401
    assert "detail" in r.json()


async def test_login_rejected_when_inactive(client, db_super):
    from .conftest import create_user_direct

    user = await create_user_direct(db_super, email="inactive@example.com", is_active=False)
    r = await client.post(
        "/api/v1/auth/login", json={"email": "inactive@example.com", "password": "Password123"}
    )
    assert r.status_code == 403
    assert "detail" in r.json()


async def test_forgot_reset_password_never_leaks(client):
    email = "resetflow@example.com"
    r = await client.post(
        "/api/v1/auth/register",
        json={"name": "Reset Flow", "email": email, "password": "Password123"},
    )
    assert r.status_code == 201

    # selalu 200, bahkan untuk email yang tidak terdaftar
    r = await client.post("/api/v1/auth/forgot-password", json={"email": "tidak@ada.com"})
    assert r.status_code == 200
    r = await client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    assert "message" in r.json()

    outbox = [t for t in get_dev_outbox() if t.email == email and t.type == "password_reset"]
    assert len(outbox) == 1

    r = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": outbox[0].token, "new_password": "BaruPassword123"},
    )
    assert r.status_code == 200, r.text

    # login dengan password baru berhasil
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": "BaruPassword123"})
    assert r.status_code == 200, r.text
