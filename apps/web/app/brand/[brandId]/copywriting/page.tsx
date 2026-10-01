"use client";

import { useState } from "react";
import { useBrandId } from "@/lib/brand";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { Alert, Button, Card, Input, Select, TextArea } from "@/components/ui";

const GOALS = ["Awareness", "Edukasi", "Hiburan", "Konversi"];
const CTAS = ["Save", "Share", "Comment", "Click link konversi", "Follow"];
const GAYA = ["Casual", "Friendly", "Warm", "Formal", "Akademis", "Emotional"];
const PLATFORMS = ["Instagram", "Facebook", "TikTok", "Threads", "Blog Artikel"];
const FRAMEWORKS = [
  { value: "storybrand", label: "StoryBrand (Donald Miller)" },
  { value: "pas", label: "Problem-Agitate-Solve" },
  { value: "bab", label: "Before-After-Bridge" },
  { value: "freytag", label: "Freytag's Pyramid" },
  { value: "truth_gap", label: "The Truth Gap (Kindra Hall)" },
];

type Hasil = { hasil: string; framework: string; platform: string };

export default function CopywritingPage() {
  const brandId = useBrandId();
  const [form, setForm] = useState({
    what: "",
    who: "",
    when: "",
    where: "",
    why: "",
    how: "",
    pov: "",
    target_audiens: "",
    goals: GOALS[0],
    cta: CTAS[0],
    gaya_bahasa: GAYA[0],
    platform: PLATFORMS[0],
    framework: FRAMEWORKS[0].value,
  });
  const [hasil, setHasil] = useState<Hasil | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function set(k: keyof typeof form, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function generate() {
    if (!form.what.trim()) {
      setError("Kolom 'What' wajib diisi dulu.");
      return;
    }
    setLoading(true);
    setError("");
    setHasil(null);
    try {
      const r = await api.post<Hasil>(
        `/content/brands/${brandId}/copywriting/generate`,
        form
      );
      setHasil(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal generate copywriting.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <RequireAuth>
      <div className="mx-auto max-w-3xl px-4 py-6">
        <h1 className="text-xl font-bold text-slate-900">Copywriting Generator</h1>
        <p className="mt-1 text-sm text-slate-500">
          Isi brief 5W1H, pilih framework storytelling, dan dapatkan draf copywriting siap posting.
        </p>

        <Card className="mt-5">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">5W1H</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <TextArea label="What * — tentang apa konten ini?" value={form.what} onChange={(e) => set("what", e.target.value)} rows={2} placeholder="Contoh: program donasi buku untuk anak pelosok" />
            </div>
            <Input label="Who — siapa yang terlibat?" value={form.who} onChange={(e) => set("who", e.target.value)} placeholder="Contoh: relawan dan donatur" />
            <Input label="When — kapan?" value={form.when} onChange={(e) => set("when", e.target.value)} placeholder="Contoh: bulan Ramadan" />
            <Input label="Where — di mana?" value={form.where} onChange={(e) => set("where", e.target.value)} placeholder="Contoh: desa terpencil di NTT" />
            <Input label="Why — kenapa ini penting?" value={form.why} onChange={(e) => set("why", e.target.value)} placeholder="Contoh: anak-anak kekurangan bahan bacaan" />
            <div className="sm:col-span-2">
              <TextArea label="How — bagaimana caranya?" value={form.how} onChange={(e) => set("how", e.target.value)} rows={2} placeholder="Contoh: donasi Rp25rb = 1 paket buku" />
            </div>
          </div>
        </Card>

        <Card className="mt-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-900">Konteks & Gaya</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <TextArea label="POV — sudut pandang brand" value={form.pov} onChange={(e) => set("pov", e.target.value)} rows={2} placeholder="Contoh: kami percaya setiap anak berhak membaca" />
            </div>
            <div className="sm:col-span-2">
              <Input label="Target audiens" value={form.target_audiens} onChange={(e) => set("target_audiens", e.target.value)} placeholder="Contoh: ibu muda 25-35 tahun, peduli pendidikan" />
            </div>
            <Select label="Goals" value={form.goals} onChange={(e) => set("goals", e.target.value)}>
              {GOALS.map((g) => <option key={g} value={g}>{g}</option>)}
            </Select>
            <Select label="CTA" value={form.cta} onChange={(e) => set("cta", e.target.value)}>
              {CTAS.map((c) => <option key={c} value={c}>{c}</option>)}
            </Select>
            <Select label="Gaya bahasa" value={form.gaya_bahasa} onChange={(e) => set("gaya_bahasa", e.target.value)}>
              {GAYA.map((g) => <option key={g} value={g}>{g}</option>)}
            </Select>
            <Select label="Platform" value={form.platform} onChange={(e) => set("platform", e.target.value)}>
              {PLATFORMS.map((p) => <option key={p} value={p}>{p}</option>)}
            </Select>
            <div className="sm:col-span-2">
              <Select label="Framework storytelling" value={form.framework} onChange={(e) => set("framework", e.target.value)}>
                {FRAMEWORKS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
              </Select>
            </div>
          </div>
        </Card>

        <div className="mt-3">{error && <Alert kind="error">{error}</Alert>}</div>

        <Button onClick={generate} disabled={loading} className="mt-4">
          {loading ? "Menulis…" : "Generate Copywriting"}
        </Button>

        {hasil && (
          <Card className="mt-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-900">Hasil — {hasil.framework}</h2>
              <span className="text-xs text-slate-500">{hasil.platform}</span>
            </div>
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{hasil.hasil}</div>
            <Button
              variant="secondary"
              className="mt-3"
              onClick={() => navigator.clipboard.writeText(hasil.hasil)}
            >
              Salin Teks
            </Button>
          </Card>
        )}
      </div>
    </RequireAuth>
  );
}
