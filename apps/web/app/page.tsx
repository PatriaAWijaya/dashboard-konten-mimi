"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { formatRupiah } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { getSelectedBrandId } from "@/lib/content";
import type { Plan } from "@/lib/types";

const FITUR = [
  {
    judul: "Analisis performa konten",
    deskripsi:
      "Lihat konten TikTok dan Instagram mana yang paling menghasilkan — views, engagement, dan pertumbuhan pengikut dalam satu dasbor.",
    ikon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v18h18M7 15l4-6 4 3 5-8" />
      </svg>
    ),
  },
  {
    judul: "Deteksi pola berbasis AI",
    deskripsi:
      "AI menemukan pola di balik konten yang menang: hook, durasi, format, dan waktu posting terbaik untuk audiens Anda.",
    ikon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09ZM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456Z" />
      </svg>
    ),
  },
  {
    judul: "Multi-brand & multi-organisasi",
    deskripsi:
      "Kelola banyak brand klien dalam satu akun organisasi. Cocok untuk agensi dan tim brand dengan banyak akun.",
    ikon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008Zm0 3h.008v.008h-.008v-.008Zm0 3h.008v.008h-.008v-.008Z" />
      </svg>
    ),
  },
  {
    judul: "Rekomendasi & rencana produksi",
    deskripsi:
      "Dapatkan rekomendasi konten yang bisa dieksekusi dan rencana produksi mingguan berdasarkan data, bukan tebakan.",
    ikon: (
      <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
    ),
  },
];

function RingkasanHarga() {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [gagal, setGagal] = useState(false);

  useEffect(() => {
    api
      .get<Plan[]>("/plans")
      .then((p) => setPlans(p))
      .catch(() => setGagal(true));
  }, []);

  if (gagal || (plans && plans.length === 0)) {
    return (
      <p className="text-sm text-slate-500">
        Daftar paket lengkap tersedia setelah Anda masuk. Pembayaran via transfer
        bank dengan kode unik.
      </p>
    );
  }

  if (!plans) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-48 animate-pulse rounded-2xl bg-slate-200"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {plans.slice(0, 3).map((plan) => (
        <div
          key={plan.id}
          className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <h3 className="text-lg font-bold text-slate-900">{plan.name}</h3>
          <p className="mt-2 text-3xl font-extrabold text-orange-600">
            {formatRupiah(plan.price)}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            per {plan.period_months} bulan · {plan.seats} kursi
          </p>
          <ul className="mt-4 space-y-2">
            {plan.features.slice(0, 4).map((f, i) => (
              <li key={i} className="flex gap-2 text-sm text-slate-600">
                <span className="text-emerald-500">✓</span>
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

export default function LandingPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [pengalihan, setPengalihan] = useState(false);

  // User yang sudah login langsung diarahkan ke halaman analisa.
  useEffect(() => {
    if (loading) return;
    if (user) {
      setPengalihan(true);
      const brandId = getSelectedBrandId();
      router.replace(brandId ? `/brand/${brandId}/analisa` : "/pilih-brand?next=analisa");
    }
  }, [user, loading, router]);

  if (loading || pengalihan) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-sm text-slate-500">Memuat…</p>
      </div>
    );
  }

  return (
    <div className="bg-white">
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-b from-orange-50 via-white to-white">
        <div className="mx-auto max-w-7xl px-4 pb-16 pt-16 sm:px-6 sm:pt-24">
          <div className="mx-auto max-w-3xl text-center">
            <span className="inline-flex items-center rounded-full bg-orange-100 px-3 py-1 text-xs font-semibold text-orange-700 ring-1 ring-inset ring-orange-200">
              Dibuat untuk brand & agensi Indonesia
            </span>
            <h1 className="mt-6 text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl lg:text-6xl">
              MySocial Watch
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-slate-600 sm:text-xl">
              Analisis performa konten TikTok & Instagram Anda dengan bantuan AI.
              Temukan pola konten yang menang, dapatkan rekomendasi yang bisa
              dieksekusi — semua dalam Bahasa Indonesia.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link
                href="/register"
                className="w-full rounded-xl bg-orange-600 px-8 py-3.5 text-base font-semibold text-white shadow-sm hover:bg-orange-700 sm:w-auto"
              >
                Daftar Sekarang
              </Link>
              <Link
                href="/login"
                className="w-full rounded-xl border border-slate-300 bg-white px-8 py-3.5 text-base font-semibold text-slate-700 hover:bg-slate-50 sm:w-auto"
              >
                Masuk
              </Link>
            </div>
            <p className="mt-4 text-sm text-slate-500">
              Pembayaran mudah via transfer bank · Tanpa kartu kredit
            </p>
          </div>
        </div>
      </section>

      {/* Fitur */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900">
            Kenapa MySocial Watch?
          </h2>
          <p className="mt-3 text-slate-600">
            Berhenti menebak-nebak. Biarkan data dan AI memandu strategi konten
            Anda.
          </p>
        </div>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {FITUR.map((f) => (
            <div
              key={f.judul}
              className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:shadow-md"
            >
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-orange-100 text-orange-600">
                {f.ikon}
              </div>
              <h3 className="text-base font-bold text-slate-900">{f.judul}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">
                {f.deskripsi}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Harga */}
      <section className="bg-slate-50">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight text-slate-900">
              Harga Transparan
            </h2>
            <p className="mt-3 text-slate-600">
              Pilih paket sesuai kebutuhan tim Anda. Keanggotaan aktif selama 1
              tahun penuh.
            </p>
          </div>
          <div className="mt-10">
            <RingkasanHarga />
          </div>
          <div className="mt-8 text-center">
            <Link
              href="/register"
              className="inline-flex items-center gap-2 font-semibold text-orange-600 hover:text-orange-700"
            >
              Daftar untuk melihat semua paket
              <span aria-hidden>→</span>
            </Link>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <div className="rounded-3xl bg-orange-600 px-6 py-12 text-center sm:px-12">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">
            Siap membuat konten yang benar-benar bekerja?
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-orange-100">
            Buat akun gratis hari ini, daftarkan organisasi Anda, dan mulai
            perjalanan konten berbasis data.
          </p>
          <Link
            href="/register"
            className="mt-8 inline-block rounded-xl bg-white px-8 py-3.5 text-base font-semibold text-orange-700 shadow hover:bg-orange-50"
          >
            Daftar Gratis
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-600 text-sm font-bold text-white">
                D
              </span>
              <span className="font-bold text-slate-900">MySocial Watch</span>
            </div>
            <p className="text-sm text-slate-500">
              Analisis konten TikTok & Instagram untuk brand Indonesia.
            </p>
          </div>
          <p className="mt-6 text-center text-xs text-slate-400">
            © 2026 MySocial Watch. Seluruh hak cipta dilindungi.
          </p>
        </div>
      </footer>
    </div>
  );
}
