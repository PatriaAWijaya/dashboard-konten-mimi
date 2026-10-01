"use client";

import { useState } from "react";
import { RequireAuth } from "@/lib/auth";
import { useBrands } from "@/lib/brand";
import NicheFinder from "@/components/NicheFinder";

/** Dropdown brand opsional — Niche Finder tetap jalan tanpa memilih brand. */
function PemilihBrand({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (brandId: string | null) => void;
}) {
  const { brands, loading } = useBrands();

  return (
    <label className="mb-4 block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700">
        Brand{" "}
        <span className="font-normal text-slate-500">
          (opsional — boleh dikosongkan)
        </span>
      </span>
      <select
        value={value ?? ""}
        disabled={loading}
        onChange={(e) => onChange(e.target.value || null)}
        className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-orange-500 sm:w-64"
      >
        <option value="">— Tanpa brand —</option>
        {brands.map((b) => (
          <option key={b.id} value={b.id}>
            {b.display_name || b.name}
            {b.industry ? ` · ${b.industry}` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}

function NicheMandiriIsi() {
  const [brandId, setBrandId] = useState<string | null>(null);
  return (
    <NicheFinder
      key={brandId ?? "tanpa-brand"}
      brandId={brandId}
      atas={<PemilihBrand value={brandId} onChange={setBrandId} />}
    />
  );
}

export default function NicheMandiriPage() {
  return (
    <RequireAuth>
      <NicheMandiriIsi />
    </RequireAuth>
  );
}
