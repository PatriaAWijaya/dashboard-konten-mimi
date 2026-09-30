#!/usr/bin/env python3
"""Uji ulang alur konten dengan nilai format yang valid (reels/carousel)."""
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


pw = open("/home/hatch/workspace/dashboard-konten-ai/.admin_password_new.txt").read().strip()
kode, resp = panggil("POST", "/auth/login", {"email": ADMIN_EMAIL, "password": pw})
token = resp.get("access_token") if kode == 200 else None
catat("login admin", bool(token), f"HTTP {kode}")
if not token:
    raise SystemExit(1)

kode, resp = panggil("GET", "/organizations", token=token)
org = next((o for o in (resp if isinstance(resp, list) else [])
            if o.get("name") == "Org Uji Billing"), None)
org_id = org["id"]
kode, resp = panggil("GET", f"/organizations/{org_id}/brands",
                     token=token, header_org=org_id)
brand = next((b for b in (resp if isinstance(resp, list) else [])
              if b.get("name") == "Brand Uji Billing"), None)
brand_id = brand["id"]
catat("org+brand uji siap", True)

kolom = ["platform", "post_id", "post_url", "tanggal_posting", "format",
         "tujuan", "caption", "views", "reach", "likes", "comments",
         "shares", "saves", "avg_watch_seconds", "profile_clicks",
         "link_clicks", "replies", "sticker_taps"]
formats = ["reels", "carousel", "reels", "foto", "reels", "story", "carousel"]
tujuans = ["edukasi", "hiburan", "interaksi", "jualan", "branding",
           "edukasi", "jualan"]
baris = []
for i in range(1, 8):
    baris.append(
        f"tiktok,okvid{i},https://tiktok.com/@x/video/{i},2026-09-2{i},"
        f"{formats[i-1]},{tujuans[i-1]},\"Konten valid {i}\",{1500*i},{1200*i},"
        f"{150*i},{12*i},{6*i},{9*i},14.2,{4*i},{3*i},{2*i},{1}")
with open("/home/hatch/workspace/dashboard-konten-ai/.e2e_ok.csv", "w") as f:
    f.write("\n".join([",".join(kolom)] + baris) + "\n")

r = subprocess.run(
    ["curl", "-s", "-o", "/home/hatch/workspace/dashboard-konten-ai/.e2e_ok_up.json",
     "-w", "%{http_code}", "-X", "POST", API + "/content/upload",
     "-H", f"Authorization: Bearer {token}",
     "-H", f"X-Organization-Id: {org_id}",
     "-F", f"brand_id={brand_id}", "-F", "platform=tiktok",
     "-F", "file=@/home/hatch/workspace/dashboard-konten-ai/.e2e_ok.csv;type=text/csv"],
    capture_output=True, text=True, timeout=120)
up = json.loads(open("/home/hatch/workspace/dashboard-konten-ai/.e2e_ok_up.json").read())
catat("upload CSV (format valid)", r.stdout.strip() in ("200", "201")
      and up.get("metrics_rows", 0) > 0,
      f"HTTP {r.stdout.strip()} rows={up.get('metrics_rows')} gagal={len(up.get('baris_gagal', []))}")

kode, resp = panggil("POST", f"/content/brands/{brand_id}/score", {},
                     token=token, header_org=org_id)
diskor = resp.get("diskor") if isinstance(resp, dict) else None
catat("scoring", kode == 200 and (diskor or 0) > 0, f"HTTP {kode} diskor={diskor}")

kode, resp = panggil("GET", f"/content/brands/{brand_id}/dashboard",
                     token=token, header_org=org_id)
kunci = list(resp.keys()) if isinstance(resp, dict) else []
catat("dashboard", kode == 200, f"HTTP {kode} keys={kunci}")

kode, resp = panggil("GET", f"/content/brands/{brand_id}/analisa",
                     token=token, header_org=org_id)
n_rec, kunci = 0, []
if isinstance(resp, dict):
    kunci = list(resp.keys())
    for k in ("rekomendasi", "recommendations", "rekomendasi_pola"):
        v = resp.get(k)
        if isinstance(v, list):
            n_rec += len(v)
catat("analisa/rekomendasi", kode == 200, f"HTTP {kode} rekomendasi={n_rec} keys={kunci}")

lolos = sum(1 for h in HASIL if h["lolos"])
print(f"\nRINGKASAN: {lolos}/{len(HASIL)} lolos")
