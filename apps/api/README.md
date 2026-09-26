# Dashboard Konten AI — Backend API (Fase 0)

Backend FastAPI untuk platform analisis konten multi-tenant dengan membership berbayar
via transfer bank manual yang diverifikasi admin.

## Teknologi

- Python 3.12, FastAPI, SQLAlchemy 2 (async) + asyncpg
- PostgreSQL 16 dengan Row Level Security (RLS) + `FORCE ROW LEVEL SECURITY`
- Alembic untuk migrasi, PyJWT untuk auth, passlib/bcrypt untuk password
- pytest + pytest-asyncio + httpx untuk tes

## Struktur

```
app/
├── main.py            # Aplikasi FastAPI (prefix /api/v1, pesan Bahasa Indonesia)
├── cli.py             # CLI: python -m app.cli maintenance
├── seed.py            # Seed idempotent: python -m app.seed
├── core/              # config, security (JWT/bcrypt), deps, permissions, events
├── db/                # session, base model
├── models/            # user, organization, brand, billing, token, audit
├── schemas/           # Pydantic v2 (request/response)
├── services/          # email, storage, payment, invoice, membership, maintenance, audit
└── routers/           # auth, organizations, billing, admin, dev
alembic/                # migrasi (0001_initial: skema + RLS)
tests/                  # 4 grup tes wajib (lihat bawah)
```

## Cara menjalankan lokal (tanpa Docker)

Prasyarat: Python 3.12 dan PostgreSQL 16 berjalan di localhost:5432.

```bash
cd apps/api

# 1. Instal dependensi
pip install -r requirements.txt

# 2. Siapkan database + role aplikasi (sebagai superuser postgres)
psql -U postgres -c "CREATE DATABASE dashboard_konten;"
psql -U postgres -c "CREATE ROLE app_user WITH LOGIN PASSWORD 'app_password';"

# 3. Salin konfigurasi
cp .env.example .env
# Isi JWT_SECRET_KEY (min. 32 karakter) dan kredensial lain bila perlu.

# 4. Migrasi
MIGRATION_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/dashboard_konten" \
  ENV=dev alembic upgrade head

# 5. Beri grant ke role aplikasi (wajib: RLS aktif + FORCE)
psql -U postgres -d dashboard_konten <<'SQL'
GRANT CONNECT ON DATABASE dashboard_konten TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
SQL

# 6. Seed (idempotent): superadmin + Paket Tahunan + organisasi contoh
DATABASE_URL="postgresql+asyncpg://app_user:app_password@localhost:5432/dashboard_konten" \
  ENV=dev python -m app.seed
# Login admin: SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD (default admin@example.com)

# 7. Jalankan server
DATABASE_URL="postgresql+asyncpg://app_user:app_password@localhost:5432/dashboard_konten" \
  ENV=dev python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# API: http://127.0.0.1:8000/api/v1   |  Health: /health   |  OpenAPI: /docs
```

Maintenance manual (kedaluwarsa invoice, grace/expired membership):

```bash
DATABASE_URL="postgresql+asyncpg://app_user:app_password@localhost:5432/dashboard_konten" \
  ENV=dev python -m app.cli maintenance
```

## Tes

```bash
# Siapkan DB tes (sekali saja)
psql -U postgres -c "CREATE DATABASE dashboard_konten_test;"

# Jalankan seluruh suite (12 tes)
TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/dashboard_konten_test" \
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/dashboard_konten_test" \
  python -m pytest -q
```

Empat grup tes wajib:

| File | Cakupan |
|---|---|
| `tests/test_auth.py` | Register → verifikasi → login → refresh; tolak login bila nonaktif; forgot/reset tidak bocor |
| `tests/test_billing_flow.py` | Alur penuh: invoice → upload bukti → antrean admin → approve → membership aktif (event `PembayaranLunas`); blokir brand saat grace |
| `tests/test_lifecycle.py` | Maintenance: invoice pending → expired; membership active → grace → expired; aktivasi memperpanjang dari `ends_at` lama |
| `tests/test_unique_code.py` | Kode unik 1–999 unik di antara invoice pending; 409 saat habis |
| `tests/test_rls.py` | Isolasi tenant via role DB non-superuser (SELECT/INSERT diblokir lintas tenant) |

Catatan: seluruh tes async berbagi satu event loop session-scoped
(`pytestmark = pytest.mark.asyncio(loop_scope="session")` di tiap modul tes) agar
engine async SQLAlchemy dapat dipakai lintas fixture dan tes.

## Konvensi penting

- Base path API: `/api/v1`. Semua pesan respons Bahasa Indonesia; error berbentuk `{"detail": "..."}`.
- Header `X-Organization-Id` (UUID) wajib pada endpoint billing/organisasi yang terlingkup tenant.
- Kode unik invoice 1–999 dijamin via fungsi PostgreSQL `SECURITY DEFINER` + retry (jumlah dari settings).
- Bukti pembayaran disimpan privat di `STORAGE_DIR/payment_proofs/` (tidak di-serve statis); diunduh via endpoint berizin.
- Event domain `PembayaranLunas` dipicu saat admin menyetujui pembayaran → membership aktif 1 tahun (durasi dari settings).
- Endpoint `/dev/*` hanya aktif saat `ENV=dev` (outbox email & token untuk pengembangan).
