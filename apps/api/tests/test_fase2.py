"""Tes Fase 2: OAuth, enkripsi, planner, undangan, ringkasan, notifikasi."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from sqlalchemy import func, select

from app.core.crypto import decrypt_text, encrypt_text
from app.core.security import create_access_token, hash_token
from app.models.brand import Brand
from app.models.fase2 import (
    AppSetting,
    ConnectedAccount,
    Invitation,
    NotificationLog,
    NotificationPreference,
    OAuthState,
    PlannedPost,
    Summary,
)
from app.models.organization import OrganizationMember
from app.services.invitations import accept_invite, create_invite, dev_lookup_token
from app.services.notifications import get_or_create_preference, notify
from app.services.settings import get_setting, set_setting
from app.services.sync_providers import TikTokSyncProvider, get_provider
from tests.conftest import auth_headers, create_org_direct, create_user_direct
from tests.kontrak_palsu import buat_org_brand, seed_konten_skor

BASE = "/api/v1"


def _now():
    return datetime.now(timezone.utc)


async def _brand(db, org, name="Brand F2"):
    brand = Brand(organization_id=org.id, name=f"{name} {uuid.uuid4().hex[:6]}")
    db.add(brand)
    await db.flush()
    await db.commit()
    return brand


def _headers_for(user):
    return auth_headers(create_access_token(user.id, False))


async def _set_kredensial_tiktok(db):
    await set_setting(db, "tiktok_client_key", "test-client-key")
    await set_setting(db, "tiktok_client_secret", "test-client-secret")
    await db.commit()


async def _hapus_kredensial_tiktok(db):
    await set_setting(db, "tiktok_client_key", None)
    await set_setting(db, "tiktok_client_secret", None)
    await db.commit()


# ---------------------------------------------------------------------------
# (b) Fernet roundtrip
# ---------------------------------------------------------------------------

async def test_fernet_roundtrip():
    rahasia = "token-rahasia-123!@#"
    enc = encrypt_text(rahasia)
    assert enc != rahasia
    assert decrypt_text(enc) == rahasia
    assert encrypt_text(None) is None
    assert decrypt_text(None) is None


# ---------------------------------------------------------------------------
# (a) OAuth: mulai → state tersimpan + auth_url; callback → akun terenkripsi
# ---------------------------------------------------------------------------

async def test_oauth_mulai_tanpa_kredensial_501(client, db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    brand = await _brand(db_super, org)
    await _hapus_kredensial_tiktok(db_super)

    h = _headers_for(owner)
    h["X-Organization-Id"] = str(org.id)
    r = await client.post(f"{BASE}/content/brands/{brand.id}/oauth/tiktok/mulai", headers=h)
    assert r.status_code == 501, r.text
    assert "kredensial" in r.json()["detail"].lower()


async def test_oauth_alur_lengkap_dengan_kredensial(client, db_super, monkeypatch):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    brand = await _brand(db_super, org)
    await _set_kredensial_tiktok(db_super)

    h = _headers_for(owner)
    h["X-Organization-Id"] = str(org.id)

    # 1. mulai → auth_url mengandung client_id & state; state tersimpan
    r = await client.post(f"{BASE}/content/brands/{brand.id}/oauth/tiktok/mulai", headers=h)
    assert r.status_code == 200, r.text
    auth_url = r.json()["auth_url"]
    assert "client_key=test-client-key" in auth_url or "client_id=test-client-key" in auth_url
    assert "state=" in auth_url

    st = await db_super.scalar(select(OAuthState).where(OAuthState.brand_id == brand.id))
    assert st is not None
    assert st.state in auth_url
    assert st.expires_at > _now()

    # 2. callback dengan provider nyata yang exchange-nya di-mock
    async def fake_exchange(self, *, code, code_verifier, redirect_uri, client_id, client_secret):
        assert code == "kode-uji"
        return {
            "access_token": "token-asli-xyz",
            "refresh_token": "refresh-asli-xyz",
            "expires_in": 3600,
            "account_name": "Akun Uji",
            "account_external_id": "tt-123",
        }

    monkeypatch.setattr(TikTokSyncProvider, "exchange_code", fake_exchange)

    r = await client.get(
        f"{BASE}/content/oauth/callback", params={"code": "kode-uji", "state": st.state}
    )
    assert r.status_code == 302, r.text
    loc = r.headers["location"]
    assert f"/brand/{brand.id}/koneksi" in loc
    assert "status=ok" in loc

    # 3. connected_accounts terisi; token terenkripsi (bukan plaintext)
    acc = await db_super.scalar(
        select(ConnectedAccount).where(
            ConnectedAccount.brand_id == brand.id, ConnectedAccount.platform == "tiktok"
        )
    )
    assert acc is not None
    assert acc.status == "aktif"
    assert acc.account_name == "Akun Uji"
    assert acc.access_token_encrypted != "token-asli-xyz"
    assert "token-asli-xyz" not in (acc.access_token_encrypted or "")
    assert decrypt_text(acc.access_token_encrypted) == "token-asli-xyz"
    assert decrypt_text(acc.refresh_token_encrypted) == "refresh-asli-xyz"

    # state terpakai → terhapus
    st2 = await db_super.scalar(select(OAuthState).where(OAuthState.state == st.state))
    assert st2 is None

    # 4. daftar koneksi tampil
    r = await client.get(f"{BASE}/content/brands/{brand.id}/koneksi", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 1
    assert items[0]["platform"] == "tiktok"
    assert items[0]["status"] == "aktif"
    assert "connected_at" in items[0]


async def test_oauth_callback_state_salah_redirect_gagal(client, db_super):
    r = await client.get(
        f"{BASE}/content/oauth/callback", params={"code": "x", "state": "tidak-ada"}
    )
    assert r.status_code == 302
    assert "status=gagal" in r.headers["location"]


# ---------------------------------------------------------------------------
# sync via mock provider (tanpa kredensial → data demo)
# ---------------------------------------------------------------------------

async def test_sync_mock_menghasilkan_konten(client, db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    brand = await _brand(db_super, org)
    await _hapus_kredensial_tiktok(db_super)

    acc = ConnectedAccount(
        organization_id=org.id, brand_id=brand.id, platform="tiktok",
        account_name="Demo", status="aktif",
    )
    db_super.add(acc)
    await db_super.commit()

    h = _headers_for(owner)
    h["X-Organization-Id"] = str(org.id)
    r = await client.post(f"{BASE}/content/koneksi/{acc.id}/sync", headers=h)
    assert r.status_code == 200, r.text
    hasil = r.json()
    assert hasil["contents_baru"] == 15
    assert hasil["contents_diupdate"] == 0

    # sync ulang → update, bukan duplikat
    r = await client.post(f"{BASE}/content/koneksi/{acc.id}/sync", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["contents_baru"] == 0
    assert r.json()["contents_diupdate"] == 15


async def test_sync_gagal_status_error_persisten(client, db_super, monkeypatch):
    """Provider yang gagal → 502, dan status='error' TETAP tersimpan.

    Tanpa commit tersendiri di sync_account, status ikut ter-rollback oleh
    get_db saat HTTPException di-raise.
    """
    from app.services.sync_providers import MockSyncProvider

    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    brand = await _brand(db_super, org)
    await _hapus_kredensial_tiktok(db_super)

    acc = ConnectedAccount(
        organization_id=org.id, brand_id=brand.id, platform="tiktok",
        account_name="Demo", status="aktif",
    )
    db_super.add(acc)
    await db_super.commit()

    async def fetch_gagal(self, account, since):
        raise RuntimeError("provider meledak")

    monkeypatch.setattr(MockSyncProvider, "fetch_posts", fetch_gagal)

    h = _headers_for(owner)
    h["X-Organization-Id"] = str(org.id)
    r = await client.post(f"{BASE}/content/koneksi/{acc.id}/sync", headers=h)
    assert r.status_code == 502, r.text

    # Status error harus persisten meski request berakhir 502 (rollback).
    await db_super.refresh(acc)
    assert acc.status == "error"


async def test_hapus_koneksi_butuh_admin(client, db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    brand = await _brand(db_super, org)
    acc = ConnectedAccount(
        organization_id=org.id, brand_id=brand.id, platform="instagram", status="aktif"
    )
    db_super.add(acc)
    await db_super.commit()

    editor = await create_user_direct(db_super)
    db_super.add(OrganizationMember(organization_id=org.id, user_id=editor.id, role="editor"))
    await db_super.commit()

    he = _headers_for(editor)
    he["X-Organization-Id"] = str(org.id)
    r = await client.delete(f"{BASE}/content/koneksi/{acc.id}", headers=he)
    assert r.status_code == 403, r.text

    ho = _headers_for(owner)
    ho["X-Organization-Id"] = str(org.id)
    r = await client.delete(f"{BASE}/content/koneksi/{acc.id}", headers=ho)
    assert r.status_code == 204, r.text


# ---------------------------------------------------------------------------
# (c) planner CRUD + isolasi antar organisasi
# ---------------------------------------------------------------------------

async def _planner_setup(client, db_super):
    owner_a = await create_user_direct(db_super)
    org_a = await create_org_direct(db_super, owner_a, name="Org Plan A")
    brand_a = await _brand(db_super, org_a, name="Brand Plan A")
    owner_b = await create_user_direct(db_super)
    org_b = await create_org_direct(db_super, owner_b, name="Org Plan B")
    ha = _headers_for(owner_a); ha["X-Organization-Id"] = str(org_a.id)
    hb = _headers_for(owner_b); hb["X-Organization-Id"] = str(org_b.id)
    return ha, hb, brand_a


async def test_planner_crud_dan_isolasi_org(client, db_super):
    ha, hb, brand_a = await _planner_setup(client, db_super)

    payload = {
        "judul": "Tips hemat ala NGO",
        "format": "carousel",
        "tujuan": "edukasi",
        "tanggal_rencana": "2026-10-05",
        "catatan": "siapkan desain",
    }
    r = await client.post(f"{BASE}/content/brands/{brand_a.id}/planner", json=payload, headers=ha)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["status"] == "ide"

    # daftar + filter bulan
    r = await client.get(f"{BASE}/content/brands/{brand_a.id}/planner", headers=ha)
    assert r.status_code == 200 and len(r.json()) == 1
    r = await client.get(
        f"{BASE}/content/brands/{brand_a.id}/planner", params={"bulan": "2026-10"}, headers=ha
    )
    assert len(r.json()) == 1
    r = await client.get(
        f"{BASE}/content/brands/{brand_a.id}/planner", params={"bulan": "2026-11"}, headers=ha
    )
    assert r.json() == []

    # org B tidak bisa akses planner brand A (brand tidak ditemukan)
    r = await client.get(f"{BASE}/content/brands/{brand_a.id}/planner", headers=hb)
    assert r.status_code == 404, r.text
    r = await client.post(f"{BASE}/content/brands/{brand_a.id}/planner", json=payload, headers=hb)
    assert r.status_code == 404, r.text

    # update status
    ubah = dict(payload, status="terjadwal", judul="Tips hemat ala NGO v2")
    r = await client.put(f"{BASE}/content/planner/{pid}", json=ubah, headers=ha)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "terjadwal"

    # org B tidak bisa ubah/hapus rencana milik A
    r = await client.put(f"{BASE}/content/planner/{pid}", json=ubah, headers=hb)
    assert r.status_code == 404
    r = await client.delete(f"{BASE}/content/planner/{pid}", headers=hb)
    assert r.status_code == 404

    # hapus
    r = await client.delete(f"{BASE}/content/planner/{pid}", headers=ha)
    assert r.status_code == 204, r.text
    r = await client.get(f"{BASE}/content/brands/{brand_a.id}/planner", headers=ha)
    assert r.json() == []


# ---------------------------------------------------------------------------
# (d) undangan
# ---------------------------------------------------------------------------

async def test_undangan_buat_terima_dan_kedaluwarsa(client, db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner, name="Org Undang")
    calon = await create_user_direct(db_super, email=f"calon-{uuid.uuid4().hex[:6]}@example.com")

    ho = _headers_for(owner); ho["X-Organization-Id"] = str(org.id)

    r = await client.post(
        f"{BASE}/organizations/{org.id}/undangan",
        json={"email": calon.email, "role": "editor"},
        headers=ho,
    )
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "editor"
    assert r.json()["status"] == "pending"

    # daftar pending tampil
    r = await client.get(f"{BASE}/organizations/{org.id}/undangan", headers=ho)
    assert r.status_code == 200 and len(r.json()) == 1

    # token dari vault dev → user lain menerima
    found = dev_lookup_token(calon.email)
    assert found is not None
    hc = _headers_for(calon)  # tanpa header organisasi
    r = await client.post(f"{BASE}/undangan/{found['token']}/terima", headers=hc)
    assert r.status_code == 200, r.text
    assert r.json()["organization_id"] == str(org.id)
    assert r.json()["role"] == "editor"

    member = await db_super.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == calon.id,
        )
    )
    assert member is not None and member.role == "editor"

    # token sudah dipakai → 400
    r = await client.post(f"{BASE}/undangan/{found['token']}/terima", headers=hc)
    assert r.status_code == 400, r.text

    # token basi / tidak dikenal → 400
    r = await client.post(f"{BASE}/undangan/token-ngawur-123/terima", headers=hc)
    assert r.status_code == 400, r.text

    # undangan kedaluwarsa → 400
    calon2 = await create_user_direct(db_super, email=f"calon2-{uuid.uuid4().hex[:6]}@example.com")
    inv, token2 = await create_invite(
        db_super, org=org, email=calon2.email, role="viewer", invited_by=owner
    )
    inv.expires_at = _now() - timedelta(hours=1)
    await db_super.commit()
    hc2 = _headers_for(calon2)
    r = await client.post(f"{BASE}/undangan/{token2}/terima", headers=hc2)
    assert r.status_code == 400, r.text
    assert "kedaluwarsa" in r.json()["detail"].lower()


async def test_undangan_email_berbeda_tetap_diterima(client, db_super):
    """Email user login TIDAK harus sama dengan email undangan.

    Keputusan desain (lihat docstring accept_invite): token valid + user
    login cukup — undangan adalah tiket masuk organisasi.
    """
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner, name="Org Undang Beda Email")
    ho = _headers_for(owner); ho["X-Organization-Id"] = str(org.id)

    email_undangan = f"tamu-{uuid.uuid4().hex[:6]}@example.com"
    r = await client.post(
        f"{BASE}/organizations/{org.id}/undangan",
        json={"email": email_undangan, "role": "viewer"},
        headers=ho,
    )
    assert r.status_code == 201, r.text

    # User login dengan email BERBEDA menerima undangan → tetap 200.
    orang_lain = await create_user_direct(
        db_super, email=f"lain-{uuid.uuid4().hex[:6]}@example.com"
    )
    assert orang_lain.email != email_undangan
    found = dev_lookup_token(email_undangan)
    assert found is not None
    hl = _headers_for(orang_lain)
    r = await client.post(f"{BASE}/undangan/{found['token']}/terima", headers=hl)
    assert r.status_code == 200, r.text
    assert r.json()["organization_id"] == str(org.id)

    member = await db_super.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == orang_lain.id,
        )
    )
    assert member is not None and member.role == "viewer"


async def test_undangan_batal_dan_validasi_role(client, db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner, name="Org Undang 2")
    ho = _headers_for(owner); ho["X-Organization-Id"] = str(org.id)

    r = await client.post(
        f"{BASE}/organizations/{org.id}/undangan",
        json={"email": "x@example.com", "role": "owner"},
        headers=ho,
    )
    assert r.status_code == 400, r.text

    r = await client.post(
        f"{BASE}/organizations/{org.id}/undangan",
        json={"email": "y@example.com", "role": "viewer"},
        headers=ho,
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]

    r = await client.delete(f"{BASE}/organizations/{org.id}/undangan/{uid}", headers=ho)
    assert r.status_code == 200, r.text

    inv = await db_super.get(Invitation, uuid.UUID(uid))
    assert inv.status == "dibatalkan"


# ---------------------------------------------------------------------------
# keluarkan anggota (kontrak frontend)
# ---------------------------------------------------------------------------

async def test_keluarkan_anggota(client, db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner, name="Org Kick")
    anggota = await create_user_direct(db_super)
    db_super.add(OrganizationMember(organization_id=org.id, user_id=anggota.id, role="editor"))
    await db_super.commit()

    ho = _headers_for(owner); ho["X-Organization-Id"] = str(org.id)

    # keluarkan diri sendiri → 400
    r = await client.delete(f"{BASE}/organizations/{org.id}/members/{owner.id}", headers=ho)
    assert r.status_code == 400, r.text

    # keluarkan owner terakhir → 400
    r = await client.delete(f"{BASE}/organizations/{org.id}/members/{owner.id}", headers=ho)
    assert r.status_code == 400, r.text

    # admin LAIN mencoba mengeluarkan satu-satunya owner → 400 (owner terakhir)
    admin = await create_user_direct(db_super)
    db_super.add(OrganizationMember(organization_id=org.id, user_id=admin.id, role="admin"))
    await db_super.commit()
    ha = _headers_for(admin); ha["X-Organization-Id"] = str(org.id)
    r = await client.delete(f"{BASE}/organizations/{org.id}/members/{owner.id}", headers=ha)
    assert r.status_code == 400, r.text
    assert "owner terakhir" in r.json()["detail"].lower()

    # setelah ada owner kedua, mengeluarkan salah satu owner → 204
    owner2 = await create_user_direct(db_super)
    db_super.add(OrganizationMember(organization_id=org.id, user_id=owner2.id, role="owner"))
    await db_super.commit()
    r = await client.delete(f"{BASE}/organizations/{org.id}/members/{owner2.id}", headers=ha)
    assert r.status_code == 204, r.text

    # keluarkan editor → 204
    r = await client.delete(f"{BASE}/organizations/{org.id}/members/{anggota.id}", headers=ho)
    assert r.status_code == 204, r.text
    sisa = await db_super.scalar(
        select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == org.id, OrganizationMember.user_id == anggota.id
        )
    )
    assert sisa == 0

    # editor tidak boleh mengeluarkan anggota
    anggota2 = await create_user_direct(db_super)
    db_super.add(OrganizationMember(organization_id=org.id, user_id=anggota2.id, role="editor"))
    anggota3 = await create_user_direct(db_super)
    db_super.add(OrganizationMember(organization_id=org.id, user_id=anggota3.id, role="viewer"))
    await db_super.commit()
    he = _headers_for(anggota2); he["X-Organization-Id"] = str(org.id)
    r = await client.delete(f"{BASE}/organizations/{org.id}/members/{anggota3.id}", headers=he)
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# (e) ringkasan: generate 2x → 1 baris (cached); GET ada:true/false
# ---------------------------------------------------------------------------

async def test_ringkasan_generate_cached_dan_baca(client, db_super):
    org, brand = await buat_org_brand(db_super, "Org Ringkas", "Brand Ringkas")
    owner = await create_user_direct(db_super)
    db_super.add(OrganizationMember(organization_id=org.id, user_id=owner.id, role="owner"))
    await db_super.commit()

    minggu = date.today() - timedelta(days=6)
    await seed_konten_skor(
        db_super, org, brand,
        [("reels", "edukasi", 4, 2), ("carousel", "jualan", 1, 3)],
        minggu, minggu + timedelta(days=6),
    )
    await db_super.commit()

    h = _headers_for(owner); h["X-Organization-Id"] = str(org.id)
    params = {"minggu": minggu.isoformat()}

    r = await client.get(f"{BASE}/content/brands/{brand.id}/ringkasan", params=params, headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"ada": False}

    r = await client.post(
        f"{BASE}/content/brands/{brand.id}/ringkasan/generate", params=params, headers=h
    )
    assert r.status_code == 200, r.text
    pertama = r.json()
    assert pertama["ada"] is True
    assert pertama["teks"] and len(pertama["teks"]) > 50
    assert pertama["period_start"] == minggu.isoformat()

    # generate kedua → cache (1 baris)
    r = await client.post(
        f"{BASE}/content/brands/{brand.id}/ringkasan/generate", params=params, headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"] == pertama["id"]

    n = await db_super.scalar(
        select(func.count()).select_from(Summary).where(Summary.brand_id == brand.id)
    )
    assert n == 1

    r = await client.get(f"{BASE}/content/brands/{brand.id}/ringkasan", params=params, headers=h)
    data = r.json()
    assert data["ada"] is True
    assert data["id"] == pertama["id"]
    assert data["teks"] == pertama["teks"]


# ---------------------------------------------------------------------------
# (f) notifikasi: preferensi di dalam notify(); skipped tercatat
# ---------------------------------------------------------------------------

async def test_notify_preferensi_dan_log(db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner, name="Org Notif")
    brand = await _brand(db_super, org, name="Brand Notif")

    payload = {
        "organization_id": str(org.id),
        "brand_id": str(brand.id),
        "brand_name": brand.name,
        "jumlah": 3,
    }

    # default on → terkirim, log 'sent'
    terkirim = await notify(db_super, owner, "rekomendasi_baru", payload)
    assert terkirim is True
    await db_super.commit()

    log = await db_super.scalar(
        select(NotificationLog)
        .where(NotificationLog.user_id == owner.id, NotificationLog.jenis == "rekomendasi_baru")
        .order_by(NotificationLog.created_at.desc())
    )
    assert log is not None
    assert log.status == "sent"
    assert log.channel == "mock"

    # preferensi off → tidak terkirim, tapi TETAP tercatat sebagai 'skipped'
    pref = await get_or_create_preference(db_super, owner.id)
    pref.rekomendasi_baru = False
    await db_super.commit()

    terkirim = await notify(db_super, owner, "rekomendasi_baru", payload)
    assert terkirim is False
    await db_super.commit()

    log2 = await db_super.scalar(
        select(NotificationLog)
        .where(NotificationLog.user_id == owner.id, NotificationLog.jenis == "rekomendasi_baru")
        .order_by(NotificationLog.created_at.desc())
    )
    assert log2.status == "skipped"


async def test_preferensi_endpoint_milik_sendiri(client, db_super):
    user = await create_user_direct(db_super)
    h = _headers_for(user)

    r = await client.get(f"{BASE}/notifikasi/preferensi", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"rekomendasi_baru": True, "ringkasan_mingguan": True}

    r = await client.put(
        f"{BASE}/notifikasi/preferensi",
        json={"ringkasan_mingguan": False},
        headers=h,
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"rekomendasi_baru": True, "ringkasan_mingguan": False}


# ---------------------------------------------------------------------------
# pengaturan admin: simpan terenkripsi, value null = hapus
# ---------------------------------------------------------------------------

async def test_pengaturan_admin_simpan_dan_hapus(client, db_super):
    admin = await create_user_direct(db_super, is_superadmin=True)
    user = await create_user_direct(db_super)
    ha = _headers_for(admin)
    hu = _headers_for(user)

    # bukan superadmin → 403
    r = await client.get(f"{BASE}/admin/pengaturan", headers=hu)
    assert r.status_code == 403, r.text

    r = await client.get(f"{BASE}/admin/pengaturan", headers=ha)
    assert r.status_code == 200, r.text
    keys = {i["key"] for i in r.json()}
    assert {"tiktok_client_key", "tiktok_client_secret", "instagram_app_id",
            "instagram_app_secret", "whatsapp_provider", "whatsapp_api_key",
            "llm_api_key"} <= keys
    assert all(i["configured"] is False for i in r.json())

    # simpan → terenkripsi di DB, terbaca via get_setting
    r = await client.put(
        f"{BASE}/admin/pengaturan",
        json={"key": "tiktok_client_key", "value": "kunci-rahasia"},
        headers=ha,
    )
    assert r.status_code == 200, r.text
    await db_super.commit()

    row = await db_super.get(AppSetting, "tiktok_client_key")
    assert row is not None
    assert row.value_encrypted != "kunci-rahasia"
    assert await get_setting(db_super, "tiktok_client_key") == "kunci-rahasia"

    r = await client.get(f"{BASE}/admin/pengaturan", headers=ha)
    item = next(i for i in r.json() if i["key"] == "tiktok_client_key")
    assert item["configured"] is True
    assert "kunci-rahasia" not in str(r.json())

    # value null → hapus
    r = await client.put(
        f"{BASE}/admin/pengaturan",
        json={"key": "tiktok_client_key", "value": None},
        headers=ha,
    )
    assert r.status_code == 200, r.text
    await db_super.commit()
    assert await get_setting(db_super, "tiktok_client_key") is None

    # key tak dikenal → 400
    r = await client.put(
        f"{BASE}/admin/pengaturan", json={"key": "ngawur", "value": "x"}, headers=ha
    )
    assert r.status_code == 400, r.text


async def test_llm_api_key_dari_db_mendahului_env(db_super, monkeypatch):
    """resolve_llm_api_key: app_settings 'llm_api_key' dipakai dulu, lalu env."""
    from app.core.config import get_settings
    from app.services.llm import resolve_llm_api_key

    # Patch pada singleton settings yang di-cache (auto-restore oleh monkeypatch).
    monkeypatch.setattr(get_settings(), "LLM_API_KEY", "kunci-dari-env")

    # DB kosong → fallback env
    assert await resolve_llm_api_key(db_super) == "kunci-dari-env"

    # DB ada → DB menang atas env
    await set_setting(db_super, "llm_api_key", "kunci-dari-db")
    await db_super.commit()
    assert await resolve_llm_api_key(db_super) == "kunci-dari-db"

    # DB dihapus → kembali ke env
    await set_setting(db_super, "llm_api_key", None)
    await db_super.commit()
    assert await resolve_llm_api_key(db_super) == "kunci-dari-env"

    # env kosong juga → None
    monkeypatch.setattr(get_settings(), "LLM_API_KEY", "")
    assert await resolve_llm_api_key(db_super) is None


# ---------------------------------------------------------------------------
# get_provider: nyata bila kredensial lengkap, mock bila tidak
# ---------------------------------------------------------------------------

async def test_get_provider_mock_tanpa_kredensial(db_super):
    await _hapus_kredensial_tiktok(db_super)
    provider = get_provider("tiktok", lambda k: None)
    assert provider.platform_name == "tiktok"
    assert type(provider).__name__ == "MockSyncProvider"


async def test_normalize_dipakai_bersama_csv_dan_sync():
    """Baris valid lolos; baris rusak raise NormalizationError (pesan Fase 1)."""
    from app.services.normalize import NormalizationError, normalize_content_row

    ok = normalize_content_row("tiktok", {
        "post_id": "v1", "tanggal_posting": "2026-09-01", "format": "reels",
        "tujuan": "hiburan", "views": "1000", "likes": "",
    })
    assert ok["views"] == 1000 and ok["likes"] == 0
    assert ok["platform"] == "tiktok"

    with pytest.raises(NormalizationError, match="post_id kosong"):
        normalize_content_row("tiktok", {"tanggal_posting": "2026-09-01",
                                        "format": "reels", "tujuan": "hiburan"})


# ---------------------------------------------------------------------------
# Dev-only: POST /dev/koneksi/mock — hubungkan akun demo tanpa OAuth asli
# ---------------------------------------------------------------------------

async def test_dev_mock_koneksi_membuat_akun(client, db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    brand = await _brand(db_super, org)

    h = _headers_for(owner)
    h["X-Organization-Id"] = str(org.id)
    r = await client.post(
        f"{BASE}/dev/koneksi/mock",
        headers=h,
        json={"brand_id": str(brand.id), "platform": "tiktok"},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["platform"] == "tiktok"
    assert data["status"] == "aktif"
    assert "mock" in (data["account_name"] or "").lower()

    acc = await db_super.scalar(
        select(ConnectedAccount).where(ConnectedAccount.id == data["id"])
    )
    assert acc is not None
    assert acc.brand_id == brand.id
    # token dummy tersimpan terenkripsi, bukan plaintext
    assert acc.access_token_encrypted != "mock-access-tiktok-dev"
    assert decrypt_text(acc.access_token_encrypted) == "mock-access-tiktok-dev"

    # panggil lagi → update, bukan duplikat (id sama)
    r2 = await client.post(
        f"{BASE}/dev/koneksi/mock",
        headers=h,
        json={"brand_id": str(brand.id), "platform": "tiktok"},
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["id"] == data["id"]


async def test_dev_mock_koneksi_platform_tidak_valid(client, db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    brand = await _brand(db_super, org)

    h = _headers_for(owner)
    h["X-Organization-Id"] = str(org.id)
    r = await client.post(
        f"{BASE}/dev/koneksi/mock",
        headers=h,
        json={"brand_id": str(brand.id), "platform": "youtube"},
    )
    assert r.status_code == 400, r.text


async def test_dev_mock_koneksi_brand_org_lain_404(client, db_super):
    owner = await create_user_direct(db_super)
    org = await create_org_direct(db_super, owner)
    owner2 = await create_user_direct(db_super)
    org2 = await create_org_direct(db_super, owner2)
    brand2 = await _brand(db_super, org2)

    h = _headers_for(owner)
    h["X-Organization-Id"] = str(org.id)
    r = await client.post(
        f"{BASE}/dev/koneksi/mock",
        headers=h,
        json={"brand_id": str(brand2.id), "platform": "instagram"},
    )
    assert r.status_code == 404, r.text
