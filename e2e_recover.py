#!/usr/bin/env python3
"""Pemulihan akses admin + selesaikan E2E konten.

Fase A: poll login admin@example.com / Admin123! tiap 90 dtk (deploy baru).
Fase B: rotasi password -> simpan di workspace (BUKAN /tmp).
Fase C: E2E konten (onboarding, CSV, scoring, dashboard, analisa).
"""
import json
import secrets
import string
import subprocess
import urllib.error
import urllib.request
import urllib.parse

API = "https://dkai-api-v4cv.onrender.com/api/v1"
ADMIN_EMAIL = "admin@example.com"
PW_FILE = "/home/hatch/workspace/dashboard-konten-ai/.admin_password_new.txt"
HASIL = []


def catat(nama, ok, info=""):
    HASIL.append({"langkah": nama, "lolos": ok, "info": info})
    print(f"[{'OK' if ok else 'GAGAL'}] {nama} {info}", flush=True)


def panggil(method, path, body=None, token=None, header_org=None, query=""):
    url = API + path + query
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if header_org:
        req.add_header("X-Organization-Id", header_org)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
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


# ---- Fase A: tunggu deploy ----
print("Fase A: menunggu deploy pemulihan (poll login tiap 90 dtk)...", flush=True)
token = None
for i in range(15):
    kode, resp = panggil("POST", "/auth/login",
                         {"email": ADMIN_EMAIL, "password": "Admin123!"})
    print(f"  poll {i+1}: login -> {kode}", flush=True)
    if kode == 200 and resp.get("access_token"):
        token = resp["access_token"]
        catat("deploy pemulihan live", True)
        break
    if i < 14:
        import time as _t
        _t.sleep(90)
if not token:
    catat("deploy pemulihan live", False, "timeout")
    print(json.dumps(HASIL, indent=1))
    raise SystemExit(1)

# ---- Fase B: rotasi ----
alfabet = string.ascii_letters + string.digits
pw_baru = "".join(secrets.choice(alfabet) for _ in range(20))
kode, _ = panggil("POST", "/users/me/change-password",
                  {"old_password": "Admin123!", "new_password": pw_baru},
                  token=token)
catat("rotasi password admin", kode == 200, f"HTTP {kode}")
if kode == 200:
    with open(PW_FILE, "w") as f:
        f.write(pw_baru)
    kode2, resp2 = panggil("POST", "/auth/login",
                           {"email": ADMIN_EMAIL, "password": pw_baru})
    token = resp2.get("access_token") if kode2 == 200 else None
    catat("login dengan password baru", kode2 == 200 and bool(token), f"HTTP {kode2}")
if not token:
    print(json.dumps(HASIL, indent=1))
    raise SystemExit(1)

# ---- Fase C: E2E konten ----
kode, resp = panggil("GET", "/organizations", token=token)
orgs = resp if isinstance(resp, list) else []
org = next((o for o in orgs if o.get("name") == "Org Uji Billing"), None)
org_id = org["id"] if org else None
catat("org uji billing ada", bool(org_id), f"HTTP {kode}")

brand_id = None
if org_id:
    kode, resp = panggil("GET", f"/organizations/{org_id}/brands",
                         token=token, header_org=org_id)
    brands = resp if isinstance(resp, list) else []
    brand = next((b for b in brands if b.get("name") == "Brand Uji Billing"), None)
    brand_id = brand["id"] if brand else None
    catat("brand uji ada", bool(brand_id), f"HTTP {kode}")

if brand_id:
    q = "?brand_id=" + urllib.parse.quote(brand_id)
    kode, _ = panggil("GET", "/onboarding/status", token=token,
                      header_org=org_id, query=q)
    catat("status onboarding", kode == 200, f"HTTP {kode}")

    kode, _ = panggil("PUT", "/onboarding/progress",
                      {"brand_id": brand_id, "langkah": "hubungkan_data"},
                      token=token, header_org=org_id)
    catat("progress onboarding", kode == 200, f"HTTP {kode}")

    kode, _ = panggil("POST", "/onboarding/selesai",
                      {"brand_id": brand_id}, token=token, header_org=org_id)
    catat("onboarding selesai", kode == 200, f"HTTP {kode}")

    kolom = ["platform", "post_id", "post_url", "tanggal_posting", "format",
             "tujuan", "caption", "views", "reach", "likes", "comments",
             "shares", "saves", "avg_watch_seconds", "profile_clicks",
             "link_clicks", "replies", "sticker_taps"]
    baris = []
    for i in range(1, 8):
        baris.append(
            f"tiktok,finalvid{i},https://tiktok.com/@x/video/{i},2026-09-2{i},"
            f"video,awareness,\"Konten final {i}\",{1500*i},{1200*i},{150*i},"
            f"{12*i},{6*i},{9*i},14.2,{4*i},{3*i},{2*i},{1}")
    with open("/home/hatch/workspace/dashboard-konten-ai/.e2e_final.csv", "w") as f:
        f.write("\n".join([",".join(kolom)] + baris) + "\n")
    r = subprocess.run(
        ["curl", "-s", "-o", "/home/hatch/workspace/dashboard-konten-ai/.e2e_up.json",
         "-w", "%{http_code}", "-X", "POST", API + "/content/upload",
         "-H", f"Authorization: Bearer {token}",
         "-H", f"X-Organization-Id: {org_id}",
         "-F", f"brand_id={brand_id}", "-F", "platform=tiktok",
         "-F", "file=@/home/hatch/workspace/dashboard-konten-ai/.e2e_final.csv;type=text/csv"],
        capture_output=True, text=True, timeout=120)
    try:
        body = open("/home/hatch/workspace/dashboard-konten-ai/.e2e_up.json").read()[:200]
    except Exception:
        body = ""
    catat("upload CSV", r.stdout.strip() in ("200", "201"),
          f"HTTP {r.stdout.strip()} {body}")

    kode, resp = panggil("POST", f"/content/brands/{brand_id}/score", {},
                         token=token, header_org=org_id)
    catat("scoring", kode == 200, f"HTTP {kode} {str(resp)[:150]}")

    kode, resp = panggil("GET", f"/content/brands/{brand_id}/dashboard",
                         token=token, header_org=org_id)
    kunci = list(resp.keys())[:8] if isinstance(resp, dict) else []
    catat("dashboard", kode == 200, f"HTTP {kode} keys={kunci}")

    kode, resp = panggil("GET", f"/content/brands/{brand_id}/analisa",
                         token=token, header_org=org_id)
    n_rec, kunci = 0, []
    if isinstance(resp, dict):
        kunci = list(resp.keys())[:8]
        for k in ("rekomendasi", "recommendations"):
            if isinstance(resp.get(k), list):
                n_rec = len(resp[k])
    catat("analisa/rekomendasi", kode == 200,
          f"HTTP {kode} rekomendasi={n_rec} keys={kunci}")

lolos = sum(1 for h in HASIL if h["lolos"])
print(f"\nRINGKASAN: {lolos}/{len(HASIL)} lolos")
print(json.dumps(HASIL, indent=1))
