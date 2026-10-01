"use client";

import { useMemo, useState } from "react";
import { Alert, Button, Card, Input, Paginasi, Select } from "@/components/ui";
import {
  DURASI_MAX_HARI,
  DURASI_MIN_HARI,
  INFO_FASE,
  LABEL_PLATFORM,
  buatRencanaFunnel,
  type FaseFunnel,
  type PlatformFunnel,
  type RencanaFunnel,
} from "@/lib/funnel";

const SEMUA_PLATFORM: PlatformFunnel[] = ["instagram", "tiktok", "facebook"];
const BARIS_PER_HALAMAN = 20;

function isoHariIni(): string {
  const d = new Date();
  const b = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${b(d.getMonth() + 1)}-${b(d.getDate())}`;
}

function isoTambah(iso: string, hari: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const t = new Date(y, m - 1, d);
  t.setDate(t.getDate() + hari);
  const b = (n: number) => String(n).padStart(2, "0");
  return `${t.getFullYear()}-${b(t.getMonth() + 1)}-${b(t.getDate())}`;
}

function formatTanggalPanjang(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("id-ID", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(y, m - 1, d));
}

export default function GeneratePlanner() {
  const [tanggalMulai, setTanggalMulai] = useState(isoHariIni);
  const [tanggalTarget, setTanggalTarget] = useState(() =>
    isoTambah(isoHariIni(), 30)
  );
  const [frekuensi, setFrekuensi] = useState("3");
  const [platform, setPlatform] = useState<PlatformFunnel[]>(["instagram"]);
  const [rencana, setRencana] = useState<RencanaFunnel | null>(null);
  const [error, setError] = useState("");
  const [halaman, setHalaman] = useState(1);

  function togglePlatform(p: PlatformFunnel) {
    setPlatform((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );
  }

  function buat() {
    setError("");
    try {
      const hasil = buatRencanaFunnel({
        tanggalMulai,
        tanggalTarget,
        frekuensi: Number(frekuensi),
        platform,
      });
      setRencana(hasil);
      setHalaman(1);
    } catch (e) {
      setRencana(null);
      setError(e instanceof Error ? e.message : "Gagal membuat rencana.");
    }
  }

  const totalHalaman = useMemo(
    () =>
      rencana ? Math.max(1, Math.ceil(rencana.items.length / BARIS_PER_HALAMAN)) : 1,
    [rencana]
  );
  const itemsHalaman = useMemo(() => {
    if (!rencana) return [];
    const awal = (halaman - 1) * BARIS_PER_HALAMAN;
    return rencana.items.slice(awal, awal + BARIS_PER_HALAMAN);
  }, [rencana, halaman]);

  const urutanFase: FaseFunnel[] = ["TOFU", "MOFU", "BOFU"];

  return (
    <div className="space-y-6">
      {/* Penjelasan framework */}
      <Card>
        <h2 className="text-base font-semibold text-slate-900">
          Rencana konten TOFU → MOFU → BOFU
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Isi formulir di bawah — sistem menyusun jadwal posting dari fase
          awareness (TOFU) sampai konversi (BOFU), menyesuaikan durasi{" "}
          {DURASI_MIN_HARI} hari – {DURASI_MAX_HARI} hari.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {urutanFase.map((f) => (
            <div
              key={f}
              className="rounded-xl border border-slate-200 bg-slate-50 p-4"
            >
              <span
                className={`inline-block rounded-full px-2.5 py-1 text-xs font-bold ${INFO_FASE[f].tone}`}
              >
                {f}
              </span>
              <p className="mt-2 text-xs leading-relaxed text-slate-600">
                {INFO_FASE[f].deskripsi}
              </p>
            </div>
          ))}
        </div>
      </Card>

      {/* Formulir */}
      <Card>
        <h2 className="mb-4 text-base font-semibold text-slate-900">
          Pengaturan rencana
        </h2>
        {error && (
          <div className="mb-4">
            <Alert kind="error">{error}</Alert>
          </div>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          <Input
            label="Tanggal mulai"
            type="date"
            value={tanggalMulai}
            onChange={(e) => setTanggalMulai(e.target.value)}
          />
          <Input
            label="Tanggal target konversi / mulai event"
            type="date"
            value={tanggalTarget}
            onChange={(e) => setTanggalTarget(e.target.value)}
          />
          <Select
            label="Seberapa sering posting dalam 1 minggu"
            value={frekuensi}
            onChange={(e) => setFrekuensi(e.target.value)}
          >
            {[1, 2, 3, 4, 5, 6, 7].map((n) => (
              <option key={n} value={String(n)}>
                {n}x seminggu
              </option>
            ))}
          </Select>
          <div>
            <span className="mb-1.5 block text-sm font-medium text-slate-700">
              Jenis platform
            </span>
            <div className="flex flex-wrap gap-2">
              {SEMUA_PLATFORM.map((p) => {
                const aktif = platform.includes(p);
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => togglePlatform(p)}
                    aria-pressed={aktif}
                    className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
                      aktif
                        ? "border-orange-500 bg-orange-50 text-orange-700"
                        : "border-slate-300 bg-white text-slate-500 hover:border-slate-400"
                    }`}
                  >
                    {LABEL_PLATFORM[p]}
                  </button>
                );
              })}
            </div>
            <p className="mt-1.5 text-xs text-slate-400">
              Saran format konten menyesuaikan platform yang dipilih.
            </p>
          </div>
        </div>
        <div className="mt-5">
          <Button onClick={buat}>Buat Rencana</Button>
        </div>
      </Card>

      {/* Hasil */}
      {rencana && (
        <Card>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-900">
              Jadwal {formatTanggalPanjang(rencana.tanggalMulai)} —{" "}
              {formatTanggalPanjang(rencana.tanggalTarget)}
            </h2>
            <p className="text-xs text-slate-500">
              {rencana.totalHari} hari · {rencana.totalKonten} konten
            </p>
          </div>

          <div className="mb-5 grid grid-cols-3 gap-3">
            {urutanFase.map((f) => (
              <div
                key={f}
                className="rounded-xl border border-slate-200 p-3 text-center"
              >
                <span
                  className={`inline-block rounded-full px-2.5 py-1 text-xs font-bold ${INFO_FASE[f].tone}`}
                >
                  {f}
                </span>
                <p className="mt-1.5 text-lg font-bold text-slate-900">
                  {rencana.perFase[f].konten}
                </p>
                <p className="text-xs text-slate-500">
                  konten · {rencana.perFase[f].hari} hari
                </p>
              </div>
            ))}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-400">
                  <th className="px-3 py-2 font-semibold">Tanggal</th>
                  <th className="px-3 py-2 font-semibold">Fase</th>
                  <th className="px-3 py-2 font-semibold">Jenis konten</th>
                  <th className="px-3 py-2 font-semibold">Format saran</th>
                </tr>
              </thead>
              <tbody>
                {itemsHalaman.map((it, i) => (
                  <tr
                    key={`${it.tanggal}-${i}`}
                    className="border-b border-slate-100 last:border-0"
                  >
                    <td className="whitespace-nowrap px-3 py-2.5 font-medium text-slate-900">
                      {formatTanggalPanjang(it.tanggal)}
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${INFO_FASE[it.fase].tone}`}
                      >
                        {it.fase}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-slate-700">{it.jenisKonten}</td>
                    <td className="px-3 py-2.5 text-slate-500">{it.formatSaran}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginasi
            halaman={halaman}
            totalHalaman={totalHalaman}
            onPindah={setHalaman}
          />
        </Card>
      )}
    </div>
  );
}
