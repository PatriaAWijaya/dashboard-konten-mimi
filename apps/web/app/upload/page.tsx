"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import {
  DEMO_FALLBACK,
  apiOrDemo,
  getSelectedBrandId,
} from "@/lib/content";
import type {
  BatchFileResult,
  BatchUploadResult,
  ScoreResult,
  UploadResult,
} from "@/lib/types";
import {
  Alert,
  Button,
  Card,
  PageHeader,
  Select,
  Spinner,
} from "@/components/ui";
import BrandSelector from "@/components/BrandSelector";
import DemoBadge from "@/components/DemoBadge";

type PlatformPilih = "tiktok" | "instagram" | "auto";
// Tujuan semua konten sosmed: account growth & engagement rate —
// tidak perlu dipilih manual, dikirim tetap ke backend.
const TUJUAN_DEFAULT = "account_growth";

function UploadIsi() {
  const router = useRouter();
  const [brandId, setBrandId] = useState<string | null>(null);
  const [platform, setPlatform] = useState<PlatformPilih>("auto");
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [hasil, setHasil] = useState<BatchUploadResult | null>(null);
  const [demoHasil, setDemoHasil] = useState(false);
  const [error, setError] = useState("");
  const [scoring, setScoring] = useState(false);
  const [skorKonten, setSkorKonten] = useState(0);
  const [fileTerbuka, setFileTerbuka] = useState<string | null>(null);

  useEffect(() => {
    setBrandId(getSelectedBrandId());
  }, []);

  function tambahFiles(daftar: FileList | null) {
    if (!daftar) return;
    const baru = Array.from(daftar).filter((f) =>
      f.name.toLowerCase().endsWith(".csv")
    );
    setFiles((lama) => [...lama, ...baru].slice(0, 10));
  }

  function hapusFile(index: number) {
    setFiles((lama) => lama.filter((_, i) => i !== index));
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setHasil(null);
    if (!brandId) {
      setError("Pilih brand terlebih dahulu.");
      return;
    }
    if (files.length === 0) {
      setError("Pilih minimal satu file CSV.");
      return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("brand_id", brandId);
      form.append("platform", platform);
      form.append("tujuan_default", TUJUAN_DEFAULT);
      for (const f of files) form.append("files", f);
      const { data, demo } = await apiOrDemo<BatchUploadResult>(
        () => api.postForm<BatchUploadResult>("/content/upload-batch", form),
        () => simulasiUploadBatchDemo(files)
      );
      setHasil(data);
      setDemoHasil(demo);
      const totalMasuk = data.total_baru + data.total_diupdate;
      if (!demo && totalMasuk > 0) {
        // Upload memicu scoring otomatis, lalu pindah ke tab Analitik.
        setScoring(true);
        setSkorKonten(totalMasuk);
        try {
          await api.post<ScoreResult>(`/content/brands/${brandId}/score`, {
            preset: "12bln",
          });
        } catch {
          // Scoring gagal bukan akhir dunia: user bisa hitung ulang
          // dari halaman analitik. Tetap lanjut ke sana.
        } finally {
          setScoring(false);
        }
        router.push(`/brand/${brandId}`);
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal mengunggah file. Coba lagi."
      );
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Upload Data"
        subtitle="Unggah file CSV metrik konten — scoring berjalan otomatis lalu Anda dibawa ke Analitik."
        action={<DemoBadge tampil={demoHasil} />}
      />

      {/* 1. Info format */}
      <Card className="mb-6">
        <h2 className="mb-1 text-base font-semibold text-slate-900">
          Format file
        </h2>
        <p className="text-sm leading-relaxed text-slate-600">
          File <strong>export langsung dari Meta</strong> (TikTok / Instagram)
          didukung apa adanya — kolom dipetakan otomatis dan platform
          dideteksi dari file. Tidak perlu mengubah atau menata ulang CSV
          Anda.
        </p>
      </Card>

      {/* 2. Form upload multi-file */}
      <Card className="mb-6">
        <h2 className="mb-1 text-base font-semibold text-slate-900">
          Unggah file
        </h2>
        <p className="mb-4 text-sm text-slate-500">
          Export data Meta dibatasi maksimal 3 bulan per file. Untuk analisa
          beberapa periode, unduh tiap periode (mis. per triwulan) lalu
          unggah semuanya sekaligus di sini — data akan digabung otomatis
          dan baris yang sama tidak diduplikasi.
        </p>
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
              onChange={(e) => setPlatform(e.target.value as PlatformPilih)}
            >
              <option value="auto">Otomatis (dari file)</option>
              <option value="tiktok">TikTok</option>
              <option value="instagram">Instagram</option>
            </Select>
          </div>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-700">
              File CSV (bisa pilih lebih dari satu, maks 10)
            </span>
            <input
              type="file"
              accept=".csv,text/csv"
              multiple
              onChange={(e) => {
                tambahFiles(e.target.files);
                e.target.value = "";
              }}
              className="w-full rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3.5 py-3 text-sm text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-orange-600 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-orange-700"
            />
          </label>
          {files.length > 0 && (
            <ul className="space-y-1.5">
              {files.map((f, i) => (
                <li
                  key={`${f.name}-${i}`}
                  className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm"
                >
                  <span className="truncate text-slate-700">
                    <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded bg-orange-100 text-[11px] font-bold text-orange-700">
                      {i + 1}
                    </span>
                    {f.name}
                    <span className="ml-2 text-xs text-slate-400">
                      {(f.size / 1024).toFixed(1)} KB
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => hapusFile(i)}
                    className="shrink-0 rounded-lg px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
                  >
                    Hapus
                  </button>
                </li>
              ))}
            </ul>
          )}
          <Button type="submit" disabled={uploading || scoring || files.length === 0}>
            {uploading
              ? `Mengunggah ${files.length} file…`
              : scoring
                ? "Menjalankan scoring otomatis…"
                : `Upload${files.length > 0 ? ` ${files.length} file` : ""}`}
          </Button>
          {uploading && (
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Spinner
                label={`Mengunggah ${files.length} file ke server — mohon tunggu, jangan tutup halaman ini…`}
              />
            </div>
          )}
          {scoring && (
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Spinner
                label={`Menjalankan scoring otomatis untuk ${skorKonten} konten — sebentar lagi pindah ke Analitik…`}
              />
            </div>
          )}
        </form>
      </Card>

      {/* 3. Hasil upload */}
      {hasil && (
        <Card>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-900">
              Hasil upload ({hasil.files.length} file)
            </h2>
            <DemoBadge tampil={demoHasil} />
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-xl bg-emerald-50 p-4">
              <p className="text-2xl font-bold text-emerald-700">
                {hasil.total_baru}
              </p>
              <p className="text-xs text-emerald-700">Konten baru</p>
            </div>
            <div className="rounded-xl bg-sky-50 p-4">
              <p className="text-2xl font-bold text-sky-700">
                {hasil.total_diupdate}
              </p>
              <p className="text-xs text-sky-700">Konten diupdate</p>
            </div>
            <div className="rounded-xl bg-orange-50 p-4">
              <p className="text-2xl font-bold text-orange-700">
                {hasil.total_metrics_rows}
              </p>
              <p className="text-xs text-orange-700">Baris metrik</p>
            </div>
          </div>

          {/* Rincian per file */}
          <div className="mt-4 space-y-2">
            {hasil.files.map((f) => (
              <div key={f.filename} className="rounded-xl border border-slate-200">
                <button
                  type="button"
                  onClick={() =>
                    setFileTerbuka(fileTerbuka === f.filename ? null : f.filename)
                  }
                  className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
                >
                  <span className="flex min-w-0 items-center gap-2 text-sm">
                    <span
                      className={`inline-flex h-2.5 w-2.5 shrink-0 rounded-full ${
                        f.sukses ? "bg-emerald-500" : "bg-red-500"
                      }`}
                    />
                    <span className="truncate font-medium text-slate-800">
                      {f.filename}
                    </span>
                  </span>
                  <span className="shrink-0 text-xs text-slate-500">
                    {f.sukses
                      ? `+${f.contents_baru} baru · ${f.contents_diupdate} update · ${f.metrics_rows} baris`
                      : `Gagal: ${f.error}`}
                    {f.baris_gagal.length > 0 &&
                      ` · ${f.baris_gagal.length} baris gagal`}
                  </span>
                </button>
                {fileTerbuka === f.filename && (
                  <div className="border-t border-slate-100 px-4 py-3">
                    {f.baris_gagal.length > 0 && (
                      <div className="mb-3">
                        <h4 className="mb-1.5 text-xs font-semibold uppercase text-slate-500">
                          Baris gagal ({f.baris_gagal.length})
                        </h4>
                        <ul className="max-h-40 space-y-1 overflow-y-auto">
                          {f.baris_gagal.map((b) => (
                            <li
                              key={b.baris}
                              className="rounded-lg bg-red-50 px-3 py-1.5 text-sm text-red-800"
                            >
                              <strong>Baris {b.baris}:</strong> {b.alasan}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {f.warnings.length > 0 && (
                      <ul className="list-disc space-y-1 pl-5 text-sm text-amber-800">
                        {f.warnings.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    )}
                    {f.sukses && f.baris_gagal.length === 0 && f.warnings.length === 0 && (
                      <p className="text-sm text-slate-500">
                        Semua baris berhasil diproses.
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {brandId && (
            <div className="mt-4">
              <Link
                href={`/brand/${brandId}`}
                className="text-sm font-medium text-orange-600 hover:text-orange-800"
              >
                Lihat dasbor analitik →
              </Link>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

/** Simulasi hasil upload batch untuk mode demo: hitung baris CSV di sisi klien. */
async function simulasiUploadBatchDemo(files: File[]): Promise<BatchUploadResult> {
  const hasilFiles: BatchFileResult[] = [];
  let total_baru = 0;
  let total_diupdate = 0;
  let total_metrics_rows = 0;
  let total_baris_gagal = 0;
  for (const file of files) {
    const r: UploadResult = await simulasiUploadDemo(file);
    total_baru += r.contents_baru;
    total_diupdate += r.contents_diupdate;
    total_metrics_rows += r.metrics_rows;
    total_baris_gagal += r.baris_gagal.length;
    hasilFiles.push({
      filename: file.name,
      sukses: true,
      error: null,
      contents_baru: r.contents_baru,
      contents_diupdate: r.contents_diupdate,
      metrics_rows: r.metrics_rows,
      baris_gagal: r.baris_gagal,
      warnings: r.warnings,
    });
  }
  return {
    files: hasilFiles,
    total_baru,
    total_diupdate,
    total_metrics_rows,
    total_baris_gagal,
  };
}

/** Simulasi hasil upload satu file untuk mode demo: hitung baris CSV di sisi klien. */
function simulasiUploadDemo(file: File): Promise<UploadResult> {
  return file.text().then((teks) => {
    const baris = teks.split(/\r?\n/).filter((b) => b.trim().length > 0);
    const data = Math.max(0, baris.length - 1);
    const gagal: { baris: number; alasan: string }[] = [];
    const header = (baris[0] ?? "").split(",");
    if (!header.includes("post_id") && !header.includes("Post ID")) {
      gagal.push({ baris: 1, alasan: "Kolom 'post_id'/'Post ID' tidak ditemukan di header (simulasi demo)." });
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
