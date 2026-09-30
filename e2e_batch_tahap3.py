#!/usr/bin/env python3
"""E2E tahap 3: billing (aktifkan membership) -> brand -> batch -> scoring -> perbandingan."""
import base64
import json
import subprocess
import urllib.error
import urllib.request

API = "https://dkai-api-v4cv.onrender.com/api/v1"
EMAIL = "wijaya.patria+dkaitest8@gmail.com"
PW = open("/tmp/e2e_pw8.txt").read().strip()
ADMIN_EMAIL = "admin@example.com"
ADMIN_PW = open("/home/hatch/workspace/dashboard-konten-ai/.admin_password_new.txt").read().strip()
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
            detail = e.read().decode()[:300]
        except Exception:
            detail = ""
        return e.code, {"_error": detail}
    except Exception as e:
        return -1, {"_error": f"{type(e).__name__}: {str(e)[:80]}"}


kode, resp = panggil("POST", "/auth/login", {"email": EMAIL, "password": PW})
token = resp.get("access_token")
catat("login dkaitest8", kode == 200 and bool(token), f"HTTP {kode}")

org_id = None
if token:
    kode, resp = panggil("GET", "/organizations", token=token)
    orgs = resp if isinstance(resp, list) else []
    org = next((o for o in orgs if o.get("name") == "Org Uji Batch"), None)
    org_id = org["id"] if org else None
    catat("org uji ditemukan", bool(org_id), f"HTTP {kode}")

# --- billing: aktifkan membership ---
if token and org_id:
    kode, resp = panggil("GET", "/plans", token=token, header_org=org_id)
    plans = resp if isinstance(resp, list) else resp.get("items", [])
    plan = next((p for p in plans if "Tahunan" in p.get("name", "")), plans[0] if plans else None)
    plan_id = plan["id"] if plan else None
    catat("paket billing ada", bool(plan_id), f"HTTP {kode}")

    inv_id = None
    if plan_id:
        kode, resp = panggil("POST", "/billing/invoices",
                             {"organization_id": org_id, "plan_id": plan_id},
                             token=token, header_org=org_id)
        inv_id = resp.get("id") if kode == 201 else None
        catat("buat invoice", kode == 201, f"HTTP {kode}")

    pay_id = None
    if inv_id:
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
        open("/tmp/bukti3.png", "wb").write(png)
        up = subprocess.run(
            ["curl", "-s", "-o", "/tmp/e2e_pay3.json", "-w", "%{http_code}",
             "-X", "POST", f"{API}/billing/invoices/{inv_id}/payment-proof",
             "-H", f"Authorization: Bearer {token}",
             "-H", f"X-Organization-Id: {org_id}",
             "-F", "file=@/tmp/bukti3.png;type=image/png"],
            capture_output=True, text=True, timeout=120)
        try:
            dpay = json.load(open("/tmp/e2e_pay3.json"))
            pay_id = dpay.get("payment_id") or dpay.get("id")
        except Exception:
            pay_id = None
        catat("upload bukti bayar", up.stdout.strip() in ("200", "201"), f"HTTP {up.stdout.strip()}")

    if pay_id:
        kode, resp = panggil("POST", "/auth/login",
                             {"email": ADMIN_EMAIL, "password": ADMIN_PW})
        atoken = resp.get("access_token")
        catat("login superadmin", kode == 200 and bool(atoken), f"HTTP {kode}")
        if atoken:
            kode, resp = panggil("POST", f"/admin/payments/{pay_id}/approve", {},
                                 token=atoken)
            catat("approve pembayaran", kode == 200, f"HTTP {kode}")

    kode, resp = panggil("GET", "/billing/memberships", token=token, header_org=org_id)
    st = resp.get("status") if isinstance(resp, dict) else None
    catat("membership aktif", st not in (None, "pending_payment"), f"HTTP {kode} status={st}")

# --- brand ---
brand_id = None
if token and org_id:
    kode, resp = panggil("POST", f"/organizations/{org_id}/brands",
                         {"name": "Brand Uji Batch"}, token=token, header_org=org_id)
    brand_id = resp.get("id")
    catat("buat brand", kode in (200, 201) and bool(brand_id), f"HTTP {kode}")

# --- batch upload & co ---
if token and org_id and brand_id:
    files = ["/tmp/e2e_multi/q1_2026.csv", "/tmp/e2e_multi/q2_2026.csv", "/tmp/e2e_multi/q3_2026.csv"]

    def upload_batch(flist, platform="tiktok"):
        cmd = ["curl", "-s", "-o", "/tmp/e2e_b.json", "-w", "%{http_code}",
               "-X", "POST", f"{API}/content/upload-batch",
               "-H", f"Authorization: Bearer {token}",
               "-H", f"X-Organization-Id: {org_id}",
               "-F", f"brand_id={brand_id}", "-F", f"platform={platform}"]
        for fp in flist:
            cmd += ["-F", f"files=@{fp};type=text/csv"]
        up = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        try:
            return up.stdout.strip(), json.load(open("/tmp/e2e_b.json"))
        except Exception:
            return up.stdout.strip(), {}

    http, detail = upload_batch(files)
    fl = detail.get("files", [])
    ok = (http == "200" and len(fl) == 3 and all(f.get("sukses") for f in fl)
          and detail.get("total_baru") == 36 and detail.get("total_baris_gagal") == 0)
    catat("upload batch 3 file (36 konten baru)", ok,
          f"HTTP {http} baru={detail.get('total_baru')} gagal={detail.get('total_baris_gagal')}")

    http2, d2 = upload_batch(["/tmp/e2e_multi/q1_2026.csv"])
    ok2 = (http2 == "200" and d2.get("total_baru") == 0 and d2.get("total_diupdate") == 12)
    catat("upload ulang idempoten (0 baru, 12 update)", ok2,
          f"HTTP {http2} baru={d2.get('total_baru')} update={d2.get('total_diupdate')}")

    up1 = subprocess.run(
        ["curl", "-s", "-o", "/tmp/e2e_b1.json", "-w", "%{http_code}",
         "-X", "POST", f"{API}/content/upload",
         "-H", f"Authorization: Bearer {token}",
         "-H", f"X-Organization-Id: {org_id}",
         "-F", f"brand_id={brand_id}", "-F", "platform=tiktok",
         "-F", "file=@/tmp/e2e_multi/q1_2026.csv;type=text/csv"],
        capture_output=True, text=True, timeout=120)
    catat("endpoint upload lama tetap 200", up1.stdout.strip() == "200", f"HTTP {up1.stdout.strip()}")

    kode, resp = panggil("POST", f"/content/brands/{brand_id}/score",
                        {"preset": "12bln"}, token=token, header_org=org_id)
    catat("scoring preset 12bln", kode == 200 and resp.get("diskor") == 36,
          f"HTTP {kode} diskor={resp.get('diskor')}")

    kode, resp = panggil("GET", f"/content/brands/{brand_id}/perbandingan",
                         token=token, header_org=org_id,
                         query="?start=2026-01-01&end=2026-09-30")
    bulan = resp.get("bulan", []) if isinstance(resp, dict) else []
    berdata = [b for b in bulan if b.get("jumlah_konten", 0) > 0]
    mom_ok = all((b.get("mom") or {}).get("bulan_pembanding") for b in berdata[1:])
    mom_view_terisi = all((b.get("mom") or {}).get("views_pct") is not None for b in berdata[1:])
    yoy_kosong = all((b.get("yoy") or {}).get("bulan_pembanding") is None for b in bulan)
    ok8 = (kode == 200 and len(bulan) == 9 and len(berdata) == 9
           and all(b.get("jumlah_konten") == 4 for b in berdata)
           and mom_ok and mom_view_terisi and yoy_kosong)
    contoh = ""
    if len(berdata) > 1:
        m = berdata[1].get("mom") or {}
        contoh = f"cth {berdata[1]['label']}: MoM views {m.get('views_pct')}%"
    catat("perbandingan 9 bln, MoM terisi, YoY kosong", ok8,
          f"HTTP {kode} bulan={len(bulan)} berdata={len(berdata)} {contoh}")

    with open("/tmp/e2e_multi/sep2025.csv", "w") as f:
        f.write("platform,post_id,post_url,tanggal_posting,format,tujuan,caption,views,reach,likes,comments,shares,saves,avg_watch_seconds,profile_clicks,link_clicks,replies,sticker_taps\n")
        for i in range(4):
            f.write(f"tiktok,post2025_{i},https://tiktok.com/@b/video/9{i},2025-09-{3+i*7:02d},reels,edukasi,Konten 2025 {i},{5000+i*1000},{4200+i*800},{300+i*20},{15+i},{8+i},{20+i},12.5,50,20,5,10\n")
    http3, d3 = upload_batch(["/tmp/e2e_multi/sep2025.csv"])
    kode, resp = panggil("GET", f"/content/brands/{brand_id}/perbandingan",
                         token=token, header_org=org_id,
                         query="?start=2026-09-01&end=2026-09-30")
    bulan2 = resp.get("bulan", []) if isinstance(resp, dict) else []
    sep26 = next((b for b in bulan2 if b.get("bulan") == "2026-09"), {})
    yoy = sep26.get("yoy") or {}
    ok_yoy = (http3 == "200" and yoy.get("bulan_pembanding") == "2025-09"
              and yoy.get("views_pct") is not None)
    catat("YoY terisi setelah upload data 2025", ok_yoy,
          f"pembanding={yoy.get('bulan_pembanding')} views_pct={yoy.get('views_pct')}%")

    kode, resp = panggil("GET", f"/content/brands/{brand_id}/dashboard",
                         token=token, header_org=org_id, query="?preset=12bln")
    n_konten = len(resp.get("konten", [])) if isinstance(resp, dict) else 0
    catat("dashboard preset 12bln", kode == 200 and n_konten == 40,
          f"HTTP {kode} konten={n_konten}")
    kode, _ = panggil("GET", f"/content/brands/{brand_id}/analisa",
                      token=token, header_org=org_id, query="?preset=90d")
    catat("analisa preset 90d", kode == 200, f"HTTP {kode}")

    with open("/tmp/e2e_multi/campur.csv", "w") as f:
        f.write("platform,post_id,post_url,tanggal_posting,format,tujuan,caption,views,reach,likes,comments,shares,saves,avg_watch_seconds,profile_clicks,link_clicks,replies,sticker_taps\n")
        f.write("tiktok,campur1,https://tiktok.com/@b/video/c1,2026-09-20,reels,hiburan,Campur 1,8000,6500,400,20,10,25,10.0,40,15,4,8\n")
        f.write("instagram,campur2,https://instagram.com/p/c2,2026-09-21,foto,branding,Campur 2,6000,5000,350,18,9,22,0,30,12,3,5\n")
    httpA, dA = upload_batch(["/tmp/e2e_multi/campur.csv"], platform="auto")
    catat("batch platform=auto (2 konten campur)", httpA == "200" and dA.get("total_baru") == 2,
          f"HTTP {httpA} baru={dA.get('total_baru')}")

print("\nRINGKASAN:")
print(json.dumps(HASIL, indent=1, ensure_ascii=False))
gagal = [h for h in HASIL if not h["lolos"]]
print(f"\nLOLOS {len(HASIL)-len(gagal)}/{len(HASIL)}")
raise SystemExit(1 if gagal else 0)
