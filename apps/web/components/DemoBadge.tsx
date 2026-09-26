"use client";

// Penanda kecil bahwa halaman memakai DATA CONTOH (backend belum tersedia).
// Muncul hanya bila prop `tampil` true.
export default function DemoBadge({ tampil }: { tampil: boolean }) {
  if (!tampil) return null;
  return (
    <span
      title="Backend belum tersedia — data yang tampil adalah data contoh."
      className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 ring-1 ring-inset ring-amber-200"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
      Mode demo — data contoh
    </span>
  );
}
