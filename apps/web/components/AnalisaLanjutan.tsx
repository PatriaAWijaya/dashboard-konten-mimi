"use client";

import { useCallback, useEffect, useState } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { api, ApiError } from "@/lib/api";
import { apiOrDemo, demoAnalisaLanjutan } from "@/lib/content";
import { formatAngka, formatPersen } from "@/lib/format";
import type { AnalisaLanjutan, DiagnosisItem } from "@/lib/types";
import { Alert, Card, Select, Spinner, Tabel } from "@/components/ui";

const WARNA_ENGAGEMENT: { kunci: string; label: string; warna: string }[] = [
  { kunci: "likes", label: "Likes", warna: "#e11d48" },
  { kunci: "comments", label: "Comments", warna: "#d97706" },
  { kunci: "saves", label: "Saves", warna: "#7c3aed" },
  { kunci: "shares", label: "Shares", warna: "#0d9488" },
  { kunci: "follows", label: "Follows", warna: "#db2777" },
];

const TONE_DIAGNOSIS: Record<DiagnosisItem["tingkat"], string> = {
  kritis: "border-red-400 bg-red-50",
  perhatian: "border-amber-400 bg-amber-50",
  baik: "border-emerald-400 bg-emerald-50",
};
const BADGE_DIAGNOSIS: Record<DiagnosisItem["tingkat"], string> = {
  kritis: "bg-red-100 text-red-700",
  perhatian: "bg-amber-100 text-amber-700",
  baik: "bg-emerald-100 text-emerald-700",
};
const LABEL_DIAGNOSIS: Record<DiagnosisItem["tingkat"], string> = {
  kritis: "Kritis",
  perhatian: "Perhatian",
  baik: "Baik",
};

/** Warna ikon peringkat konten terbaik: emas, perak, perunggu, lalu oranye. */
const WARNA_RANK = [
  "bg-amber-400 text-amber-950",
  "bg-slate-300 text-slate-800",
  "bg-amber-700 text-white",
  "bg-orange-500 text-white",
  "bg-orange-200 text-orange-800",
];

/** Persentase nilai engagement terhadap views, mis. "6,4% dari views". */
function persenDariViews(nilai: number | null | undefined, views: number | null | undefined): string {
  if (nilai === null || nilai === undefined || !views || views <= 0) return "-";
  return ((nilai / views) * 100).toLocaleString("id-ID", { maximumFractionDigits: 2 }) + "% dari views";
}

function warnaSkor(skor: number): string {
  if (skor >= 8) return "text-emerald-600";
  if (skor >= 6.5) return "text-lime-600";
  if (skor >= 5) return "text-amber-600";
  if (skor >= 3.5) return "text-orange-600";
  return "text-red-600";
}

function potongCaption(caption: string, batas = 140): { pendek: string; perlu: boolean } {
  const rapi = caption.replace(/\s+/g, " ").trim();
  if (rapi.length <= batas) return { pendek: rapi, perlu: false };
  return { pendek: rapi.slice(0, batas) + "…", perlu: true };
}

/** Label ramah untuk format: "foto" dari export Meta ditampilkan sebagai "Image/Foto". */
function labelFormat(format: string): string {
  if (format === "foto") return "Image/Foto";
  return format.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AnalisaLanjutan({
  brandId,
  periode,
}: {
  brandId: string;
  periode: { preset: string; start?: string; end?: string };
}) {
  const [data, setData] = useState<AnalisaLanjutan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [bulan, setBulan] = useState("");
  const [formatF, setFormatF] = useState("");
  const [kategoriF, setKategoriF] = useState("");
  const [ctaF, setCtaF] = useState("");
  const [captionTerbuka, setCaptionTerbuka] = useState<Set<string>>(new Set());

  const muat = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const q = new URLSearchParams({ preset: periode.preset });
      if (periode.start) q.set("start", periode.start);
      if (periode.end) q.set("end", periode.end);
      if (bulan) q.set("bulan", bulan);
      if (formatF) q.set("format", formatF);
      if (kategoriF) q.set("kategori", kategoriF);
      if (ctaF) q.set("cta", ctaF);
      const { data: d } = await apiOrDemo(
        () => api.get<AnalisaLanjutan>(`/content/brands/${brandId}/analisa-lanjutan?${q}`),
        demoAnalisaLanjutan
      );
      setData(d);
      // Sinkronkan pilihan bulan dengan bulan aktif dari backend (default: terbaru).
      if (!bulan && d.bulan_aktif) setBulan(d.bulan_aktif);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal memuat analisa lanjutan.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [brandId, periode, bulan, formatF, kategoriF, ctaF]);

  useEffect(() => {
    muat();
  }, [muat]);

  const toggleCaption = (id: string) => {
    setCaptionTerbuka((s) => {
      const baru = new Set(s);
      if (baru.has(id)) baru.delete(id);
      else baru.add(id);
      return baru;
    });
  };

  if (loading) return <Spinner label="Memuat analisa lanjutan…" />;
  if (error) return <Alert kind="error">{error}</Alert>;
  if (!data || data.kosong || !data.komposisi || !data.skor_akun) {
    return (
      <p className="py-4 text-center text-sm text-slate-500">
        Belum ada data untuk analisa lanjutan pada periode ini.
      </p>
    );
  }

  const komposisi = data.komposisi;
  const skor = data.skor_akun;
  const dataPie = WARNA_ENGAGEMENT.map((w) => ({
    name: w.label,
    value: komposisi[w.kunci as keyof typeof komposisi] as number,
  })).filter((d) => d.value > 0);
  const opsi = data.filter_options;

  return (
    <div className="space-y-8">
      {/* 1. Skor performa akun */}
      <Card className="mb-8">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Skor Performa Akun</h2>
            <p className="text-sm text-slate-500">
              Nilai gabungan 1–10 dari kualitas engagement, konsistensi, tren, dan
              proporsi konten kuat.
            </p>
          </div>
          <div className="text-right">
            <p className={`text-5xl font-bold tabular-nums ${warnaSkor(skor.skor)}`}>
              {skor.skor.toLocaleString("id-ID")}
              <span className="text-xl text-slate-400">/10</span>
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-700">{skor.grade}</p>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {skor.komponen.map((k) => (
            <div key={k.nama} className="rounded-xl bg-slate-50 p-3">
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-sm font-semibold text-slate-800">
                  {k.nama}{" "}
                  <span className="font-normal text-slate-400">
                    ({Math.round(k.bobot * 100)}%)
                  </span>
                </p>
                <p className={`text-sm font-bold tabular-nums ${warnaSkor(k.nilai)}`}>
                  {k.nilai.toLocaleString("id-ID")}
                </p>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
                <div
                  className={`h-full rounded-full ${warnaSkor(k.nilai).replace("text-", "bg-")}`}
                  style={{ width: `${Math.min(100, k.nilai * 10)}%` }}
                />
              </div>
              <p className="mt-1.5 text-xs text-slate-500">{k.penjelasan}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-500">{skor.cara_hitung}</p>
      </Card>

      {/* 2. Komposisi engagement */}
      <Card className="mb-8">
        <h2 className="text-lg font-semibold text-slate-900">Komposisi Engagement</h2>
        <p className="mb-4 text-sm text-slate-500">
          Total tiap jenis engagement pada periode ini · {formatAngka(komposisi.jumlah_konten)} konten ·
          rata-rata {formatAngka(komposisi.rata_engagement_per_konten)} engagement/konten
        </p>
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {WARNA_ENGAGEMENT.map((w) => (
              <div key={w.kunci} className="rounded-xl bg-slate-50 p-3">
                <p className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: w.warna }}
                  />
                  {w.label}
                </p>
                <p className="mt-1 text-xl font-bold tabular-nums text-slate-900">
                  {formatAngka(komposisi[w.kunci as keyof typeof komposisi] as number)}
                </p>
                <p className="mt-0.5 text-[11px] tabular-nums text-slate-400">
                  {persenDariViews(komposisi[w.kunci as keyof typeof komposisi] as number, komposisi.views)}
                </p>
              </div>
            ))}
            <div className="rounded-xl bg-orange-50 p-3">
              <p className="text-xs font-medium text-orange-700">Total engagement</p>
              <p className="mt-1 text-xl font-bold tabular-nums text-orange-900">
                {formatAngka(komposisi.total_engagement)}
              </p>
              <p className="mt-0.5 text-[11px] tabular-nums text-orange-600/70">
                {persenDariViews(komposisi.total_engagement, komposisi.views)}
              </p>
            </div>
            <div className="rounded-xl bg-slate-50 p-3">
              <p className="text-xs font-medium text-slate-500">Views</p>
              <p className="mt-1 text-xl font-bold tabular-nums text-slate-900">
                {formatAngka(komposisi.views)}
              </p>
              <p className="mt-0.5 text-[11px] tabular-nums text-slate-400">
                100% · baseline
              </p>
            </div>
            <div className="rounded-xl bg-slate-50 p-3">
              <p className="text-xs font-medium text-slate-500">Reach</p>
              <p className="mt-1 text-xl font-bold tabular-nums text-slate-900">
                {formatAngka(komposisi.reach)}
              </p>
              <p className="mt-0.5 text-[11px] tabular-nums text-slate-400">
                {persenDariViews(komposisi.reach, komposisi.views)}
              </p>
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={dataPie}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  label={({ name, percent }) =>
                    `${name} ${((percent ?? 0) * 100).toFixed(0)}%`
                  }
                  labelLine={false}
                >
                  {dataPie.map((d, i) => (
                    <Cell
                      key={d.name}
                      fill={WARNA_ENGAGEMENT[i % WARNA_ENGAGEMENT.length].warna}
                    />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => formatAngka(typeof v === "number" ? v : null)} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Engagement = likes + komentar + simpanan + share. Gunakan filter
          &ldquo;Metrik&rdquo; pada seksi Tren &amp; Perbandingan Bulanan untuk melihat
          tren tiap jenis engagement per bulan.
        </p>
      </Card>

      {/* 3. Total per jenis post */}
      <Card className="mb-8">
        <h2 className="text-lg font-semibold text-slate-900">Total per Jenis Post</h2>
        <p className="mb-4 text-sm text-slate-500">
          Jumlah konten dan akumulasi engagement tiap format pada periode yang dipilih.
        </p>
        <div className="overflow-x-auto">
          <Tabel
            kolom={[
              "Jenis post",
              "Konten",
              "Views",
              "Likes",
              "Comments",
              "Saves",
              "Shares",
              "Follows",
              "Total eng.",
              "Rata-rata ER",
            ]}
            rata={[
              "left",
              "right",
              "right",
              "right",
              "right",
              "right",
              "right",
              "right",
              "right",
              "right",
            ]}
            baris={data.per_format.map((f) => [
              <span key="j" className="font-medium text-slate-900">
                {labelFormat(f.format)}
              </span>,
              <span key="k" className="tabular-nums">
                {formatAngka(f.jumlah)}
              </span>,
              <span key="v" className="tabular-nums">
                {formatAngka(f.views)}
              </span>,
              <span key="l" className="tabular-nums">
                {formatAngka(f.likes)}
              </span>,
              <span key="c" className="tabular-nums">
                {formatAngka(f.comments)}
              </span>,
              <span key="sv" className="tabular-nums">
                {formatAngka(f.saves)}
              </span>,
              <span key="sh" className="tabular-nums">
                {formatAngka(f.shares)}
              </span>,
              <span key="fo" className="tabular-nums">
                {formatAngka(f.follows)}
              </span>,
              <span key="t" className="font-semibold tabular-nums text-slate-900">
                {formatAngka(f.total_engagement)}
              </span>,
              <span key="e" className="tabular-nums">
                {formatPersen(f.rata_er, 1, false)}
              </span>,
            ])}
          />
        </div>
      </Card>

      {/* 4. Laporan detail per bulan */}
      <Card className="mb-8">
        <h2 className="text-lg font-semibold text-slate-900">Laporan Detail per Bulan</h2>
        <p className="mb-4 text-sm text-slate-500">
          Tiap konten: jenis post, caption, engagement, dan tipe CTA.
          {opsi?.heuristik ? ` ${opsi.heuristik}` : ""}
        </p>
        {opsi && (
          <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Select label="Bulan" value={bulan} onChange={(e) => setBulan(e.target.value)}>
              {opsi.bulan.map((b) => (
                <option key={b.value} value={b.value}>
                  {b.label}
                </option>
              ))}
            </Select>
            <Select
              label="Jenis post"
              value={formatF}
              onChange={(e) => setFormatF(e.target.value)}
            >
              <option value="">Semua jenis</option>
              {opsi.format.map((f) => (
                <option key={f} value={f}>
                  {labelFormat(f)}
                </option>
              ))}
            </Select>
            <Select
              label="Kategori post"
              value={kategoriF}
              onChange={(e) => setKategoriF(e.target.value)}
            >
              <option value="">Semua kategori</option>
              {opsi.kategori.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </Select>
            <Select label="Tipe CTA" value={ctaF} onChange={(e) => setCtaF(e.target.value)}>
              <option value="">Semua CTA</option>
              {opsi.cta.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </Select>
          </div>
        )}
        {data.detail_bulanan.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">
            Tidak ada konten yang cocok dengan filter pada bulan ini.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Tabel
              kolom={[
                "Tanggal",
                "Jenis post",
                "Caption",
                "Views",
                "Engagement",
                "Tipe CTA",
                "Kategori",
              ]}
              rata={[
                "left",
                "left",
                "left",
                "right",
                "right",
                "left",
                "left",
              ]}
              baris={data.detail_bulanan.map((d) => {
                const { pendek, perlu } = potongCaption(d.caption);
                const terbuka = captionTerbuka.has(d.content_id);
                return [
                  <span key="t" className="whitespace-nowrap text-slate-600">
                    {d.tanggal}
                  </span>,
                  <span key="j" className="font-medium text-slate-900">
                    {labelFormat(d.format)}
                  </span>,
                  <span key="c" className="block max-w-[280px] text-slate-600">
                    <span className="break-words text-[13px] leading-snug">
                      {terbuka
                        ? d.caption.replace(/\s+/g, " ").trim()
                        : pendek}
                    </span>
                    {perlu && (
                      <button
                        type="button"
                        onClick={() => toggleCaption(d.content_id)}
                        className="mt-1 block text-xs font-medium text-orange-600 hover:underline"
                      >
                        {terbuka ? "Tutup" : "Lihat lengkap"}
                      </button>
                    )}
                  </span>,
                  <span key="v" className="tabular-nums">
                    {formatAngka(d.views)}
                  </span>,
                  <span key="e">
                    <span className="block font-semibold tabular-nums text-slate-900">
                      {formatAngka(d.total_engagement)}
                    </span>
                    <span className="block text-[11px] tabular-nums text-slate-400">
                      L {formatAngka(d.likes)} · K {formatAngka(d.comments)} · S{" "}
                      {formatAngka(d.saves)} · Sh {formatAngka(d.shares)} · F{" "}
                      {formatAngka(d.follows)}
                    </span>
                  </span>,
                  <span key="cta" className="flex max-w-[160px] flex-wrap gap-1">
                    {d.cta_label.map((c) => (
                      <span
                        key={c}
                        className="inline-block rounded-full bg-orange-100 px-2 py-0.5 text-[11px] font-medium text-orange-700"
                      >
                        {c}
                      </span>
                    ))}
                  </span>,
                  <span
                    key="k"
                    className="inline-block rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600"
                  >
                    {d.kategori_label}
                  </span>,
                ];
              })}
            />
          </div>
        )}
      </Card>

      {/* 5. Diagnosis & saran */}
      <div className="grid items-start gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <Card>
            <h2 className="text-lg font-semibold text-slate-900">Kenapa Akun Stuck?</h2>
            <p className="mb-4 text-sm text-slate-500">
              Diagnosis berbasis data pada periode ini.
            </p>
            <div className="space-y-3">
              {data.diagnosis.map((d, i) => (
                <div key={i} className={`rounded-xl border-l-4 p-3 ${TONE_DIAGNOSIS[d.tingkat]}`}>
                  <p className="mb-1 flex items-center gap-2">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${BADGE_DIAGNOSIS[d.tingkat]}`}
                    >
                      {LABEL_DIAGNOSIS[d.tingkat]}
                    </span>
                    <span className="text-sm font-semibold text-slate-900">{d.judul}</span>
                  </p>
                  <p className="text-sm text-slate-600">{d.detail}</p>
                </div>
              ))}
            </div>
          </Card>
          {(() => {
            const saranWinning = data.saran.find((s) => s.contoh && s.contoh.length > 0);
            if (!saranWinning?.contoh) return null;
            return (
              <Card>
                <h2 className="text-lg font-semibold text-slate-900">
                  {saranWinning.contoh.length} Konten Terbaik
                </h2>
                <p className="mb-4 text-sm text-slate-500">
                  ER tertinggi pada periode ini — bahan growth loop.
                </p>
                <div className="space-y-3">
                  {saranWinning.contoh.map((c, idx) => (
                    <div key={c.post_id} className="flex items-start gap-3 rounded-xl bg-slate-50 p-3">
                      <span
                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${WARNA_RANK[idx % WARNA_RANK.length]}`}
                        title={`Peringkat ${idx + 1}`}
                      >
                        {idx + 1}
                      </span>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-slate-800">
                          ER {c.er.toLocaleString("id-ID")}% · {labelFormat(c.format)}
                        </p>
                        <p className="mt-0.5 break-words text-xs text-slate-600">
                          {c.caption_singkat}
                        </p>
                        {c.post_url && (
                          <a
                            href={c.post_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-1 inline-block text-xs font-medium text-orange-600 underline hover:text-orange-700"
                          >
                            Lihat konten asli ↗
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            );
          })()}
        </div>
        <Card>
          <h2 className="text-lg font-semibold text-slate-900">Saran Perbaikan Pola</h2>
          <p className="mb-4 text-sm text-slate-500">
            Disusun dari pola konten dengan performa terbaik.
          </p>
          <div className="space-y-4">
            {data.saran.map((s, i) => (
              <div key={i} className="rounded-xl bg-slate-50 p-3">
                <p className="text-sm font-semibold text-slate-900">
                  <span className="mr-1.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-orange-600 text-[11px] font-bold text-white">
                    {i + 1}
                  </span>
                  {s.judul}
                </p>
                <p className="mt-1.5 text-sm text-slate-600">{s.detail}</p>
                <p className="mt-1 text-xs italic text-slate-400">{s.dasar}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
