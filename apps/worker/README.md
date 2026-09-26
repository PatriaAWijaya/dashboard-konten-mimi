# Worker — Penjadwal Dashboard Konten AI (Fase 2)

Worker menjalankan tiga job terjadwal memakai APScheduler (`AsyncIOScheduler`):

| Job | Jadwal default | Kerja |
|---|---|---|
| `sync_terjadwal` | tiap `SYNC_INTERVAL_HOURS` jam (default 6) | Ambil semua `ConnectedAccount` status `aktif`, panggil `sync_account` per akun (session sendiri), update `last_sync_at`. Error satu akun dicatat, lanjut ke akun lain. |
| `ringkasan_mingguan` | cron `SUMMARY_CRON` (default `0 7 * * 1` = Senin 07:00, `Asia/Jakarta`) | Untuk tiap brand yang membership org-nya aktif: hitung periode Senin–Minggu minggu lalu, panggil `get_or_generate_summary` (cached menurut kontrak, aman bila sudah ada), lalu `notify` tiap anggota org yang preferensinya on (`jenis='ringkasan_mingguan'`). |
| `pengingat_membership` | cron `REMINDER_CRON` (default `0 8 * * *` = harian 08:00, `Asia/Jakarta`) | Cari membership aktif yang kedaluwarsa H-30/H-7/H-1/H-0, lalu `notify_org` dengan `jenis='pengingat_membership'` berisi sisa hari + tanggal kedaluwarsa. Guard dalam-proses mencegah kirim ganda bila job diulang di hari yang sama. |

Idempoten & aman:
- Akun yang `last_sync_at`-nya masih dalam interval dilewati (guard bila
  scheduler restart); `last_sync_at` hanya diupdate bila sync sukses.
- Notifikasi dideduplikasi dalam-proses per (user, brand, periode).
- Tiap job log terstruktur: mulai, selesai, dan jumlah (ok/gagal/dilewati).
- `max_instances=1` + `coalesce=True`: run yang tumpang tindih tidak dobel.

## Kebutuhan backend

Worker dikoding terhadap kontrak backend Fase 2 (dibangun paralel agen lain):

- `app.services.sync_service.sync_account(db, account)` → dict
- `app.services.summaries.get_or_generate_summary(db, brand, org_id, period_start, period_end, llm)`
- `app.services.notifications.notify(db, user, jenis, payload)`
- `app.services.llm.get_llm_provider()` (sudah ada di Fase 1)
- `app.db.session.get_session()` → `AsyncSession`
  (fallback: `get_session_factory()()` — pola yang ada di Fase 1)
- Model: `ConnectedAccount` (`status`, `last_sync_at`, `brand_id`, `organization_id`),
  `Brand`, `Organization`, `OrganizationMember`, `Membership`, `User`.

Semua import `app.*` dilakukan malas dan dibungkus: bila backend belum siap,
worker keluar (kode 2) dengan pesan jelas:

> modul backend Fase 2 belum tersedia — jalankan setelah backend selesai

Asumsi kontrak yang dipakai worker (perlu dikonfirmasi saat integrasi):
1. `ConnectedAccount.status == "aktif"` untuk akun yang disync.
2. Membership "aktif" = `Membership.status == "active"` (pakai
   `MembershipStatus.ACTIVE` bila tersedia).
3. Preferensi notifikasi dibaca dari atribut user `notif_ringkasan_mingguan`
   (default `True` bila atribut belum ada).
4. `get_session()` bila belum ada, dipakai `get_session_factory()()`.

## Cara jalan lokal (tanpa docker)

```bash
cd apps/worker

# 1. Instal dependensi backend + worker (butuh Python 3.12)
pip install -r ../api/requirements.txt -r requirements.txt

# 2. Pastikan .env di root repo terisi (DATABASE_URL, dkk.)

# 3. Jalankan dari direktori apps/ agar paket `worker` ketemu:
cd ../
PYTHONPATH=apps:apps/api python -m worker.main
```

Jadwal bisa diubah tanpa deploy ulang (cukup restart worker):

```bash
SYNC_INTERVAL_HOURS=2 SUMMARY_CRON="0 8 * * 1" \
  PYTHONPATH=apps:apps/api python -m worker.main
```

| Env | Default | Arti |
|---|---|---|
| `SYNC_INTERVAL_HOURS` | `6` | interval sync akun (jam) |
| `SUMMARY_CRON` | `0 7 * * 1` | jadwal ringkasan (crontab), Senin 07:00 |
| `REMINDER_CRON` | `0 8 * * *` | jadwal pengingat membership (crontab), harian 08:00 |
| `WORKER_TIMEZONE` | `Asia/Jakarta` | zona waktu penjadwalan |
| `LOG_LEVEL` | `INFO` | level logging |

## Cara jalan via docker

```bash
cp .env.example .env   # lalu isi rahasia
docker compose up --build worker
```

Service `worker` memakai `apps/worker/Dockerfile` (build context = root repo,
agar kode `apps/api` ikut terbawa), `env_file: .env`, dan `depends_on`
`db` (healthy), `redis`, dan `api` (sudah jalan → migrasi selesai).

## Tes

Backend Fase 2 belum ada saat worker dibangun, jadi tes memakai stub
(`tests/test_worker_jobs.py`): fake async function bernama sama seperti
kontrak yang mencatat pemanggilan. Tes memverifikasi scheduler memanggil
job yang benar, interval/cron benar, error per akun/brand tidak menghentikan
loop, periode Senin–Minggu benar (termasuk batas bulan & tahun), notifikasi
hanya ke preferensi on, dan tidak dobel.

```bash
cd apps/worker
./.venv/bin/python -m pytest -v   # atau: pytest -v bila pytest terinstal global
```

## Struktur

```
apps/worker/
├── main.py            # entrypoint: bootstrap sys.path + AsyncIOScheduler
├── config.py          # WorkerConfig dari env
├── jobs.py            # sync_terjadwal, ringkasan_mingguan, minggu_lalu()
├── _backend.py        # RealBackend: akses defensif ke app.* + check_ready()
├── requirements.txt   # apscheduler (sisanya reuse apps/api/requirements.txt)
├── Dockerfile         # image worker (COPY apps/api + apps/worker)
├── pytest.ini
├── README.md          # file ini
└── tests/
    └── test_worker_jobs.py
```
