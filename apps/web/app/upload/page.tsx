"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import {
  DEMO_FALLBACK,
  apiOrDemo,
  demoCsvColumns,
  getSelectedBrandId,
} from "@/lib/content";
import type { CsvColumnInfo, Platform, ScoreResult, UploadResult } from "@/lib/types";
import {
  Alert,
  Button,
  Card,
  PageHeader,
  Select,
} from "@/components/ui";
import BrandSelector from "@/components/BrandSelector";
import DemoBadge from "@/components/DemoBadge";

function UploadIsi() {
  const [brandId, setBrandId] = useState<string | null>(null);
  const [platform, setPlatform] = useState<Platform>("tiktok");
  const [file, setFile] = useState<File | null>(null);
  const [kolom, setKolom] = useState<CsvColumnInfo[]>([]);
  const [demoKolom, setDemoKolom] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [hasil, setHasil] = useState<UploadResult | null>(null);
  const [demoHasil, setDemoHasil] = useState(false);
  const [error, setError] = useState("");
  const [scoring, setScoring] = useState(false);
  const [skor, setSkor] = useState<ScoreResult | null>(null);

  useEffect(() => {
    setBrandId(getSelectedBrandId());
  }, []);

  // Dokumentasi format kolom (dengan fallback tabel statis).
  useEffect(() => {
    let batal = false;
    apiOrDemo(
      () => api.get<{ columns: CsvColumnInfo[] }>("/content/csv-format"),
      { columns: demoCsvColumns }
    ).then(({ data, demo }) => {
      if (!batal) {
        setKolom(data.columns);
        setDemoKolom(demo);
      }
    });
    return () => {
      batal = true;
    };
  }, []);

  function contohUrl() {
    return `/contoh/${platform}_contoh.csv`;
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setHasil(null);
    setSkor(null);
    if (!brandId) {
      setError("Pilih brand terlebih dahulu.");
      return;
    }
    if (!file) {
      setError("Pilih file CSV terlebih dahulu.");
      return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("brand_id", brandId);
      form.append("platform", platform);
      form.append("file", file);
      const { data, demo } = await apiOrDemo<UploadResult>(
        () => api.postForm<UploadResult>("/content/upload", form),
        () => simulasiUploadDemo(file)
      );
      setHasil(data);
      setDemoHasil(demo);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal mengunggah file. Coba lagi."
      );
    } finally {
      setUploading(false);
    }
  }

  async function jalankanScoring() {
    if (!brandId) return;
    setScoring(true);
    setError("");
    try {
      const { data } = await apiOrDemo<ScoreResult>(
        () => api.post<ScoreResult>(`/content/brands/${brandId}/score`, { preset: "30d" }),
        { diskor: hasil?.contents_baru ?? 0, periode: "30 hari terakhir (demo)" }
      );
      setSkor(data);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal menjalankan scoring."
      );
    } finally {
      setScoring(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Upload Data"
        subtitle="Unggah metrik konten TikTok / Instagram dalam format CSV, lalu jalankan scoring."
        action={<DemoBadge tampil={demoHasil} />}
      />

      {/* 1. Dokumentasi format kolom */}
      <Card className="mb-6">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold text-slate-900">
            Format kolom CSV
          </h2>
          <a href={contohUrl()} download>
            <Button variant="secondary">
              Unduh contoh ({platform === "tiktok" ? "TikTok" : "Instagram"})
            </Button>
          </a>
        </div>
        {demoKolom && (
          <p className="mb-3 text-xs text-amber-700">
            Dokumentasi kolom memakai tabel statis karena backend belum
            tersedia (DEMO_FALLBACK).
          </p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <th className="py-2 pr-4">Kolom</th>
                <th className="py-2 pr-4">Deskripsi</th>
                <th className="py-2">Wajib</th>
              </tr>
            </thead>
            <tbody>
              {kolom.map((k) => (
                <tr key={k.nama} className="border-b border-slate-100 last:border-0">
                  <td className="py-2 pr-4 font-mono text-[13px] font-medium text-slate-900">
                    {k.nama}
                  </td>
                  <td className="py-2 pr-4 text-slate-600">{k.deskripsi}</td>
                  <td className="py-2">
                    {k.wajib ? (
                      <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
                        Ya
                      </span>
                    ) : (
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
                        Opsional
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* 2. Form upload */}
      <Card className="mb-6">
        <h2 className="mb-4 text-base font-semibold text-slate-900">
          Unggah file
        </h2>
        {error && (
          <div className="mb-4">
            <Alert kind="error">{error}</Alert>
          </div>
        )}
        <form onSubmit={handleUpload} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <BrandSelector value={brandId} onChange={setBrandId} />
            <Select
              label="Platform"
              value={platform}
              onChange={(e) => setPlatform(e.target.value as Platform)}
            >
              <option value="tiktok">TikTok</option>
              <option value="instagram">Instagram</option>
            </Select>
          </div>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-700">
              File CSV
            </span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="w-full rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3.5 py-3 text-sm text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-indigo-600 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-indigo-700"
            />
            {file && (
              <span className="mt-1 block text-xs text-slate-500">
                {file.name} · {(file.size / 1024).toFixed(1)} KB
              </span>
            )}
          </label>
          <Button type="submit" disabled={uploading}>
            {uploading ? "Mengunggah…" : "Upload"}
          </Button>
        </form>
      </Card>

      {/* 3. Hasil upload */}
      {hasil && (
        <Card>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-900">
              Hasil upload
            </h2>
            <DemoBadge tampil={demoHasil} />
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-xl bg-emerald-50 p-4">
              <p className="text-2xl font-bold text-emerald-700">
                {hasil.contents_baru}
              </p>
              <p className="text-xs text-emerald-700">Konten baru</p>
            </div>
            <div className="rounded-xl bg-sky-50 p-4">
              <p className="text-2xl font-bold text-sky-700">
                {hasil.contents_diupdate}
              </p>
              <p className="text-xs text-sky-700">Konten diupdate</p>
            </div>
            <div className="rounded-xl bg-indigo-50 p-4">
              <p className="text-2xl font-bold text-indigo-700">
                {hasil.metrics_rows}
              </p>
              <p className="text-xs text-indigo-700">Baris metrik</p>
            </div>
          </div>

          {hasil.baris_gagal.length > 0 && (
            <div className="mt-4">
              <h3 className="mb-2 text-sm font-semibold text-slate-900">
                Baris gagal ({hasil.baris_gagal.length})
              </h3>
              <ul className="space-y-1.5">
                {hasil.baris_gagal.map((b) => (
                  <li
                    key={b.baris}
                    className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800"
                  >
                    <strong>Baris {b.baris}:</strong> {b.alasan}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {hasil.warnings.length > 0 && (
            <div className="mt-4">
              <h3 className="mb-2 text-sm font-semibold text-slate-900">
                Peringatan
              </h3>
              <ul className="list-disc space-y-1 pl-5 text-sm text-amber-800">
                {hasil.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button onClick={jalankanScoring} disabled={scoring}>
              {scoring ? "Menghitung…" : "Jalankan Scoring"}
            </Button>
            {skor && (
              <Alert kind="success">
                Scoring selesai: <strong>{skor.diskor}</strong> konten diskor
                ({skor.periode}).
              </Alert>
            )}
          </div>
          {brandId && (
            <Link
              href={`/brand/${brandId}`}
              className="mt-4 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-800"
            >
              Lihat dasbor analitik →
            </Link>
          )}
        </Card>
      )}
    </div>
  );
}

/** Simulasi hasil upload untuk mode demo: hitung baris CSV di sisi klien. */
function simulasiUploadDemo(file: File): Promise<UploadResult> {
  return file.text().then((teks) => {
    const baris = teks.split(/\r?\n/).filter((b) => b.trim().length > 0);
    const data = Math.max(0, baris.length - 1);
    const gagal: { baris: number; alasan: string }[] = [];
    const header = (baris[0] ?? "").split(",");
    if (!header.includes("post_id")) {
      gagal.push({ baris: 1, alasan: "Kolom wajib 'post_id' tidak ditemukan di header (simulasi demo)." });
    }
    // Tandai satu baris contoh sebagai gagal agar tampilan terverifikasi.
    if (data >= 3) {
      gagal.push({ baris: 4, alasan: "Nilai 'views' bukan angka (simulasi demo)." });
    }
    return {
      contents_baru: Math.max(0, data - gagal.length),
      contents_diupdate: 0,
      metrics_rows: data,
      baris_gagal: gagal,
      warnings: DEMO_FALLBACK
        ? ["Mode demo: hasil ini disimulasikan di browser, bukan dari backend."]
        : [],
    };
  });
}

export default function UploadPage() {
  return (
    <RequireAuth>
      <UploadIsi />
    </RequireAuth>
  );
}
