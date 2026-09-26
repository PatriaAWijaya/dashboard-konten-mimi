# Dashboard Konten AI — Frontend (Fase 0)

Frontend Next.js 14 (App Router) + TypeScript + Tailwind CSS v3 untuk aplikasi
analisis performa konten TikTok/Instagram. **Tema terang saja**, seluruh UI
berbahasa Indonesia.

## Menjalankan mode dev

```bash
cd apps/web
npm install
npm run dev
```

Buka http://localhost:3000.

### Konfigurasi API

Base URL API diambil dari environment variable (tanpa hardcode di kode):

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Default bila tidak diisi: `http://localhost:8000`, sehingga base penuh menjadi
`<API_URL>/api/v1` sesuai kontrak.

## Build produksi

```bash
npm run build
npm start
```

## Docker

```bash
docker build --build-arg NEXT_PUBLIC_API_URL=https://api.contoh.id -t dkai-web .
docker run -p 3000:3000 dkai-web
```

## Struktur

- `app/` — halaman (App Router): landing, login, register, verify-email,
  forgot-password, reset-password, dashboard, organisasi/[id], tagihan,
  tagihan/[id], admin, profil
- `components/` — Navbar, badge status, komponen UI bersama
- `lib/api.ts` — fetch wrapper (token, auto-refresh, X-Organization-Id, multipart)
- `lib/auth.tsx` — Auth context + guard `RequireAuth`
- `lib/format.ts` — format rupiah & tanggal id-ID
- `lib/types.ts` — tipe sesuai kontrak API
