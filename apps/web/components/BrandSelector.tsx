"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getSelectedBrandId, setSelectedBrandId } from "@/lib/content";
import { useBrands } from "@/lib/brand";

// Dropdown pilih brand aktif. Menyimpan pilihan ke localStorage "dkai_brand_id".
export default function BrandSelector({
  value,
  onChange,
  className = "",
}: {
  value?: string | null;
  onChange?: (brandId: string | null) => void;
  className?: string;
}) {
  const { selectedOrgId, user } = useAuth();
  const { brands, loading } = useBrands();
  const [selected, setSelected] = useState<string>("");

  // Validasi pilihan tersimpan terhadap daftar brand yang ada.
  useEffect(() => {
    const tersimpan = value ?? getSelectedBrandId();
    const valid = brands.find((b) => b.id === tersimpan);
    setSelected(valid ? valid.id : "");
  }, [brands]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (value !== undefined) setSelected(value ?? "");
  }, [value]);

  function handleChange(id: string) {
    setSelected(id);
    setSelectedBrandId(id || null);
    onChange?.(id || null);
  }

  if (!selectedOrgId) {
    return (
      <p className={`text-sm text-slate-500 ${className}`}>
        Pilih organisasi terlebih dahulu.
      </p>
    );
  }

  return (
    <label className={`block ${className}`}>
      <span className="mb-1.5 block text-sm font-medium text-slate-700">
        Brand aktif
      </span>
      <select
        value={selected}
        disabled={loading}
        onChange={(e) => handleChange(e.target.value)}
        className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-orange-500 sm:w-64"
      >
        <option value="">
          {loading ? "Memuat brand…" : brands.length === 0 ? user?.name || "Belum ada brand" : "— Pilih brand —"}
        </option>
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
