"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { RequireAuth, useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import {
  apiOrDemo,
  demoBrands,
  getSelectedBrandId,
  setSelectedBrandId,
} from "@/lib/content";
import type { Brand } from "@/lib/types";
import { Alert, Card, PageHeader, Spinner } from "@/components/ui";
import DemoBadge from "@/components/DemoBadge";

function PilihBrandIsi() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
  const { selectedOrgId } = useAuth();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [demo, setDemo] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedOrgId) {
      setLoading(false);
      return;
    }
    let batal = false;
    setError("");
    apiOrDemo(
      () => api.get<Brand[]>(`/organizations/${selectedOrgId}/brands`),
      demoBrands
    ).then(({ data, demo: d }) => {
      if (batal) return;
      setBrands(data);
      setDemo(d);
      setLoading(false);
    }).catch((err) => {
      if (batal) return;
      setError(err instanceof ApiError ? err.message : "Gagal memuat daftar brand.");
      setLoading(false);
    });
    return () => {
      batal = true;
    };
  }, [selectedOrgId]);

  function pilih(b: Brand) {
    setSelectedBrandId(b.id);
    const suffix = next === "niche" ? "/niche" : next === "analisa" ? "/analisa" : next === "rekomendasi" ? "/rekomendasi" : "";
    router.push(`/brand/${b.id}${suffix}`);
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Pilih brand"
        subtitle="Analitik, rekomendasi, dan Niche Finder bekerja per brand."
        action={<DemoBadge tampil={demo} />}
      />
      {loading && <Spinner label="Memuat daftar brand…" />}
      {!loading && error && (
        <Alert kind="error">{error}</Alert>
      )}
      {!loading && !error && getSelectedBrandId() && brands.some((b) => b.id === getSelectedBrandId()) && (
        <Alert kind="info">
          Brand aktif saat ini:{" "}
          <strong>{brands.find((b) => b.id === getSelectedBrandId())?.name}</strong>.
          Pilih brand lain di bawah untuk menggantinya.
        </Alert>
      )}
      {!loading && brands.length === 0 && (
        <Alert kind="warning">
          Belum ada brand di organisasi ini. Minta admin organisasi menambahkan
          brand terlebih dahulu.
        </Alert>
      )}
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {brands.map((b) => (
          <button key={b.id} type="button" onClick={() => pilih(b)} className="text-left">
            <Card className="transition hover:border-orange-300 hover:shadow">
              <p className="font-semibold text-slate-900">{b.name}</p>
              {b.industry && (
                <p className="mt-1 text-sm text-slate-500">{b.industry}</p>
              )}
              <p className="mt-3 text-sm font-medium text-orange-600">
                Pilih brand →
              </p>
            </Card>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function PilihBrandPage() {
  return (
    <RequireAuth>
      <Suspense fallback={<Spinner label="Memuat…" />}>
        <PilihBrandIsi />
      </Suspense>
    </RequireAuth>
  );
}
