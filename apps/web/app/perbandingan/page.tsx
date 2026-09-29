"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { apiOrDemo, getSelectedBrandId } from "@/lib/content";
import type {
  PerbandinganBulan,
  PerbandinganData,
  PerbandinganDelta,
} from "@/lib/types";
import {
  Alert,
  Button,
  Card,
  EmptyBox,
  PageHeader,
  Select,
  Spinner,
} from "@/components/ui";
import BrandSelector from "@/components/BrandSelector";
import DemoBadge from "@/components/DemoBadge";

const RENTANG = [
  { value: "6", label: "6 bulan terakhir" },
  { value: "12", label: "12 bulan terakhir" },
] as const;

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

function awalRentang(bulanKeBelakang: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() - (bulanKeBelakang - 1), 1);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}-01`;
}

function PerbandinganIsi() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [platform, setPlatform] = useState("semua");
  const [rentang, setRentang] = useState<string>("12");
  const [data, setData] = useState<PerbandinganData | null>(null);
  const [demo, setDemo] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setBrandId(getSelectedBrandId());
  }, []);

  const muat = useCallback(async () => {
    if (!brandId) return;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        platform,
        start: awalRentang(Number(rentang)),
      });
      const { data: hasil, demo: pakaiDemo } = await apiOrDemo<PerbandinganData>(
        () => api.get<PerbandinganData>(`/content/brands/${brandId}/perbandingan?${params}`),
        () => demoPerbandingan()
      );
      setData(hasil);
      setDemo(pakaiDemo);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal memuat data perbandingan."
      );
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [brandId, platform, rentang]);

  useEffect(() => {
    muat();
  }, [muat]);

  const kosong = !loading && !error && data && data.bulan.every((b) => b.jumlah_konten === 0);

  const grafik = (data?.bulan ?? []).map((b) => ({
    label: b.label,
    Views: b.views,
    Engagement: b.engagement,
  }));

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Perbandingan Kinerja"
        subtitle="Bandingkan performa konten month-on-month (MoM) dan year-on-year (YoY). Unggah beberapa file CSV untuk melihat beberapa periode sekaligus."
        action={
          <div className="flex items-center gap-2">
            <DemoBadge tampil={demo} />
            <Link href="/upload">
              <Button variant="secondary">Upload CSV</Button>
            </Link>
          </div>
        }
      />

      <Card className="mb-6">
        <div className="grid gap-4 sm:grid-cols-3">
          <BrandSelector value={brandId} onChange={setBrandId} />
          <Select
            label="Platform"
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
          >
            <option value="semua">Semua platform</option>
            <option value="tiktok">TikTok</option>
            <option value="instagram">Instagram</option>
          </Select>
          <Select
            label="Rentang"
            value={rentang}
            onChange={(e) => setRentang(e.target.value)}
          >
            {RENTANG.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </Select>
        </div>
      </Card>

      {loading && (
        <div className="flex justify-center py-16">
          <Spinner />
        </div>
      )}
      {error && <Alert kind="error">{error}</Alert>}
      {!loading && !error && !brandId && (
        <EmptyBox title="Pilih brand" description="Pilih brand terlebih dahulu untuk melihat perbandingan." icon="🏷️" />
      )}
      {kosong && (
        <EmptyBox
          title="Belum ada data"
          description="Belum ada data konten pada rentang ini. Unggah CSV terlebih dahulu, lalu jalankan scoring."
          icon="📊"
        />
      )}

      {!loading && !error && data && !kosong && (
        <>
          <Card className="mb-6">
            <h3 className="mb-4 text-base font-semibold text-slate-900">
              Tren bulanan — views & engagement
            </h3>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={grafik} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="#64748b" />
                  <YAxis tick={{ fontSize: 12 }} stroke="#64748b" />
                  <Tooltip
                    formatter={(value) => [
                      fmtAngka(typeof value === "number" ? value : null),
                      "",
                    ]}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="Views" stroke="#4f46e5" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="Engagement" stroke="#0ea5e9" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-base font-semibold text-slate-900">
                Detail per bulan
              </h3>
              <p className="text-xs text-slate-500">
                MoM = vs bulan sebelumnya · YoY = vs bulan yang sama tahun lalu ·
                <span className="ml-1">— = data pembanding belum ada</span>
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[880px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                    <th className="py-2 pr-3">Bulan</th>
                    <th className="py-2 pr-3 text-right">Konten</th>
                    <th className="py-2 pr-3 text-right">Views</th>
                    <th className="py-2 pr-3 text-right">Engagement</th>
                    <th className="py-2 pr-3 text-right">Reach</th>
                    <th className="py-2 pr-3 text-right">Rata skor</th>
                    <th className="py-2 pr-3">MoM (views)</th>
                    <th className="py-2 pr-3">MoM (eng.)</th>
                    <th className="py-2 pr-3">YoY (views)</th>
                    <th className="py-2">YoY (eng.)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.bulan.map((b) => (
                    <tr key={b.bulan} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                      <td className="py-2.5 pr-3 font-medium text-slate-900">{b.label}</td>
                      <td className="py-2.5 pr-3 text-right tabular-nums">{fmtAngka(b.jumlah_konten)}</td>
                      <td className="py-2.5 pr-3 text-right tabular-nums">{fmtAngka(b.views)}</td>
                      <td className="py-2.5 pr-3 text-right tabular-nums">{fmtAngka(b.engagement)}</td>
                      <td className="py-2.5 pr-3 text-right tabular-nums">{fmtAngka(b.reach)}</td>
                      <td className="py-2.5 pr-3 text-right tabular-nums">
                        {b.rata_skor === null ? "-" : b.rata_skor.toLocaleString("id-ID", { maximumFractionDigits: 2 })}
                      </td>
                      <td className="py-2.5 pr-3">
                        <DeltaBadge nilai={b.mom?.views_pct} jenis="MoM views" />
                      </td>
                      <td className="py-2.5 pr-3">
                        <DeltaBadge nilai={b.mom?.engagement_pct} jenis="MoM engagement" />
                      </td>
                      <td className="py-2.5 pr-3">
                        <DeltaBadge nilai={b.yoy?.views_pct} jenis="YoY views" />
                      </td>
                      <td className="py-2.5">
                        <DeltaBadge nilai={b.yoy?.engagement_pct} jenis="YoY engagement" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card className="mt-6">
            <h3 className="mb-2 text-base font-semibold text-slate-900">
              Cara membaca tabel ini
            </h3>
            <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-600">
              <li>
                <strong>MoM</strong> membandingkan bulan berjalan dengan bulan
                kalender sebelumnya — cocok melihat tren jangka pendek
                (mis. dampak perubahan strategi konten).
              </li>
              <li>
                <strong>YoY</strong> membandingkan dengan bulan yang sama di
                tahun sebelumnya — cocok melihat pertumbuhan tahunan dan
                menghilangkan efek musiman.
              </li>
              <li>
                Tanda <strong>—</strong> berarti bulan pembanding belum punya
                data. Karena export Meta dibatasi 3 bulan per file, unggah
                file-file periode sebelumnya lewat halaman Upload agar
                perbandingan YoY terisi.
              </li>
              <li>
                Engagement = likes + komentar + share + simpanan.
              </li>
            </ul>
          </Card>
        </>
      )}
    </div>
  );
}

/** Data demo: 12 bulan sintetis dengan delta MoM/YoY terisi sebagian. */
function demoPerbandingan(): Promise<PerbandinganData> {
  const namaBulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
  const sekarang = new Date();
  const bulan: PerbandinganBulan[] = [];
  const historis: { views: number; engagement: number; jumlah_konten: number; reach: number; rata_skor: number }[] = [];
  for (let i = 23; i >= 0; i--) {
    const d = new Date(sekarang.getFullYear(), sekarang.getMonth() - i, 1);
    const faktor = 1 + Math.sin(i / 2.4) * 0.35 + (23 - i) * 0.03;
    const views = Math.round(12000 * faktor);
    const engagement = Math.round(views * 0.06 * (1 + Math.sin(i) * 0.15));
    historis.push({
      views,
      engagement,
      jumlah_konten: 8 + (i % 5),
      reach: Math.round(views * 0.8),
      rata_skor: 0.55 + Math.sin(i / 3) * 0.15,
    });
    void d;
  }
  for (let i = 0; i < 12; i++) {
    const idx = i + 12; // 12 bulan tampilan = paruh kedua historis
    const h = historis[idx];
    const d = new Date(sekarang.getFullYear(), sekarang.getMonth() - (11 - i), 1);
    const kunci = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const momH = historis[idx - 1];
    const yoyH = i === 0 ? null : historis[idx - 12];
    const delta = (cur: number, prev: number | null | undefined): number | null =>
      prev === null || prev === undefined || prev === 0
        ? null
        : Math.round(((cur - prev) / prev) * 1000) / 10;
    const mom: PerbandinganDelta = {
      bulan_pembanding: momH ? `${d.getFullYear()}-${String(d.getMonth()).padStart(2, "0")}` : null,
      views_pct: delta(h.views, momH?.views),
      engagement_pct: delta(h.engagement, momH?.engagement),
      jumlah_konten_pct: delta(h.jumlah_konten, momH?.jumlah_konten),
      reach_pct: delta(h.reach, momH?.reach),
      rata_skor_pct: delta(h.rata_skor, momH?.rata_skor),
    };
    const yoy: PerbandinganDelta = {
      bulan_pembanding: yoyH ? `${d.getFullYear() - 1}-${String(d.getMonth() + 1).padStart(2, "0")}` : null,
      views_pct: delta(h.views, yoyH?.views),
      engagement_pct: delta(h.engagement, yoyH?.engagement),
      jumlah_konten_pct: delta(h.jumlah_konten, yoyH?.jumlah_konten),
      reach_pct: delta(h.reach, yoyH?.reach),
      rata_skor_pct: delta(h.rata_skor, yoyH?.rata_skor),
    };
    bulan.push({
      bulan: kunci,
      label: `${namaBulan[d.getMonth()]} ${d.getFullYear()}`,
      jumlah_konten: h.jumlah_konten,
      views: h.views,
      likes: Math.round(h.engagement * 0.6),
      comments: Math.round(h.engagement * 0.2),
      shares: Math.round(h.engagement * 0.12),
      saves: Math.round(h.engagement * 0.08),
      reach: h.reach,
      engagement: h.engagement,
      rata_skor: Math.round(h.rata_skor * 100) / 100,
      rata_wer: 0.06,
      mom,
      yoy,
    });
  }
  return Promise.resolve({
    rentang: { mulai: bulan[0].bulan + "-01", selesai: "demo" },
    platform: "semua",
    bulan,
  });
}

export default function PerbandinganPage() {
  return (
    <RequireAuth>
      <PerbandinganIsi />
    </RequireAuth>
  );
}
