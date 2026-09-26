"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "@/components/ui";

interface StatusOnboarding {
  selesai: boolean;
  ditutup: boolean;
}

// Banner di dasbor brand: ajak pengguna menyelesaikan onboarding 4 langkah.
// Disembunyikan bila onboarding sudah selesai/ditutup, atau bila layanan
// onboarding di server belum tersedia (fetch defensif).
export default function OnboardingBanner({ brandId }: { brandId: string }) {
  const [tampil, setTampil] = useState(false);
  const [menutup, setMenutup] = useState(false);

  useEffect(() => {
    let batal = false;
    api
      .get<StatusOnboarding>(
        `/onboarding/status?brand_id=${encodeURIComponent(brandId)}`
      )
      .then((s) => {
        if (!batal && !s.selesai && !s.ditutup) setTampil(true);
      })
      .catch(() => {
        // Layanan belum tersedia → jangan ganggu dasbor.
      });
    return () => {
      batal = true;
    };
  }, [brandId]);

  async function tutup() {
    setMenutup(true);
    try {
      await api.post("/onboarding/tutup", { brand_id: brandId });
    } catch {
      // abaikan — banner tetap disembunyikan di sisi klien
    }
    setTampil(false);
  }

  if (!tampil) return null;

  return (
    <div className="mb-6 flex flex-col gap-3 rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50 to-sky-50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="text-sm font-semibold text-indigo-900">
          Lengkapi onboarding 4 langkah 🚀
        </p>
        <p className="mt-0.5 text-sm text-indigo-700">
          Profil brand → hubungkan akun → definisi konten menang → sync
          pertama. Hanya butuh beberapa menit.
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Link href={`/onboarding?brand=${encodeURIComponent(brandId)}`}>
          <Button>Lanjutkan</Button>
        </Link>
        <Button variant="ghost" onClick={tutup} disabled={menutup}>
          {menutup ? "Menutup…" : "Tutup"}
        </Button>
      </div>
    </div>
  );
}
