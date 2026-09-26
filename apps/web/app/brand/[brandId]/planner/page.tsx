"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { RequireAuth } from "@/lib/auth";
import { api, apiDownload, ApiError } from "@/lib/api";
import { formatTanggal } from "@/lib/format";
import {
  Alert,
  Button,
  Card,
  EmptyBox,
  Input,
  PageHeader,
  Select,
  Spinner,
  TextArea,
} from "@/components/ui";
import BrandNav from "@/components/BrandNav";

type StatusRencana = "ide" | "terjadwal" | "terbit" | "dibatalkan";

interface Rencana {
  id: string;
  judul: string;
  format: string;
  tujuan: string;
  tanggal_rencana: string;
  status: StatusRencana;
  catatan: string | null;
  rekomendasi_sumber_id: string | null;
}

const STATUS_META: Record<StatusRencana, { label: string; tone: string }> = {
  ide: { label: "Ide", tone: "bg-slate-100 text-slate-700" },
  terjadwal: { label: "Terjadwal", tone: "bg-sky-100 text-sky-800" },
  terbit: { label: "Terbit", tone: "bg-emerald-100 text-emerald-800" },
  dibatalkan: { label: "Dibatalkan", tone: "bg-red-100 text-red-800" },
};

const PILIHAN_FORMAT = ["video", "carousel", "foto", "story", "live"];
const PILIHAN_TUJUAN = ["edukasi", "hiburan", "jualan", "branding", "engagement"];
const SEMUA_STATUS = Object.keys(STATUS_META) as StatusRencana[];

function bulanKey(d: Date): string {
  const m = d.getMonth() + 1;
  return `${d.getFullYear()}-${String(m).padStart(2, "0")}`;
}

function tambahBulan(kunci: string, geser: number): string {
  const [t, b] = kunci.split("-").map(Number);
  const d = new Date(t, b - 1 + geser, 1);
  return bulanKey(d);
}

function labelBulan(kunci: string): string {
  const [t, b] = kunci.split("-").map(Number);
  return new Date(t, b - 1, 1).toLocaleDateString("id-ID", {
    month: "long",
    year: "numeric",
  });
}

function isoTanggal(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate()
  ).padStart(2, "0")}`;
}

// Kisi 6x7 dimulai hari Senin, berisi tanggal ISO.
function kisiKalender(kunci: string): string[] {
  const [t, b] = kunci.split("-").map(Number);
  const awal = new Date(t, b - 1, 1);
  const offset = (awal.getDay() + 6) % 7; // 0 = Senin
  const mulai = new Date(t, b - 1, 1 - offset);
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(mulai);
    d.setDate(mulai.getDate() + i);
    return isoTanggal(d);
  });
}

const NAMA_HARI = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"];

// ---------- Tipe kontrak backend (alokator, ringkasan, realisasi, ekspor) ----------
interface RingkasanTarget {
  total_rencana: number;
  estimasi_views_min: number | null;
  estimasi_views_max: number | null;
  target_er: number | null;
  label: string | null;
  catatan: string | null;
}

interface KonfigurasiPlanner {
  kapasitas_mingguan: number;
  target_distribusi: unknown;
  porsi_eksperimen: number | null;
}

interface SlotUsulan {
  tanggal: string;
  platform: string;
  format: string;
  topik: string;
  hook: string;
  konten_acuan_ids?: string[];
  target_er: number | null;
  target_views_min: number | null;
  target_views_max: number | null;
  sumber_rekomendasi_id: string | null;
}

interface Realisasi {
  sesuai_rencana: { jumlah: number; rata_wer: number | null };
  di_luar_rencana: { jumlah: number; rata_wer: number | null };
  rasio: number | null;
  narasi: string | null;
}

function fmtPersenRasio(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  return (
    (n * 100).toLocaleString("id-ID", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }) + "%"
  );
}

function fmtRentangViews(
  min: number | null | undefined,
  maks: number | null | undefined
): string {
  if (min === null || min === undefined || maks === null || maks === undefined)
    return "-";
  return `${min.toLocaleString("id-ID")} – ${maks.toLocaleString("id-ID")}`;
}

// Senin (YYYY-MM-DD) dari sebuah tanggal ISO.
function seninDari(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  const geser = (d.getDay() + 6) % 7; // 0 = Senin
  d.setDate(d.getDate() - geser);
  return isoTanggal(d);
}

function seninDepan(): string {
  const d = new Date();
  const geser = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - geser + 7);
  return isoTanggal(d);
}

// ---------- Kartu "Target & estimasi" ----------
function KartuTargetEstimasi({
  brandId,
  bulan,
}: {
  brandId: string;
  bulan: string;
}) {
  const [data, setData] = useState<RingkasanTarget | null>(null);
  const [tidakTersedia, setTidakTersedia] = useState(false);

  useEffect(() => {
    let batal = false;
    setData(null);
    setTidakTersedia(false);
    api
      .get<RingkasanTarget>(
        `/content/brands/${brandId}/planner/ringkasan?bulan=${bulan}`
      )
      .then((d) => {
        if (!batal) setData(d);
      })
      .catch(() => {
        // Endpoint belum tersedia di server → sembunyikan kartu.
        if (!batal) setTidakTersedia(true);
      });
    return () => {
      batal = true;
    };
  }, [brandId, bulan]);

  if (tidakTersedia) return null;

  return (
    <Card>
      <h2 className="text-base font-semibold text-slate-900">
        Target & estimasi
      </h2>
      {!data && <Spinner label="Memuat ringkasan…" />}
      {data && (
        <dl className="mt-4 space-y-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <dt className="text-slate-500">Total rencana</dt>
            <dd className="text-lg font-bold text-slate-900">
              {data.total_rencana}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-slate-500">
              Estimasi views
              <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                Estimasi
              </span>
            </dt>
            <dd className="font-semibold tabular-nums text-slate-900">
              {fmtRentangViews(data.estimasi_views_min, data.estimasi_views_max)}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-slate-500">Target ER</dt>
            <dd className="font-semibold tabular-nums text-indigo-700">
              {fmtPersenRasio(data.target_er)}
            </dd>
          </div>
          {data.label && (
            <div className="flex items-center justify-between gap-3">
              <dt className="text-slate-500">Label</dt>
              <dd className="font-medium text-slate-700">{data.label}</dd>
            </div>
          )}
          {data.catatan && (
            <p className="rounded-xl bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-600">
              {data.catatan}
            </p>
          )}
        </dl>
      )}
    </Card>
  );
}

// ---------- Kartu "Realisasi vs rencana" ----------
function RealisasiVsRencana({
  brandId,
  bulan,
}: {
  brandId: string;
  bulan: string;
}) {
  const [data, setData] = useState<Realisasi | null>(null);
  const [gagal, setGagal] = useState(false);

  useEffect(() => {
    let batal = false;
    setData(null);
    setGagal(false);
    api
      .get<Realisasi>(
        `/content/brands/${brandId}/planner/realisasi?bulan=${bulan}`
      )
      .then((d) => {
        if (!batal) setData(d);
      })
      .catch(() => {
        if (!batal) setGagal(true);
      });
    return () => {
      batal = true;
    };
  }, [brandId, bulan]);

  if (gagal) return null;

  return (
    <Card>
      <h2 className="text-base font-semibold text-slate-900">
        Realisasi vs rencana
      </h2>
      {!data && <Spinner label="Memuat realisasi…" />}
      {data && data.narasi && (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 text-center">
            <div className="rounded-xl bg-emerald-50 px-3 py-3">
              <p className="text-xl font-bold text-emerald-700">
                {data.sesuai_rencana.jumlah}
              </p>
              <p className="text-xs text-emerald-800">
                Sesuai rencana
                <br />
                (rata WER {fmtPersenRasio(data.sesuai_rencana.rata_wer)})
              </p>
            </div>
            <div className="rounded-xl bg-slate-100 px-3 py-3">
              <p className="text-xl font-bold text-slate-700">
                {data.di_luar_rencana.jumlah}
              </p>
              <p className="text-xs text-slate-600">
                Di luar rencana
                <br />
                (rata WER {fmtPersenRasio(data.di_luar_rencana.rata_wer)})
              </p>
            </div>
          </div>
          {data.rasio !== null && data.rasio !== undefined && (
            <p className="mt-3 text-center text-sm font-semibold text-slate-800">
              Rasio kepatuhan: {fmtPersenRasio(data.rasio)}
            </p>
          )}
          <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-700">
            {data.narasi}
          </p>
        </>
      )}
      {data && !data.narasi && (
        <Alert kind="info">
          Data realisasi belum cukup — tandai rencana yang sudah terbit dan
          sync data konten agar perbandingan bisa dihitung.
        </Alert>
      )}
    </Card>
  );
}

// ---------- Bagian "Alokator" ----------
function Alokator({
  brandId,
  onRencanaBaru,
}: {
  brandId: string;
  onRencanaBaru: () => void;
}) {
  const [kapasitas, setKapasitas] = useState(4);
  const [porsiEksperimen, setPorsiEksperimen] = useState(20);
  const [distribusi, setDistribusi] = useState<string | null>(null);
  const [konfigTersedia, setKonfigTersedia] = useState(true);
  const [menyimpan, setMenyimpan] = useState(false);
  const [minggu, setMinggu] = useState(() => seninDepan());
  const [slots, setSlots] = useState<SlotUsulan[]>([]);
  const [info, setInfo] = useState("");
  const [membuat, setMembuat] = useState(false);
  const [menerima, setMenerima] = useState(false);
  const [error, setError] = useState("");
  const [sukses, setSukses] = useState("");

  useEffect(() => {
    let batal = false;
    api
      .get<KonfigurasiPlanner>(`/content/brands/${brandId}/planner/konfigurasi`)
      .then((k) => {
        if (batal) return;
        if (typeof k.kapasitas_mingguan === "number")
          setKapasitas(k.kapasitas_mingguan);
        if (typeof k.porsi_eksperimen === "number")
          setPorsiEksperimen(k.porsi_eksperimen * 100);
        if (k.target_distribusi !== null && k.target_distribusi !== undefined) {
          setDistribusi(
            typeof k.target_distribusi === "string"
              ? k.target_distribusi
              : JSON.stringify(k.target_distribusi)
          );
        }
        setKonfigTersedia(true);
      })
      .catch(() => {
        if (!batal) setKonfigTersedia(false);
      });
    return () => {
      batal = true;
    };
  }, [brandId]);

  async function simpanKonfigurasi() {
    setMenyimpan(true);
    setError("");
    setSukses("");
    try {
      const k = await api.put<KonfigurasiPlanner>(
        `/content/brands/${brandId}/planner/konfigurasi`,
        {
          kapasitas_mingguan: kapasitas,
          porsi_eksperimen: porsiEksperimen / 100,
        }
      );
      if (typeof k.kapasitas_mingguan === "number")
        setKapasitas(k.kapasitas_mingguan);
      if (typeof k.porsi_eksperimen === "number")
        setPorsiEksperimen(k.porsi_eksperimen * 100);
      setSukses("Konfigurasi alokator disimpan.");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Gagal menyimpan konfigurasi."
      );
    } finally {
      setMenyimpan(false);
    }
  }

  async function buatUsulan() {
    setMembuat(true);
    setError("");
    setSukses("");
    setSlots([]);
    setInfo("");
    try {
      const r = await api.post<{
        slots: SlotUsulan[];
        info?: string;
      }>(`/content/brands/${brandId}/planner/alokasi/generate`, {
        minggu: seninDari(minggu || seninDepan()),
      });
      const daftar = r.slots ?? [];
      setSlots(daftar);
      setInfo(r.info ?? "");
      if (daftar.length === 0) {
        setSukses(
          "Tidak ada usulan untuk minggu ini — coba ubah kapasitas atau pilih minggu lain."
        );
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal membuat usulan."
      );
    } finally {
      setMembuat(false);
    }
  }

  async function terimaSemua() {
    setMenerima(true);
    setError("");
    setSukses("");
    try {
      const r = await api.post<{ dibuat: number }>(
        `/content/brands/${brandId}/planner/alokasi/terima`,
        { slots }
      );
      setSukses(`${r.dibuat} usulan diterima dan menjadi rencana.`);
      setSlots([]);
      setInfo("");
      onRencanaBaru();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal menerima usulan."
      );
    } finally {
      setMenerima(false);
    }
  }

  return (
    <Card>
      <h2 className="text-base font-semibold text-slate-900">Alokator</h2>
      <p className="mt-1 text-sm text-slate-500">
        Buat usulan jadwal konten mingguan otomatis dari rekomendasi AI dan
        pola konten menang Anda.
      </p>

      {error && (
        <div className="mt-3">
          <Alert kind="error">{error}</Alert>
        </div>
      )}
      {sukses && (
        <div className="mt-3">
          <Alert kind="success">{sukses}</Alert>
        </div>
      )}

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Input
          label="Kapasitas / minggu"
          type="number"
          min={1}
          max={30}
          value={kapasitas}
          onChange={(e) => setKapasitas(Number(e.target.value))}
        />
        <Input
          label="Porsi eksperimen (%)"
          type="number"
          min={0}
          max={100}
          value={porsiEksperimen}
          onChange={(e) => setPorsiEksperimen(Number(e.target.value))}
        />
        <div className="flex items-end">
          <Button
            variant="secondary"
            onClick={simpanKonfigurasi}
            disabled={menyimpan || !konfigTersedia}
            className="w-full"
          >
            {menyimpan ? "Menyimpan…" : "Simpan konfigurasi"}
          </Button>
        </div>
      </div>
      {!konfigTersedia && (
        <p className="mt-2 text-xs text-slate-400">
          Konfigurasi tersimpan di server belum tersedia — nilai di atas hanya
          dipakai sesi ini.
        </p>
      )}
      {distribusi && (
        <p className="mt-2 text-xs text-slate-400">
          Target distribusi saat ini: {distribusi}
        </p>
      )}

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
        <Input
          label="Pilih minggu (dimulai Senin)"
          type="date"
          value={minggu}
          onChange={(e) => setMinggu(e.target.value)}
        />
        <Button onClick={buatUsulan} disabled={membuat} className="sm:mb-0">
          {membuat ? "Membuat…" : "Buat usulan"}
        </Button>
      </div>

      {info && (
        <p className="mt-3 rounded-xl bg-sky-50 px-3 py-2 text-xs leading-relaxed text-sky-800">
          {info}
        </p>
      )}

      {slots.length > 0 && (
        <div className="mt-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">
              Usulan slot ({slots.length})
            </h3>
            <Button onClick={terimaSemua} disabled={menerima}>
              {menerima ? "Menyimpan…" : "Terima semua"}
            </Button>
          </div>
          <div className="space-y-2">
            {slots.map((s, i) => (
              <div
                key={`${s.tanggal}-${i}`}
                className="rounded-xl border border-slate-200 px-4 py-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-slate-900">
                    {formatTanggal(s.tanggal)}
                  </span>
                  <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-semibold capitalize text-indigo-700">
                    {s.platform}
                  </span>
                  {s.format && (
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium capitalize text-slate-600">
                      {s.format}
                    </span>
                  )}
                  {s.sumber_rekomendasi_id && (
                    <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                      dari rekomendasi AI
                    </span>
                  )}
                </div>
                <p className="mt-1.5 text-sm font-medium text-slate-800">
                  {s.topik}
                </p>
                {s.hook && (
                  <p className="mt-0.5 text-sm text-slate-600">
                    <span className="font-medium">Hook:</span> {s.hook}
                  </p>
                )}
                <p className="mt-1 text-xs text-slate-500">
                  Target ER {fmtPersenRasio(s.target_er)} · estimasi views{" "}
                  {fmtRentangViews(s.target_views_min, s.target_views_max)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function PlannerIsi() {
  const params = useParams();
  const brandId = params.brandId as string;
  const searchParams = useSearchParams();

  const [bulan, setBulan] = useState(() => bulanKey(new Date()));
  const [items, setItems] = useState<Rencana[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sukses, setSukses] = useState("");

  // Form tambah rencana (diprefill dari query bila ada).
  const [tanggalPilih, setTanggalPilih] = useState(() => isoTanggal(new Date()));
  const [judul, setJudul] = useState(() => searchParams.get("judul") ?? "");
  const [format, setFormat] = useState(() => searchParams.get("format") ?? "");
  const [tujuan, setTujuan] = useState(() => searchParams.get("tujuan") ?? "");
  const [catatan, setCatatan] = useState("");
  const dariRekomendasi = searchParams.get("dari_rekomendasi");
  const [menyimpan, setMenyimpan] = useState(false);
  const [prosesId, setProsesId] = useState<string | null>(null);
  const [exporting, setExporting] = useState<"csv" | "pdf" | null>(null);

  const muat = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get<Rencana[]>(
        `/content/brands/${brandId}/planner?bulan=${bulan}`
      );
      setItems(data);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal memuat rencana konten."
      );
    } finally {
      setLoading(false);
    }
  }, [brandId, bulan]);

  useEffect(() => {
    muat();
  }, [muat]);

  const rencanaPerTanggal = useMemo(() => {
    const peta = new Map<string, Rencana[]>();
    for (const r of items) {
      const tgl = r.tanggal_rencana.slice(0, 10);
      const daftar = peta.get(tgl) ?? [];
      daftar.push(r);
      peta.set(tgl, daftar);
    }
    return peta;
  }, [items]);

  async function tambahRencana(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSukses("");
    setMenyimpan(true);
    try {
      const baru = await api.post<Rencana>(`/content/brands/${brandId}/planner`, {
        judul: judul.trim(),
        format: format || null,
        tujuan: tujuan || null,
        tanggal_rencana: tanggalPilih,
        catatan: catatan.trim() || undefined,
        ...(dariRekomendasi ? { rekomendasi_sumber_id: dariRekomendasi } : {}),
      });
      setItems((prev) => [...prev, baru]);
      setSukses(`Rencana "${baru.judul}" ditambahkan ke ${formatTanggal(baru.tanggal_rencana)}.`);
      setJudul("");
      setFormat("");
      setTujuan("");
      setCatatan("");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal menambah rencana."
      );
    } finally {
      setMenyimpan(false);
    }
  }

  async function ubahStatus(id: string, status: StatusRencana) {
    setProsesId(id);
    setError("");
    try {
      const diubah = await api.put<Rencana>(`/content/planner/${id}`, { status });
      setItems((prev) => prev.map((r) => (r.id === id ? diubah : r)));
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal mengubah status."
      );
    } finally {
      setProsesId(null);
    }
  }

  async function hapusRencana(id: string, judulRencana: string) {
    if (!window.confirm(`Hapus rencana "${judulRencana}"?`)) return;
    setProsesId(id);
    setError("");
    try {
      await api.del(`/content/planner/${id}`);
      setItems((prev) => prev.filter((r) => r.id !== id));
      setSukses(`Rencana "${judulRencana}" dihapus.`);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal menghapus rencana."
      );
    } finally {
      setProsesId(null);
    }
  }

  async function exportBerkas(jenis: "csv" | "pdf") {
    setExporting(jenis);
    setError("");
    try {
      const blob = await apiDownload(
        `/content/brands/${brandId}/planner/export.${jenis}?bulan=${bulan}`
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `planner-${bulan}.${jenis}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : `Gagal mengekspor ${jenis.toUpperCase()}.`
      );
    } finally {
      setExporting(null);
    }
  }

  const kisi = kisiKalender(bulan);
  const hariIni = isoTanggal(new Date());

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Content Planner"
        subtitle="Jadwalkan ide konten Anda bulan per bulan."
      />
      <BrandNav brandId={brandId} />

      {error && (
        <div className="mb-4">
          <Alert kind="error">{error}</Alert>
        </div>
      )}
      {sukses && (
        <div className="mb-4">
          <Alert kind="success">{sukses}</Alert>
        </div>
      )}
      {dariRekomendasi && (
        <div className="mb-4">
          <Alert kind="info">
            Formulir di bawah sudah terisi dari rekomendasi AI. Lengkapi
            format, tujuan, dan tanggalnya lalu simpan.
          </Alert>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Kalender */}
        <Card className="lg:col-span-3">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold capitalize text-slate-900">
              {labelBulan(bulan)}
            </h2>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                onClick={() => setBulan(tambahBulan(bulan, -1))}
                className="px-3!"
              >
                ←
              </Button>
              <Button
                variant="secondary"
                onClick={() => setBulan(bulanKey(new Date()))}
              >
                Hari ini
              </Button>
              <Button
                variant="secondary"
                onClick={() => setBulan(tambahBulan(bulan, 1))}
                className="px-3!"
              >
                →
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-7 gap-1 text-center">
            {NAMA_HARI.map((h) => (
              <div
                key={h}
                className="py-1 text-xs font-semibold uppercase text-slate-400"
              >
                {h}
              </div>
            ))}
            {kisi.map((tgl) => {
              const dalamBulan = tgl.slice(0, 7) === bulan;
              const daftar = rencanaPerTanggal.get(tgl) ?? [];
              const dipilih = tgl === tanggalPilih;
              return (
                <button
                  key={tgl}
                  type="button"
                  onClick={() => setTanggalPilih(tgl)}
                  className={`flex min-h-[3.5rem] flex-col items-center rounded-xl border p-1 transition ${
                    dipilih
                      ? "border-indigo-500 bg-indigo-50"
                      : "border-slate-100 bg-white hover:border-indigo-200 hover:bg-slate-50"
                  } ${dalamBulan ? "" : "opacity-40"}`}
                >
                  <span
                    className={`text-xs font-semibold ${
                      tgl === hariIni ? "text-indigo-700" : "text-slate-700"
                    }`}
                  >
                    {Number(tgl.slice(8, 10))}
                  </span>
                  <span className="mt-1 flex w-full flex-col gap-0.5">
                    {daftar.slice(0, 2).map((r) => (
                      <span
                        key={r.id}
                        className={`truncate rounded px-1 text-[10px] font-medium ${STATUS_META[r.status]?.tone ?? STATUS_META.ide.tone}`}
                      >
                        {r.judul}
                      </span>
                    ))}
                    {daftar.length > 2 && (
                      <span className="text-[10px] text-slate-400">
                        +{daftar.length - 2} lagi
                      </span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </Card>

        {/* Form tambah */}
        <Card className="lg:col-span-2">
          <h2 className="text-base font-semibold text-slate-900">
            Tambah rencana — {formatTanggal(tanggalPilih)}
          </h2>
          <form onSubmit={tambahRencana} className="mt-4 space-y-3">
            <Input
              label="Judul konten"
              required
              placeholder="Contoh: Behind the scenes packing"
              value={judul}
              onChange={(e) => setJudul(e.target.value)}
            />
            <Input
              label="Tanggal rencana"
              type="date"
              required
              value={tanggalPilih}
              onChange={(e) => setTanggalPilih(e.target.value)}
            />
            <Select
              label="Format"
              value={format}
              onChange={(e) => setFormat(e.target.value)}
            >
              <option value="">— Pilih —</option>
              {PILIHAN_FORMAT.map((f) => (
                <option key={f} value={f}>
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </option>
              ))}
            </Select>
            <Select
              label="Tujuan"
              value={tujuan}
              onChange={(e) => setTujuan(e.target.value)}
            >
              <option value="">— Pilih —</option>
              {PILIHAN_TUJUAN.map((t) => (
                <option key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </option>
              ))}
            </Select>
            <TextArea
              label="Catatan (opsional)"
              rows={3}
              placeholder="Angle, hook, atau CTA yang direncanakan…"
              value={catatan}
              onChange={(e) => setCatatan(e.target.value)}
            />
            <Button type="submit" disabled={menyimpan} className="w-full">
              {menyimpan ? "Menyimpan…" : "Simpan rencana"}
            </Button>
          </form>
        </Card>
      </div>

      {/* Target & estimasi + Realisasi vs rencana */}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <KartuTargetEstimasi brandId={brandId} bulan={bulan} />
        <RealisasiVsRencana brandId={brandId} bulan={bulan} />
      </div>

      {/* Alokator */}
      <div className="mt-6">
        <Alokator brandId={brandId} onRencanaBaru={muat} />
      </div>

      {/* Daftar rencana bulan ini */}
      <Card className="mt-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold capitalize text-slate-900">
            Rencana bulan {labelBulan(bulan)}
          </h2>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => exportBerkas("csv")}
              disabled={exporting !== null}
              className="px-3! py-1.5! text-xs"
            >
              {exporting === "csv" ? "Mengunduh…" : "Export CSV"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => exportBerkas("pdf")}
              disabled={exporting !== null}
              className="px-3! py-1.5! text-xs"
            >
              {exporting === "pdf" ? "Mengunduh…" : "Export PDF"}
            </Button>
          </div>
        </div>
        {loading && <Spinner label="Memuat rencana…" />}
        {!loading && items.length === 0 && (
          <EmptyBox
            title="Belum ada rencana bulan ini"
            description="Klik tanggal di kalender, isi formulir, lalu simpan rencana pertama Anda."
            icon={
              <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5" />
              </svg>
            }
          />
        )}
        {!loading && items.length > 0 && (
          <div className="space-y-2">
            {[...items]
              .sort((a, b) => a.tanggal_rencana.localeCompare(b.tanggal_rencana))
              .map((r) => (
                <div
                  key={r.id}
                  className="flex flex-col gap-3 rounded-xl border border-slate-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-900">
                      {r.judul}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {formatTanggal(r.tanggal_rencana)}
                      {r.format && ` · ${r.format}`}
                      {r.tujuan && ` · ${r.tujuan}`}
                      {r.rekomendasi_sumber_id && " · dari rekomendasi AI"}
                    </p>
                    {r.catatan && (
                      <p className="mt-1 text-xs text-slate-600">{r.catatan}</p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <select
                      value={r.status}
                      disabled={prosesId === r.id}
                      onChange={(e) =>
                        ubahStatus(r.id, e.target.value as StatusRencana)
                      }
                      className={`rounded-full px-3 py-1.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-indigo-500 ${STATUS_META[r.status]?.tone ?? STATUS_META.ide.tone}`}
                      aria-label="Ubah status"
                    >
                      {SEMUA_STATUS.map((s) => (
                        <option key={s} value={s}>
                          {STATUS_META[s].label}
                        </option>
                      ))}
                    </select>
                    <Button
                      variant="ghost"
                      onClick={() => hapusRencana(r.id, r.judul)}
                      disabled={prosesId === r.id}
                      className="px-3! py-1.5! text-xs text-red-600 hover:bg-red-50"
                    >
                      Hapus
                    </Button>
                  </div>
                </div>
              ))}
          </div>
        )}
      </Card>
    </div>
  );
}

export default function PlannerPage() {
  return (
    <RequireAuth>
      <Suspense fallback={<Spinner label="Memuat planner…" />}>
        <PlannerIsi />
      </Suspense>
    </RequireAuth>
  );
}
