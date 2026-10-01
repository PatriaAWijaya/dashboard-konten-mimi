"use client";

import { useEffect, useState } from "react";
import { RequireAuth, useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { apiOrDemo, demoBrands } from "@/lib/content";
import type { Brand } from "@/lib/types";
import NicheFinder from "@/components/NicheFinder";

/** Dropdown brand opsional — Niche Finder tetap jalan tanpa memilih brand. */
function PemilihBrand({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (brandId: string | null) => void;
}) {
  const { selectedOrgId } = useAuth();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!selectedOrgId) {
      setBrands([]);
      setLoading(false);
      return;
    }
    let batal = false;
    setLoading(true);
    apiOrDemo(
      () => api.get<Brand[]>(`/organizations/${selectedOrgId}/brands`),
      demoBrands
    )
      .then(({ data }) => {
        if (!batal) setBrands(data);
      })
      .catch(() => {
        if (!batal) setBrands([]);
      })
      .finally(() => {
        if (!batal) setLoading(false);
      });
    return () => {
      batal = true;
    };
  }, [selectedOrgId]);

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
