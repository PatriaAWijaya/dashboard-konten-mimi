"use client";

import { useMemo, useState } from "react";
import { Alert, Button, Card, Input, Paginasi, Select, TextArea } from "@/components/ui";
import {
  DURASI_MAX_HARI,
  DURASI_MIN_HARI,
  INFO_FASE,
  LABEL_PLATFORM,
  LABEL_TUJUAN,
  buatRencanaFunnel,
  type BriefCampaign,
  type FaseFunnel,
  type PlatformFunnel,
  type RencanaFunnel,
  type TujuanCampaign,
} from "@/lib/funnel";
import {
  LABEL_KANAL,
  TONE_KANAL,
  buatTimelineTerintegrasi,
  type KanalTimeline,
} from "@/lib/timeline";
import { exportTimelinePdf } from "@/lib/export-timeline-pdf";
import {
  rekomendasiTema,
  type RekomendasiTema,
} from "@/lib/tema";

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
  // 5W1H event campaign — dasar pelaksanaan campaign
  const [apa, setApa] = useState("");
  const [mengapa, setMengapa] = useState<TujuanCampaign>("jualan");
  const [siapa, setSiapa] = useState("");
  const [dimana, setDimana] = useState("");
  const [bagaimana, setBagaimana] = useState("");
  // Pengaturan jadwal
  const [tanggalMulai, setTanggalMulai] = useState(isoHariIni);
  const [tanggalTarget, setTanggalTarget] = useState(() =>
    isoTambah(isoHariIni(), 30)
  );
  const [frekuensi, setFrekuensi] = useState("3");
  const [platform, setPlatform] = useState<PlatformFunnel[]>(["instagram"]);
  const [rencana, setRencana] = useState<RencanaFunnel | null>(null);
  const [brief, setBrief] = useState<BriefCampaign | null>(null);
  const [error, setError] = useState("");
  const [halaman, setHalaman] = useState(1);
  const [filterKanal, setFilterKanal] = useState<KanalTimeline | "semua">("semua");
  // Rekomendasi tema campaign + pilihan user (disnapshot saat generate)
  const [temaOpsi, setTemaOpsi] = useState<RekomendasiTema[]>([]);
  const [temaId, setTemaId] = useState<string | null>(null);
  const [namaMomentum, setNamaMomentum] = useState<string | null>(null);
  const [snap, setSnap] = useState<{
    tanggalMulai: string;
    tanggalTarget: string;
    frekuensi: number;
    platform: PlatformFunnel[];
    tujuan: TujuanCampaign;
  } | null>(null);

  function togglePlatform(p: PlatformFunnel) {
    setPlatform((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
    );
  }

  function buat() {
    setError("");
    if (!apa.trim()) {
      setRencana(null);
      setBrief(null);
      setError("Isi dulu nama event/campaign pada bagian 5W1H.");
      return;
    }
    try {
      const freq = Number(frekuensi);
      const rek = rekomendasiTema({ mengapa }, tanggalMulai, tanggalTarget);
      const temaPertama = rek.daftar[0] ?? null;
      const hasil = buatRencanaFunnel({
        tanggalMulai,
        tanggalTarget,
        frekuensi: freq,
        platform,
        tujuan: mengapa,
        tema: temaPertama
          ? { namaTema: temaPertama.namaTema, angle: temaPertama.angle }
          : undefined,
      });
      setRencana(hasil);
      setBrief({ apa: apa.trim(), mengapa, siapa: siapa.trim(), dimana: dimana.trim(), bagaimana: bagaimana.trim() });
      setTemaOpsi(rek.daftar);
      setTemaId(temaPertama ? temaPertama.id : null);
      setNamaMomentum(rek.momentum ? rek.momentum.nama : null);
      setSnap({ tanggalMulai, tanggalTarget, frekuensi: freq, platform, tujuan: mengapa });
      setHalaman(1);
      setFilterKanal("semua");
    } catch (e) {
      setRencana(null);
      setBrief(null);
      setError(e instanceof Error ? e.message : "Gagal membuat rencana.");
    }
  }

  const temaTerpilih = useMemo(
    () => temaOpsi.find((t) => t.id === temaId) ?? null,
    [temaOpsi, temaId]
  );

  /** Ganti tema → rencana dihitung ulang dengan tema baru. */
  function pilihTema(id: string) {
    const t = temaOpsi.find((x) => x.id === id);
    if (!t || !snap) return;
    try {
      const hasil = buatRencanaFunnel({
        ...snap,
        tema: { namaTema: t.namaTema, angle: t.angle },
      });
      setTemaId(id);
      setRencana(hasil);
      setHalaman(1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal menerapkan tema.");
    }
  }

  const timeline = useMemo(
    () => (rencana && brief ? buatTimelineTerintegrasi(rencana, brief) : []),
    [rencana, brief]
  );
  const kanalTersedia = useMemo(
    () =>
      (Object.keys(LABEL_KANAL) as KanalTimeline[]).filter((k) =>
        timeline.some((it) => it.kanal === k)
      ),
    [timeline]
  );
  const timelineFilter = useMemo(
    () =>
      filterKanal === "semua"
        ? timeline
        : timeline.filter((it) => it.kanal === filterKanal),
    [timeline, filterKanal]
  );
  const totalHalaman = useMemo(
    () =>
      Math.max(1, Math.ceil(timelineFilter.length / BARIS_PER_HALAMAN)),
    [timelineFilter]
  );
  const itemsHalaman = useMemo(() => {
    const awal = (halaman - 1) * BARIS_PER_HALAMAN;
    return timelineFilter.slice(awal, awal + BARIS_PER_HALAMAN);
  }, [timelineFilter, halaman]);

  function pilihFilter(k: KanalTimeline | "semua") {
    setFilterKanal(k);
    setHalaman(1);
  }

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

      {/* 5W1H — dasar pelaksanaan campaign */}
      <Card>
        <h2 className="text-base font-semibold text-slate-900">
          5W1H Event Campaign
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Dasar pelaksanaan campaign — jawaban di sini menjadi brief yang
          menjiwai seluruh jadwal konten, termasuk ajakan di fase BOFU.
        </p>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Input
            label="Apa — nama event/campaign"
            value={apa}
            onChange={(e) => setApa(e.target.value)}
            placeholder="Contoh: Webinar Fundraising Qurban 2026"
          />
          <Select
            label="Mengapa — tujuan campaign"
            value={mengapa}
            onChange={(e) => setMengapa(e.target.value as TujuanCampaign)}
          >
            {(Object.keys(LABEL_TUJUAN) as TujuanCampaign[]).map((t) => (
              <option key={t} value={t}>
                {LABEL_TUJUAN[t]}
              </option>
            ))}
          </Select>
          <Input
            label="Siapa — target audiens"
            value={siapa}
            onChange={(e) => setSiapa(e.target.value)}
            placeholder="Contoh: Donatur usia 25–40 tahun"
          />
          <Input
            label="Kapan — tanggal target / mulai event"
            type="date"
            value={tanggalTarget}
            onChange={(e) => setTanggalTarget(e.target.value)}
          />
          <Input
            label="Di mana — lokasi / platform event"
            value={dimana}
            onChange={(e) => setDimana(e.target.value)}
            placeholder="Contoh: Online via Zoom"
          />
        </div>
        <div className="mt-4">
          <TextArea
            label="Bagaimana — mekanisme pelaksanaan"
            value={bagaimana}
            onChange={(e) => setBagaimana(e.target.value)}
            rows={3}
            placeholder="Contoh: Peserta daftar via link, donasi via QRIS, pengumuman di Instagram Live…"
          />
        </div>
      </Card>

      {/* Formulir */}
      <Card>
        <h2 className="mb-4 text-base font-semibold text-slate-900">
          Pengaturan jadwal
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
          <div className="md:col-span-2">
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
      {rencana && brief && (
        <>
        <Card>
          <h2 className="mb-3 text-base font-semibold text-slate-900">
            Brief Campaign — {brief.apa}
          </h2>
          <dl className="grid gap-3 md:grid-cols-2">
            {[
              { t: "Apa", v: brief.apa },
              { t: "Mengapa", v: LABEL_TUJUAN[brief.mengapa] },
              { t: "Siapa", v: brief.siapa || "—" },
              { t: "Kapan", v: formatTanggalPanjang(rencana.tanggalTarget) },
              { t: "Di mana", v: brief.dimana || "—" },
              { t: "Bagaimana", v: brief.bagaimana || "—" },
            ].map((b) => (
              <div key={b.t} className="rounded-xl bg-slate-50 px-4 py-3">
                <dt className="text-xs font-semibold uppercase text-slate-400">
                  {b.t}
                </dt>
                <dd className="mt-1 text-sm font-medium text-slate-800">{b.v}</dd>
              </div>
            ))}
          </dl>
        </Card>

        {/* Rekomendasi Tema Campaign */}
        {temaOpsi.length > 0 && (
          <Card>
            <h2 className="text-base font-semibold text-slate-900">
              Rekomendasi Tema Campaign
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              {namaMomentum
                ? `Momentum terdeteksi: ${namaMomentum}.`
                : "Tidak ada momentum hari besar pada rentang ini — tema umum."}{" "}
              Pilih satu tema; seluruh kegiatan konten organik memakai nama
              tema ini dan detailnya mengikuti big idea.
            </p>
            <div
              role="radiogroup"
              aria-label="Pilihan tema campaign"
              className="mt-4 grid gap-3 md:grid-cols-2"
            >
              {temaOpsi.map((t) => {
                const aktif = t.id === temaId;
                return (
                  <button
                    key={t.id}
                    type="button"
                    role="radio"
                    aria-checked={aktif}
                    onClick={() => pilihTema(t.id)}
                    className={`rounded-xl border p-4 text-left transition ${
                      aktif
                        ? "border-orange-500 bg-orange-50 ring-2 ring-orange-500"
                        : "border-slate-200 bg-white hover:border-orange-300"
                    }`}
                  >
                    <p className="flex items-center gap-2 text-sm font-bold text-slate-900">
                      <span
                        aria-hidden
                        className={`inline-block h-3.5 w-3.5 rounded-full border-2 ${
                          aktif ? "border-orange-500 bg-orange-500" : "border-slate-300"
                        }`}
                      />
                      {t.namaTema}
                    </p>
                    <p className="mt-2 text-sm text-slate-700">
                      <span className="font-semibold">Big idea:</span> {t.bigIdea}
                    </p>
                    <dl className="mt-3 space-y-2 text-xs text-slate-500">
                      <div>
                        <dt className="font-semibold uppercase text-slate-400">
                          Dasar tren (6 bulan terakhir)
                        </dt>
                        <dd className="mt-0.5">{t.tren}</dd>
                      </div>
                      <div>
                        <dt className="font-semibold uppercase text-slate-400">
                          Pola acuan
                        </dt>
                        <dd className="mt-0.5">{t.polaAcuan}</dd>
                      </div>
                      <div>
                        <dt className="font-semibold uppercase text-slate-400">
                          Kenapa cocok
                        </dt>
                        <dd className="mt-0.5">{t.penjelasan}</dd>
                      </div>
                    </dl>
                  </button>
                );
              })}
            </div>
          </Card>
        )}

        <Card>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-slate-900">
              Timeline Campaign Terintegrasi
            </h2>
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-xs text-slate-500">
                {rencana.totalHari} hari · {rencana.totalKonten} konten ·{" "}
                {timeline.length - rencana.totalKonten} aktivitas pendukung
              </p>
              <Button
                variant="secondary"
                onClick={() =>
                  brief &&
                  exportTimelinePdf(
                    brief,
                    rencana,
                    timeline,
                    filterKanal,
                    temaTerpilih
                  )
                }
                className="px-3! py-1.5! text-xs"
              >
                Export PDF
              </Button>
            </div>
          </div>
          <p className="mb-4 text-sm text-slate-500">
            Usulan menyeluruh {formatTanggalPanjang(rencana.tanggalMulai)} —{" "}
            {formatTanggalPanjang(rencana.tanggalTarget)}: konten organik
            ditopang placement ads, kolaborasi, web internal, dan galang dana,
            tersusun kronologis per fase.
          </p>

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

          <div className="mb-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => pilihFilter("semua")}
              className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition ${
                filterKanal === "semua"
                  ? "border-orange-500 bg-orange-50 text-orange-700"
                  : "border-slate-300 bg-white text-slate-500 hover:border-slate-400"
              }`}
            >
              Semua ({timeline.length})
            </button>
            {kanalTersedia.map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => pilihFilter(k)}
                className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition ${
                  filterKanal === k
                    ? "border-orange-500 bg-orange-50 text-orange-700"
                    : "border-slate-300 bg-white text-slate-500 hover:border-slate-400"
                }`}
              >
                {LABEL_KANAL[k]} ({timeline.filter((it) => it.kanal === k).length})
              </button>
            ))}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-400">
                  <th className="px-3 py-2 font-semibold">Tanggal</th>
                  <th className="px-3 py-2 font-semibold">Fase</th>
                  <th className="px-3 py-2 font-semibold">Kanal</th>
                  <th className="px-3 py-2 font-semibold">Kegiatan</th>
                  <th className="px-3 py-2 font-semibold">Detail</th>
                </tr>
              </thead>
              <tbody>
                {itemsHalaman.map((it, i) => (
                  <tr
                    key={`${it.tanggal}-${it.kanal}-${i}`}
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
                    <td className="px-3 py-2.5">
                      <span
                        className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-bold ${TONE_KANAL[it.kanal]}`}
                      >
                        {LABEL_KANAL[it.kanal]}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 font-medium text-slate-700">
                      {it.kegiatan}
                    </td>
                    <td className="px-3 py-2.5 text-slate-500">{it.detail}</td>
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
        </>
      )}
    </div>
  );
}
