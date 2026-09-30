"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import {
  apiOrDemo,
  demoDNA,
  demoInterview,
  demoNiches,
} from "@/lib/content";
import type {
  BrandDNA,
  Interview,
  InterviewQuestion,
  JawabResult,
  LabelSumber,
  NicheSuggestion,
} from "@/lib/types";
import { Alert, Button, Card, PageHeader, Spinner, TextArea } from "@/components/ui";
import { labelSumberTone } from "@/components/badges";
import BrandNav from "@/components/BrandNav";
import DemoBadge from "@/components/DemoBadge";

type Fase = "wawancara" | "review" | "dna" | "saran";

const TOTAL_LANGKAH = 8;

function salinInterview(i: Interview): Interview {
  return {
    ...i,
    answers: { ...i.answers },
    skipped: [...i.skipped],
    questions: i.questions.map((q) => ({ ...q })),
  };
}

function NicheIsi() {
  const params = useParams();
  const brandId = params.brandId as string;

  const [fase, setFase] = useState<Fase>("wawancara");
  const [interview, setInterview] = useState<Interview | null>(null);
  const [demo, setDemo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [jawaban, setJawaban] = useState("");
  const [menyimpan, setMenyimpan] = useState(false);
  const [elaborasi, setElaborasi] = useState(0); // hitungan butuh_elaborasi di langkah ini
  const [pesanElaborasi, setPesanElaborasi] = useState("");

  const [dna, setDna] = useState<BrandDNA | null>(null);
  const [sintesisLoading, setSintesisLoading] = useState(false);

  const [saran, setSaran] = useState<NicheSuggestion[]>([]);
  const [dipilih, setDipilih] = useState<string[]>([]);
  const [menyimpanPilihan, setMenyimpanPilihan] = useState(false);
  const [bukaAngle, setBukaAngle] = useState<Record<string, boolean>>({});

  const elaborasiRef = useRef<Record<number, number>>({});

  // --- Inisialisasi: buat / lanjutkan interview ---
  useEffect(() => {
    let batal = false;
    (async () => {
      setLoading(true);
      const { data, demo: isDemo } = await apiOrDemo<Interview>(
        async () => {
          const dibuat = await api.post<{
            id: string;
            current_step: number;
            status: string;
          }>(`/content/brands/${brandId}/niche/interviews`, {});
          return api.get<Interview>(`/content/niche/interviews/${dibuat.id}`);
        },
        () => salinInterview(demoInterview)
      );
      if (batal) return;
      setInterview(data);
      setDemo(isDemo);
      setJawaban(data.answers[data.questions[data.current_step - 1]?.key] ?? "");
      if (data.current_step > TOTAL_LANGKAH || data.status === "selesai") {
        setFase("review");
      }
      setLoading(false);
    })();
    return () => {
      batal = true;
    };
  }, [brandId]);

  const langkah = interview ? Math.min(interview.current_step, TOTAL_LANGKAH) : 1;
  const pertanyaan: InterviewQuestion | undefined =
    interview?.questions[langkah - 1];

  function resetElaborasi(keLangkah: number) {
    elaborasiRef.current = {};
    setElaborasi(0);
    setPesanElaborasi("");
    const q = interview?.questions[keLangkah - 1];
    setJawaban(interview?.answers[q?.key ?? ""] ?? "");
  }

  async function kirimJawaban(dilewati: boolean) {
    if (!interview || !pertanyaan) return;
    setMenyimpan(true);
    setError("");
    setPesanElaborasi("");
    try {
      const { data, demo: isDemo } = await apiOrDemo<JawabResult>(
        () =>
          api.post<JawabResult>(`/content/niche/interviews/${interview.id}/jawab`, {
            step: langkah,
            jawaban: dilewati ? undefined : jawaban.trim(),
            dilewati,
          }),
        () => simulasiJawabDemo(langkah, dilewati ? "" : jawaban.trim(), elaborasiRef.current[langkah] ?? 0)
      );
      setDemo((d) => d || isDemo);

      const next = salinInterview(interview);
      if (dilewati) {
        if (!next.skipped.includes(pertanyaan.key)) next.skipped.push(pertanyaan.key);
        delete next.answers[pertanyaan.key];
      } else {
        next.answers[pertanyaan.key] = jawaban.trim();
        next.skipped = next.skipped.filter((k) => k !== pertanyaan.key);
      }

      if (data.status === "butuh_elaborasi") {
        elaborasiRef.current[langkah] = (elaborasiRef.current[langkah] ?? 0) + 1;
        setElaborasi(elaborasiRef.current[langkah]);
        setPesanElaborasi(
          "Jawabanmu masih terlalu umum, coba elaborasi lebih detail: siapa tepatnya, contoh konkretnya apa, dan kenapa itu penting bagimu."
        );
        setInterview(next); // simpan draf jawaban, tetap di langkah sama
      } else {
        next.current_step = data.next_step;
        elaborasiRef.current[langkah] = 0;
        setElaborasi(0);
        setInterview(next);
        if (data.next_step > TOTAL_LANGKAH) {
          setFase("review");
        } else {
          resetElaborasi(data.next_step);
        }
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal menyimpan jawaban.");
    } finally {
      setMenyimpan(false);
    }
  }

  // --- Sintesis Brand DNA ---
  async function sintesis() {
    if (!interview) return;
    setSintesisLoading(true);
    setError("");
    try {
      const { data, demo: isDemo } = await apiOrDemo<BrandDNA>(
        () => api.post<BrandDNA>(`/content/niche/interviews/${interview.id}/sintesis`, {}),
        () => ({ ...demoDNA, version: (dna?.version ?? 0) + 1 })
      );
      setDna(data);
      setDemo((d) => d || isDemo);
      setFase("dna");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal melakukan sintesis.");
    } finally {
      setSintesisLoading(false);
    }
  }

  async function konfirmasiDNA() {
    if (!dna) return;
    setSintesisLoading(true);
    setError("");
    try {
      const { demo: isDemo } = await apiOrDemo(
        () => api.post<{ confirmed: boolean }>(`/content/niche/dna/${dna.id}/konfirmasi`, {}),
        { confirmed: true }
      );
      setDna({ ...dna, confirmed: true });
      setDemo((d) => d || isDemo);
      await muatSaran();
      setFase("saran");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal mengonfirmasi DNA.");
    } finally {
      setSintesisLoading(false);
    }
  }

  const muatSaran = useCallback(async () => {
    const { data, demo: isDemo } = await apiOrDemo<NicheSuggestion[]>(
      () => api.get<NicheSuggestion[]>(`/content/brands/${brandId}/niche/saran`),
      () => demoNiches.map((n) => ({ ...n }))
    );
    setSaran(data);
    setDipilih(data.filter((n) => n.is_selected).map((n) => n.id).slice(0, 2));
    setDemo((d) => d || isDemo);
  }, [brandId]);

  function togglePilih(id: string) {
    setDipilih((lama) => {
      if (lama.includes(id)) return lama.filter((x) => x !== id);
      if (lama.length >= 2) return lama; // maksimal 2
      return [...lama, id];
    });
  }

  async function simpanPilihan() {
    setMenyimpanPilihan(true);
    setError("");
    try {
      const { demo: isDemo } = await apiOrDemo(
        () => api.post<{ terpilih: string[] }>(`/content/brands/${brandId}/niche/pilih`, { ids: dipilih }),
        { terpilih: dipilih }
      );
      setSaran((lama) => lama.map((n) => ({ ...n, is_selected: dipilih.includes(n.id) })));
      setDemo((d) => d || isDemo);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal menyimpan pilihan.");
    } finally {
      setMenyimpanPilihan(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        <Spinner label="Menyiapkan wawancara niche…" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Niche Finder"
        subtitle="Kenali DNA brand Anda, lalu temukan niche konten yang paling cocok."
        action={<DemoBadge tampil={demo} />}
      />
      <BrandNav brandId={brandId} />
      {error && (
        <div className="mb-4">
          <Alert kind="error">{error}</Alert>
        </div>
      )}

      {fase === "wawancara" && interview && pertanyaan && (
        <WawancaraView
          langkah={langkah}
          pertanyaan={pertanyaan}
          jawaban={jawaban}
          setJawaban={setJawaban}
          menyimpan={menyimpan}
          pesanElaborasi={pesanElaborasi}
          elaborasi={elaborasi}
          onSimpan={() => kirimJawaban(false)}
          onLewati={() => kirimJawaban(true)}
        />
      )}

      {fase === "review" && interview && (
        <ReviewView
          interview={interview}
          setInterview={setInterview}
          onKembali={(step) => {
            setInterview({ ...interview, current_step: step });
            resetElaborasi(step);
            setFase("wawancara");
          }}
          onSintesis={sintesis}
          sintesisLoading={sintesisLoading}
        />
      )}

      {fase === "dna" && dna && (
        <DnaView
          dna={dna}
          loading={sintesisLoading}
          onKonfirmasi={konfirmasiDNA}
          onUlangi={sintesis}
        />
      )}

      {fase === "saran" && (
        <SaranView
          saran={saran}
          dipilih={dipilih}
          togglePilih={togglePilih}
          bukaAngle={bukaAngle}
          setBukaAngle={setBukaAngle}
          onSimpan={simpanPilihan}
          menyimpan={menyimpanPilihan}
        />
      )}
    </div>
  );
}

/** Heuristik demo: jawaban < 20 karakter dianggap terlalu umum (maks 2x elaborasi). */
function simulasiJawabDemo(langkah: number, jawaban: string, sudahElaborasi: number): JawabResult {
  if (jawaban.length > 0 && jawaban.length < 20 && sudahElaborasi < 2) {
    return { status: "butuh_elaborasi", next_step: langkah };
  }
  return { status: "ok", next_step: langkah + 1 };
}

// ============================================================
// (a) Kartu pertanyaan aktif
// ============================================================
function WawancaraView(props: {
  langkah: number;
  pertanyaan: InterviewQuestion;
  jawaban: string;
  setJawaban: (v: string) => void;
  menyimpan: boolean;
  pesanElaborasi: string;
  elaborasi: number;
  onSimpan: () => void;
  onLewati: () => void;
}) {
  const {
    langkah, pertanyaan, jawaban, setJawaban, menyimpan,
    pesanElaborasi, elaborasi, onSimpan, onLewati,
  } = props;
  const persen = Math.round(((langkah - 1) / TOTAL_LANGKAH) * 100);

  return (
    <div>
      {/* Progress bar */}
      <div className="mb-5">
        <div className="mb-1.5 flex items-center justify-between text-sm">
          <span className="font-medium text-slate-700">
            Langkah {langkah} dari {TOTAL_LANGKAH}
          </span>
          <span className="text-slate-500">{persen}%</span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-orange-600 transition-all"
            style={{ width: `${persen}%` }}
          />
        </div>
      </div>

      <Card>
        <p className="text-xs font-semibold uppercase tracking-wide text-orange-600">
          Pertanyaan {langkah}
        </p>
        <h2 className="mt-1 text-lg font-semibold leading-relaxed text-slate-900">
          {pertanyaan.pertanyaan}
        </h2>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="rounded-xl bg-sky-50 p-3">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-sky-700">
              Kenapa penting
            </p>
            <p className="text-sm text-slate-700">{pertanyaan.alasan}</p>
          </div>
          <div className="rounded-xl bg-violet-50 p-3">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-violet-700">
              Cara menjawab
            </p>
            <p className="text-sm text-slate-700">{pertanyaan.cara_menjawab}</p>
          </div>
          <div className="rounded-xl bg-emerald-50 p-3">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-emerald-700">
              Contoh jawaban baik
            </p>
            <p className="text-sm italic text-slate-700">“{pertanyaan.contoh}”</p>
          </div>
        </div>

        {pesanElaborasi && (
          <div className="mt-4">
            <Alert kind="warning">
              {pesanElaborasi}
              {elaborasi >= 2 && " (Anda bisa tetap lanjut — jawaban akan ditandai untuk ditinjau.)"}
            </Alert>
          </div>
        )}

        <div className="mt-4">
          <TextArea
            label="Jawaban Anda"
            rows={5}
            placeholder="Tulis jawaban sejujur dan sedetail mungkin…"
            value={jawaban}
            onChange={(e) => setJawaban(e.target.value)}
          />
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={onSimpan} disabled={menyimpan || jawaban.trim().length === 0}>
            {menyimpan ? "Menyimpan…" : "Simpan & Lanjut"}
          </Button>
          <Button variant="secondary" onClick={onLewati} disabled={menyimpan}>
            Lewati
          </Button>
        </div>
      </Card>
    </div>
  );
}

// ============================================================
// (b) Review semua jawaban
// ============================================================
function ReviewView(props: {
  interview: Interview;
  setInterview: (i: Interview) => void;
  onKembali: (step: number) => void;
  onSintesis: () => void;
  sintesisLoading: boolean;
}) {
  const { interview, setInterview, onKembali, onSintesis, sintesisLoading } = props;

  function ubahJawaban(key: string, nilai: string) {
    const next = salinInterview(interview);
    next.answers[key] = nilai;
    next.skipped = next.skipped.filter((k) => k !== key);
    setInterview(next);
  }

  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold text-slate-900">
        Tinjau jawaban Anda
      </h2>
      <p className="mb-4 text-sm text-slate-500">
        Anda bisa mengedit jawaban langsung di bawah. Pertanyaan yang dilewati
        ditandai sebagai <strong>celah</strong> — sintesis tetap bisa jalan,
        tapi hasilnya lebih tajam bila celah diisi.
      </p>
      <div className="space-y-3">
        {interview.questions.map((q, idx) => {
          const dilewati = interview.skipped.includes(q.key) && !interview.answers[q.key];
          const nilai = interview.answers[q.key] ?? "";
          return (
            <Card key={q.key} className={dilewati ? "border-dashed border-amber-300 bg-amber-50/40" : ""}>
              <div className="mb-2 flex items-start justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">
                  <span className="mr-2 text-slate-400">{idx + 1}.</span>
                  {q.pertanyaan}
                </p>
                {dilewati ? (
                  <span className="shrink-0 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
                    Celah — dilewati
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => onKembali(idx + 1)}
                    className="shrink-0 text-xs font-medium text-orange-600 hover:text-orange-800"
                  >
                    Jawab ulang
                  </button>
                )}
              </div>
              <textarea
                rows={3}
                value={nilai}
                placeholder={dilewati ? "Belum dijawab — tulis di sini atau biarkan sebagai celah." : ""}
                onChange={(e) => ubahJawaban(q.key, e.target.value)}
                className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-orange-500"
              />
            </Card>
          );
        })}
      </div>
      <div className="mt-6 flex flex-wrap gap-2">
        <Button onClick={onSintesis} disabled={sintesisLoading}>
          {sintesisLoading ? "Menyintesis…" : "Sintesis Brand DNA"}
        </Button>
      </div>
    </div>
  );
}

// ============================================================
// (c) Brand DNA Card
// ============================================================
function DnaView(props: {
  dna: BrandDNA;
  loading: boolean;
  onKonfirmasi: () => void;
  onUlangi: () => void;
}) {
  const { dna, loading, onKonfirmasi, onUlangi } = props;
  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold text-slate-900">Brand DNA Anda</h2>
      <Card className="border-orange-200 bg-gradient-to-br from-orange-50 to-white">
        <div className="mb-4 flex items-center justify-between">
          <span className="text-2xl" aria-hidden>
            🧬
          </span>
          <span className="rounded-full bg-orange-100 px-3 py-1 text-xs font-semibold text-orange-700">
            Versi {dna.version}
            {dna.confirmed ? " · Terkonfirmasi" : ""}
          </span>
        </div>
        <dl className="space-y-4">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Misi</dt>
            <dd className="mt-1 text-base font-medium text-slate-900">{dna.misi}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Nilai inti</dt>
            <dd className="mt-1.5 flex flex-wrap gap-2">
              {dna.nilai_inti.map((n, i) => (
                <span key={i} className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-medium text-emerald-800">
                  {n}
                </span>
              ))}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Kepribadian</dt>
            <dd className="mt-1 text-sm leading-relaxed text-slate-700">{dna.kepribadian}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Positioning statement</dt>
            <dd className="mt-1 rounded-xl bg-white p-3 text-sm italic leading-relaxed text-slate-800 ring-1 ring-slate-200">
              “{dna.positioning_statement}”
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">Diferensiasi</dt>
            <dd className="mt-1 text-sm leading-relaxed text-slate-700">{dna.diferensiasi}</dd>
          </div>
        </dl>
      </Card>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button onClick={onKonfirmasi} disabled={loading}>
          {loading ? "Memproses…" : "Konfirmasi"}
        </Button>
        <Button variant="secondary" onClick={onUlangi} disabled={loading}>
          Ulangi sintesis
        </Button>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Konfirmasi akan mengunci DNA ini dan membuka saran niche yang dihitung
        dari DNA tersebut.
      </p>
    </div>
  );
}

// ============================================================
// (d) Daftar saran niche
// ============================================================
function SaranView(props: {
  saran: NicheSuggestion[];
  dipilih: string[];
  togglePilih: (id: string) => void;
  bukaAngle: Record<string, boolean>;
  setBukaAngle: (v: Record<string, boolean>) => void;
  onSimpan: () => void;
  menyimpan: boolean;
}) {
  const { saran, dipilih, togglePilih, bukaAngle, setBukaAngle, onSimpan, menyimpan } = props;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            Saran niche untuk brand Anda
          </h2>
          <p className="text-sm text-slate-500">
            Pilih maksimal 2 niche yang paling ingin Anda dalami.
            {dipilih.length > 0 && (
              <span className="font-medium text-orange-600"> ({dipilih.length}/2 dipilih)</span>
            )}
          </p>
        </div>
        <Button onClick={onSimpan} disabled={menyimpan || dipilih.length === 0}>
          {menyimpan ? "Menyimpan…" : "Simpan Pilihan"}
        </Button>
      </div>

      <div className="space-y-4">
        {saran.map((n) => {
          const terbuka = !!bukaAngle[n.id];
          const dicentang = dipilih.includes(n.id);
          const disabledCentang = !dicentang && dipilih.length >= 2;
          return (
            <Card key={n.id} className={dicentang ? "border-orange-300 ring-1 ring-orange-200" : ""}>
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={dicentang}
                  disabled={disabledCentang}
                  onChange={() => togglePilih(n.id)}
                  className="mt-1 h-5 w-5 shrink-0 rounded accent-orange-600 disabled:opacity-40"
                  aria-label={`Pilih niche ${n.name}`}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-semibold text-slate-900">{n.name}</h3>
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-bold ring-1 ring-inset ${labelSumberTone(n.label_sumber as LabelSumber)}`}
                      title={keteranganLabel(n.label_sumber)}
                    >
                      {n.label_sumber}
                    </span>
                    {n.is_selected && (
                      <span className="rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-semibold text-orange-700">
                        Tersimpan
                      </span>
                    )}
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <div className="h-2 w-32 overflow-hidden rounded-full bg-slate-200">
                      <div
                        className="h-full rounded-full bg-orange-600"
                        style={{ width: `${n.match_percent}%` }}
                      />
                    </div>
                    <span className="text-sm font-bold text-orange-700">
                      {n.match_percent}% cocok
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-slate-700">{n.alasan}</p>

                  <button
                    type="button"
                    onClick={() => setBukaAngle({ ...bukaAngle, [n.id]: !terbuka })}
                    className="mt-3 text-sm font-medium text-orange-600 hover:text-orange-800"
                  >
                    {terbuka ? "▾ Sembunyikan" : "▸ Lihat"} 10 angle konten
                  </button>
                  {terbuka && (
                    <ol className="mt-2 list-decimal space-y-1 rounded-xl bg-slate-50 p-4 pl-9 text-sm text-slate-700">
                      {n.angles.map((a, i) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ol>
                  )}

                  <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
                    <div className="rounded-xl bg-emerald-50 p-3">
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-emerald-700">
                        Monetisasi
                      </p>
                      <p className="text-slate-700">{n.monetisasi}</p>
                    </div>
                    <div className="rounded-xl bg-slate-100 p-3">
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
                        Persaingan
                      </p>
                      <p className="text-slate-700">{n.persaingan}</p>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function keteranganLabel(label: string): string {
  switch (label) {
    case "DATA":
      return "Berdasarkan data performa brand Anda";
    case "ESTIMASI":
      return "Berdasarkan estimasi pola pasar";
    default:
      return "Berdasarkan klaim umum / belum terverifikasi data";
  }
}

export default function NichePage() {
  return (
    <RequireAuth>
      <NicheIsi />
    </RequireAuth>
  );
}
