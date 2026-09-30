#!/usr/bin/env python3
"""Monitor redeploy Render, lalu uji end-to-end Dashboard Konten AI.

Fase 1: poll login admin tiap 90 dtk (maks ~22 mnt). Login 200 = deploy baru live
        (seed membuat admin@example.com).
Fase 2: E2E penuh -> register, login, onboarding, org, brand, upload CSV,
        score, dashboard, analisa, suspend akun uji, rotasi password admin.
"""
import json
import secrets
import string
import subprocess
import time
import urllib.error
import urllib.request

API = "https://dkai-api-v4cv.onrender.com/api/v1"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PW_LAMA = "Admin123!"
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


def pw_acak(n=20):
    abjad = string.ascii_letters + string.digits
    return "".join(secrets.choice(abjad) for _ in range(n))


# ---------- FASE 1: tunggu deploy baru ----------
print("Fase 1: menunggu deploy baru (poll login admin tiap 90 dtk)...", flush=True)
token_admin = None
for i in range(15):
    kode, resp = panggil("POST", "/auth/login",
                         {"email": ADMIN_EMAIL, "password": ADMIN_PW_LAMA})
    print(f"  poll {i+1}: login admin -> {kode}", flush=True)
    if kode == 200 and resp.get("access_token"):
        token_admin = resp["access_token"]
        catat("deploy-baru-live (login admin 200)", True)
        break
    if i < 14:
        time.sleep(90)

if not token_admin:
    catat("deploy-baru-live (login admin 200)", False, "timeout 22 mnt, deploy belum live")
    print(json.dumps(HASIL, indent=1))
    raise SystemExit(1)

# ---------- FASE 2: E2E ----------
ts = int(time.time())
email_uji = f"e2e-{ts}@example.com"
pw_uji = pw_acak(16)

kode, resp = panggil("POST", "/auth/register",
                     {"name": "Akun Uji E2E", "email": email_uji, "password": pw_uji})
catat("register akun baru (bukan 500)", kode == 201, f"HTTP {kode}")
id_uji = resp.get("id")

kode, resp = panggil("POST", "/auth/login", {"email": email_uji, "password": pw_uji})
token_uji = resp.get("access_token") if kode == 200 else None
catat("login akun baru", kode == 200 and bool(token_uji), f"HTTP {kode}")

if token_uji:
    kode, _ = panggil("GET", "/onboarding/status", token=token_uji)
    catat("status onboarding", kode == 200, f"HTTP {kode}")

    kode, resp = panggil("POST", "/organizations", {"name": "Org Uji E2E"}, token=token_uji)
    org_id = resp.get("id") if kode == 201 else None
    catat("buat organisasi", kode == 201, f"HTTP {kode}")

    brand_id = None
    if org_id:
        kode, resp = panggil("POST", f"/organizations/{org_id}/brands",
                             {"name": "Brand Uji", "industry": "Kuliner"}, token=token_uji)
        brand_id = resp.get("id") if kode == 201 else None
        catat("buat brand", kode == 201, f"HTTP {kode}")

    if org_id and brand_id:
        kolom = ["platform", "post_id", "post_url", "tanggal_posting", "format",
                 "tujuan", "caption", "views", "reach", "likes", "comments",
                 "shares", "saves", "avg_watch_seconds", "profile_clicks",
                 "link_clicks", "replies", "sticker_taps"]
        baris = []
        for i in range(1, 6):
            baris.append(
                f"tiktok,vid{i},https://tiktok.com/@x/video/{i},2026-09-2{i},"
                f"video,awareness,\"Caption uji {i}\",{1000*i},{800*i},{100*i},"
                f"{10*i},{5*i},{8*i},12.5,{3*i},{2*i},{1*i},{0}"
            )
        csv_data = "\n".join([",".join(kolom)] + baris) + "\n"
        with open("/tmp/e2e_sample.csv", "w") as f:
            f.write(csv_data)
        up = subprocess.run(
            ["curl", "-s", "-o", "/tmp/e2e_up.json", "-w", "%{http_code}",
             "-X", "POST", f"{API}/content/upload",
             "-H", f"Authorization: Bearer {token_uji}",
             "-H", f"X-Organization-Id: {org_id}",
             "-F", f"brand_id={brand_id}", "-F", "platform=tiktok",
             "-F", "file=@/tmp/e2e_sample.csv;type=text/csv"],
            capture_output=True, text=True, timeout=120)
        catat("upload CSV contoh", up.stdout.strip() in ("200", "201"),
              f"HTTP {up.stdout.strip()}")

        kode, resp = panggil("POST", f"/content/brands/{brand_id}/score",
                             {}, token=token_uji, header_org=org_id)
        catat("scoring konten", kode == 200, f"HTTP {kode}")

        kode, _ = panggil("GET", f"/content/brands/{brand_id}/dashboard",
                          token=token_uji, header_org=org_id)
        catat("dashboard brand", kode == 200, f"HTTP {kode}")

        kode, resp = panggil("GET", f"/content/brands/{brand_id}/analisa",
                             token=token_uji, header_org=org_id)
        n_rec = 0
        if kode == 200:
            try:
                n_rec = len(resp.get("rekomendasi", []) or resp.get("recommendations", []))
            except Exception:
                pass
        catat("rekomendasi/analisa", kode == 200, f"HTTP {kode}, rekomendasi={n_rec}")

# ---------- admin: suspend akun uji + rotasi password ----------
if id_uji and token_admin:
    kode, _ = panggil("POST", f"/admin/users/{id_uji}/suspend", {}, token=token_admin)
    catat("suspend akun uji", kode == 200, f"HTTP {kode}")
    kode, _ = panggil("POST", "/auth/login", {"email": email_uji, "password": pw_uji})
    catat("akun uji tidak bisa login lagi", kode in (401, 403), f"HTTP {kode}")

pw_admin_baru = pw_acak(20)
kode, _ = panggil("POST", "/users/me/change-password",
                  {"old_password": ADMIN_PW_LAMA, "new_password": pw_admin_baru},
                  token=token_admin)
catat("rotasi password admin", kode == 200, f"HTTP {kode}")

if kode == 200:
    kode, resp = panggil("POST", "/auth/login",
                         {"email": ADMIN_EMAIL, "password": ADMIN_PW_LAMA})
    catat("password lama ditolak", kode == 401, f"HTTP {kode}")
    kode, resp = panggil("POST", "/auth/login",
                         {"email": ADMIN_EMAIL, "password": pw_admin_baru})
    catat("password baru diterima", kode == 200, f"HTTP {kode}")
    with open("/tmp/e2e_admin_pw.txt", "w") as f:
        f.write(pw_admin_baru)

lolos = sum(1 for h in HASIL if h["lolos"])
print(f"\nRINGKASAN: {lolos}/{len(HASIL)} lolos", flush=True)
print(json.dumps(HASIL, indent=1))
