# Panduan Deploy Uji Publik — Dashboard Konten AI

Stack uji publik (semua punya tier gratis, tanpa kartu kredit):

| Lapisan  | Layanan  | Keterangan                          |
|----------|----------|-------------------------------------|
| Kode     | GitHub   | Repo privat                         |
| Database | Supabase | PostgreSQL gratis, tidak kedaluwarsa|
| API      | Render   | `render.yaml` (web + worker)        |
| Frontend | Vercel   | Paling cocok untuk Next.js          |

> **Batasan jujur uji publik:** tier gratis Render "tidur" setelah 15 menit tanpa
> traffic (request pertama membangunkan ±1 menit). File bukti transfer tersimpan di
> disk lokal API dan **hilang saat redeploy** — untuk uji coba boleh, untuk produksi
> butuh object storage. Tombol "Akun demo" hanya ada di development; di publik yang
> jalan: upload CSV, scoring, dashboard, rekomendasi, planner, onboarding.
> OAuth TikTok/Instagram asli butuh kredensial developer (lihat README).

## Langkah 1 — GitHub (dilakukan Patria)

1. Buat akun di [github.com](https://github.com) (bisa login dengan Google).
2. Buat repo **privat** baru, mis. `dashboard-konten-ai`. Jangan centang "Add README".
3. Di komputer/VPS ini kode sudah di-commit lokal — tinggal push:
   ```bash
   cd ~/workspace/dashboard-konten-ai
   git remote add origin https://github.com/USERNAME/dashboard-konten-ai.git
   git push -u origin main
   ```
   (Butuh login GitHub sekali — bisa via browser atau personal access token.)

## Langkah 2 — Database Supabase (dilakukan Patria)

1. Buat akun di [supabase.com](https://supabase.com) → New project.
2. Catat **connection string** (Project Settings → Database → Connection string,
   mode Session pooler atau Direct). Format untuk aplikasi:
   `postgresql+asyncpg://postgres:PASSWORD@db.xxxxx.supabase.co:5432/postgres`
   (ganti `postgresql://` menjadi `postgresql+asyncpg://`).

## Langkah 3 — API + Worker di Render (dilakukan Patria)

1. Buat akun di [render.com](https://render.com) (bisa login dengan GitHub).
2. New → **Blueprint** → pilih repo `dashboard-konten-ai`.
3. Render membaca `render.yaml` dan membuat 2 service: `dkai-api` (web) dan
   `dkai-worker` (background).
4. Isi environment variables yang bertanda manual (lihat `.env.production.example`):
   - `DATABASE_URL` — dari Supabase (SAMA untuk api & worker)
   - `FERNET_KEY` — generate: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - `FRONTEND_URL`, `API_BASE_URL`, `CORS_ORIGINS` — diisi setelah Langkah 4
   - `BANK_ACCOUNT_NUMBER`, `BANK_ACCOUNT_NAME` — rekening transfer manual
   - `JWT_SECRET_KEY` — otomatis di-generate Render
5. Deploy. Entrypoint otomatis menjalankan `alembic upgrade head` (migrasi DB).

## Langkah 4 — Frontend di Vercel (dilakukan Patria)

1. Buat akun di [vercel.com](https://vercel.com) (login dengan GitHub).
2. Add New → Project → import repo `dashboard-konten-ai`.
   - Root Directory: `apps/web`
   - Environment Variable: `NEXT_PUBLIC_API_URL=https://dkai-api.onrender.com`
     (sesuaikan dengan URL Render-mu)
3. Deploy → dapat URL mis. `https://dkai-web.vercel.app`.
4. Kembali ke Render, isi `FRONTEND_URL`, `API_BASE_URL`, `CORS_ORIGINS`
   dengan URL Vercel, lalu **Redeploy** `dkai-api`.

## Langkah 5 — Verifikasi

1. Buka URL Vercel → halaman login tampil.
2. Daftar akun baru → verifikasi email (mode prod: cek log SMTP bila belum
   diset — kode verifikasi tercatat di log server).
3. Buat invoice → upload bukti → approve via `/admin` → "Brand Utama" otomatis.
4. Upload `contoh/tiktok_contoh.csv` → dashboard & rekomendasi tampil.

## Setelah uji publik

- [ ] Tempel kredensial TikTok Developers & Meta Developers (OAuth asli)
- [ ] Pilih provider WhatsApp API + layanan email transaksional
- [ ] Pindahkan file bukti transfer ke object storage (Supabase Storage/S3)
- [ ] Pertimbangkan paket berbayar Render agar API tidak tidur
