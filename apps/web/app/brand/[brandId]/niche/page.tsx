"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { apiOrDemo, demoNicheQuestions, buatLaporanDemo } from "@/lib/content";
import type {
  Interview,
  InterviewQuestion,
  JawabResult,
  LaporanNiche,
} from "@/lib/types";
import { Alert, Button, Card, PageHeader, Spinner, TextArea, Input } from "@/components/ui";
import BrandNav from "@/components/BrandNav";
import DemoBadge from "@/components/DemoBadge";

type Fase = "kartu" | "selesai" | "laporan";

const TOTAL_KARTU = 11;

// ============================================================
// Helper draf jawaban per tipe kartu
// ============================================================

type Draf = unknown;

function drafAwal(q: InterviewQuestion, tersimpan: unknown): Draf {
  const s = tersimpan as Record<string, unknown> | null;
  switch (q.tipe) {
    case "pilihan_tunggal":
      return (s?.pilihan as string) ?? null;
    case "pilihan_ganda": {
      const terpilih = [...((s?.terpilih as string[]) ?? [])];
      if (q.key === "pengalaman") {
        return { terpilih, bukti: { ...((s?.bukti as Record<string, string>) ?? {}) } };
      }
      return { terpilih };
    }
    case "teks":
      return (s?.teks as string) ?? "";
    case "teks_ganda": {
      const o: Record<string, string> = {};
      for (const f of q.fields ?? []) o[f.key] = (s?.[f.key] as string) ?? "";
      return o;
    }
    case "kreator": {
      const arr = (Array.isArray(tersimpan) ? tersimpan : []) as { username: string; alasan: string }[];
      return [0, 1, 2].map((i) => ({
        username: arr[i]?.username ?? "",
        alasan: arr[i]?.alasan ?? "",
      }));
    }
    case "kata": {
      const arr = (Array.isArray(tersimpan) ? tersimpan : []) as string[];
      return [arr[0] ?? "", arr[1] ?? "", arr[2] ?? ""];
    }
  }
}

function jawabanDariDraf(q: InterviewQuestion, draf: Draf): unknown {
  switch (q.tipe) {
    case "pilihan_tunggal":
      return { pilihan: draf as string };
    case "pilihan_ganda": {
      const d = draf as { terpilih: string[]; bukti?: Record<string, string> };
      return q.key === "pengalaman"
        ? { terpilih: d.terpilih, bukti: d.bukti ?? {} }
        : { terpilih: d.terpilih };
    }
    case "teks":
      return { teks: draf as string };
    case "teks_ganda":
      return draf;
    case "kreator":
      return (draf as { username: string; alasan: string }[]).filter((x) => x.username.trim());
    case "kata":
      return (draf as string[]).map((k) => k.trim()).filter(Boolean);
  }
}

/** Validasi ringan di sisi klien (backend tetap sumber kebenaran). */
function validasiKlien(q: InterviewQuestion, draf: Draf): string | null {
  const kosong = (v: unknown) => v === null || v === undefined || v === "" ||
    (Array.isArray(v) && v.length === 0);
  switch (q.tipe) {
    case "pilihan_tunggal":
      if (q.wajib && kosong(draf)) return "Pilih salah satu opsi untuk lanjut.";
      return null;
    case "pilihan_ganda": {
      const d = draf as { terpilih: string[]; bukti?: Record<string, string> };
      const min = q.min_pilih ?? 1;
      if (d.terpilih.length < min) {
        if (!q.wajib && d.terpilih.length === 0) return null;
        return `Pilih minimal ${min} opsi.`;
      }
      if (q.key === "pengalaman") {
        for (const t of d.terpilih) {
          if (((d.bukti ?? {})[t] ?? "").trim().length < 10) {
            const label = q.opsi?.find((o) => o.value === t)?.judul ?? t;
            return `Isi bukti singkat untuk '${label}' (minimal 10 karakter).`;
          }
        }
      }
      return null;
    }
    case "teks":
      if (q.wajib && !(draf as string).trim()) return "Jawaban tidak boleh kosong.";
      return null;
    case "teks_ganda": {
      const d = draf as Record<string, string>;
      for (const f of q.fields ?? []) {
        if (f.wajib && !(d[f.key] ?? "").trim()) return `Isi '${f.label}'.`;
      }
      return null;
    }
    case "kreator": {
      const terisi = (draf as { username: string }[]).filter((x) => x.username.trim());
      if (terisi.length < (q.min_slot ?? 1)) {
        if (!q.wajib && terisi.length === 0) return null;
        return `Isi minimal ${q.min_slot ?? 1} kreator inspirasi.`;
      }
      return null;
    }
    case "kata": {
      const kata = (draf as string[]).map((k) => k.trim()).filter(Boolean);
      if (kata.length < (q.min_kata ?? 1)) {
        if (!q.wajib && kata.length === 0) return null;
        return `Tulis minimal ${q.min_kata ?? 1} kata.`;
      }
      return null;
    }
  }
}

function salinInterview(i: Interview): Interview {
  return {
    ...i,
    answers: { ...i.answers },
    skipped: [...i.skipped],
    questions: i.questions.map((q) => ({ ...q })),
  };
}

// ============================================================
// Halaman utama
// ============================================================

function NicheIsi() {
  const params = useParams();
  const brandId = params.brandId as string;

  const [fase, setFase] = useState<Fase>("kartu");
  const [interview, setInterview] = useState<Interview | null>(null);
  const [posisi, setPosisi] = useState(0);
  const [draf, setDraf] = useState<Draf>(null);
  const [demo, setDemo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [menyimpan, setMenyimpan] = useState(false);
  const [pesanElaborasi, setPesanElaborasi] = useState("");
  const [laporan, setLaporan] = useState<LaporanNiche | null>(null);
  const [laporanLoading, setLaporanLoading] = useState(false);
  const [mulaiUlangLoading, setMulaiUlangLoading] = useState(false);

  useEffect(() => {
    let batal = false;
    (async () => {
      setLoading(true);
      const { data, demo: isDemo } = await apiOrDemo<Interview>(
        async () => {
          const dibuat = await api.post<{ id: string; current_step: number; status: string }>(
            `/content/brands/${brandId}/niche/interviews`, {}
          );
          return api.get<Interview>(`/content/niche/interviews/${dibuat.id}`);
        },
        () => ({
          id: "interview-demo-1",
          brand_id: brandId,
          current_step: 0,
          answers: {},
          skipped: [],
          status: "berjalan",
          questions: demoNicheQuestions,
        })
      );
      if (batal) return;
      setInterview(data);
      setDemo(isDemo);
      if (data.status === "selesai") {
        setFase("selesai");
      } else {
        const idx = Math.min(data.current_step, data.questions.length - 1);
        setPosisi(idx);
        setDraf(drafAwal(data.questions[idx], data.answers[data.questions[idx].key]));
      }
      setLoading(false);
    })();
    return () => {
      batal = true;
    };
  }, [brandId]);

  const kartu: InterviewQuestion | undefined = interview?.questions[posisi];
  const total = interview?.questions.length ?? TOTAL_KARTU;

  function keKartu(idx: number) {
    if (!interview) return;
    const q = interview.questions[idx];
    setPosisi(idx);
    setDraf(drafAwal(q, interview.answers[q.key]));
    setPesanElaborasi("");
    setError("");
  }

  async function simpanJawaban() {
    if (!interview || !kartu) return;
    const salah = validasiKlien(kartu, draf);
    if (salah) {
      setError(salah);
      return;
    }
    setMenyimpan(true);
    setError("");
    setPesanElaborasi("");
    try {
      const jawaban = jawabanDariDraf(kartu, draf);
      if (demo) {
        // Mode demo: simpan lokal, tanpa elaborasi.
        const next = salinInterview(interview);
        (next.answers as Record<string, unknown>)[kartu.key] = jawaban;
        next.skipped = next.skipped.filter((k) => k !== kartu.key);
        next.current_step = posisi + 1;
        if (next.current_step >= total) next.status = "selesai";
        setInterview(next);
        if (next.current_step >= total) {
          setFase("selesai");
        } else {
          keKartuDengan(next, next.current_step);
        }
      } else {
        const hasil = await api.post<JawabResult>(
          `/content/niche/interviews/${interview.id}/jawab`,
          { step: posisi, jawaban, dilewati: false }
        );
        const next = salinInterview(interview);
        (next.answers as Record<string, unknown>)[kartu.key] = jawaban;
        next.skipped = next.skipped.filter((k) => k !== kartu.key);
        if (hasil.status === "butuh_elaborasi") {
          setPesanElaborasi(
            "Jawabanmu masih terlalu umum — coba elaborasi lebih detail: siapa tepatnya, contoh konkretnya apa, dan kenapa itu penting bagimu."
          );
          setInterview(next);
        } else {
          next.current_step = hasil.next_step;
          if (hasil.next_step >= total) {
            next.status = "selesai";
            setInterview(next);
            setFase("selesai");
          } else {
            setInterview(next);
            keKartuDengan(next, hasil.next_step);
          }
        }
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal menyimpan jawaban.");
    } finally {
      setMenyimpan(false);
    }
  }

  function keKartuDengan(iv: Interview, idx: number) {
    const q = iv.questions[idx];
    setPosisi(idx);
    setDraf(drafAwal(q, iv.answers[q.key]));
    setPesanElaborasi("");
    setError("");
  }

  async function lewatiKartu() {
    if (!interview || !kartu || kartu.wajib) return;
    setMenyimpan(true);
    setError("");
    try {
      if (demo) {
        const next = salinInterview(interview);
        delete (next.answers as Record<string, unknown>)[kartu.key];
        if (!next.skipped.includes(kartu.key)) next.skipped.push(kartu.key);
        next.current_step = posisi + 1;
        if (next.current_step >= total) next.status = "selesai";
        setInterview(next);
        if (next.current_step >= total) setFase("selesai");
        else keKartuDengan(next, next.current_step);
      } else {
        const hasil = await api.post<JawabResult>(
          `/content/niche/interviews/${interview.id}/jawab`,
          { step: posisi, dilewati: true }
        );
        const next = salinInterview(interview);
        delete (next.answers as Record<string, unknown>)[kartu.key];
        if (!next.skipped.includes(kartu.key)) next.skipped.push(kartu.key);
        next.current_step = hasil.next_step;
        if (hasil.next_step >= total) {
          next.status = "selesai";
          setInterview(next);
          setFase("selesai");
        } else {
          setInterview(next);
          keKartuDengan(next, hasil.next_step);
        }
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal melewati kartu.");
    } finally {
      setMenyimpan(false);
    }
  }

  async function mulaiUlang() {
    if (!interview) return;
    if (!window.confirm("Mulai ulang kuesioner? Semua jawaban yang sudah diisi akan dibuang.")) return;
    setMulaiUlangLoading(true);
    setError("");
    try {
      if (demo) {
        const next = salinInterview(interview);
        next.answers = {};
        next.skipped = [];
        next.current_step = 0;
        next.status = "berjalan";
        setInterview(next);
        setLaporan(null);
        setFase("kartu");
        keKartuDengan(next, 0);
      } else {
        await api.post(`/content/niche/interviews/${interview.id}/mulai-ulang`, {});
        const segar = await api.get<Interview>(`/content/niche/interviews/${interview.id}`);
        setInterview(segar);
        setLaporan(null);
        setFase("kartu");
        keKartuDengan(segar, 0);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal memulai ulang.");
    } finally {
      setMulaiUlangLoading(false);
    }
  }

  async function muatLaporan() {
    if (!interview) return;
    setLaporanLoading(true);
    setError("");
    try {
      const { data, demo: isDemo } = await apiOrDemo<LaporanNiche>(
        () => api.post<LaporanNiche>(`/content/niche/interviews/${interview.id}/laporan`, {}),
        () => buatLaporanDemo((interview.answers ?? {}) as Record<string, unknown>)
      );
      setLaporan(data);
      setDemo((d) => d || isDemo);
      setFase("laporan");
      window.scrollTo({ top: 0 });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal menyusun laporan.");
    } finally {
      setLaporanLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        <Spinner label="Menyiapkan Niche Finder…" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Niche Finder"
        subtitle="Jawab 11 kartu, dapatkan laporan strategi niche 13 bagian + skor kekuatan niche."
        action={<DemoBadge tampil={demo} />}
      />
      <BrandNav brandId={brandId} />
      {error && (
        <div className="mb-4">
          <Alert kind="error">{error}</Alert>
        </div>
      )}

      {fase === "kartu" && interview && kartu && (
        <KartuView
          kartu={kartu}
          posisi={posisi}
          total={total}
          draf={draf}
          setDraf={setDraf}
          menyimpan={menyimpan}
          pesanElaborasi={pesanElaborasi}
          mulaiUlangLoading={mulaiUlangLoading}
          onSimpan={simpanJawaban}
          onLewati={lewatiKartu}
          onKembali={() => posisi > 0 && keKartu(posisi - 1)}
          onMulaiUlang={mulaiUlang}
        />
      )}

      {fase === "selesai" && (
        <Card className="border-orange-200 bg-gradient-to-br from-orange-50 via-amber-50 to-white text-center">
          <p className="text-4xl" aria-hidden>🎯</p>
          <h2 className="mt-3 text-xl font-bold text-slate-900">
            Kuesioner selesai!
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-slate-600">
            Semua kartu sudah terisi. Sekarang susun laporan strategi niche kamu —
            13 bagian lengkap plus skor kekuatan niche.
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <Button onClick={muatLaporan} disabled={laporanLoading}>
              {laporanLoading ? "Menyusun laporan…" : "Lihat Laporan Saya"}
            </Button>
            <Button variant="secondary" onClick={mulaiUlang} disabled={mulaiUlangLoading}>
              {mulaiUlangLoading ? "Memproses…" : "Mulai Ulang"}
            </Button>
          </div>
        </Card>
      )}

      {fase === "laporan" && laporan && (
        <LaporanView laporan={laporan} onMulaiUlang={mulaiUlang} mulaiUlangLoading={mulaiUlangLoading} />
      )}
    </div>
  );
}

// ============================================================
// Tampilan kartu kuesioner
// ============================================================

function KartuView(props: {
  kartu: InterviewQuestion;
  posisi: number;
  total: number;
  draf: Draf;
  setDraf: (v: Draf) => void;
  menyimpan: boolean;
  pesanElaborasi: string;
  mulaiUlangLoading: boolean;
  onSimpan: () => void;
  onLewati: () => void;
  onKembali: () => void;
  onMulaiUlang: () => void;
}) {
  const { kartu, posisi, total, draf, setDraf, menyimpan, pesanElaborasi, mulaiUlangLoading,
    onSimpan, onLewati, onKembali, onMulaiUlang } = props;
  const persen = Math.round((posisi / total) * 100);

  return (
    <div>
      {/* Progress */}
      <div className="mb-5">
        <div className="mb-1.5 flex items-center justify-between text-sm">
          <span className="font-semibold text-slate-800">
            Kartu {posisi + 1} dari {total}
          </span>
          <span className="flex items-center gap-2">
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
              kartu.wajib
                ? "bg-orange-100 text-orange-800"
                : "bg-slate-100 text-slate-600"
            }`}>
              {kartu.wajib ? "Wajib diisi" : "Opsional"}
            </span>
            <span className="text-slate-500">{persen}%</span>
          </span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-orange-100">
          <div
            className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-600 transition-all"
            style={{ width: `${persen}%` }}
          />
        </div>
        <div className="mt-2 flex gap-1.5">
          {Array.from({ length: total }).map((_, i) => (
            <span
              key={i}
              className={`h-1.5 flex-1 rounded-full ${i <= posisi ? "bg-orange-500" : "bg-orange-100"}`}
            />
          ))}
        </div>
      </div>

      <Card className="border-orange-100">
        <p className="text-xs font-semibold uppercase tracking-wide text-orange-600">
          Kartu {posisi + 1}
        </p>
        <h2 className="mt-1 text-lg font-bold leading-relaxed text-slate-900">
          {kartu.pertanyaan}
          {kartu.wajib && <span className="text-orange-600"> *</span>}
        </h2>
        {kartu.subteks && (
          <p className="mt-1 text-sm text-slate-500">{kartu.subteks}</p>
        )}

        <div className="mt-3 rounded-xl bg-amber-50 p-3 ring-1 ring-amber-100">
          <p className="text-sm text-slate-700">
            <span className="font-semibold text-amber-800">Kenapa penting: </span>
            {kartu.alasan}
          </p>
          {kartu.contoh && (
            <p className="mt-1 text-sm italic text-slate-600">Contoh: “{kartu.contoh}”</p>
          )}
        </div>

        {pesanElaborasi && (
          <div className="mt-4">
            <Alert kind="warning">{pesanElaborasi}</Alert>
          </div>
        )}

        <div className="mt-5">
          <InputKartu kartu={kartu} draf={draf} setDraf={setDraf} />
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={onKembali} disabled={menyimpan || posisi === 0}>
            ← Kembali
          </Button>
          <Button onClick={onSimpan} disabled={menyimpan}>
            {menyimpan ? "Menyimpan…" : posisi === total - 1 ? "Selesai" : "Lanjut →"}
          </Button>
          {!kartu.wajib && (
            <Button variant="ghost" onClick={onLewati} disabled={menyimpan}>
              Lewati kartu ini
            </Button>
          )}
          <span className="flex-1" />
          <button
            type="button"
            onClick={onMulaiUlang}
            disabled={mulaiUlangLoading || menyimpan}
            className="text-xs font-medium text-slate-400 hover:text-orange-600 disabled:opacity-50"
          >
            {mulaiUlangLoading ? "Memproses…" : "↺ Mulai ulang"}
          </button>
        </div>
      </Card>
    </div>
  );
}

// ============================================================
// Input per tipe kartu
// ============================================================

const FOKUS = "focus:ring-orange-500";

function InputKartu(props: { kartu: InterviewQuestion; draf: Draf; setDraf: (v: Draf) => void }) {
  const { kartu, draf, setDraf } = props;

  if (kartu.tipe === "pilihan_tunggal") {
    const nilai = draf as string | null;
    return (
      <div className="grid gap-3 sm:grid-cols-3">
        {(kartu.opsi ?? []).map((o) => {
          const aktif = nilai === o.value;
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => setDraf(aktif ? null : o.value)}
              className={`rounded-2xl border-2 p-4 text-left transition ${
                aktif
                  ? "border-orange-600 bg-orange-50 ring-2 ring-orange-200"
                  : "border-slate-200 bg-white hover:border-orange-300 hover:bg-orange-50/50"
              }`}
            >
              <p className={`font-bold ${aktif ? "text-orange-800" : "text-slate-900"}`}>{o.judul}</p>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">{o.deskripsi}</p>
            </button>
          );
        })}
      </div>
    );
  }

  if (kartu.tipe === "pilihan_ganda") {
    const d = (draf ?? { terpilih: [] }) as { terpilih: string[]; bukti?: Record<string, string> };
    const terpilih: string[] = d.terpilih ?? [];
    const bukti: Record<string, string> = d.bukti ?? {};
    const toggle = (v: string) => {
      const ada = terpilih.includes(v);
      setDraf({
        terpilih: ada ? terpilih.filter((x) => x !== v) : [...terpilih, v],
        bukti,
      });
    };
    return (
      <div className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          {(kartu.opsi ?? []).map((o) => {
            const aktif = terpilih.includes(o.value);
            return (
              <button
                key={o.value}
                type="button"
                onClick={() => toggle(o.value)}
                className={`rounded-2xl border-2 p-4 text-left transition ${
                  aktif
                    ? "border-orange-600 bg-orange-50 ring-2 ring-orange-200"
                    : "border-slate-200 bg-white hover:border-orange-300 hover:bg-orange-50/50"
                }`}
              >
                <p className="flex items-center gap-2 font-bold text-slate-900">
                  <span className={`flex h-5 w-5 items-center justify-center rounded-md border-2 text-xs font-bold text-white ${
                    aktif ? "border-orange-600 bg-orange-600" : "border-slate-300 bg-white"
                  }`}>
                    {aktif ? "✓" : ""}
                  </span>
                  <span className={aktif ? "text-orange-800" : ""}>{o.judul}</span>
                </p>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">{o.deskripsi}</p>
              </button>
            );
          })}
        </div>
        {kartu.key === "pengalaman" && terpilih.length > 0 && (
          <div className="space-y-3 rounded-2xl bg-amber-50/60 p-4 ring-1 ring-amber-100">
            {terpilih.map((v) => {
              const label = kartu.opsi?.find((o) => o.value === v)?.judul ?? v;
              return (
                <div key={v}>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700">
                    {kartu.label_bukti} — <span className="font-bold text-orange-700">{label}</span>
                  </label>
                  <textarea
                    rows={2}
                    value={bukti[v] ?? ""}
                    placeholder={kartu.placeholder_bukti}
                    onChange={(e) => setDraf({ terpilih, bukti: { ...bukti, [v]: e.target.value } })}
                    className={`w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 ${FOKUS}`}
                  />
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  if (kartu.tipe === "teks") {
    return (
      <TextArea
        label={kartu.wajib ? "Jawabanmu" : "Jawabanmu (opsional)"}
        rows={4}
        placeholder={kartu.placeholder ?? "Tulis jawaban sejujur dan sedetail mungkin…"}
        value={(draf as string) ?? ""}
        onChange={(e) => setDraf(e.target.value)}
      />
    );
  }

  if (kartu.tipe === "teks_ganda") {
    const d = (draf ?? {}) as Record<string, string>;
    return (
      <div className="space-y-4">
        {(kartu.fields ?? []).map((f) => (
          <div key={f.key}>
            <TextArea
              label={`${f.label}${f.wajib ? " *" : " (opsional)"}`}
              rows={f.key === "utama" ? 3 : 2}
              placeholder={f.placeholder}
              value={d[f.key] ?? ""}
              onChange={(e) => setDraf({ ...d, [f.key]: e.target.value })}
            />
          </div>
        ))}
      </div>
    );
  }

  if (kartu.tipe === "kreator") {
    const slots = (draf ?? []) as { username: string; alasan: string }[];
    const labelSlot = ["Kreator inspirasi 1 · Utama", "Kreator inspirasi 2 · Opsional", "Kreator inspirasi 3 · Opsional"];
    return (
      <div className="space-y-4">
        {slots.map((s, i) => (
          <div key={i} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
            <p className="mb-2 text-sm font-bold text-slate-800">{labelSlot[i]}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label="Username"
                placeholder={kartu.placeholder_username}
                value={s.username}
                onChange={(e) => {
                  const next = [...slots];
                  next[i] = { ...next[i], username: e.target.value };
                  setDraf(next);
                }}
              />
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Kenapa suka</label>
                <textarea
                  rows={2}
                  placeholder={kartu.placeholder_alasan}
                  value={s.alasan}
                  onChange={(e) => {
                    const next = [...slots];
                    next[i] = { ...next[i], alasan: e.target.value };
                    setDraf(next);
                  }}
                  className={`w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 ${FOKUS}`}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (kartu.tipe === "kata") {
    const kata = (draf ?? []) as string[];
    return (
      <div className="grid grid-cols-3 gap-3">
        {kata.map((k, i) => (
          <div key={i}>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Kata {i + 1}{i === 0 ? " *" : ""}
            </label>
            <input
              value={k}
              placeholder={["praktis", "hangat", "berbukti"][i]}
              onChange={(e) => {
                const next = [...kata];
                next[i] = e.target.value;
                setDraf(next);
              }}
              className={`w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-center text-sm font-semibold text-slate-900 placeholder:font-normal placeholder:text-slate-400 focus:outline-none focus:ring-2 ${FOKUS}`}
            />
          </div>
        ))}
      </div>
    );
  }

  return null;
}

// ============================================================
// Tampilan laporan 13 bagian
// ============================================================

function gradeTone(grade: string): string {
  switch (grade) {
    case "A": return "bg-emerald-100 text-emerald-800 ring-emerald-200";
    case "B": return "bg-amber-100 text-amber-800 ring-amber-200";
    case "C": return "bg-yellow-100 text-yellow-800 ring-yellow-200";
    default: return "bg-red-100 text-red-800 ring-red-200";
  }
}

function DaftarItem({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-slate-700">
      {items.map((t, i) => <li key={i}>{t}</li>)}
    </ul>
  );
}

function LaporanView(props: { laporan: LaporanNiche; onMulaiUlang: () => void; mulaiUlangLoading: boolean }) {
  const { laporan, onMulaiUlang, mulaiUlangLoading } = props;
  const b = laporan.bagian;
  const s = (k: string) => (b[k] ?? {}) as Record<string, unknown>;
  const str = (v: unknown) => (typeof v === "string" ? v : "");
  const arr = (v: unknown) => (Array.isArray(v) ? v : []) as unknown[];

  const ringkasan = s("ringkasan");
  const temuan = s("temuan_akun");
  const kemas = s("pengemasan_konten");
  const target = s("target_market");
  const positioning = s("positioning");
  const transisi = s("strategi_transisi");
  const pilar = s("pilar_konten");
  const ide = s("ide_siap_posting");
  const bio = s("opsi_bio");
  const kuat = s("kekuatan_niche");
  const swot = s("swot");
  const minggu = s("minggu_pertama");
  const simpulan = s("kesimpulan");

  const judulBagian = (v: unknown, def: string) => str((v as Record<string, unknown>)?.judul) || def;

  return (
    <div className="space-y-5">
      {/* Kepala laporan + skor (Bagian 1: Ringkasan) */}
      <Card className="border-orange-200 bg-gradient-to-br from-orange-50 via-amber-50 to-white">
        <h3 className="mb-3 text-base font-bold text-slate-900">Ringkasan</h3>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-orange-600">
              Laporan Niche Finder · {laporan.tujuan_label}
            </p>
            <h2 className="mt-1 text-xl font-bold leading-snug text-slate-900">
              {str(ringkasan.niche_utama)}
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600">
              {str(ringkasan.kalimat)}
            </p>
          </div>
          <div className="text-center">
            <span className={`inline-block rounded-2xl px-5 py-3 text-3xl font-black ring-2 ${gradeTone(laporan.skor.grade)}`}>
              {laporan.skor.grade}
            </span>
            <p className="mt-1 text-xs font-semibold text-slate-500">
              {laporan.skor.total}/{laporan.skor.maksimal}
            </p>
          </div>
        </div>
        <p className="mt-3 text-xs italic leading-relaxed text-slate-500">
          {str(ringkasan.disclaimer)}
        </p>
      </Card>

      {/* 5 dimensi skor */}
      <Card>
        <h3 className="mb-3 text-base font-bold text-slate-900">
          {judulBagian(kuat, "Kekuatan niche")}
        </h3>
        <div className="space-y-3">
          {(arr(kuat.dimensi) as { label: string; skor: number; maksimal: number; alasan: string }[]).map((d) => (
            <div key={d.label}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-800">{d.label}</span>
                <span className="font-bold text-orange-700">{d.skor}/{d.maksimal}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-orange-100">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-600"
                  style={{ width: `${(d.skor / d.maksimal) * 100}%` }}
                />
              </div>
              <p className="mt-0.5 text-xs text-slate-500">{d.alasan}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm font-medium text-amber-900 ring-1 ring-amber-100">
          {str(kuat.ringkasan)}
        </p>
      </Card>

      {/* Temuan akun */}
      <Card>
        <div className="mb-2 flex items-center gap-2">
          <h3 className="text-base font-bold text-slate-900">{judulBagian(temuan, "Temuan akun")}</h3>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
            temuan.sumber === "DATA" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
          }`}>
            {str(temuan.sumber)}
          </span>
        </div>
        <p className="text-sm leading-relaxed text-slate-700">{str(temuan.narasi)}</p>
        {temuan.mode === "data" && (
          <div className="mt-3">
            <p className="text-sm text-slate-600">
              Total konten dinilai: <strong>{String(temuan.total_konten ?? 0)}</strong> ·
              Menang: <strong className="text-emerald-700">{String(temuan.konten_menang ?? 0)}</strong>
            </p>
            {(arr(temuan.pola_menang) as { format: string; tujuan: string; jumlah_menang: number }[]).length > 0 && (
              <ul className="mt-2 space-y-1.5">
                {(arr(temuan.pola_menang) as { format: string; tujuan: string; jumlah_menang: number }[]).map((p, i) => (
                  <li key={i} className="rounded-xl bg-orange-50 px-3 py-2 text-sm text-slate-700 ring-1 ring-orange-100">
                    Format <strong>{p.format}</strong> · tujuan <strong>{p.tujuan}</strong> — {p.jumlah_menang} menang
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-sm italic text-slate-500">{str(temuan.yang_dihentikan)}</p>
          </div>
        )}
        {temuan.mode !== "data" && (arr(temuan.yang_dilacak) as string[]).length > 0 && (
          <div className="mt-3">
            <p className="mb-1 text-sm font-semibold text-slate-800">Yang perlu dilacak 30 hari ke depan:</p>
            <DaftarItem items={(arr(temuan.yang_dilacak) as string[])} />
          </div>
        )}
      </Card>

      {/* Pengemasan konten */}
      <Card>
        <h3 className="mb-3 text-base font-bold text-slate-900">{judulBagian(kemas, "Pengemasan konten")}</h3>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-xl bg-orange-50 p-3 ring-1 ring-orange-100">
            <p className="mb-1 text-xs font-bold uppercase tracking-wide text-orange-700">Hook</p>
            <DaftarItem items={(arr(kemas.hook) as string[])} />
          </div>
          <div className="rounded-xl bg-amber-50 p-3 ring-1 ring-amber-100">
            <p className="mb-1 text-xs font-bold uppercase tracking-wide text-amber-700">CTA</p>
            <DaftarItem items={(arr(kemas.cta) as string[])} />
          </div>
          <div className="rounded-xl bg-yellow-50 p-3 ring-1 ring-yellow-100">
            <p className="mb-1 text-xs font-bold uppercase tracking-wide text-yellow-700">Optimasi</p>
            <DaftarItem items={(arr(kemas.optimasi) as string[])} />
          </div>
        </div>
        <div className="mt-3 grid gap-3 text-sm md:grid-cols-2">
          <p className="rounded-xl bg-slate-50 p-3 text-slate-700 ring-1 ring-slate-100">
            <span className="font-semibold">Inspirasi gaya: </span>{str(kemas.inspirasi_gaya)}
          </p>
          <p className="rounded-xl bg-slate-50 p-3 text-slate-700 ring-1 ring-slate-100">
            <span className="font-semibold">Pantangan: </span>{str(kemas.pantangan)}
          </p>
        </div>
      </Card>

      {/* Target market */}
      <Card>
        <h3 className="mb-3 text-base font-bold text-slate-900">{judulBagian(target, "Target market")}</h3>
        <p className="rounded-xl bg-orange-50 p-3 text-sm font-semibold text-orange-900 ring-1 ring-orange-100">
          “{str(target.kalimat_niche)}”
        </p>
        <dl className="mt-3 space-y-2 text-sm">
          <div><dt className="font-semibold text-slate-800">Siapa mereka</dt><dd className="text-slate-600">{str(target.siapa)}</dd></div>
          <div><dt className="font-semibold text-slate-800">Masalah mereka</dt><dd className="text-slate-600">{str(target.masalah_mereka)}</dd></div>
          <div><dt className="font-semibold text-slate-800">Tujuan mereka</dt><dd className="text-slate-600">{str(target.tujuan_mereka)}</dd></div>
        </dl>
      </Card>

      {/* Positioning */}
      <Card>
        <h3 className="mb-3 text-base font-bold text-slate-900">{judulBagian(positioning, "Positioning")}</h3>
        <div className="grid gap-3 md:grid-cols-3">
          {(arr(positioning.opsi) as { nama: string; deskripsi: string; pembeda: string; risiko: string }[]).map((o, i) => (
            <div key={i} className="rounded-2xl border-2 border-orange-100 bg-gradient-to-b from-orange-50/60 to-white p-4">
              <p className="font-bold text-orange-800">{o.nama}</p>
              <p className="mt-1 text-sm leading-relaxed text-slate-700">{o.deskripsi}</p>
              <p className="mt-2 text-xs text-slate-600"><span className="font-semibold text-emerald-700">Pembeda: </span>{o.pembeda}</p>
              <p className="mt-1 text-xs text-slate-600"><span className="font-semibold text-red-600">Risiko: </span>{o.risiko}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Strategi transisi */}
      <Card>
        <h3 className="mb-1 text-base font-bold text-slate-900">{judulBagian(transisi, "Strategi transisi")}</h3>
        <p className="mb-3 inline-block rounded-full bg-orange-100 px-3 py-1 text-sm font-bold text-orange-800">
          {str(transisi.nama)}
        </p>
        <p className="text-sm leading-relaxed text-slate-700">{str(transisi.kenapa_cocok)}</p>
        <p className="mb-1 mt-3 text-sm font-semibold text-slate-800">Cara menjalankan:</p>
        <DaftarItem items={(arr(transisi.cara_jalan) as string[])} />
        <p className="mb-1 mt-3 text-sm font-semibold text-slate-800">Yang perlu diwaspadai:</p>
        <DaftarItem items={(arr(transisi.yang_perlu_diwaspadai) as string[])} />
      </Card>

      {/* Pilar konten */}
      <Card>
        <div className="mb-3 flex items-center gap-2">
          <h3 className="text-base font-bold text-slate-900">{judulBagian(pilar, "Pilar konten")}</h3>
          <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-800">
            {str(pilar.fase)}
          </span>
        </div>
        <div className="space-y-3">
          {(arr(pilar.mix) as { nama: string; porsi: number; keterangan: string }[]).map((m, i) => (
            <div key={i}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="font-semibold text-slate-800">{m.nama}</span>
                <span className="font-bold text-orange-700">{m.porsi}%</span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-orange-100">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-600"
                  style={{ width: `${m.porsi}%` }}
                />
              </div>
              <p className="mt-0.5 text-xs text-slate-500">{m.keterangan}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Ide siap posting */}
      <Card>
        <h3 className="mb-3 text-base font-bold text-slate-900">{judulBagian(ide, "Ide siap posting")}</h3>
        <div className="space-y-3">
          {(arr(ide.ide) as { judul: string; hook: string; format: string; cta: string; tips: string }[]).map((d, i) => (
            <div key={i} className="rounded-2xl border border-slate-200 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-bold text-slate-900">{i + 1}. {d.judul}</p>
                <span className="rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-semibold text-orange-800">
                  {d.format}
                </span>
              </div>
              <p className="mt-1.5 text-sm text-slate-700"><span className="font-semibold">Hook: </span>“{d.hook}”</p>
              <p className="mt-1 text-sm text-slate-700"><span className="font-semibold">CTA: </span>{d.cta}</p>
              <p className="mt-1 text-xs italic text-slate-500">💡 {d.tips}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Opsi bio */}
      <Card>
        <h3 className="mb-1 text-base font-bold text-slate-900">{judulBagian(bio, "Opsi bio")}</h3>
        <p className="mb-3 text-xs italic text-slate-500">{str(bio.catatan)}</p>
        <div className="grid gap-3 md:grid-cols-3">
          {(arr(bio.opsi) as { nama: string; baris: string[]; nada: string }[]).map((o, i) => (
            <div key={i} className="rounded-2xl bg-slate-900 p-4 text-white">
              <p className="mb-2 text-xs font-bold uppercase tracking-wide text-amber-400">{o.nama}</p>
              {(o.baris as string[]).map((br, j) => (
                <p key={j} className="text-sm leading-relaxed">{br}</p>
              ))}
              <p className="mt-2 border-t border-white/15 pt-2 text-xs italic text-slate-300">{o.nada}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* SWOT */}
      <Card>
        <h3 className="mb-3 text-base font-bold text-slate-900">{judulBagian(swot, "SWOT")}</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          {([
            ["Kekuatan", swot.kekuatan, "bg-emerald-50 ring-emerald-100 text-emerald-800"],
            ["Kelemahan", swot.kelemahan, "bg-red-50 ring-red-100 text-red-800"],
            ["Peluang", swot.peluang, "bg-amber-50 ring-amber-100 text-amber-800"],
            ["Ancaman", swot.ancaman, "bg-orange-50 ring-orange-100 text-orange-800"],
          ] as [string, unknown, string][]).map(([label, isi, tone]) => (
            <div key={label} className={`rounded-2xl p-4 ring-1 ${tone}`}>
              <p className="mb-1.5 text-sm font-bold">{label}</p>
              <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed text-slate-700">
                {(arr(isi) as string[]).map((t, i) => <li key={i}>{t}</li>)}
              </ul>
            </div>
          ))}
        </div>
      </Card>

      {/* Minggu pertama */}
      <Card>
        <h3 className="mb-3 text-base font-bold text-slate-900">{judulBagian(minggu, "Minggu pertama")}</h3>
        <div className="space-y-3">
          {(arr(minggu.aksi) as { judul: string; detail: string; level: string }[]).map((a, i) => (
            <div key={i} className="flex items-start gap-3 rounded-2xl border border-slate-200 p-4">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-orange-600 text-sm font-bold text-white">
                {i + 1}
              </span>
              <div className="flex-1">
                <p className="flex flex-wrap items-center gap-2 font-bold text-slate-900">
                  {a.judul}
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                    a.level === "Gampang" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                  }`}>
                    {a.level}
                  </span>
                </p>
                <p className="mt-1 text-sm leading-relaxed text-slate-600">{a.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Kesimpulan */}
      <Card className="border-orange-200 bg-gradient-to-br from-orange-50 to-amber-50">
        <h3 className="mb-3 text-base font-bold text-slate-900">{judulBagian(simpulan, "Kesimpulan")}</h3>
        <dl className="space-y-2.5 text-sm">
          <div>
            <dt className="font-semibold text-slate-800">A · Niche kamu</dt>
            <dd className="text-slate-700">{str(simpulan.niche)}</dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-800">B · Seberapa kuat niche-nya</dt>
            <dd>
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ring-1 ${gradeTone(String(simpulan.grade).charAt(0))}`}>
                Grade {str(simpulan.grade)}
              </span>
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-800">C · Arah selanjutnya</dt>
            <dd className="text-slate-700">{str(simpulan.arah_selanjutnya)}</dd>
          </div>
          <div>
            <dt className="font-semibold text-slate-800">D · Langkah pertama</dt>
            <dd className="font-medium text-orange-800">{str(simpulan.langkah_pertama)}</dd>
          </div>
        </dl>
        <div className="mt-5">
          <Button variant="secondary" onClick={onMulaiUlang} disabled={mulaiUlangLoading}>
            {mulaiUlangLoading ? "Memproses…" : "↺ Ulangi Kuesioner"}
          </Button>
        </div>
      </Card>
    </div>
  );
}

export default function NichePage() {
  return (
    <RequireAuth>
      <NicheIsi />
    </RequireAuth>
  );
}
