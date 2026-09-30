#!/usr/bin/env python3
"""E2E fitur baru: upload CSV batch multi-file + perbandingan MoM/YoY.

Alur: register akun uji -> verifikasi email via Gmail -> login -> org ->
brand -> upload batch 3 file (Q1/Q2/Q3 2026) -> uji idempoten -> scoring
12bln -> perbandingan (MoM terisi, YoY kosong) -> dashboard & analisa
preset baru.
"""
import json
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.request

API = "https://dkai-api-v4cv.onrender.com/api/v1"
EMAIL = "wijaya.patria+dkaitest7@gmail.com"
PASSWORD = "Uji" + secrets.token_hex(6) + "1!"
HASIL = []


def catat(nama, ok, info=""):
    HASIL.append({"langkah": nama, "lolos": bool(ok), "info": info})
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
            detail = e.read().decode()[:400]
        except Exception:
            detail = ""
        return e.code, {"_error": detail}
    except Exception as e:
        return -1, {"_error": f"{type(e).__name__}: {e}"}


def gmail_triage(query):
    out = subprocess.run(
        ["hatch_gws_cli", "gmail", "+triage", "--query", query, "--max", "5", "--format", "json"],
        capture_output=True, text=True, timeout=60)
    try:
        return json.loads(out.stdout)
    except Exception:
        return {"_error": out.stdout[:200] + out.stderr[:200]}


def gmail_read(mid):
    out = subprocess.run(
        ["hatch_gws_cli", "gmail", "+read", "--id", mid, "--format", "json"],
        capture_output=True, text=True, timeout=60)
    return out.stdout


# 1. Register
kode, resp = panggil("POST", "/auth/register",
                     {"email": EMAIL, "password": PASSWORD, "name": "Uji Batch"})
catat("register akun uji", kode in (200, 201), f"HTTP {kode}")

# 2. Tunggu email verifikasi, ambil token
token_verif = None
for _ in range(12):
    time.sleep(15)
    hasil = gmail_triage(f"to:{EMAIL} subject:verifikasi newer_than:1d")
    msgs = hasil.get("messages") or hasil.get("results") or []
    if isinstance(hasil, list):
        msgs = hasil
    for m in msgs:
        mid = m.get("id")
        if not mid:
            continue
        body = gmail_read(mid)
        mm = re.search(r"verify-email\?token=([A-Za-z0-9\-_]+)", body)
        if not mm:
            mm = re.search(r'"token"\s*:\s*"([A-Za-z0-9\-_]+)"', body)
        if mm:
            token_verif = mm.group(1)
            break
    if token_verif:
        break
catat("token verifikasi dari Gmail", bool(token_verif))

# 3. Verifikasi + login
if token_verif:
    kode, _ = panggil("POST", "/auth/verify-email", {"token": token_verif})
    catat("verifikasi email", kode == 200, f"HTTP {kode}")
kode, resp = panggil("POST", "/auth/login", {"email": EMAIL, "password": PASSWORD})
token = resp.get("access_token")
catat("login akun uji", kode == 200 and bool(token), f"HTTP {kode}")

# 4. Org + brand
org_id = brand_id = None
if token:
    kode, resp = panggil("POST", "/organizations", {"name": "Org Uji Batch"}, token=token)
    org_id = resp.get("id")
    catat("buat organisasi", kode in (200, 201) and bool(org_id), f"HTTP {kode}")
if token and org_id:
    kode, resp = panggil("POST", f"/organizations/{org_id}/brands",
                         {"name": "Brand Uji Batch"}, token=token, header_org=org_id)
    brand_id = resp.get("id")
    catat("buat brand", kode in (200, 201) and bool(brand_id), f"HTTP {kode} {str(resp)[:150]}")

# 5. Upload batch 3 file
if token and org_id and brand_id:
    files = ["/tmp/e2e_multi/q1_2026.csv", "/tmp/e2e_multi/q2_2026.csv", "/tmp/e2e_multi/q3_2026.csv"]
    cmd = ["curl", "-s", "-o", "/tmp/e2e_batch.json", "-w", "%{http_code}",
           "-X", "POST", f"{API}/content/upload-batch",
           "-H", f"Authorization: Bearer {token}",
           "-H", f"X-Organization-Id: {org_id}",
           "-F", f"brand_id={brand_id}", "-F", "platform=tiktok"]
    for fp in files:
        cmd += ["-F", f"files=@{fp};type=text/csv"]
    up = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    http = up.stdout.strip()
    try:
        detail = json.load(open("/tmp/e2e_batch.json"))
    except Exception:
        detail = {}
    fl = detail.get("files", [])
    ok = (http == "200" and len(fl) == 3 and all(f.get("sukses") for f in fl)
          and detail.get("total_baru") == 36 and detail.get("total_baris_gagal") == 0)
    catat("upload batch 3 file (36 konten baru)", ok,
          f"HTTP {http} baru={detail.get('total_baru')} gagal={detail.get('total_baris_gagal')}")

    # 6. Idempoten: upload ulang q1 -> 0 baru, 12 diupdate
    cmd2 = ["curl", "-s", "-o", "/tmp/e2e_batch2.json", "-w", "%{http_code}",
            "-X", "POST", f"{API}/content/upload-batch",
            "-H", f"Authorization: Bearer {token}",
            "-H", f"X-Organization-Id: {org_id}",
            "-F", f"brand_id={brand_id}", "-F", "platform=tiktok",
            "-F", "files=@/tmp/e2e_multi/q1_2026.csv;type=text/csv"]
    up2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=120)
    try:
        d2 = json.load(open("/tmp/e2e_batch2.json"))
    except Exception:
        d2 = {}
    ok2 = (up2.stdout.strip() == "200" and d2.get("total_baru") == 0
           and d2.get("total_diupdate") == 12)
    catat("upload ulang idempoten (0 baru, 12 update)", ok2,
          f"HTTP {up2.stdout.strip()} baru={d2.get('total_baru')} update={d2.get('total_diupdate')}")

    # 7. Scoring 12bln
    kode, resp = panggil("POST", f"/content/brands/{brand_id}/score",
                        {"preset": "12bln"}, token=token, header_org=org_id)
    catat("scoring preset 12bln", kode == 200 and resp.get("diskor") == 36,
          f"HTTP {kode} diskor={resp.get('diskor')}")

    # 8. Perbandingan
    kode, resp = panggil("GET", f"/content/brands/{brand_id}/perbandingan",
                         token=token, header_org=org_id,
                         query="?start=2026-01-01&end=2026-09-30")
    bulan = resp.get("bulan", []) if isinstance(resp, dict) else []
    berdata = [b for b in bulan if b.get("jumlah_konten", 0) > 0]
    mom_ok = all((b.get("mom") or {}).get("bulan_pembanding") for b in berdata[1:])
    yoy_kosong = all((b.get("yoy") or {}).get("bulan_pembanding") is None for b in bulan)
    ok8 = (kode == 200 and len(bulan) == 9 and len(berdata) == 9
           and all(b.get("jumlah_konten") == 4 for b in berdata)
           and mom_ok and yoy_kosong)
    contoh = ""
    if berdata and len(berdata) > 1:
        m = berdata[1].get("mom") or {}
        contoh = f"cth {berdata[1]['label']}: mom_views={m.get('views_pct')}%"
    catat("perbandingan 9 bulan, MoM terisi, YoY kosong", ok8,
          f"HTTP {kode} bulan={len(bulan)} berdata={len(berdata)} {contoh}")

    # 9. Dashboard & analisa preset baru
    kode, resp = panggil("GET", f"/content/brands/{brand_id}/dashboard",
                         token=token, header_org=org_id, query="?preset=12bln")
    n_konten = len(resp.get("konten", [])) if isinstance(resp, dict) else 0
    catat("dashboard preset 12bln", kode == 200 and n_konten == 36,
          f"HTTP {kode} konten={n_konten}")
    kode, resp = panggil("GET", f"/content/brands/{brand_id}/analisa",
                         token=token, header_org=org_id, query="?preset=90d")
    catat("analisa preset 90d", kode == 200, f"HTTP {kode}")

print("\nRINGKASAN:")
print(json.dumps(HASIL, indent=1, ensure_ascii=False))
gagal = [h for h in HASIL if not h["lolos"]]
print(f"\nLOLOS {len(HASIL)-len(gagal)}/{len(HASIL)}")
raise SystemExit(1 if gagal else 0)
