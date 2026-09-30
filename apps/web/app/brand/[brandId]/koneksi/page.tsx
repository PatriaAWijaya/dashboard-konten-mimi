"use client";

import { Suspense } from "react";
import { useParams } from "next/navigation";
import { RequireAuth } from "@/lib/auth";
import { PageHeader, Spinner } from "@/components/ui";
import BrandNav from "@/components/BrandNav";

// Halaman "Hubungkan Akun" — Fase 1: Coming Soon.
// Sinkronisasi otomatis (OAuth TikTok/Instagram) BELUM dibangun; halaman ini
// hanya menampilkan placeholder "Coming Soon" sesuai instruksi.
function KoneksiIsi() {
  const params = useParams();
  const brandId = params.brandId as string;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Hubungkan Akun"
        subtitle="Sinkronisasi otomatis data performa dari akun TikTok dan Instagram brand Anda."
      />
      <BrandNav brandId={brandId} />

      <div className="relative overflow-hidden rounded-3xl border border-slate-200 bg-white">
        {/* Latar gradien lembut — eye-catching tapi minimalis */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(600px 300px at 20% 0%, rgba(99,102,241,0.12), transparent 60%), radial-gradient(500px 260px at 85% 100%, rgba(236,72,153,0.10), transparent 60%)",
          }}
        />
        <div className="relative px-6 py-16 text-center sm:px-12 sm:py-20">
          <span className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-4 py-1.5 text-xs font-semibold uppercase tracking-widest text-indigo-700">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-indigo-500" />
            </span>
            Segera hadir — Fase 1
          </span>

          <h2 className="mx-auto mt-6 max-w-2xl text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl">
            Coming Soon
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-lg font-medium text-slate-700">
            Realtime analisa performa sosial media
          </p>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-slate-500">
            Sinkronisasi otomatis data performa dari akun TikTok dan Instagram
            brand Anda — tanpa upload CSV manual. Data views, reach, likes,
            comments, saves, shares, dan follows akan mengalir sendiri dan
            teranalisa secara realtime.
          </p>

          <div className="mx-auto mt-8 flex max-w-md items-center justify-center gap-6 text-slate-400">
            <div className="flex flex-col items-center gap-2">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-xl text-white">
                🎵
              </span>
              <span className="text-xs font-medium">TikTok</span>
            </div>
            <div className="h-px w-10 bg-slate-200" aria-hidden />
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-400">
              <svg className="h-5 w-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
              </svg>
            </div>
            <div className="h-px w-10 bg-slate-200" aria-hidden />
            <div className="flex flex-col items-center gap-2">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-amber-400 via-pink-500 to-purple-600 text-xl text-white">
                📸
              </span>
              <span className="text-xs font-medium">Instagram</span>
            </div>
          </div>

          <p className="mt-8 text-xs text-slate-400">
            Sementara ini, gunakan menu Upload CSV untuk memasukkan data performa konten.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function KoneksiPage() {
  return (
    <RequireAuth>
      <Suspense fallback={<Spinner label="Memuat…" />}>
        <KoneksiIsi />
      </Suspense>
    </RequireAuth>
  );
}
