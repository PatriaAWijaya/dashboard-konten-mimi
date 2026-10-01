"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { apiOrDemo, demoDashboard } from "@/lib/content";
import type { BrandDashboard, KartuPlatform, Platform, ScoreResult } from "@/lib/types";
import { formatTanggal } from "@/lib/format";

// Chart di-load lazy agar bundle awal ringan (recharts ~100kB).
const TrenChart = dynamic(() => import("@/components/TrenChart"), {
  ssr: false,
  loading: () => <p className="text-sm text-slate-500">Memuat grafik…</p>,
});
import { Alert, Button, Card, EmptyBox, PageHeader, Spinner } from "@/components/ui";
import { StatusKontenBadge } from "@/components/badges";
import BrandNav from "@/components/BrandNav";
import DemoBadge from "@/components/DemoBadge";
import ExportPdfButton from "@/components/ExportPdfButton";
// import OnboardingBanner from "@/components/OnboardingBanner"; // disembunyikan sementara
import PeriodPicker, { type PilihanPeriode } from "@/components/PeriodPicker";

function fmtAngka(n: number | null | undefined, desimal = 1): string {
  if (n === null || n === undefined) return "-";
  return n.toLocaleString("id-ID", {
    minimumFractionDigits: desimal,
    maximumFractionDigits: desimal,
  });
}

// Backend mengirim skor (0-1) dan ER (rasio 0-1); tampilkan sebagai persen.
function fmtPersen(n: number | null | undefined, desimal = 1): string {
  if (n === null || n === undefined) return "-";
  return (n * 100).toLocaleString("id-ID", {
    minimumFractionDigits: desimal,
    maximumFractionDigits: desimal,
  }) + "%";
}

function KartuRingkasan({
  judul,
  data,
}: {
  judul: string;
  data: KartuPlatform;
}) {
  return (
    <Card>
      <h3 className="mb-4 text-base font-semibold text-slate-900">{judul}</h3>
      <div className="grid grid-cols-3 gap-3 text-center">
        <div>
          <p className="text-2xl font-bold text-slate-900">{data.jumlah_konten}</p>
          <p className="text-xs text-slate-500">Konten</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-orange-600">{fmtPersen(data.rata_skor)}</p>
          <p className="text-xs text-slate-500">Rata-rata skor</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-sky-600">{fmtPersen(data.rata_er)}</p>
          <p className="text-xs text-slate-500">Rata-rata ER</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
          MENANG · {data.menang}
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">
          CUKUP · {data.cukup}
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-red-100 px-3 py-1 text-xs font-semibold text-red-800">
          KURANG · {data.kurang}
        </span>
      </div>
    </Card>
  );
}

// Senin (YYYY-MM-DD) dari minggu berjalan.
function seninMingguIni(): string {
  const d = new Date();
  const geser = (d.getDay() + 6) % 7; // 0 = Senin
  d.setDate(d.getDate() - geser);
  const t = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const hari = String(d.getDate()).padStart(2, "0");
  return `${t}-${m}-${hari}`;
}

type RingkasanPekan =
  | { ada: false }
  | {
      ada: true;
      id: string;
      teks: string;
      period_start: string;
      period_end: string;
      created_at: string;
    };

function KartuRingkasanPekan({ brandId }: { brandId: string }) {
  const [ringkasan, setRingkasan] = useState<RingkasanPekan | null | undefined>(
    undefined
  );
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const minggu = useMemo(() => seninMingguIni(), []);

  useEffect(() => {
    let batal = false;
    api
      .get<RingkasanPekan>(`/content/brands/${brandId}/ringkasan?minggu=${minggu}`)
      .then((r) => {
        if (!batal) setRingkasan(r);
      })
      .catch((err) => {
        if (!batal)
          setError(
            err instanceof ApiError ? err.message : "Gagal memuat ringkasan."
          );
      })
      .finally(() => {
        if (!batal) setLoading(false);
      });
    return () => {
      batal = true;
    };
  }, [brandId, minggu]);

  async function buatRingkasan() {
    setGenerating(true);
    setError("");
    try {
      const r = await api.post<RingkasanPekan>(
        `/content/brands/${brandId}/ringkasan/generate?minggu=${minggu}`
      );
      setRingkasan(r);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal membuat ringkasan."
      );
    } finally {
      setGenerating(false);
    }
  }

  return (
    <Card className="mt-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold text-slate-900">
          Ringkasan pekan ini
        </h3>
        {ringkasan && ringkasan.ada && (
          <span className="text-xs text-slate-400">
            {formatTanggal(ringkasan.created_at, true)}
          </span>
        )}
      </div>
      {loading && <Spinner label="Memuat ringkasan…" />}
      {error && <Alert kind="error">{error}</Alert>}
      {!loading && !error && ringkasan && ringkasan.ada && (
        <>
          <p className="mt-1 text-xs text-slate-500">
            {formatTanggal(ringkasan.period_start)} –{" "}
            {formatTanggal(ringkasan.period_end)}
          </p>
          <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-700">
            {ringkasan.teks}
          </p>
        </>
      )}
      {!loading && !error && ringkasan && !ringkasan.ada && (
        <div className="mt-3">
          <p className="text-sm text-slate-500">
            Belum ada ringkasan untuk pekan ini. Buat ringkasan otomatis dari
            performa konten Anda.
          </p>
          <Button onClick={buatRingkasan} disabled={generating} className="mt-3">
            {generating ? "Membuat…" : "Buat ringkasan"}
          </Button>
        </div>
      )}
    </Card>
  );
}

function DasborBrandIsi() {
  const params = useParams();
  const brandId = params.brandId as string;
  const [periode, setPeriode] = useState<PilihanPeriode>({ preset: "30d" });
  const [data, setData] = useState<BrandDashboard | null>(null);
  const [demo, setDemo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scoring, setScoring] = useState(false);
  const [pesanSkor, setPesanSkor] = useState("");

  const muat = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const q = new URLSearchParams({ preset: periode.preset });
      if (periode.start) q.set("start", periode.start);
      if (periode.end) q.set("end", periode.end);
      const { data: d, demo: isDemo } = await apiOrDemo(
        () => api.get<BrandDashboard>(`/content/brands/${brandId}/dashboard?${q}`),
        demoDashboard
      );
      setData(d);
      setDemo(isDemo);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal memuat dasbor brand.");
    } finally {
      setLoading(false);
    }
  }, [brandId, periode]);

  useEffect(() => {
    muat();
  }, [muat]);

  async function hitungUlangSkor() {
    setScoring(true);
    setPesanSkor("");
    setError("");
    try {
      const body: Record<string, string> = { preset: periode.preset };
      if (periode.start) body.start = periode.start;
      if (periode.end) body.end = periode.end;
      const { data: hasil, demo: isDemo } = await apiOrDemo<ScoreResult>(
        () => api.post<ScoreResult>(`/content/brands/${brandId}/score`, body),
        { diskor: data?.konten.length ?? 0, periode: "periode terpilih (demo)" }
      );
      setPesanSkor(
        `Scoring selesai: ${hasil.diskor} konten diskor untuk ${hasil.periode}.${isDemo ? " (demo)" : ""}`
      );
      muat();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal menjalankan scoring."
      );
    } finally {
      setScoring(false);
    }
  }

  // Jumlah konten dari seluruh kartu platform (defensif: kunci platform
  // boleh tidak ada bila backend lama / data kosong).
  const jumlahKartu =
    !loading && data
      ? Object.values(data.kartu ?? {}).reduce(
          (s, k) => s + (k?.jumlah_konten ?? 0),
          0
        )
      : 0;
  const kosong =
    !loading && !!data && data.konten.length === 0 && jumlahKartu === 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Dasbor Analitik"
        subtitle="Ringkasan performa konten per platform."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <DemoBadge tampil={demo} />
            <ExportPdfButton />
            <Button onClick={hitungUlangSkor} disabled={scoring} variant="secondary">
              {scoring ? "Menghitung…" : "Hitung Ulang Skor"}
            </Button>
          </div>
        }
      />
      <BrandNav brandId={brandId} />
      {/* OnboardingBanner disembunyikan sementara — tampilkan lagi setelah alur onboarding siap. */}
      {/* <OnboardingBanner brandId={brandId} /> */}

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <PeriodPicker value={periode} onChange={setPeriode} />
        {pesanSkor && (
          <p className="text-sm font-medium text-emerald-700">{pesanSkor}</p>
        )}
      </div>

      {loading && <Spinner label="Memuat dasbor…" />}
      {error && <Alert kind="error">{error}</Alert>}

      {!loading && !error && kosong && (
        <EmptyBox
          title="Belum ada data — mulai dari sini"
          description="Hubungkan akun TikTok atau Instagram brand untuk sync otomatis, upload CSV metrik konten, atau lanjutkan onboarding 4 langkah untuk dipandu dari awal."
          icon={
            <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
            </svg>
          }
        />
      )}
      {!loading && !error && kosong && (
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <Link href={`/brand/${brandId}/koneksi`}>
            <Button variant="secondary">Hubungkan akun</Button>
          </Link>
          <Link href="/upload">
            <Button variant="secondary">Upload CSV</Button>
          </Link>
          <Link href={`/onboarding?brand=${brandId}`}>
            <Button>Lanjutkan onboarding</Button>
          </Link>
        </div>
      )}

      {!loading && !error && data && !kosong && (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            {data.kartu?.tiktok && (
              <KartuRingkasan judul="TikTok" data={data.kartu.tiktok} />
            )}
            {data.kartu?.instagram && (
              <KartuRingkasan judul="Instagram" data={data.kartu.instagram} />
            )}
          </div>

          <KartuRingkasanPekan brandId={brandId} />

          {/* Grafik tren */}
          <Card className="mt-4">
            <h3 className="mb-4 text-base font-semibold text-slate-900">
              Tren mingguan — rata-rata skor & ER
            </h3>
            <TrenChart data={data.tren} />
          </Card>

          {/* Tabel konten */}
          <Card className="mt-4">
            <h3 className="mb-4 text-base font-semibold text-slate-900">
              Daftar konten ({data.konten.length})
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                    <th className="py-2 pr-3">Post ID</th>
                    <th className="py-2 pr-3">Platform</th>
                    <th className="py-2 pr-3">Format</th>
                    <th className="py-2 pr-3">Tujuan</th>
                    <th className="py-2 pr-3 text-right">Views</th>
                    <th className="py-2 pr-3 text-right">ER</th>
                    <th className="py-2 pr-3 text-right">Skor</th>
                    <th className="py-2 pr-3">Status</th>
                    <th className="py-2">Label</th>
                  </tr>
                </thead>
                <tbody>
                  {data.konten.map((k) => (
                    <tr key={k.content_id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                      <td className="py-2.5 pr-3 font-mono text-[13px] font-medium text-slate-900">
                        {k.post_id}
                      </td>
                      <td className="py-2.5 pr-3 capitalize text-slate-600">{k.platform}</td>
                      <td className="py-2.5 pr-3 text-slate-600">{formatLabel(k.format)}</td>
                      <td className="py-2.5 pr-3 capitalize text-slate-600">{k.tujuan}</td>
                      <td className="py-2.5 pr-3 text-right tabular-nums text-slate-700">
                        {k.views?.toLocaleString("id-ID") ?? "-"}
                      </td>
                      <td className="py-2.5 pr-3 text-right tabular-nums text-slate-700">
                        {k.er !== null && k.er !== undefined ? fmtPersen(k.er) : "-"}
                      </td>
                      <td className="py-2.5 pr-3 text-right font-semibold tabular-nums text-slate-900">
                        {k.score ?? "-"}
                      </td>
                      <td className="py-2.5 pr-3">
                        <StatusKontenBadge status={k.status} />
                      </td>
                      <td className="py-2.5">
                        {k.labels.includes("winner") ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-semibold text-orange-700">
                            🏆 winner
                          </span>
                        ) : (
                          <span className="text-slate-300">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-slate-400">
              Data per {formatTanggal(new Date().toISOString())} · ER = weighted
              engagement rate.
            </p>
          </Card>
        </>
      )}
    </div>
  );
}

function formatLabel(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function DasborBrandPage() {
  return (
    <RequireAuth>
      <DasborBrandIsi />
    </RequireAuth>
  );
}
