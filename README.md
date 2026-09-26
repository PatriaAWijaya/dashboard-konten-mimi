# Dashboard Konten AI

Aplikasi web analisis konten **TikTok / Instagram** untuk kreator dan agensi, dirancang
**multi-tenant** (Organization → Brand) dengan model bisnis **membership** yang dibayar
melalui **transfer bank manual** (diverifikasi admin).

## Status: Fase 2 lanjutan (selesai, terverifikasi 2026-09-26)

Fase 0 (fondasi: autentikasi, multi-tenancy, membership, pembayaran manual, panel admin)
**selesai**. Fase 1 (intelijen konten) **selesai**: import CSV TikTok/Instagram, scoring
deterministik (Weighted ER), Analisa Kesesuaian, Rekomendasi AI (agregat dulu, narasi
kemudian), dan Niche Finder 8 langkah. Semua halaman UI Fase 1 tersedia di frontend.

Fase 2 (sinkronisasi provider, planner, undangan, ringkasan, notifikasi) — **selesai
penuh termasuk UI**: koneksi OAuth TikTok/Instagram (state+PKCE, token terenkripsi
Fernet), tombol akun demo (dev), sync manual + worker terjadwal, planner, undangan
anggota, ringkasan mingguan AI, notifikasi mock. Verifikasi: 88/88 tes backend,
18/18 tes worker, tsc bersih, `npm run build` sukses, E2E penuh lolos.

Fase 2 lanjutan (modul yang tertinggal) — **selesai, terverifikasi 2026-09-26**:
117/117 tes backend, 26/26 tes worker, tsc bersih, `npm run build` sukses, E2E penuh
lolos di DB fresh (daftar → aktivasi → "Brand Utama" otomatis → onboarding 4 langkah
→ preview kemenangan → 2 akun demo → sync → scoring → rekomendasi diterima → alokasi
→ terima → export CSV/PDF → notifikasi mock tercatat).

| Lapisan | Teknologi |
|---|---|
| Backend | FastAPI (`apps/api`) |
| Frontend | Next.js (`apps/web`) |
| Database | PostgreSQL 16 |
| Cache / queue (disiapkan) | Redis 7 |
| Orkestrasi lokal | Docker Compose |

---

## Prasyarat

- [Docker](https://docs.docker.com/get-docker/) dan Docker Compose v2 (plugin `docker compose`).
- Port bebas: `5432` (Postgres), `6379` (Redis), `8000` (API), `3000` (web).

## Quickstart

```bash
# 1. Salin contoh konfigurasi, lalu isi nilai yang ditandai GANTI
cp .env.example .env

# 2. Build & jalankan semua service (entrypoint backend otomatis membuat
#    role DB + menjalankan migrasi, lalu menyalakan uvicorn)
docker compose up --build

# 3. (terminal lain) Seed akun admin
docker compose exec api python -m app.seed

# 4. Buka http://localhost:3000
```

API tersedia di `http://localhost:8000` (dokumentasi interaktif: `/docs`).

### Kredensial seed (dev saja)

- Email: `admin@example.com`
- Password: `Admin123!`

> ⚠️ **Hanya untuk development.** Di produksi, ganti `SEED_ADMIN_PASSWORD` lewat
> environment variable atau buat admin langsung dari shell backend. Jangan pernah
> commit file `.env` berisi kredensial asli.

---

## Endpoint API penting (Fase 0)

Semua endpoint di bawah prefix `/api`. Prefix persisnya mengikuti implementasi backend;
cek `http://localhost:8000/docs` untuk daftar final.

| Area | Endpoint | Keterangan |
|---|---|---|
| Auth | `POST /auth/register` | Registrasi user baru |
| Auth | `POST /auth/login` | Login, dapat access + refresh token (JWT) |
| Auth | `POST /auth/refresh` | Perpanjang access token |
| Auth | `GET /auth/me` | Profil user yang sedang login |
| Organisasi | `POST /organizations` | Buat organisasi (jadi owner) |
| Organisasi | `GET /organizations` | Daftar organisasi milik user |
| Organisasi | `GET /organizations/{id}` | Detail organisasi |
| Brand | `POST /organizations/{id}/brands` | Tambah brand (dibatasi `MAX_BRANDS_PER_ORG`) |
| Brand | `GET /organizations/{id}/brands` | Daftar brand dalam organisasi |
| Billing | `POST /billing/invoices` | Buat invoice pembayaran manual (rekening dari `BANK_*`) |
| Billing | `POST /billing/invoices/{id}/proof` | Upload bukti transfer (disimpan di `storage/`) |
| Billing | `GET /billing/invoices` | Daftar invoice + status |
| Billing | `GET /billing/membership` | Status membership organisasi |
| Admin | `GET /admin/invoices` | Semua invoice menunggu verifikasi |
| Admin | `POST /admin/invoices/{id}/approve` | Setujui pembayaran → membership aktif |
| Admin | `POST /admin/invoices/{id}/reject` | Tolak pembayaran |
| Admin | `GET /admin/organizations` | Semua organisasi + status membership |
| Admin | `GET /admin/users` | Daftar user |

## Endpoint API penting (Fase 1 — konten)

Prefix: `/api/v1`. Semua endpoint konten butuh header `X-Organization-Id` dan membership aktif.

| Area | Endpoint | Keterangan |
|---|---|---|
| Konten | `POST /content/upload` | Import CSV (multipart: `brand_id`, `platform`, `file`). Idempoten per brand+platform+post_id; baris rusak dilaporkan per baris |
| Konten | `GET /content/csv-format` | Spesifikasi 18 kolom CSV + contoh |
| Konten | `POST /content/brands/{id}/score` | Jalankan scoring (`preset`: 7d/30d/90d atau `mulai`+`selesai`) |
| Konten | `GET /content/brands/{id}/dashboard` | Kartu ringkasan per platform, tren mingguan, tabel konten (skor, WER, status) |
| Analisa | `GET /content/brands/{id}/analisa` | Ringkasan pola format×tujuan, diagnosis per metrik, saran per konten |
| Rekomendasi | `POST /content/brands/{id}/recommendations/generate` | Hasilkan rekomendasi (rule-based + narasi LLM) |
| Rekomendasi | `GET /content/brands/{id}/recommendations` | Daftar rekomendasi aktif (yang ditolak tidak dimunculkan) |
| Rekomendasi | `POST /content/recommendations/{id}/terima` | Tandai diterima |
| Rekomendasi | `POST /content/recommendations/{id}/tolak` | Tandai ditolak |
| Niche | `POST /content/brands/{id}/niche/interviews` | Mulai wawancara Niche Finder (8 pertanyaan) |
| Niche | `POST /content/niche/interviews/{id}/jawab` | Jawab satu langkah (`step`, `jawaban`, atau `dilewati: true`) |
| Niche | `POST /content/niche/interviews/{id}/sintesis` | Susun Brand DNA Card (perlu dikonfirmasi) |
| Niche | `PUT /content/niche/dna/{id}/konfirmasi` | Konfirmasi kartu DNA |
| Niche | `GET /content/brands/{id}/niche/saran` | 5–7 saran niche (persentase kecocokan, 10 angle, monetisasi, label DATA/ESTIMASI/KLAIM) |
| Niche | `POST /content/brands/{id}/niche/pilih` | Pilih maks. 2 niche utama |

### Format CSV (18 kolom)

`platform, post_id, post_url, tanggal_posting, format, tujuan, caption, views, reach,
likes, comments, shares, saves, avg_watch_seconds, profile_clicks, link_clicks,
replies, sticker_taps`. Mendukung UTF-8 BOM, koma, dan semicolon. File contoh
(30 baris, termasuk 3 baris rusak untuk uji validasi) di `apps/web/public/contoh/`.

### Prinsip AI

**Agregat dulu, narasi kemudian** — LLM hanya menerima agregat (rata-rata, pola,
contoh pemenang), tidak pernah data mentah per konten. Provider LLM dipilih lewat
env: `LLM_PROVIDER=mock|openai|anthropic` (`LLM_API_KEY`, `LLM_MODEL`). Di dev,
`MockLLMProvider` dipakai secara default.

### Halaman frontend Fase 1

`/upload` (import CSV + unduh contoh), `/pilih-brand`, `/brand/[id]` (dashboard +
grafik tren), `/brand/[id]/analisa`, `/brand/[id]/rekomendasi`, `/brand/[id]/niche`
(wawancara 8 langkah → DNA → saran niche → pilih niche). Bila API tidak terjangkau,
halaman memakai data demo lokal bertanda badge "Demo".

---

## Fase 2 — backend (sinkronisasi & kolaborasi)

### Arsitektur

```
TikTok/Meta OAuth ──► connected_accounts (token terenkripsi Fernet)
        │ sync (tiap 6 jam, via worker)
        ▼
normalize_content_row() ──► contents + content_metrics_daily   (satu pintu validasi dgn CSV)
        │
        ├── scoring / dashboard / analisa / rekomendasi (Fase 1, tidak berubah)
        ├── planned_posts (planner: ide → terjadwal → terbit)
        ├── summaries (ringkasan mingguan, cached per periode)
        ├── invitations (undang anggota via token; terima tanpa login ulang org)
        └── notifications (preferensi per user; log sent/failed/skipped)
```

- **Satu pintu validasi**: sinkronisasi provider memakai `normalize_content_row()` dan
  `upsert_content_row()` yang sama dengan import CSV — baris rusak dilaporkan per baris,
  tidak pernah menggagalkan seluruh batch.
- **Agregat dulu, narasi kemudian** tetap berlaku: LLM (ringkasan & rekomendasi) hanya
  membaca JSON agregat. `llm_api_key` bisa diisi superadmin via `/admin/pengaturan`
  (didahulukan atas env `LLM_API_KEY`).
- **Tanpa kredensial, hanya Mock yang berjalan**: bila kredensial TikTok/Meta belum
  dikonfigurasi, endpoint OAuth mengembalikan **HTTP 501** dengan pesan jelas, dan
  sinkronisasi memakai `MockSyncProvider` (15 data demo, bertanda jelas).
- **Mencoba koneksi tanpa kredensial (dev only)**: endpoint
  `POST /api/v1/dev/koneksi/mock` (`{brand_id, platform}`) membuat ConnectedAccount
  demo — halaman Koneksi punya tombol "Akun demo" untuk ini. Hanya tersedia saat
  backend berjalan dalam mode development (router `/dev` tidak dimuat di produksi).
- Token OAuth & kredensial admin disimpan **terenkripsi (Fernet)** di
  `connected_accounts` / `app_settings`. `FERNET_KEY` wajib diisi di produksi —
  tanpanya backend memakai kunci sementara per proses (hilang saat restart).

### Endpoint API penting (Fase 2)

| Area | Endpoint |
|---|---|
| OAuth | `POST /api/v1/content/brands/{id}/oauth/{tiktok\|instagram}/mulai` → `{auth_url}` |
| | `GET /api/v1/content/oauth/callback?code&state` → 302 ke `{FRONTEND_URL}/brand/{id}/koneksi?status=ok\|gagal` |
| Koneksi | `GET /api/v1/content/brands/{id}/koneksi`, `DELETE /api/v1/content/koneksi/{conn_id}` (min admin) |
| Sync | `POST /api/v1/content/koneksi/{conn_id}/sync` → `{contents_baru, contents_diupdate}` (idempoten) |
| Planner | `GET/POST /api/v1/content/brands/{id}/planner` (`?bulan=YYYY-MM`, `?status=`), `PUT/DELETE /api/v1/content/planner/{post_id}` |
| Undangan | `POST/GET /api/v1/organizations/{id}/undangan`, `DELETE /api/v1/organizations/{id}/undangan/{uid}`, `POST /api/v1/undangan/{token}/terima` |
| Anggota | `DELETE /api/v1/organizations/{id}/members/{user_id}` (min admin; tidak bisa mengeluarkan diri sendiri / owner terakhir) |
| Ringkasan | `GET /api/v1/content/brands/{id}/ringkasan?minggu=YYYY-MM-DD` → `{ada, teks, ...}`, `POST .../ringkasan/generate` (cached) |
| Notifikasi | `GET/PUT /api/v1/notifikasi/preferensi` |
| Pengaturan | `GET/PUT /api/v1/admin/pengaturan` (superadmin; `{"key": "...", "value": null}` menghapus nilai) |
| Dev | `GET /api/v1/dev/undangan?email=` — intip token undangan (ENV=dev saja) |

### Worker terjadwal (`apps/worker`)

- `sync_terjadwal`: tiap `SYNC_INTERVAL_HOURS` jam (default 6), sinkronkan semua
  `connected_accounts` berstatus `aktif`.
- `ringkasan_mingguan`: cron `SUMMARY_CRON` (default `0 7 * * 1`, Senin 07:00 WIB) —
  buat ringkasan minggu lalu per brand, notifikasi anggota yang preferensinya on.
- `pengingat_membership`: cron `REMINDER_CRON` (default `0 8 * * *`, tiap hari
  08:00 Asia/Jakarta) — kirim pengingat ke organisasi yang membership-nya
  kedaluwarsa H-30/H-7/H-1/H-0 (mock di dev).

## Fase 2 lanjutan — modul tertinggal (selesai 2026-09-26)

- **Onboarding 4 langkah** (`/onboarding`): muncul setelah membership aktif, bisa
  ditutup & dilanjutkan dari banner dashboard. Langkah: profil brand (nama, logo,
  kategori industri — `logo_url`, `industry_category`), hubungkan TikTok/Instagram
  (OAuth/demo) atau lewati/upload CSV, atur threshold "konten menang" dengan
  **preview tanpa menyimpan** (7 template kategori), sync pertama 90 hari.
  Progress tersimpan di tabel `onboarding_progress` (migrasi `0004_onboarding`).
- **Multi-akun**: maks 3 akun per platform per brand (configurable via pengaturan
  admin `max_accounts_per_platform`); unique key `(brand_id, platform,
  account_external_id)` (migrasi `0005_multiakun`). Akun ke-4 ditolak HTTP 409
  dengan pesan jelas. Endpoint `GET /content/brands/{id}/koneksi/status`.
- **Alokator planner deterministik**: konfigurasi kapasitas mingguan (default 7)
  + porsi eksperimen (default 20%) + target distribusi format (opsional);
  `POST .../planner/alokasi/generate` (deterministik, hasil identik bila input sama)
  → `POST .../planner/alokasi/terima` menjadi `planned_posts`. Slot eksperimen =
  kombinasi (format, tujuan) yang belum pernah dicoba brand.
- **Estimasi & export**: ringkasan planner menampilkan rentang estimasi views
  dengan label **"estimasi"** (bukan angka pasti); export CSV & PDF; endpoint
  `.../planner/realisasi` membandingkan ER konten sesuai rencana vs di luar rencana.
- **Brand default otomatis**: aktivasi membership pertama membuatkan brand
  `"Brand Utama"` bila organisasi belum punya brand + notifikasi aktivasi via
  provider mock (tanpa password).
- **Hardening**: rate limit (login 30/mnt, register 20/mnt, verify 30/mnt,
  forgot/reset 10/mnt) + security headers (HSTS, X-Frame-Options,
  X-Content-Type-Options, Referrer-Policy).
- Halaman frontend baru/diperbarui: `/onboarding`, banner "Lanjutkan onboarding",
  halaman koneksi multi-akun, planner (target & estimasi, konfigurasi alokator,
  export CSV/PDF, realisasi vs rencana), empty state dashboard.

> **Catatan unit**: UI planner bekerja dalam persen untuk porsi eksperimen
> (0–100%), backend menyimpan rasio (0–1); konversi dilakukan di frontend.

### Checklist untuk Patria (keputusan/aksi di tangan Anda)

> **Tanpa item di bawah ini, aplikasi tetap berjalan penuh dengan data demo/Mock.**
> Tidak ada satu pun layanan pihak ketiga yang didaftarkan oleh asisten — semua
> pendaftaran akun developer di bawah ini perlu Anda lakukan sendiri.

1. **TikTok Developers** (https://developers.tiktok.com) — buat app, aktifkan
   *Login Kit* + *Video List* (scopes: `user.info.basic`, `video.list`), daftarkan
   redirect URI `{API_BASE_URL}/api/v1/content/oauth/callback`. Salin *Client key*
   & *Client secret* → isi via halaman Pengaturan admin (`tiktok_client_key`,
   `tiktok_client_secret`) atau env `TIKTOK_CLIENT_KEY`/`TIKTOK_CLIENT_SECRET`.
2. **Meta Developers** (https://developers.facebook.com) — buat app tipe *Business*,
   tambahkan produk *Instagram Graph API* dengan izin `instagram_basic`,
   `instagram_manage_insights`, `pages_read_engagement`, `pages_show_list`
   (akun Instagram harus **Bisnis/Kreator** dan terhubung ke Halaman Facebook).
   Salin *App ID* & *App secret* → `instagram_app_id`, `instagram_app_secret`.
3. **WhatsApp API** — pilih sendiri penyedia yang diinginkan (mis. Fonnte, Wablas,
   atau WhatsApp Business Cloud API resmi Meta). Setelah memilih, isi
   `whatsapp_provider` + `whatsapp_api_key` di Pengaturan admin. Sampai saat itu,
   notifikasi memakai provider `mock` (hanya tercatat di log, tidak terkirim).
4. **LLM API key** — pilih sendiri provider (`openai` atau `anthropic`), isi
   `llm_api_key` di Pengaturan admin atau env `LLM_API_KEY`. Tanpa key, narasi
   memakai template deterministik Mock (gratis, tanpa biaya).

### Hal yang belum terverifikasi (jujur)

- Alur OAuth & fetch data **TikTok/Meta asli belum bisa diuji** tanpa kredensial
  developer asli (butuh langkah 1–2 di atas).
- Pengiriman **WhatsApp via Fonnte belum teruji** tanpa API key nyata.
- Verifikasi dilakukan pada PostgreSQL 16 lokal; **Docker Compose belum
  terverifikasi** di mesin ini (tidak ada Docker daemon) — sama seperti Fase 0/1.

---

## Struktur repo

```
dashboard-konten-ai/
├── docker-compose.yml      # Orkestrasi: db, redis, api, web
├── .env.example            # Contoh semua environment variable
├── .gitignore
├── README.md
├── storage/                # Folder privat bukti transfer (diabaikan git)
│   └── .gitkeep
├── apps/
│   ├── api/                # Backend FastAPI
│   └── web/                # Frontend Next.js
```

---

## Konfigurasi environment

Semua variabel ada di `.env.example` dengan contoh dev. Yang sering diubah **tanpa
perlu deploy ulang** (cukup restart service) ditandai ⭐.

| Nama | Default | Keterangan |
|---|---|---|
| `POSTGRES_USER` | `postgres` | Superuser Postgres |
| `POSTGRES_PASSWORD` | *(wajib diisi)* | Password superuser — **GANTI dengan string acak** |
| `POSTGRES_DB` | `dashboard` | Nama database |
| `APP_DB_USER` | `app_user` | User DB least-privilege untuk aplikasi (dibuat entrypoint) |
| `APP_DB_PASSWORD` | *(wajib diisi)* | Password `APP_DB_USER` — **GANTI** |
| `DATABASE_URL` | — | Koneksi asyncpg untuk API (`app_user`) |
| `SUPERUSER_DATABASE_URL` | — | Koneksi superuser (untuk setup role) |
| `MIGRATION_DATABASE_URL` | — | Koneksi yang dipakai migrasi |
| `REDIS_URL` | `redis://redis:6379/0` | Koneksi Redis (worker fase berikut) |
| `JWT_SECRET_KEY` | *(wajib diisi)* | Kunci tanda tangan JWT — **wajib diganti di produksi** |
| `JWT_ALGORITHM` | `HS256` | Algoritma JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Umur access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Umur refresh token |
| `ENV` | `dev` | `dev`/`prod` — di `prod` endpoint `/dev` dimatikan |
| ⭐ `MAX_BRANDS_PER_ORG` | `3` | **Batas jumlah brand per organisasi** |
| ⭐ `GRACE_PERIOD_DAYS` | `7` | **Masa tenggang** setelah membership kedaluwarsa |
| ⭐ `MEMBERSHIP_DURATION_DAYS` | `365` | **Durasi satu paket membership** (hari) |
| ⭐ `INVOICE_EXPIRY_HOURS` | `24` | **Batas waktu pembayaran invoice** (jam) |
| ⭐ `BANK_NAME` | `BCA` | **Bank tujuan transfer** |
| ⭐ `BANK_ACCOUNT_NUMBER` | `1234567890` | **Nomor rekening tujuan** |
| ⭐ `BANK_ACCOUNT_NAME` | `PT Dashboard Konten AI` | **Nama pemilik rekening** |
| `STORAGE_DIR` | `./storage` | Folder bukti transfer (di-mount sebagai volume) |
| `SEED_ADMIN_EMAIL` | `admin@example.com` | Email admin hasil seed |
| `SEED_ADMIN_PASSWORD` | `Admin123!` | Password admin seed — **ganti via env** |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | URL API yang dipakai frontend |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | *(kosong)* | Opsional, untuk email di fase berikut |

> Catatan: harga paket dan jumlah **seats per plan** dikelola lewat panel admin /
> database (bukan env), agar bisa diubah tanpa restart.

---

## Panduan deploy gratis (tanpa membuat akun)

Panduan ini hanya langkah-langkah; tidak ada akun/hosting/domain yang dibuat di sini.

### 1. Database — Supabase (Postgres terkelola, tier gratis)

1. Buat project Postgres di Supabase (gratis, dari dashboard mereka).
2. Ambil connection string, lalu di environment API set:
   - `DATABASE_URL`, `SUPERUSER_DATABASE_URL`, `MIGRATION_DATABASE_URL`
     ke connection string Supabase (format `postgresql+asyncpg://...`).
3. Jalankan migrasi sekali dari mesin lokal/CI terhadap database Supabase.
4. Untuk service `db` di compose produksi, database lokal tidak dipakai — gunakan
   Supabase sebagai gantinya.

### 2. Web — Cloudflare Pages (hosting frontend gratis)

1. Hubungkan repo ini ke Cloudflare Pages.
2. Build command & output mengikuti konfigurasi `apps/web` (Next.js).
3. Set environment variable `NEXT_PUBLIC_API_URL` ke URL publik API (langkah 3).

### 3. API — Render atau Cloud Run (tier gratis)

1. Deploy `apps/api` sebagai web service di **Render** (gratis, sleep saat idle)
   atau **Google Cloud Run** (gratis dalam kuota bulanan).
2. Set **semua** environment variable dari `.env.example` di dashboard service
   (nilai produksi, bukan contoh).
3. Pastikan `ENV=prod`, `NEXT_PUBLIC_API_URL` di web menunjuk ke URL service ini,
   dan volume `storage/` diganti object storage bila bukti transfer harus persisten
   (disk Render/Cloud Run bersifat ephemeral).

> ⚠️ **Vercel Hobby tidak cocok** untuk API ini karena produknya komersial
> (ketentuan fair-use Vercel melarang penggunaan komersial di tier Hobby).

### Keamanan produksi (wajib)

- Ganti `JWT_SECRET_KEY` dengan string acak ≥ 64 karakter.
- Ganti `POSTGRES_PASSWORD`, `APP_DB_PASSWORD`, `SEED_ADMIN_PASSWORD`.
- `ENV=prod` (mematikan endpoint `/dev` dan mode debug).
- Jangan commit `.env`; simpan secret di secret manager / env dashboard hosting.
- Batasi CORS ke domain frontend produksi saja.
- Backup database terjadwal (Supabase menyediakan backup otomatis di tier berbayar;
  di tier gratis, jadwalkan `pg_dump` sendiri).

---

## Troubleshooting

| Gejala | Penyebab umum & solusi |
|---|---|
| Port bentrok (`address already in use`) | Service lain memakai 5432/6379/8000/3000. Hentikan service tersebut atau ubah mapping port di `docker-compose.yml`. |
| `api` tidak start: "db belum healthy" | Postgres masih inisialisasi. Tunggu; cek `docker compose logs db`. Bila berulang, cek `POSTGRES_PASSWORD` di `.env` (karakter spesial perlu di-quote). |
| Migrasi gagal | Cek log `docker compose logs api`; pastikan `MIGRATION_DATABASE_URL` benar dan DB bisa dijangkau. Jalankan ulang: `docker compose up --build api`. |
| Web 404 / tidak bisa hubungi API | Pastikan `NEXT_PUBLIC_API_URL` sesuai (di Docker antar-service, web memanggil API dari browser — pakai URL yang bisa dijangkau browser, default `http://localhost:8000`). |
| Bukti transfer tidak tersimpan | Pastikan folder `storage/` ada di root repo dan volume `./storage:/app/storage` ter-mount. |
| Lupa password admin dev | Jalankan ulang seed: `docker compose exec api python -m app.seed`, atau buat ulang via shell backend. |
