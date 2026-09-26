"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import BrandSelector from "./BrandSelector";
import { getSelectedBrandId } from "@/lib/content";

// Navigasi tab antar-halaman analitik satu brand + pemilih brand.
export default function BrandNav({ brandId }: { brandId: string }) {
  const pathname = usePathname();
  const router = useRouter();

  const tabs = [
    { href: `/brand/${brandId}`, label: "Dasbor", exact: true },
    { href: `/brand/${brandId}/analisa`, label: "Analisa", exact: false },
    { href: `/brand/${brandId}/rekomendasi`, label: "Rekomendasi", exact: false },
    { href: `/brand/${brandId}/niche`, label: "Niche Finder", exact: false },
    { href: `/brand/${brandId}/planner`, label: "Planner", exact: false },
    { href: `/brand/${brandId}/koneksi`, label: "Koneksi", exact: false },
  ];

  function aktif(t: { href: string; exact: boolean }) {
    if (!pathname) return false;
    return t.exact ? pathname === t.href : pathname.startsWith(t.href);
  }

  return (
    <div className="mb-6 flex flex-col gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <BrandSelector
          value={brandId}
          onChange={(id) => {
            if (id && id !== brandId) {
              // Pertahankan tab yang sedang dibuka saat ganti brand.
              const suffix = pathname
                ? pathname.replace(`/brand/${brandId}`, "")
                : "";
              router.push(`/brand/${id}${suffix}`);
            }
          }}
        />
      </div>
      <nav className="flex gap-1 overflow-x-auto rounded-2xl border border-slate-200 bg-white p-1.5">
        {tabs.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className={`whitespace-nowrap rounded-xl px-4 py-2 text-sm font-medium transition ${
              aktif(t)
                ? "bg-indigo-600 text-white"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            {t.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}

// Hook kecil: baca brand aktif dari localStorage (untuk Navbar).
export function useBrandIdTersimpan(): string | null {
  if (typeof window === "undefined") return null;
  return getSelectedBrandId();
}
