"use client";

import { useMemo, useState } from "react";
import { Alert, Button, Card, Input, Paginasi, Select, Tabel, TextArea } from "@/components/ui";
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
import {
  BANK_NICHE_KOMPETITOR,
  NICHE_DEFAULT,
  dapatkanNiche,
  type Kompetitor,
} from "@/lib/kompetitor";
import {
  PRINSIP_SINKRONISASI_WA,
  SEKUENS_PASCA_WA,
  STRATEGI_WA_KOMPETITOR,
  buatJadwalWA,
} from "@/lib/wa-marketing";

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
  // Kompetitor se-niche untuk ide konten (bisa diganti/tambah/hapus)
  const [nicheId, setNicheId] = useState<string>(NICHE_DEFAULT);
  const [daftarKompetitor, setDaftarKompetitor] = useState<Kompetitor[]>(() =>
    (dapatkanNiche(NICHE_DEFAULT)?.kompetitor ?? []).map((k) => ({
      ...k,
      polaAndalan: [...k.polaAndalan],
    }))
  );
  const [namaKomp, setNamaKomp] = useState("");
  const [handleKomp, setHandleKomp] = useState("");
  const [polaKomp, setPolaKomp] = useState("");
  const [exportingPdf, setExportingPdf] = useState(false);
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
        kompetitor: daftarKompetitor,
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

  /** Hitung ulang rencana dengan tema & daftar kompetitor terbaru. */
  function hitungUlangRencana(
    tema: RekomendasiTema | null,
    komp: Kompetitor[]
  ) {
    if (!snap) return;
    try {
      const hasil = buatRencanaFunnel({
        ...snap,
        tema: tema ? { namaTema: tema.namaTema, angle: tema.angle } : undefined,
        kompetitor: komp,
      });
      setRencana(hasil);
      setHalaman(1);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Gagal menghitung ulang rencana."
      );
    }
  }

  /** Ganti tema → rencana dihitung ulang dengan tema baru. */
  function pilihTema(id: string) {
    const t = temaOpsi.find((x) => x.id === id);
    if (!t || !snap) return;
    setTemaId(id);
    hitungUlangRencana(t, daftarKompetitor);
  }

  /** Ganti niche → daftar kompetitor diisi dari bank, rencana dihitung ulang. */
  function gantiNiche(id: string) {
    setNicheId(id);
    const daftar = (dapatkanNiche(id)?.kompetitor ?? []).map((k) => ({
      ...k,
      polaAndalan: [...k.polaAndalan],
    }));
    setDaftarKompetitor(daftar);
    hitungUlangRencana(temaTerpilih, daftar);
  }

  /** Tambah kompetitor manual (untuk niche apa pun). */
  function tambahKompetitor() {
    if (!namaKomp.trim()) {
      setError("Isi dulu nama kompetitor yang ingin ditambahkan.");
      return;
    }
    setError("");
    const baru: Kompetitor = {
      id: `kustom-${Date.now()}`,
      nama: namaKomp.trim(),
      handle: handleKomp.trim().replace(/^@/, ""),
      polaAndalan: polaKomp
        .split(/[,\n]/)
        .map((s) => s.trim())
        .filter(Boolean),
      sumberPola: "umum",
    };
    const daftar = [...daftarKompetitor, baru];
    setDaftarKompetitor(daftar);
    setNamaKomp("");
    setHandleKomp("");
    setPolaKomp("");
    hitungUlangRencana(temaTerpilih, daftar);
  }

  /** Hapus kompetitor dari daftar. */
  function hapusKompetitor(id: string) {
    const daftar = daftarKompetitor.filter((k) => k.id !== id);
    setDaftarKompetitor(daftar);
    hitungUlangRencana(temaTerpilih, daftar);
  }

  const nicheAktif = useMemo(
    () => dapatkanNiche(nicheId),
    [nicheId]
  );

  const timeline = useMemo(
    () => (rencana && brief ? buatTimelineTerintegrasi(rencana, brief) : []),
    [rencana, brief]
  );
  const jadwalWA = useMemo(
    () => (rencana && brief ? buatJadwalWA(rencana, brief) : []),
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
        {/* Kompetitor Se-Niche */}
        <Card>
          <h2 className="text-base font-semibold text-slate-900">
            Kompetitor Se-Niche
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Untuk ide konten, kenali minimal 5 kompetitor dengan niche yang
            sama. Tiap jadwal konten menyertakan satu pola andalan mereka
            sebagai referensi untuk ditiru dan diadaptasi.
          </p>
          <div className="mt-4">
            <Select
              label="Niche"
              value={nicheId}
              onChange={(e) => gantiNiche(e.target.value)}
            >
              {BANK_NICHE_KOMPETITOR.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.label}
                </option>
              ))}
            </Select>
            {nicheAktif && (
              <p className="mt-1.5 text-xs text-slate-400">
                {nicheAktif.deskripsi}
              </p>
            )}
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {daftarKompetitor.map((k) => (
              <div
                key={k.id}
                className="rounded-xl border border-slate-200 bg-white p-4"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-bold text-slate-900">{k.nama}</p>
                    {k.handle && (
                      <p className="text-xs text-slate-400">@{k.handle}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => hapusKompetitor(k.id)}
                    aria-label={`Hapus ${k.nama}`}
                    className="rounded-lg px-2 py-1 text-xs font-semibold text-slate-400 hover:bg-slate-100 hover:text-red-600"
                  >
                    Hapus
                  </button>
                </div>
                {k.polaAndalan.length > 0 ? (
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-slate-500">
                    {k.polaAndalan.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-slate-400">
                    Belum ada pola andalan — amati akunnya lalu adaptasi.
                  </p>
                )}
              </div>
            ))}
          </div>
          {daftarKompetitor.length < 5 && (
            <p className="mt-3 text-xs font-medium text-amber-600">
              Disarankan minimal 5 kompetitor — saat ini {daftarKompetitor.length}.
            </p>
          )}
          <div className="mt-4 rounded-xl bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-700">
              Tambah kompetitor manual
            </p>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <Input
                label="Nama"
                value={namaKomp}
                onChange={(e) => setNamaKomp(e.target.value)}
                placeholder="cth. Yayasan ABC"
              />
              <Input
                label="Handle Instagram"
                value={handleKomp}
                onChange={(e) => setHandleKomp(e.target.value)}
                placeholder="cth. yayasanabc"
              />
              <Input
                label="Pola andalan (pisah koma)"
                value={polaKomp}
                onChange={(e) => setPolaKomp(e.target.value)}
                placeholder="cth. Reels storytelling, CTA tunggal"
              />
            </div>
            <Button
              type="button"
              variant="secondary"
              onClick={tambahKompetitor}
              className="mt-3 px-3! py-1.5! text-xs"
            >
              + Tambah kompetitor
            </Button>
          </div>
        </Card>

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

        {/* Sinkronisasi WA Marketing */}
        <Card>
          <h2 className="text-base font-semibold text-slate-900">
            Sinkronisasi WA Marketing
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Jadwal broadcast WA yang selaras dengan fase campaign — meniru pola
            kompetitor se-niche. Prinsipnya: satu pesan dua kecepatan (IG =
            jangkauan, WA = nurturing).
          </p>

          <h3 className="mt-5 text-sm font-bold text-slate-800">
            Strategi WA 5 kompetitor se-niche
          </h3>
          <div className="mt-2 grid gap-3 md:grid-cols-2">
            {STRATEGI_WA_KOMPETITOR.map((s) => (
              <div
                key={s.kompetitorId}
                className="rounded-xl border border-slate-200 bg-white p-4"
              >
                <p className="flex flex-wrap items-center gap-2 text-sm font-bold text-slate-900">
                  {s.nama}
                  {s.handle && (
                    <span className="text-xs font-normal text-slate-400">
                      @{s.handle}
                    </span>
                  )}
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                      s.sumberPola === "riset"
                        ? "bg-green-100 text-green-700"
                        : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {s.sumberPola === "riset"
                      ? "Riset benchmark"
                      : "Pola umum"}
                  </span>
                </p>
                <p className="mt-1 text-xs text-slate-500">{s.ringkasan}</p>
                <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-slate-500">
                  {s.pola.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <h3 className="mt-5 text-sm font-bold text-slate-800">
            Jadwal broadcast tersinkron ({jadwalWA.length} kiriman)
          </h3>
          <div className="mt-2">
            <Tabel
              padat
              kolom={["Tanggal", "Fase", "Kegiatan", "Segmen", "Detail"]}
              baris={jadwalWA.map((w) => [
                <span
                  key="t"
                  className="whitespace-nowrap font-medium text-slate-900"
                >
                  {formatTanggalPanjang(w.tanggal)}
                </span>,
                <span
                  key="f"
                  className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${INFO_FASE[w.fase].tone}`}
                >
                  {w.fase}
                </span>,
                <span key="k" className="font-medium text-slate-700">
                  {w.kegiatan}
                </span>,
                w.segmen,
                w.detail,
              ])}
            />
          </div>

          <h3 className="mt-5 text-sm font-bold text-slate-800">
            4 prinsip sinkronisasi
          </h3>
          <ol className="mt-2 grid gap-2 md:grid-cols-2">
            {PRINSIP_SINKRONISASI_WA.map((p, i) => (
              <li
                key={i}
                className="rounded-xl bg-slate-50 px-4 py-3 text-xs text-slate-600"
              >
                <span className="font-bold text-slate-800">
                  {i + 1}. {p.judul} —{" "}
                </span>
                {p.isi}
              </li>
            ))}
          </ol>

          <h3 className="mt-5 text-sm font-bold text-slate-800">
            Template sekuens pasca-event
          </h3>
          <div className="mt-2">
            <Tabel
              padat
              kolom={["Momen", "Kegiatan", "Detail"]}
              baris={SEKUENS_PASCA_WA.map((s) => [
                <span
                  key="m"
                  className="whitespace-nowrap font-bold text-slate-900"
                >
                  {s.momen}
                </span>,
                <span key="k" className="font-medium text-slate-700">
                  {s.kegiatan}
                </span>,
                s.detail,
              ])}
            />
          </div>
          <p className="mt-3 text-xs text-slate-400">
            Catatan: isi pesan broadcast aktual bersifat privat — yang
            direkonstruksi dari riset adalah jenis konten dan momen kirimnya.
          </p>
        </Card>

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
                disabled={exportingPdf}
                onClick={async () => {
                  if (!brief || exportingPdf) return;
                  setExportingPdf(true);
                  try {
                    await exportTimelinePdf(
                      brief,
                      rencana,
                      timeline,
                      filterKanal,
                      temaTerpilih,
                      { nicheLabel: nicheAktif?.label, kompetitor: daftarKompetitor }
                    );
                  } catch (e) {
                    setError(
                      e instanceof Error ? e.message : "Gagal membuat PDF."
                    );
                  } finally {
                    setExportingPdf(false);
                  }
                }}
                className="px-3! py-1.5! text-xs"
              >
                {exportingPdf ? "Menyiapkan PDF…" : "Export PDF"}
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

          <Tabel
            padat
            kolom={["Tanggal", "Fase", "Kanal", "Kegiatan", "Detail"]}
            baris={itemsHalaman.map((it) => [
              <span
                key="t"
                className="whitespace-nowrap font-medium text-slate-900"
              >
                {formatTanggalPanjang(it.tanggal)}
              </span>,
              <span
                key="f"
                className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${INFO_FASE[it.fase].tone}`}
              >
                {it.fase}
              </span>,
              <span
                key="k"
                className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-bold ${TONE_KANAL[it.kanal]}`}
              >
                {LABEL_KANAL[it.kanal]}
              </span>,
              <span key="kg" className="font-medium text-slate-700">
                {it.kegiatan}
              </span>,
              <span key="d">
                {it.detail}
                {it.referensiKompetitor && (
                  <span className="mt-1 block text-xs text-slate-400">
                    {it.referensiKompetitor}
                  </span>
                )}
              </span>,
            ])}
          />
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
