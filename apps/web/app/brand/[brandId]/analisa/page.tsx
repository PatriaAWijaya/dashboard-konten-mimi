"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { apiOrDemo, demoAnalisa, demoPerbandingan } from "@/lib/content";
import type {
  AnalisaKesesuaian,
  PerbandinganBulan,
  PerbandinganData,
  PerbandinganDelta,
} from "@/lib/types";
import { Alert, Card, EmptyBox, PageHeader, Select, Spinner } from "@/components/ui";
import { StatusKontenBadge, statusKontenTone, statusKontenLabel, verdictTone } from "@/components/badges";
import BrandNav from "@/components/BrandNav";
import DemoBadge from "@/components/DemoBadge";
import PeriodPicker, { type PilihanPeriode } from "@/components/PeriodPicker";

type MetrikBanding = "views" | "engagement" | "jumlah_konten" | "reach";
const METRIK_BANDING: { value: MetrikBanding; label: string }[] = [
  { value: "views", label: "Views" },
  { value: "engagement", label: "Engagement" },
  { value: "jumlah_konten", label: "Jumlah konten" },
  { value: "reach", label: "Reach" },
];
const RENTANG_BANDING = [
  { value: "6", label: "6 bulan terakhir" },
  { value: "12", label: "12 bulan terakhir" },
] as const;

/** Label tampil untuk nilai tujuan (semua konten sosmed = account growth & engagement rate). */
function labelTujuan(t: string): string {
  if (t === "account_growth") return "Account growth & engagement rate";
  return t.replace(/_/g, " ");
}

function fmtAngka(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  return n.toLocaleString("id-ID");
}

/** Badge delta MoM/YoY: ▲ hijau (naik), ▼ merah (turun), — abu (belum ada data pembanding). */
function DeltaBadge({ nilai, jenis }: { nilai: number | null | undefined; jenis: string }) {
  if (nilai === null || nilai === undefined) {
    return (
      <span className="inline-block rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-400" title={`${jenis}: data pembanding belum tersedia`}>
        —
      </span>
    );
  }
  const naik = nilai >= 0;
  const teks = `${naik ? "▲" : "▼"} ${Math.abs(nilai).toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${
        naik ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
      }`}
      title={`${jenis}: ${nilai > 0 ? "+" : ""}${nilai}%`}
    >
      {teks}
    </span>
  );
}

function awalRentangBanding(bulanKeBelakang: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() - (bulanKeBelakang - 1), 1);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}-01`;
}

/** Ambil nilai delta MoM/YoY (persen) untuk satu metrik. */
function deltaUntuk(
  b: PerbandinganBulan,
  jenis: "mom" | "yoy",
  metrik: MetrikBanding
): number | null {
  const d = jenis === "mom" ? b.mom : b.yoy;
  if (!d) return null;
  const kunci = `${metrik}_pct` as
    | "views_pct"
    | "engagement_pct"
    | "jumlah_konten_pct"
    | "reach_pct";
  return d[kunci] ?? null;
}

function AnalisaIsi() {
  const params = useParams();
  const brandId = params.brandId as string;
  const [periode, setPeriode] = useState<PilihanPeriode>({ preset: "30d" });
  const [data, setData] = useState<AnalisaKesesuaian | null>(null);
  const [demo, setDemo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // --- Tren & perbandingan MoM/YoY (terintegrasi di tab Analisa) ---
  const [bandingPlatform, setBandingPlatform] = useState("semua");
  const [bandingRentang, setBandingRentang] = useState<string>("12");
  const [bandingMetrik, setBandingMetrik] = useState<MetrikBanding>("views");
  const [banding, setBanding] = useState<PerbandinganData | null>(null);
  const [bandingLoading, setBandingLoading] = useState(false);
  const [bandingError, setBandingError] = useState("");

  const muatBanding = useCallback(async () => {
    setBandingLoading(true);
    setBandingError("");
    try {
      const params = new URLSearchParams({
        platform: bandingPlatform,
        start: awalRentangBanding(Number(bandingRentang)),
      });
      const { data: hasil } = await apiOrDemo<PerbandinganData>(
        () => api.get<PerbandinganData>(`/content/brands/${brandId}/perbandingan?${params}`),
        demoPerbandingan
      );
      setBanding(hasil);
    } catch (err) {
      setBandingError(
        err instanceof ApiError ? err.message : "Gagal memuat data perbandingan."
      );
      setBanding(null);
    } finally {
      setBandingLoading(false);
    }
  }, [brandId, bandingPlatform, bandingRentang]);

  useEffect(() => {
    muatBanding();
  }, [muatBanding]);

  const bandingKosong =
    !bandingLoading && !bandingError && banding && banding.bulan.every((b) => b.jumlah_konten === 0);
  const labelMetrik = METRIK_BANDING.find((m) => m.value === bandingMetrik)?.label ?? bandingMetrik;
  const grafikBanding = (banding?.bulan ?? []).map((b) => ({
    label: b.label,
    Nilai: b[bandingMetrik] ?? 0,
    mom: deltaUntuk(b, "mom", bandingMetrik),
    yoy: deltaUntuk(b, "yoy", bandingMetrik),
  }));

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

      {/* Tren & perbandingan MoM/YoY — terintegrasi di tab Analisa */}
      <Card className="mb-8">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Tren & Perbandingan Bulanan
            </h2>
            <p className="text-sm text-slate-500">
              MoM = vs bulan sebelumnya · YoY = vs bulan yang sama tahun lalu ·
              — = data pembanding belum ada
            </p>
          </div>
        </div>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <Select
            label="Platform"
            value={bandingPlatform}
            onChange={(e) => setBandingPlatform(e.target.value)}
          >
            <option value="semua">Semua platform</option>
            <option value="tiktok">TikTok</option>
            <option value="instagram">Instagram</option>
          </Select>
          <Select
            label="Rentang"
            value={bandingRentang}
            onChange={(e) => setBandingRentang(e.target.value)}
          >
            {RENTANG_BANDING.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
          <Select
            label="Metrik"
            value={bandingMetrik}
            onChange={(e) => setBandingMetrik(e.target.value as MetrikBanding)}
          >
            {METRIK_BANDING.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </Select>
        </div>

        {bandingLoading && <Spinner label="Memuat tren…" />}
        {bandingError && <Alert kind="error">{bandingError}</Alert>}
        {bandingKosong && (
          <p className="py-6 text-center text-sm text-slate-500">
            Belum ada data konten pada rentang ini.
          </p>
        )}

        {!bandingLoading && !bandingError && banding && !bandingKosong && (
          <>
            <h3 className="mb-3 text-base font-semibold text-slate-900">
              Tren {labelMetrik} per bulan
            </h3>
            <div className="mb-6 h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={grafikBanding} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="#64748b" />
                  <YAxis tick={{ fontSize: 12 }} stroke="#64748b" />
                  <Tooltip
                    formatter={(value, _name, item) => {
                      const p = item?.payload as { mom?: number | null; yoy?: number | null } | undefined;
                      const ket: string[] = [];
                      if (p?.mom !== null && p?.mom !== undefined) ket.push(`MoM ${p.mom > 0 ? "+" : ""}${p.mom}%`);
                      if (p?.yoy !== null && p?.yoy !== undefined) ket.push(`YoY ${p.yoy > 0 ? "+" : ""}${p.yoy}%`);
                      return [fmtAngka(typeof value === "number" ? value : null), ket.join(" · ") || labelMetrik];
                    }}
                  />
                  <Bar dataKey="Nilai" fill="#4f46e5" radius={[6, 6, 0, 0]} name={labelMetrik} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <h3 className="mb-3 text-base font-semibold text-slate-900">
              Detail MoM / YoY — {labelMetrik}
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                    <th className="py-2 pr-3">Bulan</th>
                    <th className="py-2 pr-3 text-right">{labelMetrik}</th>
                    <th className="py-2 pr-3">MoM</th>
                    <th className="py-2">YoY</th>
                  </tr>
                </thead>
                <tbody>
                  {banding.bulan.map((b) => (
                    <tr key={b.bulan} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                      <td className="py-2.5 pr-3 font-medium text-slate-900">{b.label}</td>
                      <td className="py-2.5 pr-3 text-right tabular-nums">{fmtAngka(b[bandingMetrik])}</td>
                      <td className="py-2.5 pr-3">
                        <DeltaBadge nilai={deltaUntuk(b, "mom", bandingMetrik)} jenis={`MoM ${labelMetrik}`} />
                      </td>
                      <td className="py-2.5">
                        <DeltaBadge nilai={deltaUntuk(b, "yoy", bandingMetrik)} jenis={`YoY ${labelMetrik}`} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Engagement = likes + komentar + share + simpanan. Karena export
              Meta dibatasi 3 bulan per file, unggah file-file periode
              sebelumnya lewat halaman Upload agar perbandingan YoY terisi.
            </p>
          </>
        )}
      </Card>

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
                    <p className="text-sm text-slate-500">
                      Tujuan: {labelTujuan(r.tujuan)}
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
                        {k.format.replace(/_/g, " ")} · tujuan {labelTujuan(k.tujuan)}
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
