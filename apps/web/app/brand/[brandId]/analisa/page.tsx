"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { RequireAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { apiOrDemo, demoAnalisa } from "@/lib/content";
import type { AnalisaKesesuaian } from "@/lib/types";
import { Alert, Card, EmptyBox, PageHeader, Spinner } from "@/components/ui";
import { StatusKontenBadge, statusKontenTone, statusKontenLabel, verdictTone } from "@/components/badges";
import BrandNav from "@/components/BrandNav";
import DemoBadge from "@/components/DemoBadge";
import PeriodPicker, { type PilihanPeriode } from "@/components/PeriodPicker";

function AnalisaIsi() {
  const params = useParams();
  const brandId = params.brandId as string;
  const [periode, setPeriode] = useState<PilihanPeriode>({ preset: "30d" });
  const [data, setData] = useState<AnalisaKesesuaian | null>(null);
  const [demo, setDemo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const muat = useCallback(async () => {
    setLoading(true);
    setError("");
    const q = new URLSearchParams({ preset: periode.preset });
    if (periode.start) q.set("start", periode.start);
    if (periode.end) q.set("end", periode.end);
    const { data: d, demo: isDemo } = await apiOrDemo(
      () => api.get<AnalisaKesesuaian>(`/content/brands/${brandId}/analisa?${q}`),
      demoAnalisa
    );
    setData(d);
    setDemo(isDemo);
    setLoading(false);
  }, [brandId, periode]);

  useEffect(() => {
    muat();
  }, [muat]);

  const kosong = !loading && data && data.ringkasan.length === 0 && data.bermasalah.length === 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Analisa Kesesuaian"
        subtitle="Apakah tiap format konten sudah cocok dengan tujuannya?"
        action={<DemoBadge tampil={demo} />}
      />
      <BrandNav brandId={brandId} />

      <div className="mb-6">
        <PeriodPicker value={periode} onChange={setPeriode} />
      </div>

      {loading && <Spinner label="Menganalisa konten…" />}
      {error && <Alert kind="error">{error}</Alert>}

      {!loading && !error && kosong && (
        <EmptyBox
          title="Belum ada data — upload CSV dulu"
          description="Analisa kesesuaian membutuhkan data konten yang sudah diskor. Mulai dari halaman Upload."
          icon={
            <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 5.25h.008v.008H12v-.008Z" />
            </svg>
          }
        />
      )}

      {!loading && !error && data && !kosong && (
        <>
          {/* 1. Ringkasan per pasangan format × tujuan */}
          <h2 className="mb-3 text-lg font-semibold text-slate-900">
            Ringkasan per pasangan format × tujuan
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.ringkasan.map((r, i) => (
              <Card key={i} className="flex flex-col gap-2">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold capitalize text-slate-900">
                      {r.format.replace(/_/g, " ")}
                    </p>
                    <p className="text-sm capitalize text-slate-500">
                      Tujuan: {r.tujuan}
                    </p>
                  </div>
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${statusKontenTone(r.dominan_status)}`}
                  >
                    {statusKontenLabel(r.dominan_status)}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-4 text-sm">
                  <span className="text-slate-600">
                    <strong className="text-slate-900">{r.jumlah}</strong> konten
                  </span>
                  <span className="text-slate-600">
                    Rata-rata skor{" "}
                    <strong className="text-indigo-600">
                      {r.rata_skor !== null
                        ? (r.rata_skor * 100).toLocaleString("id-ID", {
                            minimumFractionDigits: 1,
                            maximumFractionDigits: 1,
                          }) + "%"
                        : "-"}
                    </strong>
                  </span>
                </div>
              </Card>
            ))}
          </div>

          {/* 2. Konten bermasalah */}
          <h2 className="mb-3 mt-8 text-lg font-semibold text-slate-900">
            Konten bermasalah ({data.bermasalah.length})
          </h2>
          {data.bermasalah.length === 0 ? (
            <Alert kind="success">
              Tidak ada konten bermasalah pada periode ini. Pertahankan polanya!
            </Alert>
          ) : (
            <div className="space-y-4">
              {data.bermasalah.map((k) => (
                <Card key={k.content_id}>
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-mono text-sm font-semibold text-slate-900">
                        {k.post_id}
                      </p>
                      <p className="text-sm capitalize text-slate-500">
                        {k.format.replace(/_/g, " ")} · tujuan {k.tujuan}
                      </p>
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${verdictTone(k.verdict)}`}
                    >
                      {k.verdict}
                    </span>
                  </div>

                  <h3 className="mb-2 text-sm font-semibold text-slate-900">
                    Diagnosis per metrik
                  </h3>
                  <div className="space-y-2">
                    {k.diagnoses.map((d, j) => (
                      <div key={j} className="rounded-xl bg-slate-50 p-3">
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <p className="text-sm font-semibold text-slate-800">
                            {d.metrik}
                          </p>
                          <p className="text-sm">
                            <span className="font-semibold text-red-700">{d.nilai}</span>
                            <span className="text-slate-400"> vs </span>
                            <span className="font-medium text-emerald-700">{d.harapan}</span>
                          </p>
                        </div>
                        <p className="mt-1 text-sm text-slate-600">{d.masalah}</p>
                      </div>
                    ))}
                  </div>

                  {k.suggestions.length > 0 && (
                    <>
                      <h3 className="mb-2 mt-4 text-sm font-semibold text-slate-900">
                        Saran perbaikan
                      </h3>
                      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                        {k.suggestions.map((s, j) => (
                          <li key={j}>{s}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </Card>
              ))}
            </div>
          )}

          {/* 3. Rekomendasi pola */}
          <h2 className="mb-3 mt-8 text-lg font-semibold text-slate-900">
            Rekomendasi perbaikan pola
          </h2>
          <Card>
            <ol className="list-decimal space-y-2.5 pl-5 text-sm leading-relaxed text-slate-700">
              {data.rekomendasi_pola.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ol>
          </Card>
        </>
      )}
    </div>
  );
}

export default function AnalisaPage() {
  return (
    <RequireAuth>
      <AnalisaIsi />
    </RequireAuth>
  );
}
