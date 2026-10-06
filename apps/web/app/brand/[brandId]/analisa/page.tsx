"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useBrandId } from "@/lib/brand";
import dynamic from "next/dynamic";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";

// Chart di-load lazy agar bundle awal ringan (recharts ~100kB).
const BandingChart = dynamic(() => import("@/components/BandingChart"), {
  ssr: false,
  loading: () => <p className="text-sm text-slate-500">Memuat grafik…</p>,
});
import { apiOrDemo, demoAnalisa, demoPerbandingan } from "@/lib/content";
import { formatAngka } from "@/lib/format";
import type {
  AnalisaKesesuaian,
  PerbandinganBulan,
  PerbandinganData,
  PerbandinganDelta,
} from "@/lib/types";
import { Alert, Card, EmptyBox, PageHeader, Select, Spinner, Tabel } from "@/components/ui";
import { statusKontenTone, statusKontenLabel } from "@/components/badges";
import BrandNav from "@/components/BrandNav";
const AnalisaLanjutan = dynamic(() => import("@/components/AnalisaLanjutan"), {
  ssr: false,
  loading: () => <p className="text-sm text-slate-500">Memuat analisa lanjutan…</p>,
});
import DemoBadge from "@/components/DemoBadge";
import ExportPdfButton from "@/components/ExportPdfButton";
import PeriodPicker, { type PilihanPeriode } from "@/components/PeriodPicker";

type MetrikBanding =
  | "views"
  | "engagement"
  | "jumlah_konten"
  | "reach"
  | "likes"
  | "comments"
  | "saves"
  | "shares"
  | "follows";
const METRIK_BANDING: { value: MetrikBanding; label: string; warna: string }[] = [
  { value: "views", label: "Views", warna: "#4f46e5" },
  { value: "engagement", label: "Engagement", warna: "#059669" },
  { value: "jumlah_konten", label: "Posts", warna: "#64748b" },
  { value: "reach", label: "Reach", warna: "#0284c7" },
  { value: "likes", label: "Likes", warna: "#e11d48" },
  { value: "comments", label: "Comments", warna: "#d97706" },
  { value: "saves", label: "Saves", warna: "#7c3aed" },
  { value: "shares", label: "Shares", warna: "#0d9488" },
  { value: "follows", label: "Follows", warna: "#db2777" },
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
    | "reach_pct"
    | "likes_pct"
    | "comments_pct"
    | "saves_pct"
    | "shares_pct"
    | "follows_pct";
  return d[kunci] ?? null;
}

function AnalisaIsi() {
  const searchParams = useSearchParams();
  const brandId = useBrandId();
  // Deep-link dari dasbor: ?bulan=YYYY-MM → periode custom satu bulan penuh.
  const [periode, setPeriode] = useState<PilihanPeriode>(() => {
    const b = searchParams.get("bulan");
    if (b && /^\d{4}-\d{2}$/.test(b)) {
      const [th, bl] = b.split("-").map(Number);
      const last = new Date(th, bl, 0).getDate();
      const pad = String(bl).padStart(2, "0");
      return { preset: "custom", start: `${th}-${pad}-01`, end: `${th}-${pad}-${last}` };
    }
    return { preset: "30d" };
  });
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
  const warnaMetrik = METRIK_BANDING.find((m) => m.value === bandingMetrik)?.warna ?? "#4f46e5";
  const grafikBanding = (banding?.bulan ?? [])
    .filter((b) => (b[bandingMetrik] ?? 0) > 0)
    .map((b) => ({
      label: b.label,
      Nilai: b[bandingMetrik] ?? 0,
      mom: deltaUntuk(b, "mom", bandingMetrik),
      yoy: deltaUntuk(b, "yoy", bandingMetrik),
    }));

  const muat = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const q = new URLSearchParams({ preset: periode.preset });
      if (periode.start) q.set("start", periode.start);
      if (periode.end) q.set("end", periode.end);
      const { data: d, demo: isDemo } = await apiOrDemo(
        () => api.get<AnalisaKesesuaian>(`/content/brands/${brandId}/analisa?${q}`),
        demoAnalisa
      );
      setData(d);
      setDemo(isDemo);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal memuat analisa.");
    } finally {
      setLoading(false);
    }
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
        action={
          <div className="flex flex-wrap items-center gap-2">
            <DemoBadge tampil={demo} />
            <ExportPdfButton />
          </div>
        }
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
            <option value="facebook">Facebook</option>
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
            <BandingChart data={grafikBanding} warna={warnaMetrik} label={labelMetrik} />

            <h3 className="mb-3 text-base font-semibold text-slate-900">
              Detail MoM / YoY — {labelMetrik}
            </h3>
            <div className="overflow-x-auto">
              <Tabel
                kolom={["Bulan", labelMetrik, "MoM", "YoY"]}
                rata={["left", "right", "left", "left"]}
                baris={banding.bulan
                  .filter((b) => (b[bandingMetrik] ?? 0) > 0)
                  .map((b) => [
                    <span key="b" className="font-medium text-slate-900">
                      {b.label}
                    </span>,
                    <span key="m" className="tabular-nums">
                      {formatAngka(b[bandingMetrik])}
                    </span>,
                    <DeltaBadge
                      key="mom"
                      nilai={deltaUntuk(b, "mom", bandingMetrik)}
                      jenis={`MoM ${labelMetrik}`}
                    />,
                    <DeltaBadge
                      key="yoy"
                      nilai={deltaUntuk(b, "yoy", bandingMetrik)}
                      jenis={`YoY ${labelMetrik}`}
                    />,
                  ])}
              />
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Engagement = likes + komentar + share + simpanan. Karena export
              Meta dibatasi 3 bulan per file, unggah file-file periode
              sebelumnya lewat halaman Upload agar perbandingan YoY terisi.
            </p>
          </>
        )}
      </Card>

      {/* Analisa lanjutan: skor akun, komposisi engagement, per format, detail bulanan, diagnosis & saran */}
      {!loading && !error && !kosong && <AnalisaLanjutan brandId={brandId} periode={periode} />}

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
                    <strong className="text-orange-600">
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

          {/* 2. Konten bermasalah — ringkasan per jenis konten */}
          <h2 className="mb-3 mt-8 text-lg font-semibold text-slate-900">
            Konten bermasalah ({data.bermasalah.length})
          </h2>
          {data.bermasalah.length === 0 ? (
            <Alert kind="success">
              Tidak ada konten bermasalah pada periode ini. Pertahankan polanya!
            </Alert>
          ) : (
            <div className="space-y-4">
              {(() => {
                const grup: Record<string, typeof data.bermasalah> = {};
                for (const k of data.bermasalah) {
                  const fmt = (k.format || "lainnya").toLowerCase();
                  if (!grup[fmt]) grup[fmt] = [];
                  grup[fmt].push(k);
                }
                // Total post per format dari ringkasan.
                const totalPerFormat: Record<string, number> = {};
                for (const r of data.ringkasan) {
                  const fmt = (r.format || "").toLowerCase();
                  totalPerFormat[fmt] = (totalPerFormat[fmt] || 0) + (r.jumlah || 0);
                }
                const urutan = ["carousel", "foto", "image", "reels", "story", "live"];
                const keys = Object.keys(grup).sort(
                  (a, b) => (urutan.indexOf(a) === -1 ? 99 : urutan.indexOf(a)) -
                            (urutan.indexOf(b) === -1 ? 99 : urutan.indexOf(b))
                );
                const namaFormat = (fmt: string) =>
                  fmt === "foto" ? "Image" : fmt.replace(/_/g, " ");
                return keys.map((fmt) => {
                  const items = grup[fmt];
                  const total = totalPerFormat[fmt] ?? items.length;
                  // Agregasi masalah: hitung per jenis metrik.
                  const masalahCount: Record<string, { jumlah: number; contoh: string }> = {};
                  for (const k of items) {
                    for (const d of k.diagnoses) {
                      const kunci = d.metrik;
                      if (!masalahCount[kunci]) {
                        masalahCount[kunci] = { jumlah: 0, contoh: d.masalah };
                      }
                      masalahCount[kunci].jumlah += 1;
                    }
                  }
                  // Agregasi saran unik.
                  const saranUnik: string[] = [];
                  for (const k of items) {
                    for (const s of k.suggestions) {
                      if (!saranUnik.includes(s)) saranUnik.push(s);
                    }
                  }
                  return (
                    <Card key={fmt}>
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                        <h3 className="text-base font-bold capitalize text-slate-900">
                          {namaFormat(fmt)}
                        </h3>
                        <span className="inline-flex items-center rounded-full bg-red-50 px-3 py-1 text-sm font-semibold text-red-700 ring-1 ring-inset ring-red-200">
                          {items.length} bermasalah dari {total} post
                        </span>
                      </div>
                      <h4 className="mb-2 text-sm font-semibold text-slate-800">
                        Uraian masalah
                      </h4>
                      <ul className="mb-4 list-disc space-y-1.5 pl-5 text-sm text-slate-700">
                        {Object.entries(masalahCount).map(([metrik, info]) => (
                          <li key={metrik}>
                            <span className="font-semibold text-slate-900">
                              {info.jumlah} konten
                            </span>{" "}
                            — {info.contoh.split(".")[0]}.
                          </li>
                        ))}
                      </ul>
                      {saranUnik.length > 0 && (
                        <>
                          <h4 className="mb-2 text-sm font-semibold text-slate-800">
                            Saran perbaikan
                          </h4>
                          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
                            {saranUnik.map((s, j) => (
                              <li key={j}>{s}</li>
                            ))}
                          </ul>
                        </>
                      )}
                    </Card>
                  );
                });
              })()}
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
