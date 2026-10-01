"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { apiOrDemo, demoBrands } from "@/lib/content";
import type { Brand } from "@/lib/types";

/** Ambil brandId dari segmen route /brand/[brandId]. Satu tempat untuk cast. */
export function useBrandId(): string {
  const params = useParams();
  return String(params?.brandId ?? "");
}

/** Daftar brand organisasi aktif. Fallback data demo hanya saat network error;
 *  error HTTP (401/403/dll) menghasilkan daftar kosong agar halaman
 *  menampilkan pesan error yang sebenarnya. */
export function useBrands(): { brands: Brand[]; loading: boolean } {
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

  return { brands, loading };
}
