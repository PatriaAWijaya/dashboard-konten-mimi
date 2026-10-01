"use client";

import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useBrandId } from "@/lib/brand";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { apiOrDemo, demoRekomendasi } from "@/lib/content";
import type {
  GenerateRekomendasiResult,
  Rekomendasi,
  StatusRekomendasi,
  TipeRekomendasi,
} from "@/lib/types";
import { Alert, Button, Card, EmptyBox, PageHeader, Spinner } from "@/components/ui";
import BrandNav from "@/components/BrandNav";
import DemoBadge from "@/components/DemoBadge";
import ExportPdfButton from "@/components/ExportPdfButton";
import PeriodPicker, { type PilihanPeriode } from "@/components/PeriodPicker";

const TIPE_META: Record<TipeRekomendasi, { label: string; tone: string; ikon: string }> = {
  umum: { label: "Umum", tone: "bg-orange-50 border-orange-200", ikon: "🏠" },
  khusus: { label: "Khusus", tone: "bg-violet-50 border-violet-200", ikon: "🎯" },
  perbanyak: { label: "Perbanyak", tone: "bg-emerald-50 border-emerald-200", ikon: "📈" },
  perbaiki: { label: "Perbaiki", tone: "bg-amber-50 border-amber-200", ikon: "🔧" },
  kurangi: { label: "Kurangi", tone: "bg-red-50 border-red-200", ikon: "📉" },
  coba_baru: { label: "Coba Baru", tone: "bg-sky-50 border-sky-200", ikon: "✨" },
};

/** Format evidence (dict dari backend) menjadi kalimat yang mudah dibaca. */
function formatEvidence(ev: Record<string, unknown> | string): string {
  if (typeof ev === "string") return ev;
  if (!ev || typeof ev !== "object") return "-";
  const bagian: string[] = [];
  const n = ev["n"];
  const menang = ev["menang"];
  if (typeof n === "number") {
    bagian.push(
      typeof menang === "number"
        ? `${menang} dari ${n} konten berkinerja baik`
        : `${n} konten`
    );
  }
  const skor = ev["avg_score"];
  if (typeof skor === "number") bagian.push(`nilai rata-rata ${skor.toLocaleString("id-ID", { maximumFractionDigits: 1 })}`);
  const fmt = ev["format"];
  if (typeof fmt === "string" && fmt) {
    const namaFmt = fmt.toLowerCase() === "foto" ? "Image" : fmt.charAt(0).toUpperCase() + fmt.slice(1);
    bagian.push(`jenis ${namaFmt}`);
  }
  const tjn = ev["tujuan"];
  if (typeof tjn === "string" && tjn) {
    const labelTujuan: Record<string, string> = {
      edukasi: "edukasi",
      hiburan: "hiburan",
      interaksi: "interaksi",
      jualan: "jualan",
      branding: "branding",
      account_growth: "menambah followers",
    };
    bagian.push(`untuk ${labelTujuan[tjn] || tjn}`);
  }
  // Strategi khusus (502, 90 komentar): tampilkan komposisinya.
  const komposisi = ev["komposisi"];
  if (typeof komposisi === "string" && komposisi) bagian.push(komposisi);
  return bagian.length > 0 ? bagian.join(" · ") : "-";
}

/** Ubah ID konten di teks narasi menjadi link ke konten asli (buka tab baru). */
function linkifyKonten(
  teks: string,
  urlMap: Map<string, string | null>
): ReactNode[] {
  // Cocokkan ID numerik panjang (post_id Instagram) atau pola c-001.
  const pola = /\b(\d{8,}|c-\d{3})\b/g;
  const hasil: React.ReactNode[] = [];
  let terakhir = 0;
  let m: RegExpExecArray | null;
  let kunci = 0;
  while ((m = pola.exec(teks)) !== null) {
    if (m.index > terakhir) hasil.push(teks.slice(terakhir, m.index));
    const pid = m[1];
    const url = urlMap.get(pid);
    if (url) {
      hasil.push(
        <a
          key={kunci++}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-orange-600 underline hover:text-orange-700"
        >
          {pid}
        </a>
      );
    } else {
      hasil.push(pid);
    }
    terakhir = m.index + m[0].length;
  }
  if (terakhir < teks.length) hasil.push(teks.slice(terakhir));
  return hasil;
}

function KartuRekomendasi({
  item,
  brandId,
  onUbahStatus,
  sibuk,
}: {
  item: Rekomendasi;
  brandId: string;
  onUbahStatus: (id: string, aksi: "terima" | "tolak") => void;
  sibuk: boolean;
}) {
  const meta = TIPE_META[item.type] ?? TIPE_META.coba_baru;
  const ditolak = item.status === "ditolak";
  const diterima = item.status === "diterima";
  const bisaRencana =
    (item.type === "perbanyak" || item.type === "coba_baru") && !ditolak;

  const tautanRencana = `/brand/${brandId}/planner?dari_rekomendasi=${encodeURIComponent(
    item.id
  )}&judul=${encodeURIComponent(item.title)}&format=${encodeURIComponent(
    ""
  )}&tujuan=${encodeURIComponent("")}`;

  const urlMap = useMemo(
    () =>
      new Map(
        (item.reference_contents ?? []).map((r) => [r.post_id, r.post_url] as const)
      ),
    [item.reference_contents]
  );
  const acuan = item.reference_contents ?? [];

  return (
    <Card
      className={`border ${meta.tone} ${ditolak ? "opacity-60" : ""}`}
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <span className="text-lg" aria-hidden>
          {meta.ikon}
        </span>
        {ditolak && (
          <span className="rounded-full bg-slate-200 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
            Ditolak
          </span>
        )}
        {diterima && (
          <span className="rounded-full bg-emerald-200 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
            Diterima
          </span>
        )}
      </div>
      <h3 className="text-base font-semibold text-slate-900">{item.title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-700">{linkifyKonten(item.narrative, urlMap)}</p>

      <div className="mt-3 rounded-xl bg-white/70 p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Bukti angka
        </p>
        <p className="mt-1 text-sm text-slate-700">{formatEvidence(item.evidence)}</p>
      </div>

      {acuan.length > 0 && (
        <p className="mt-3 text-sm text-slate-600">
          <span className="font-medium text-slate-800">Contoh konten acuan:</span>{" "}
          {acuan.map((r) =>
            r.post_url ? (
              <a
                key={r.post_id}
                href={r.post_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mr-1.5 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-orange-700 underline hover:bg-orange-100"
              >
                {r.post_id} ↗
              </a>
            ) : (
              <code key={r.post_id} className="mr-1.5 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700">
                {r.post_id}
              </code>
            )
          )}
        </p>
      )}

      {!ditolak && !diterima && (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="secondary" disabled={sibuk} onClick={() => onUbahStatus(item.id, "terima")}>
            Terima
          </Button>
          <Button variant="ghost" disabled={sibuk} onClick={() => onUbahStatus(item.id, "tolak")}>
            Tolak
          </Button>
          {bisaRencana && (
            <Link href={tautanRencana}>
              <Button variant="ghost" disabled={sibuk}>
                📅 Buat rencana
              </Button>
            </Link>
          )}
        </div>
      )}
      {(ditolak || diterima) && bisaRencana && (
        <div className="mt-4">
          <Link href={tautanRencana}>
            <Button variant="secondary" className="w-full">
              📅 Buat rencana dari rekomendasi ini
            </Button>
          </Link>
        </div>
      )}
    </Card>
  );
}

function RekomendasiIsi() {
  const brandId = useBrandId();
  const [periode, setPeriode] = useState<PilihanPeriode>({ preset: "30d" });
  const [items, setItems] = useState<Rekomendasi[]>([]);
  const [demo, setDemo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [sibukId, setSibukId] = useState<string | null>(null);
  const [dataSedikit, setDataSedikit] = useState(false);

  const muat = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const { data, demo: isDemo } = await apiOrDemo(
        () => api.get<Rekomendasi[]>(`/content/brands/${brandId}/recommendations`),
        demoRekomendasi.map((r) => ({ ...r, status: "baru" as StatusRekomendasi }))
      );
      setItems(data);
      setDemo(isDemo);
      // Bila backend nyata menjawab dengan <10 rekomendasi/data, sampaikan apa adanya.
      if (!isDemo && data.length > 0 && data.length < 10) setDataSedikit(true);
      else if (isDemo) setDataSedikit(data.length < 10);
      else setDataSedikit(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal memuat rekomendasi.");
    } finally {
      setLoading(false);
    }
  }, [brandId]);

  useEffect(() => {
    muat();
  }, [muat]);

  async function buatRekomendasi() {
    setGenerating(true);
    setError("");
    try {
      const body: Record<string, string> = { preset: periode.preset };
      if (periode.start) body.start = periode.start;
      if (periode.end) body.end = periode.end;
      const { data, demo: isDemo } = await apiOrDemo<GenerateRekomendasiResult>(
        () => api.post<GenerateRekomendasiResult>(`/content/brands/${brandId}/recommendations/generate`, body),
        { dibuat: demoRekomendasi.map((r) => ({ ...r, status: "baru" as StatusRekomendasi })), pesan: "Mode demo: rekomendasi disimulasikan." }
      );
      setItems((lama) => [...data.dibuat, ...lama]);
      setDemo((d) => d || isDemo);
      if (data.pesan) setError(""); // pesan info, bukan error
      if (data.dibuat.length === 0) {
        setDataSedikit(true);
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal membuat rekomendasi."
      );
    } finally {
      setGenerating(false);
    }
  }

  async function ubahStatus(id: string, aksi: "terima" | "tolak") {
    setSibukId(id);
    const statusBaru: StatusRekomendasi = aksi === "terima" ? "diterima" : "ditolak";
    try {
      await apiOrDemo(
        () => api.post<{ status: string }>(`/content/recommendations/${id}/${aksi}`, {}),
        { status: statusBaru }
      );
      setItems((lama) => lama.map((r) => (r.id === id ? { ...r, status: statusBaru } : r)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal memperbarui status.");
    } finally {
      setSibukId(null);
    }
  }

  const rekomendasiUmum = useMemo(
    () => items.filter((r) => r.type === "umum"),
    [items]
  );
  const rekomendasiKhusus = useMemo(
    () => items.filter((r) => r.type === "khusus"),
    [items]
  );
  const kelompokLain = useMemo(() => {
    const urutan: TipeRekomendasi[] = ["perbanyak", "perbaiki", "kurangi", "coba_baru"];
    return urutan
      .map((t) => ({ tipe: t, items: items.filter((r) => r.type === t) }))
      .filter((g) => g.items.length > 0);
  }, [items]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Rekomendasi AI"
        subtitle="Saran berbasis pola performa konten Anda."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <DemoBadge tampil={demo} />
            <ExportPdfButton />
          </div>
        }
      />
      <BrandNav brandId={brandId} />

      <Card className="mb-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">
              Periode analisis
            </p>
            <PeriodPicker value={periode} onChange={setPeriode} />
          </div>
          <Button onClick={buatRekomendasi} disabled={generating}>
            {generating ? "Membuat…" : "Buat Rekomendasi"}
          </Button>
        </div>
      </Card>

      {loading && <Spinner label="Memuat rekomendasi…" />}
      {error && (
        <div className="mb-4">
          <Alert kind="error">{error}</Alert>
        </div>
      )}

      {!loading && !error && dataSedikit && items.length === 0 && (
        <EmptyBox
          title="Data belum cukup"
          description="Rekomendasi membutuhkan minimal 10 konten yang sudah diskor pada periode ini. Upload lebih banyak data CSV lalu jalankan scoring, atau pilih periode yang lebih panjang."
          icon={
            <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 0 0 1.5-.189m-1.5.189a6.01 6.01 0 0 1-1.5-.189m3.75 7.478a12.06 12.06 0 0 1-4.5 0m3.75 2.383a14.406 14.406 0 0 1-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 1 0-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
            </svg>
          }
        />
      )}

      {!loading && !error && dataSedikit && items.length > 0 && (
        <div className="mb-4">
          <Alert kind="warning">
            Data pada periode ini kurang dari 10 konten — rekomendasi di bawah
            bersifat awal dan bisa berubah saat data bertambah.
          </Alert>
        </div>
      )}

      {!loading && !error && rekomendasiUmum.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-1 flex items-center gap-2 text-lg font-semibold text-slate-900">
            <span aria-hidden>🏠</span>
            Rekomendasi Umum
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
              {rekomendasiUmum.length}
            </span>
          </h2>
          <p className="mb-3 text-sm text-slate-500">
            Kondisi akun secara keseluruhan.
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            {rekomendasiUmum.map((r) => (
              <KartuRekomendasi
                key={r.id}
                item={r}
                brandId={brandId}
                sibuk={sibukId === r.id}
                onUbahStatus={ubahStatus}
              />
            ))}
          </div>
        </section>
      )}

      {!loading && !error && rekomendasiKhusus.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-1 flex items-center gap-2 text-lg font-semibold text-slate-900">
            <span aria-hidden>🎯</span>
            Rekomendasi Khusus
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
              {rekomendasiKhusus.length}
            </span>
          </h2>
          <p className="mb-3 text-sm text-slate-500">
            Per jenis post beserta metrik dominan masing-masing.
          </p>
          <div className="grid gap-4 md:grid-cols-2">
            {rekomendasiKhusus.map((r) => (
              <KartuRekomendasi
                key={r.id}
                item={r}
                brandId={brandId}
                sibuk={sibukId === r.id}
                onUbahStatus={ubahStatus}
              />
            ))}
          </div>
        </section>
      )}

      {!loading &&
        !error &&
        kelompokLain.map((g) => (
          <section key={g.tipe} className="mb-8">
            <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-slate-900">
              <span aria-hidden>{TIPE_META[g.tipe].ikon}</span>
              {TIPE_META[g.tipe].label}
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                {g.items.length}
              </span>
            </h2>
            <div className="grid gap-4 md:grid-cols-2">
              {g.items.map((r) => (
                <KartuRekomendasi
                  key={r.id}
                  item={r}
                  brandId={brandId}
                  sibuk={sibukId === r.id}
                  onUbahStatus={ubahStatus}
                />
              ))}
            </div>
          </section>
        ))}
    </div>
  );
}

export default function RekomendasiPage() {
  return (
    <RequireAuth>
      <RekomendasiIsi />
    </RequireAuth>
  );
}
