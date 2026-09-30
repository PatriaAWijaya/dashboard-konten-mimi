#!/usr/bin/env python3
"""E2E alur billing + konten sebagai admin.

Org baru -> invoice -> bukti bayar -> approve admin -> membership ACTIVE
-> brand -> upload CSV -> score -> dashboard -> analisa -> onboarding.
"""
import base64
import json
import subprocess
import urllib.error
import urllib.request

API = "https://dkai-api-v4cv.onrender.com/api/v1"
ADMIN_EMAIL = "admin@example.com"
HASIL = []


def catat(nama, ok, info=""):
    HASIL.append({"langkah": nama, "lolos": ok, "info": info})
    print(f"[{'OK' if ok else 'GAGAL'}] {nama} {info}", flush=True)


def panggil(method, path, body=None, token=None, header_org=None):
    url = API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if header_org:
        req.add_header("X-Organization-Id", header_org)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            mentah = r.read().decode()
            return r.status, (json.loads(mentah) if mentah else {})
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:300]
        except Exception:
            detail = ""
        return e.code, {"_error": detail}
    except Exception as e:
        return -1, {"_error": f"{type(e).__name__}: {e}"}


def curl_multipart(path, token, header_org, fields, file_field=None, file_path=None):
    cmd = ["curl", "-s", "-o", "/tmp/e2e_bc.json", "-w", "%{http_code}",
           "-X", "POST", API + path,
           "-H", f"Authorization: Bearer {token}"]
    if header_org:
        cmd += ["-H", f"X-Organization-Id: {header_org}"]
    for k, v in fields.items():
        cmd += ["-F", f"{k}={v}"]
    if file_field and file_path:
        cmd += ["-F", f"{file_field}=@{file_path}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    try:
        body = open("/tmp/e2e_bc.json").read()[:200]
    except Exception:
        body = ""
    return r.stdout.strip(), body


with open("/tmp/e2e_admin_pw.txt") as f:
    pw_admin = f.read().strip()

kode, resp = panggil("POST", "/auth/login",
                     {"email": ADMIN_EMAIL, "password": pw_admin})
token = resp.get("access_token") if kode == 200 else None
catat("login admin", kode == 200 and bool(token), f"HTTP {kode}")
if not token:
    raise SystemExit(1)

# 1. org baru
kode, resp = panggil("POST", "/organizations", {"name": "Org Uji Billing"}, token=token)
org_id = resp.get("id") if kode == 201 else None
catat("buat organisasi (admin terverifikasi)", kode == 201, f"HTTP {kode}")
if not org_id:
    print(json.dumps(HASIL, indent=1))
    raise SystemExit(1)

# 2. paket
kode, resp = panggil("GET", "/plans", token=token, header_org=org_id)
plans = resp if isinstance(resp, list) else []
plan = next((p for p in plans if p.get("name") == "Paket Tahunan"), None)
plan_id = plan["id"] if plan else None
catat("paket 'Paket Tahunan' dari seed ada", bool(plan_id), f"HTTP {kode}")

# 3. invoice
inv_id = None
if plan_id:
    kode, resp = panggil("POST", "/billing/invoices",
                         {"organization_id": org_id, "plan_id": plan_id},
                         token=token, header_org=org_id)
    inv_id = resp.get("id") if kode == 201 else None
    catat("buat invoice", kode == 201, f"HTTP {kode}")

# 4. bukti bayar (PNG 1px)
png_1px = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
open("/tmp/bukti.png", "wb").write(png_1px)
pay_id = None
if inv_id:
    kode_s, body = curl_multipart(f"/billing/invoices/{inv_id}/payment-proof",
                                  token, org_id, {}, "file", "/tmp/bukti.png")
    catat("upload bukti bayar", kode_s in ("200", "201"), f"HTTP {kode_s} {body}")
    try:
        pay_id = json.loads(open("/tmp/e2e_bc.json").read()).get("payment_id") or \
                 json.loads(open("/tmp/e2e_bc.json").read()).get("id")
    except Exception:
        pass

# 5. approve via antrian admin
if not pay_id:
    kode, resp = panggil("GET", "/admin/payments/queue", token=token)
    q = resp if isinstance(resp, list) else []
    it = next((x for x in q if x.get("organization_id") == org_id), q[0] if q else None)
    pay_id = it.get("id") or it.get("payment_id") if it else None
    catat("payment masuk antrian admin", bool(pay_id), f"HTTP {kode}")
if pay_id:
    kode, resp = panggil("POST", f"/admin/payments/{pay_id}/approve", {}, token=token)
    catat("approve pembayaran", kode == 200, f"HTTP {kode} {str(resp)[:150]}")

# 6. membership aktif?
kode, resp = panggil("GET", "/billing/memberships", token=token, header_org=org_id)
st = resp.get("status") if isinstance(resp, dict) else None
catat("membership aktif", st not in (None, "pending_payment"), f"HTTP {kode} status={st}")

# 7. brand
kode, resp = panggil("POST", f"/organizations/{org_id}/brands",
                     {"name": "Brand Uji Billing", "industry": "Kuliner"},
                     token=token, header_org=org_id)
brand_id = resp.get("id") if kode == 201 else None
catat("buat brand", kode == 201, f"HTTP {kode}")

if brand_id:
    # 8. onboarding
    kode, _ = panggil("GET", "/onboarding/status", token=token,
                      header_org=org_id)
    # endpoint butuh query brand_id
    kode, resp = panggil("GET", "/onboarding/status", token=token,
                         header_org=org_id)
    import urllib.parse
    url = API + f"/onboarding/status?brand_id={urllib.parse.quote(brand_id)}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-Organization-Id", org_id)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            kode, ob = r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        kode, ob = e.code, {}
    catat("status onboarding", kode == 200, f"HTTP {kode}")

    kode, _ = panggil("PUT", "/onboarding/progress",
                      {"brand_id": brand_id, "langkah": "hubungkan_data"},
                      token=token, header_org=org_id)
    catat("progress onboarding", kode == 200, f"HTTP {kode}")

    # 9. CSV
    kolom = ["platform", "post_id", "post_url", "tanggal_posting", "format",
             "tujuan", "caption", "views", "reach", "likes", "comments",
             "shares", "saves", "avg_watch_seconds", "profile_clicks",
             "link_clicks", "replies", "sticker_taps"]
    baris = []
    for i in range(1, 8):
        baris.append(
            f"tiktok,billvid{i},https://tiktok.com/@x/video/{i},2026-09-2{i},"
            f"video,awareness,\"Konten billing {i}\",{1500*i},{1200*i},{150*i},"
            f"{12*i},{6*i},{9*i},14.2,{4*i},{3*i},{2*i},{1}")
    with open("/tmp/e2e_bill.csv", "w") as f:
        f.write("\n".join([",".join(kolom)] + baris) + "\n")
    kode_s, body = curl_multipart("/content/upload", token, org_id,
                                  {"brand_id": brand_id, "platform": "tiktok"},
                                  "file", "/tmp/e2e_bill.csv")
    catat("upload CSV", kode_s in ("200", "201"), f"HTTP {kode_s} {body}")

    kode, _ = panggil("POST", f"/content/brands/{brand_id}/score", {},
                      token=token, header_org=org_id)
    catat("scoring", kode == 200, f"HTTP {kode}")

    kode, resp = panggil("GET", f"/content/brands/{brand_id}/dashboard",
                         token=token, header_org=org_id)
    kunci = list(resp.keys())[:6] if isinstance(resp, dict) else []
    catat("dashboard", kode == 200, f"HTTP {kode} keys={kunci}")

    kode, resp = panggil("GET", f"/content/brands/{brand_id}/analisa",
                         token=token, header_org=org_id)
    n_rec = 0
    if isinstance(resp, dict):
        for k in ("rekomendasi", "recommendations"):
            if isinstance(resp.get(k), list):
                n_rec = len(resp[k])
    catat("analisa/rekomendasi", kode == 200, f"HTTP {kode} rekomendasi={n_rec}")

lolos = sum(1 for h in HASIL if h["lolos"])
print(f"\nRINGKASAN: {lolos}/{len(HASIL)} lolos")
print(json.dumps(HASIL, indent=1))
