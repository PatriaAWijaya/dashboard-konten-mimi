"""Tes API content (upload CSV, skoring, dashboard, analisa, rekomendasi, niche).

Memakai kolom CSV & model ASLI Worker Data, lewat HTTP dengan auth penuh
(register/login + header X-Organization-Id).
"""

import io
import uuid

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

from app.models.organization import OrganizationMember
from app.services.email import get_dev_outbox
from app.services.membership import activate
from tests.conftest import auth_headers, create_plan_direct, create_user_direct

BASE = "/api/v1"
PESAN_KURANG_DATA = "Data belum cukup (butuh ≥10 konten per periode)."

KOLOM = [
    "platform", "post_id", "post_url", "tanggal_posting", "format", "tujuan",
    "caption", "views", "reach", "likes", "comments", "shares", "saves",
    "avg_watch_seconds", "profile_clicks", "link_clicks", "replies", "sticker_taps",
]
_MENANG = [20000, 20000, 2000, 400, 600, 800, 25, 10, 5, 20, 0]
_KURANG = [1500, 1500, 5, 0, 0, 2, 3, 0, 0, 0, 0]

# (post_id, format, tujuan, tanggal, menang?)
BARIS_12 = (
    [("r1", "reels", "edukasi", "2026-09-05", True),
     ("r2", "reels", "edukasi", "2026-09-06", True),
     ("r3", "reels", "edukasi", "2026-09-07", True),
     ("r4", "reels", "edukasi", "2026-09-08", False),
     ("r5", "reels", "edukasi", "2026-09-09", False),
     ("c1", "carousel", "jualan", "2026-09-10", False),
     ("c2", "carousel", "jualan", "2026-09-11", False),
     ("c3", "carousel", "jualan", "2026-09-12", False),
     ("c4", "carousel", "jualan", "2026-09-13", False),
     ("f1", "foto", "hiburan", "2026-09-14", True),
     ("f2", "foto", "hiburan", "2026-09-15", False),
     ("f3", "foto", "hiburan", "2026-09-16", False)]
)
BARIS_5 = BARIS_12[:5]

JAWABAN = [
    "Saya Patria, brand strategist untuk NGO dan yayasan di Indonesia.",
    "Jasa konsultasi branding dan workshop strategi konten untuk yayasan.",
    "Pengurus yayasan dan NGO kecil di Jawa Timur usia 30-45 tahun.",
    "Yayasan kesulitan fundraising karena brand-nya tidak dikenal donatur.",
    "Pengalaman 20 tahun membangun brand NGO hingga event 17.000 anak yatim.",
    "Strategi brand dan cara mengubah donatur menjadi advokat setia.",
    "Menaikkan donasi 3x lipat untuk sebuah yayasan dalam 6 bulan.",
    "Membership bulanan Rp99rb plus jasa konsultasi brand untuk yayasan.",
]


def _csv(baris):
    buf = io.StringIO()
    buf.write(",".join(KOLOM) + "\n")
    for pid, fmt, tjn, tgl, menang in baris:
        metrik = _MENANG if menang else _KURANG
        sel = [str(x) for x in
               ["tiktok", pid, f"https://tiktok.com/@x/video/{pid}", tgl, fmt, tjn,
                f"caption {pid}"] + metrik]
        buf.write(",".join(sel) + "\n")
    return buf.getvalue().encode()


async def _setup(client, db_super, email):
    """Register+login, buat org+brand. Return (headers, brand_id, org_id, token)."""
    r = await client.post(
        f"{BASE}/auth/register",
        json={"name": "API User", "email": email, "password": "Password123"},
    )
    assert r.status_code == 201, r.text
    token = get_dev_outbox()[-1].token
    r = await client.post(f"{BASE}/auth/verify-email", json={"token": token})
    assert r.status_code == 200, r.text
    r = await client.post(
        f"{BASE}/auth/login", json={"email": email, "password": "Password123"}
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    r = await client.post(
        f"{BASE}/organizations", json={"name": "Org API"},
        headers=auth_headers(token),
    )
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]
    # Aktifkan membership (bypass alur pembayaran untuk tes API).
    plan = await create_plan_direct(db_super)
    await activate(db_super, organization_id=uuid.UUID(org_id), plan_id=plan.id)
    await db_super.commit()
    h = auth_headers(token, org_id)
    r = await client.post(
        f"{BASE}/organizations/{org_id}/brands", json={"name": "Brand API"}, headers=h
    )
    assert r.status_code == 201, r.text
    return h, r.json()["id"], org_id, token


async def _upload(client, h, brand_id, baris):
    return await client.post(
        f"{BASE}/content/upload",
        files={"file": ("data.csv", _csv(baris), "text/csv")},
        data={"brand_id": brand_id, "platform": "tiktok"},
        headers=h,
    )


async def test_csv_format_dokumentasi_kolom_asli(client, db_super):
    h, _, _, _ = await _setup(client, db_super, "fmt@example.com")
    r = await client.get(f"{BASE}/content/csv-format", headers=h)
    assert r.status_code == 200
    nama = {c["nama"] for c in r.json()}
    assert {"platform", "post_id", "tanggal_posting", "format", "tujuan",
            "views", "avg_watch_seconds", "sticker_taps"} <= nama


async def test_upload_csv_lalu_score_dashboard_analisa(client, db_super):
    h, brand_id, _, _ = await _setup(client, db_super, "alur@example.com")

    r = await _upload(client, h, brand_id, BARIS_12)
    assert r.status_code == 200, r.text
    hasil = r.json()
    assert hasil["contents_baru"] == 12
    assert hasil["contents_diupdate"] == 0
    assert hasil["baris_gagal"] == []  # list of dict (kontrak asli), bukan int

    r = await client.post(
        f"{BASE}/content/brands/{brand_id}/score", json={"preset": "30d"}, headers=h
    )
    assert r.status_code == 200, r.text
    assert r.json()["diskor"] == 12

    r = await client.get(
        f"{BASE}/content/brands/{brand_id}/dashboard", params={"preset": "30d"}, headers=h
    )
    assert r.status_code == 200, r.text
    dash = r.json()
    assert dash["kartu"]["tiktok"]["jumlah_konten"] == 12
    assert len(dash["konten"]) == 12
    assert len(dash["tren"]) >= 1
    for item in dash["konten"]:
        assert item["er"] >= 0
        assert isinstance(item["labels"], list)
        assert item["status"] in ("menang", "cukup", "kurang", "belum_diskor")

    r = await client.get(
        f"{BASE}/content/brands/{brand_id}/analisa", params={"preset": "30d"}, headers=h
    )
    assert r.status_code == 200, r.text
    analisa = r.json()
    assert isinstance(analisa["ringkasan"], list)
    assert isinstance(analisa["bermasalah"], list)
    assert isinstance(analisa["rekomendasi_pola"], list)


async def test_upload_platform_tidak_valid_ditolak(client, db_super):
    h, brand_id, _, _ = await _setup(client, db_super, "plat@example.com")
    r = await client.post(
        f"{BASE}/content/upload",
        files={"file": ("data.csv", _csv(BARIS_5), "text/csv")},
        data={"brand_id": brand_id, "platform": "youtube"},
        headers=h,
    )
    assert r.status_code == 400
    assert "tiktok" in r.json()["detail"]


async def test_generate_kurang_data_pesan_persis(client, db_super):
    h, brand_id, _, _ = await _setup(client, db_super, "kurang@example.com")
    r = await _upload(client, h, brand_id, BARIS_5)
    assert r.status_code == 200
    r = await client.post(
        f"{BASE}/content/brands/{brand_id}/score", json={"preset": "30d"}, headers=h
    )
    assert r.status_code == 200
    r = await client.post(
        f"{BASE}/content/brands/{brand_id}/recommendations/generate",
        json={"preset": "30d"}, headers=h,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dibuat"] == []
    assert body["pesan"] == PESAN_KURANG_DATA


async def test_generate_rekomendasi_terima_tolak_dan_dedup(client, db_super):
    h, brand_id, _, _ = await _setup(client, db_super, "rec@example.com")
    r = await _upload(client, h, brand_id, BARIS_12)
    assert r.status_code == 200
    await client.post(
        f"{BASE}/content/brands/{brand_id}/score", json={"preset": "30d"}, headers=h
    )

    r = await client.post(
        f"{BASE}/content/brands/{brand_id}/recommendations/generate",
        json={"preset": "30d"}, headers=h,
    )
    assert r.status_code == 200
    dibuat = r.json()["dibuat"]
    assert len(dibuat) >= 4
    tipe = {(d["type"], d["evidence"].get("format"), d["evidence"].get("tujuan")) for d in dibuat}
    assert ("perbanyak", "reels", "edukasi") in tipe
    assert ("kurangi", "carousel", "jualan") in tipe
    for d in dibuat:
        assert d["title"]
        assert d["narrative"]
        assert d["status"] == "baru"

    # Cache: generate kedua tidak menambah.
    r2 = await client.post(
        f"{BASE}/content/brands/{brand_id}/recommendations/generate",
        json={"preset": "30d"}, headers=h,
    )
    assert {d["id"] for d in r2.json()["dibuat"]} == {d["id"] for d in dibuat}

    # Terima & tolak.
    perbanyak = next(d for d in dibuat if d["type"] == "perbanyak")
    r = await client.post(
        f"{BASE}/content/recommendations/{perbanyak['id']}/terima", headers=h
    )
    assert r.status_code == 200
    assert r.json()["status"] == "diterima"

    kurangi = next(d for d in dibuat if d["type"] == "kurangi")
    r = await client.post(
        f"{BASE}/content/recommendations/{kurangi['id']}/tolak", headers=h
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ditolak"

    # Yang ditolak tidak muncul lagi.
    r = await client.post(
        f"{BASE}/content/brands/{brand_id}/recommendations/generate",
        json={"preset": "30d"}, headers=h,
    )
    segar = r.json()["dibuat"]
    assert all(d["status"] != "ditolak" for d in segar)
    assert kurangi["id"] not in {d["id"] for d in segar}


async def test_isolasi_organisasi_brand_lain_404(client, db_super):
    h, _, org_id, token = await _setup(client, db_super, "iso@example.com")
    r = await client.post(
        f"{BASE}/organizations", json={"name": "Org Lain"},
        headers=auth_headers(token),
    )
    org2 = r.json()["id"]
    plan2 = await create_plan_direct(db_super)
    await activate(db_super, organization_id=uuid.UUID(org2), plan_id=plan2.id)
    await db_super.commit()
    h2 = auth_headers(token, org2)
    r = await client.post(
        f"{BASE}/organizations/{org2}/brands", json={"name": "Brand Lain"}, headers=h2
    )
    brand2 = r.json()["id"]
    # Akses brand org2 dengan header org1 -> 404.
    r = await client.get(
        f"{BASE}/content/brands/{brand2}/dashboard", params={"preset": "30d"}, headers=h
    )
    assert r.status_code == 404


async def test_viewer_bisa_baca_tidak_bisa_tulis(client, db_super):
    h, brand_id, org_id, _ = await _setup(client, db_super, "owner2@example.com")
    viewer = await create_user_direct(db_super, email="viewer@example.com")
    db_super.add(OrganizationMember(
        organization_id=org_id, user_id=viewer.id, role="viewer"
    ))
    await db_super.commit()
    r = await client.post(
        f"{BASE}/auth/login", json={"email": "viewer@example.com", "password": "Password123"}
    )
    hv = auth_headers(r.json()["access_token"], org_id)

    r = await client.get(
        f"{BASE}/content/brands/{brand_id}/dashboard", params={"preset": "30d"}, headers=hv
    )
    assert r.status_code == 200

    r = await _upload(client, hv, brand_id, BARIS_5)
    assert r.status_code == 403


async def test_niche_flow_lengkap_via_api(client, db_super):
    h, brand_id, _, _ = await _setup(client, db_super, "niche@example.com")

    r = await client.post(f"{BASE}/content/brands/{brand_id}/niche/interviews", headers=h)
    assert r.status_code == 201, r.text
    iid = r.json()["id"]
    assert r.json()["pertanyaan_berikut"]["pertanyaan"]

    for step, jawaban in enumerate(JAWABAN):
        r = await client.post(
            f"{BASE}/content/niche/interviews/{iid}/jawab",
            json={"step": step, "jawaban": jawaban, "dilewati": False}, headers=h,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "ok"

    r = await client.get(f"{BASE}/content/niche/interviews/{iid}", headers=h)
    assert r.json()["status"] == "selesai"

    r = await client.post(f"{BASE}/content/niche/interviews/{iid}/sintesis", headers=h)
    assert r.status_code == 200, r.text
    dna = r.json()
    assert dna["version"] == 1
    assert not dna["confirmed"]
    assert "ringkasan" not in dna  # model asli tidak punya kolom ini

    r = await client.put(f"{BASE}/content/niche/dna/{dna['id']}/konfirmasi", headers=h)
    assert r.status_code == 200
    assert r.json()["confirmed"] is True

    r = await client.get(f"{BASE}/content/brands/{brand_id}/niche/saran", headers=h)
    assert r.status_code == 200, r.text
    saran = r.json()
    assert saran["dibuat_baru"] is True
    assert 5 <= len(saran["saran"]) <= 7
    assert all(isinstance(s["match_percent"], int) for s in saran["saran"])

    ids = [s["id"] for s in saran["saran"][:2]]
    r = await client.post(
        f"{BASE}/content/brands/{brand_id}/niche/pilih", json={"ids": ids}, headers=h
    )
    assert r.status_code == 200, r.text
    assert all(s["is_selected"] for s in r.json())

    # Pilih 3 -> 422 dari validasi Pydantic.
    r = await client.post(
        f"{BASE}/content/brands/{brand_id}/niche/pilih",
        json={"ids": [s["id"] for s in saran["saran"][:3]]}, headers=h,
    )
    assert r.status_code == 422
