# Audit Performa — MySocial Watch

Tanggal: 1 Oktober 2026. Audit baca-saja (tidak ada kode diubah).
Diurut dari dampak terbesar ke terkecil. Format: `[FILE:LINE]` masalah — dampak — saran.

Konteks penting: API jalan di Render free tier yang *spin down* saat idle
(banner Render: delay 50+ detik saat cold start). Itu faktor infra di luar kode,
tapi membuat setiap roundtrip tambahan di bawah terasa jauh lebih berat.

---

## KRITIS

### 1. `[apps/api/app/services/suitability.py:341]` `analisa_report` memuat SELURUH konten brand tanpa filter tanggal
Query `select(Content).where(brand_id, organization_id)` — tidak ada batas
`posted_at`. Brand dengan 2 tahun data = ribuan baris dimuat ke memori Python
setiap kali halaman Analisa dibuka, lalu agregat metrik harian seluruhnya.
- Dampak: halaman Analisa lambat dan makin lambat seiring data bertambah;
  memori worker membengkak; satu-satunya query paling berat di alur page-load.
- Saran: tambah filter `posted_at` sesuai periode (`mulai_dt`/`selesai_dt`)
  seperti di `brand_dashboard`; agregasi metrik pakai SQL `GROUP BY`
  (pola `_agregat_per_konten` di `analisa_lanjutan.py:128` sudah benar).

### 2. `[apps/api/app/routers/content.py:693]` `brand_perbandingan` memuat SEMUA baris metrik harian tanpa filter tanggal
`select(ContentMetricsDaily).where(content_id.in_(cids))` — tanpa batas `date`.
Untuk rentang 24 bulan (12 tampil + 12 YoY), ini = konten × ratusan baris
harian yang semuanya ditarik lalu dijumlah di Python (loop `content.py:700`).
- Dampak: endpoint perbandingan (dipakai tiap buka tab Analisa) mentransfer
  puluhan ribu baris yang tidak perlu; agregasi Python O(rows) setiap request.
- Saran: ganti dengan satu query `GROUP BY content_id` + filter
  `date >= awal_ambil, date <= akhir` — contoh siap pakai:
  `_agregat_per_konten` (`analisa_lanjutan.py:128`).

### 3. `[apps/api/app/routers/content.py:421]` `brand_dashboard` mengembalikan SEMUA konten tanpa LIMIT
`konten` dibangun dari seluruh `Content` dalam periode — tidak ada
`.limit()`, tidak ada pagination. Payload JSON membesar linear dengan jumlah
konten; frontend me-render semuanya.
- Dampak: dashboard brand berat untuk akun dengan ratusan/ribuan postingan
  per periode; TTFB + parse JSON + render DOM semuanya naik.
- Saran: paginasi (`limit`/`offset` atau cursor) untuk daftar `konten`,
  mis. 50–100 per halaman; kartu agregat & tren tetap dihitung penuh via SQL.

## TINGGI

### 4. `[apps/web/lib/auth.tsx:85]` Waterfall `/auth/me` → `/organizations` di root layout
`refreshUser` menunggu `GET /auth/me` selesai dulu, baru `await refreshOrgs()`
(`GET /organizations`). Keduanya independen. Karena ini di `AuthProvider`
(root layout), SEMUA halaman menunggu 2 RTT berurutan sebelum data halaman
bisa dimuat. Halaman `/dashboard` lalu menunggu `orgsLoading` sebelum
menembak 2 request paralel lagi = total 3 RTT berurutan sebelum konten tampil.
- Dampak: first meaningful paint seluruh aplikasi tertunda 1 RTT ekstra
  (±2 RTT di koneksi lambat / cold start Render).
- Saran: `Promise.all([api.get("/auth/me"), api.get("/organizations")])`.

### 5. `[apps/api/app/core/deps.py:30-63]` Overhead ~9 roundtrip DB per request API
Setiap request: 3× `set_config` (GUC RLS) + `get_current_user` (1× `set_config`
redundan di `deps.py:93` + 1 SELECT user) + `get_org_context` (1× `set_tenant` +
SELECT org + SELECT member) + `_get_brand` (1 SELECT) + `commit()` di request
read-only + `RESET`×3 + `commit()` di `finally`. Halaman Analisa menembak 3
request paralel (analisa, perbandingan, analisa-lanjutan) → ±27 roundtrip hanya
untuk auth/tenant, sebelum query bisnis.
- Dampak: latency dasar setiap endpoint; terasa di DB jauh (Render Postgres
  free, region latency).
- Saran: (a) hapus `set_config` redundan di `deps.py:93` (sudah di-set dari
  JWT di `get_db`); (b) lewati `commit()` untuk request read-only / gunakan
  sesi read-only; (c) cache singkat org+member per request (sudah satu sesi,
  tapi 3 request paralel = 3 sesi).

### 6. `[apps/api/app/services/recommendations.py:550]` Generate rekomendasi = 3× full data load berurutan
Satu klik "Generate": `generate_recommendations` (`_baris_skor`: join
Content+ContentScore penuh) lalu `generate_rekomendasi_struktur` memanggil
`analisa_lanjutan` (full load + agregat) DAN `analisa_report` (full load lagi,
lihat temuan #1) — berurutan, masing-masing me-load dataset yang sama.
- Dampak: aksi generate bisa belasan detik; diperparah temuan #1.
- Saran: muat dataset sekali, teruskan ke ketiga fungsi (atau gabung jadi
  satu service call).

### 7. `[apps/api/app/services/scoring.py:237]` `run_scoring` memuat SEMUA konten brand tanpa filter tanggal
`select(Content).where(brand_id, organization_id)` tanpa batas periode —
hanya query metriknya yang difilter tanggal. `by_id` menampung seluruh
konten selamanya.
- Dampak: makin lama brand dipakai, makin berat tiap klik "Hitung ulang skor".
- Saran: filter `posted_at` ke periode scoring (atau minimal hanya konten
  yang punya metrik di periode itu via semi-join).

## SEDANG

### 8. `[apps/web/app/brand/[brandId]/niche/page.tsx:173]` Waterfall POST → GET saat mulai/restart interview
`POST /niche/interviews` mengembalikan hanya `{id, current_step, status}`,
frontend lalu `GET /niche/interviews/{id}` untuk data penuh. Pola sama di
`mulai-ulang` (`niche/page.tsx:346-347`). 2 RTT untuk 1 aksi (inheren, tapi
bisa dihindari).
- Dampak: jeda ganda tiap mulai/restart Niche Finder.
- Saran: POST mengembalikan objek interview penuh (atau `GET` digabung);
  hemat 1 RTT.

### 9. `[apps/api/app/routers/organizations.py:215]` N+1: satu query agregat per brand di `ringkasan-data`
Loop `for b in brands:` menembak `GROUP BY tahun,bulan` per brand.
- Dampak: request `GET /organizations/{id}/ringkasan-data` (dipakai halaman
  `/dashboard`) = 1 + N query. Kecil sekarang (brand per org sedikit), tapi
  pola N+1 murni.
- Saran: satu query `GROUP BY brand_id, tahun, bulan` untuk semua brand.

### 10. `[apps/web/app/brand/[brandId]/analisa/page.tsx:337]` 3 request berat paralel, masing-masing ulang auth penuh
`analisa` + `perbandingan` + `analisa-lanjutan` (dynamic) masing-masing
mengulang rantai `get_current_user` → `get_org_context` → `_get_brand`
(temuan #5) dan masing-masing me-load ulang baris Content yang sama
(temuan #1, #2).
- Dampak: 3× duplikasi kerja DB untuk satu page-view.
- Saran (arsitektural): satu endpoint gabungan `/analisa-ringkas`, atau
  backend cache per-request via `request.state`.

## KECIL

### 11. `[apps/api/app/routers/fase2.py:848]` N+1 `db.get(AppSetting, key)` per kunci pengaturan
Loop `PENGATURAN_KEYS` → satu `SELECT` per key.
- Dampak: halaman admin `/admin/pengaturan` (trafik rendah, N kecil).
- Saran: `select(AppSetting).where(AppSetting.key.in_(keys))` sekali.

### 12. `[apps/web/components/Navbar.tsx:101]` (+ login/register/forgot/reset/onboarding) `<img src="/logo.png">` mentah
Tanpa `next/image`: tanpa `width`/`height` (layout shift kecil), tanpa
`priority`/preload padahal logo ada di header setiap halaman. File hanya
11 KB jadi dampak kecil, tapi ini gambar di atas-the-fold di semua halaman.
- Dampak: minor CLS + request tak teroptimasi di setiap navigasi.
- Saran: pakai `next/image` dengan `priority` di Navbar; atau inline SVG
  (logo 11 KB, satu file).

### 13. `[apps/api/app/services/recommendations.py:411]` `_contoh()` scan O(P×B) + `_simpan()` query dedup per pola
Tiap pola memindai seluruh `baris`; tiap `_simpan` menembak
`_dedup_ditolak` (1 query). Jumlah pola kecil → dampak kecil.
- Saran: index `baris` sekali per `(format, tujuan)`; batch cek dedup.

---

## Yang SUDAH BAIK (tidak perlu diubah)

- `package.json` frontend minimal (next, react, recharts saja) — tidak ada
  dependensi berat tak terpakai.
- Recharts di-lazy (`TrenChart`, `BandingChart` dynamic `ssr:false`);
  `AnalisaLanjutan` dynamic import — First Load JS dasbor ±116 kB.
- Index komposit `ix_contents_brand_posted`, `ix_scores_content_period`
  (migrasi `0009`) sudah menutup query dashboard/analisa utama.
- `run_scoring`: agregat metrik via SQL `GROUP BY`, upsert batch
  (`normalize.py:upsert_content_rows`) — bukan N+1.
- `_enrich_recommendations`: lookup `post_url` di-batch via `IN`.
- `list_recommendations`: `limit(50)`.
- Tidak ada Google Fonts / font eksternal; tidak ada gambar besar di
  `public/` selain `logo.png` (11 KB).
- `dashboard/page.tsx`: `Promise.all` untuk 2 fetch org — sudah paralel.
- Tidak ada `setInterval` polling berat (hanya countdown timer tagihan &
  kirim-ulang verifikasi).
