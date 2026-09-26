"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import {
  Alert,
  Button,
  Card,
  EmptyBox,
  Input,
  PageHeader,
  Select,
  Spinner,
} from "@/components/ui";

// ---------- Tipe kontrak backend ----------
interface StatusOnboarding {
  ada: boolean;
  langkah_terakhir: number;
  selesai: boolean;
  ditutup: boolean;
}

interface TemplateThreshold {
  tiktok_wer: number;
  instagram_wer: number;
  skor_menang: number;
  skor_cukup: number;
}

interface PreviewKemenangan {
  menang: number;
  total: number;
  per_platform: {
    tiktok: { menang: number; total: number };
    instagram: { menang: number; total: number };
  };
}

interface AkunKoneksi {
  id: string;
  platform: "tiktok" | "instagram";
  account_name: string;
  status: string;
}

type Platform = "tiktok" | "instagram";

const KATEGORI = [
  { value: "ngo/filantropi", label: "NGO / Filantropi" },
  { value: "kuliner", label: "Kuliner" },
  { value: "fashion", label: "Fashion" },
  { value: "edukasi", label: "Edukasi" },
  { value: "kesehatan", label: "Kesehatan" },
  { value: "jasa", label: "Jasa" },
  { value: "lainnya", label: "Lainnya" },
];

const NAMA_LANGKAH = [
  "Profil brand",
  "Hubungkan akun",
  "Konten menang",
  "Sinkronisasi",
];

const PLATFORM_META: Record<Platform, { label: string; ikon: string }> = {
  tiktok: { label: "TikTok", ikon: "🎵" },
  instagram: { label: "Instagram", ikon: "📸" },
};

// ---------- Helper fetch defensif ----------
// Backend onboarding dibangun paralel; bila endpoint belum ada (404),
// kembalikan takTersedia agar wizard tetap bisa dijelajahi tanpa crash.
async function panggilDefensif<T>(
  fn: () => Promise<T>
): Promise<
  | { ok: true; data: T }
  | { ok: false; takTersedia: true }
  | { ok: false; takTersedia?: false; pesan: string }
> {
  try {
    const data = await fn();
    return { ok: true, data };
  } catch (err) {
    if (err instanceof ApiError && err.status === 404)
      return { ok: false, takTersedia: true };
    return {
      ok: false,
      pesan: err instanceof ApiError ? err.message : "Terjadi kesalahan.",
    };
  }
}

function IndikatorLangkah({ aktif }: { aktif: number }) {
  return (
    <ol className="mb-8 flex items-center" aria-label="Progress onboarding">
      {NAMA_LANGKAH.map((namaLangkah, i) => {
        const n = i + 1;
        const selesai = n < aktif;
        const sedang = n === aktif;
        return (
          <li
            key={namaLangkah}
            className={`flex items-center ${
              i < NAMA_LANGKAH.length - 1 ? "flex-1" : ""
            }`}
          >
            <div className="flex items-center gap-2">
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${
                  selesai
                    ? "bg-emerald-500 text-white"
                    : sedang
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-200 text-slate-500"
                }`}
              >
                {selesai ? "✓" : n}
              </span>
              <span
                className={`hidden text-sm font-medium sm:block ${
                  sedang ? "text-slate-900" : "text-slate-500"
                }`}
              >
                {namaLangkah}
              </span>
            </div>
            {i < NAMA_LANGKAH.length - 1 && (
              <div
                className={`mx-2 h-0.5 flex-1 rounded sm:mx-3 ${
                  selesai ? "bg-emerald-400" : "bg-slate-200"
                }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

// ---------- Langkah 1: Profil brand ----------
function LangkahProfil({
  nama,
  setNama,
  kategori,
  setKategori,
  logoPreview,
  onPilihLogo,
}: {
  nama: string;
  setNama: (v: string) => void;
  kategori: string;
  setKategori: (v: string) => void;
  logoPreview: string | null;
  onPilihLogo: (f: File | null) => void;
}) {
  return (
    <Card>
      <h2 className="text-lg font-semibold text-slate-900">Profil brand</h2>
      <p className="mt-1 text-sm text-slate-500">
        Kenalkan brand Anda — nama dan kategori dipakai untuk menyesuaikan
        template konten menang.
      </p>
      <div className="mt-5 space-y-4">
        <Input
          label="Nama brand"
          placeholder="Contoh: Kopi Senja"
          value={nama}
          onChange={(e) => setNama(e.target.value)}
        />
        <Select
          label="Kategori industri"
          value={kategori}
          onChange={(e) => setKategori(e.target.value)}
        >
          {KATEGORI.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </Select>
        <div>
          <span className="mb-1.5 block text-sm font-medium text-slate-700">
            Logo brand (opsional)
          </span>
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
              {logoPreview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={logoPreview}
                  alt="Pratinjau logo"
                  className="h-full w-full object-cover"
                />
              ) : (
                <span className="text-2xl text-slate-300">🖼️</span>
              )}
            </div>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => onPilihLogo(e.target.files?.[0] ?? null)}
              className="text-sm text-slate-600 file:mr-3 file:rounded-xl file:border file:border-slate-300 file:bg-white file:px-4 file:py-2 file:text-sm file:font-semibold file:text-slate-700 hover:file:bg-slate-50"
            />
          </div>
        </div>
      </div>
    </Card>
  );
}

// ---------- Langkah 2: Hubungkan akun ----------
function LangkahKoneksi({ brandId }: { brandId: string }) {
  const [akun, setAkun] = useState<AkunKoneksi[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sukses, setSukses] = useState("");
  const [oauthP, setOauthP] = useState<Platform | null>(null);
  const [demoP, setDemoP] = useState<Platform | null>(null);

  const muat = useCallback(async () => {
    setLoading(true);
    const r = await panggilDefensif(() =>
      api.get<AkunKoneksi[]>(`/content/brands/${brandId}/koneksi`)
    );
    if (r.ok) setAkun(r.data);
    setLoading(false);
  }, [brandId]);

  useEffect(() => {
    muat();
  }, [muat]);

  async function hubungkanOAuth(p: Platform) {
    setError("");
    setSukses("");
    // Simpan progress dulu agar alur OAuth yang me-redirect keluar
    // tidak membuat pengguna mengulang langkah ini.
    try {
      await api.put("/onboarding/progress", {
        brand_id: brandId,
        langkah: 2,
      });
    } catch {
      // abaikan — alur OAuth tetap jalan
    }
    setOauthP(p);
    try {
      const res = await api.post<{ auth_url: string }>(
        `/content/brands/${brandId}/oauth/${p}/mulai`
      );
      window.location.href = res.auth_url;
    } catch (err) {
      if (err instanceof ApiError && (err.status === 501 || err.status === 503)) {
        setError(
          "Koneksi nyata butuh kredensial — hubungi admin. Kredensial API " +
            "TikTok/Instagram belum disiapkan, jadi akun asli belum bisa " +
            "dihubungkan. Anda bisa pakai akun demo atau lewati dulu."
        );
      } else {
        setError(
          err instanceof ApiError ? err.message : "Gagal memulai koneksi."
        );
      }
      setOauthP(null);
    }
  }

  async function hubungkanDemo(p: Platform) {
    setDemoP(p);
    setError("");
    setSukses("");
    const r = await panggilDefensif(() =>
      api.post("/dev/koneksi/mock", { brand_id: brandId, platform: p })
    );
    if (r.ok) {
      setSukses(
        `Akun demo ${PLATFORM_META[p].label} terhubung. Anda bisa lanjut ke langkah berikutnya.`
      );
      await muat();
    } else if (r.takTersedia) {
      setError(
        "Mode demo hanya tersedia di environment development. Di production, " +
          "hubungkan akun asli lewat tombol di atas atau lewati dulu."
      );
    } else {
      setError(r.pesan);
    }
    setDemoP(null);
  }

  return (
    <div>
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
      <div className="grid gap-4 md:grid-cols-2">
        {(["tiktok", "instagram"] as Platform[]).map((p) => (
          <Card key={p}>
            <p className="flex items-center gap-2 text-base font-semibold text-slate-900">
              <span aria-hidden>{PLATFORM_META[p].ikon}</span>
              {PLATFORM_META[p].label}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              Hubungkan akun resmi {PLATFORM_META[p].label} brand untuk sync
              data otomatis.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                onClick={() => hubungkanOAuth(p)}
                disabled={oauthP !== null}
              >
                {oauthP === p ? "Membuka…" : `Hubungkan ${PLATFORM_META[p].label}`}
              </Button>
              <Button
                variant="secondary"
                onClick={() => hubungkanDemo(p)}
                disabled={demoP !== null}
              >
                {demoP === p ? "Menghubungkan…" : "Akun demo"}
              </Button>
            </div>
          </Card>
        ))}
      </div>
      <Card className="mt-4">
        <h3 className="text-sm font-semibold text-slate-900">
          Akun yang sudah terhubung ({akun.length})
        </h3>
        {loading && <Spinner label="Memuat akun…" />}
        {!loading && akun.length === 0 && (
          <p className="mt-2 text-sm text-slate-500">
            Belum ada akun terhubung — tidak apa-apa, langkah ini boleh
            dilewati. Anda tetap bisa upload CSV nanti.
          </p>
        )}
        {!loading && akun.length > 0 && (
          <ul className="mt-3 space-y-2">
            {akun.map((a) => (
              <li
                key={a.id}
                className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-2.5 text-sm"
              >
                <span className="font-medium text-slate-800">
                  <span aria-hidden className="mr-2">
                    {PLATFORM_META[a.platform]?.ikon ?? "🔗"}
                  </span>
                  {a.account_name}
                </span>
                <span className="text-xs text-slate-500">{a.status}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

// ---------- Langkah 3: Definisi konten menang ----------
function LangkahKemenangan({
  brandId,
  kategori,
}: {
  brandId: string;
  kategori: string;
}) {
  const [tiktokWer, setTiktokWer] = useState(8); // persen, tampilan UI
  const [igWer, setIgWer] = useState(5); // persen, tampilan UI
  const [skorMenang, setSkorMenang] = useState<number | null>(null);
  const [skorCukup, setSkorCukup] = useState<number | null>(null);
  const [memuat, setMemuat] = useState(true);
  const [templateAda, setTemplateAda] = useState(true);
  const [preview, setPreview] = useState<PreviewKemenangan | null>(null);
  const [pratinjauLoading, setPratinjauLoading] = useState(false);
  const [belumAdaData, setBelumAdaData] = useState(false);

  useEffect(() => {
    let batal = false;
    (async () => {
      const r = await panggilDefensif(() =>
        api.get<TemplateThreshold>(
          `/onboarding/template-threshold?kategori=${encodeURIComponent(kategori)}`
        )
      );
      if (batal) return;
      if (r.ok) {
        // Backend mengirim rasio 0-1; UI memakai persen.
        setTiktokWer(Math.round((r.data.tiktok_wer ?? 0.08) * 1000) / 10);
        setIgWer(Math.round((r.data.instagram_wer ?? 0.05) * 1000) / 10);
        setSkorMenang(r.data.skor_menang ?? null);
        setSkorCukup(r.data.skor_cukup ?? null);
        setTemplateAda(true);
      } else {
        setTemplateAda(false);
      }
      setMemuat(false);
    })();
    return () => {
      batal = true;
    };
  }, [kategori]);

  async function pratinjau() {
    setPratinjauLoading(true);
    setPreview(null);
    setBelumAdaData(false);
    const r = await panggilDefensif(() =>
      api.post<PreviewKemenangan>("/onboarding/preview-kemenangan", {
        brand_id: brandId,
        draft: { tiktok_wer: tiktokWer / 100, instagram_wer: igWer / 100 },
      })
    );
    if (r.ok) {
      setPreview(r.data);
    } else {
      // Jujur: entah belum ada konten terskor atau layanan belum siap.
      setBelumAdaData(true);
    }
    setPratinjauLoading(false);
  }

  return (
    <Card>
      <h2 className="text-lg font-semibold text-slate-900">
        Definisi konten menang
      </h2>
      <p className="mt-1 text-sm text-slate-500">
        Tentukan ambang weighted engagement rate (WER) per platform. Geser
        slider lalu klik Pratinjau untuk melihat dampaknya ke konten Anda —
        <span className="font-medium"> langkah ini hanya pratinjau</span>,
        belum menyimpan pengaturan permanen.
      </p>

      {memuat && <Spinner label="Memuat template kategori…" />}

      {!memuat && !templateAda && (
        <div className="mt-4">
          <Alert kind="warning">
            Template kategori belum bisa dimuat (kategori:{" "}
            {KATEGORI.find((k) => k.value === kategori)?.label ?? kategori}).
            Nilai awal di bawah adalah bawaan umum — silakan sesuaikan manual.
          </Alert>
        </div>
      )}

      {!memuat && (
        <div className="mt-6 space-y-6">
          <div>
            <div className="mb-2 flex items-center justify-between">
              <label
                htmlFor="wer-tiktok"
                className="text-sm font-medium text-slate-700"
              >
                🎵 Ambang WER TikTok
              </label>
              <span className="rounded-lg bg-indigo-50 px-3 py-1 text-sm font-bold text-indigo-700">
                {tiktokWer.toLocaleString("id-ID")}%
              </span>
            </div>
            <input
              id="wer-tiktok"
              type="range"
              min={0}
              max={20}
              step={0.5}
              value={tiktokWer}
              onChange={(e) => setTiktokWer(Number(e.target.value))}
              className="w-full accent-indigo-600"
            />
          </div>
          <div>
            <div className="mb-2 flex items-center justify-between">
              <label
                htmlFor="wer-ig"
                className="text-sm font-medium text-slate-700"
              >
                📸 Ambang WER Instagram
              </label>
              <span className="rounded-lg bg-indigo-50 px-3 py-1 text-sm font-bold text-indigo-700">
                {igWer.toLocaleString("id-ID")}%
              </span>
            </div>
            <input
              id="wer-ig"
              type="range"
              min={0}
              max={20}
              step={0.5}
              value={igWer}
              onChange={(e) => setIgWer(Number(e.target.value))}
              className="w-full accent-indigo-600"
            />
          </div>

          {(skorMenang !== null || skorCukup !== null) && (
            <p className="text-xs text-slate-500">
              Acuan template kategori ini
              {skorMenang !== null &&
                ` · skor MENANG ≥ ${(skorMenang * 100).toLocaleString("id-ID")}%`}
              {skorCukup !== null &&
                ` · skor CUKUP ≥ ${(skorCukup * 100).toLocaleString("id-ID")}%`}
              .
            </p>
          )}

          <div>
            <Button onClick={pratinjau} disabled={pratinjauLoading}>
              {pratinjauLoading ? "Menghitung…" : "Pratinjau"}
            </Button>
          </div>

          {belumAdaData && (
            <Alert kind="info">
              Belum ada data — hubungkan akun atau upload CSV dulu agar
              pratinjau bisa dihitung dari konten terakhirmu.
            </Alert>
          )}

          {preview && (
            <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3">
              <p className="text-sm font-semibold text-indigo-900">
                Dengan setting ini, {preview.menang} dari {preview.total} konten
                terakhirmu berstatus MENANG.
              </p>
              <ul className="mt-2 space-y-1 text-sm text-indigo-800">
                <li>
                  🎵 TikTok: {preview.per_platform.tiktok.menang} dari{" "}
                  {preview.per_platform.tiktok.total} konten berstatus MENANG
                </li>
                <li>
                  📸 Instagram: {preview.per_platform.instagram.menang} dari{" "}
                  {preview.per_platform.instagram.total} konten berstatus MENANG
                </li>
              </ul>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

// ---------- Langkah 4: Sinkronisasi pertama ----------
function LangkahSync({
  brandId,
  onLihatDashboard,
}: {
  brandId: string;
  onLihatDashboard: () => void;
}) {
  const [akun, setAkun] = useState<AkunKoneksi[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [progres, setProgres] = useState({ selesai: 0, total: 0 });
  const [hasil, setHasil] = useState<
    { nama: string; ok: boolean; pesan: string }[]
  >([]);
  const [selesaiSync, setSelesaiSync] = useState(false);

  const muat = useCallback(async () => {
    setLoading(true);
    const r = await panggilDefensif(() =>
      api.get<AkunKoneksi[]>(`/content/brands/${brandId}/koneksi`)
    );
    if (r.ok) setAkun(r.data);
    setLoading(false);
  }, [brandId]);

  useEffect(() => {
    muat();
  }, [muat]);

  async function mulaiSync() {
    setSyncing(true);
    setHasil([]);
    setSelesaiSync(false);
    setProgres({ selesai: 0, total: akun.length });
    const keluar: { nama: string; ok: boolean; pesan: string }[] = [];
    for (const a of akun) {
      try {
        const r = await api.post<{
          contents_baru: number;
          contents_diupdate: number;
        }>(`/content/koneksi/${a.id}/sync`);
        keluar.push({
          nama: a.account_name,
          ok: true,
          pesan: `${r.contents_baru} konten baru, ${r.contents_diupdate} konten diperbarui.`,
        });
      } catch (err) {
        keluar.push({
          nama: a.account_name,
          ok: false,
          pesan:
            err instanceof ApiError ? err.message : "Gagal melakukan sync.",
        });
      }
      setProgres({ selesai: keluar.length, total: akun.length });
      setHasil([...keluar]);
    }
    setSelesaiSync(true);
    setSyncing(false);
  }

  const persen =
    progres.total > 0 ? Math.round((progres.selesai / progres.total) * 100) : 0;

  return (
    <Card>
      <h2 className="text-lg font-semibold text-slate-900">
        Sinkronisasi pertama
      </h2>
      <p className="mt-1 text-sm text-slate-500">
        Tarik data 90 hari terakhir dari setiap akun yang terhubung agar
        dasbor langsung terisi.
      </p>

      {loading && <Spinner label="Memuat akun…" />}

      {!loading && akun.length === 0 && (
        <div className="mt-4">
          <Alert kind="info">
            Belum ada akun terhubung — tidak apa-apa. Anda bisa kembali ke
            langkah 2 untuk menghubungkan, atau lanjut dan upload CSV dari
            halaman Upload nanti.
          </Alert>
        </div>
      )}

      {!loading && akun.length > 0 && (
        <div className="mt-5">
          <Button onClick={mulaiSync} disabled={syncing}>
            {syncing ? "Sync berjalan…" : "Mulai sync 90 hari"}
          </Button>

          {(syncing || selesaiSync) && (
            <div className="mt-4">
              <div className="mb-1 flex justify-between text-xs text-slate-500">
                <span>
                  {progres.selesai} dari {progres.total} akun
                </span>
                <span>{persen}%</span>
              </div>
              <div
                className="h-2.5 overflow-hidden rounded-full bg-slate-200"
                role="progressbar"
                aria-valuenow={persen}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="h-full rounded-full bg-indigo-600 transition-all"
                  style={{ width: `${persen}%` }}
                />
              </div>
              <ul className="mt-3 space-y-2">
                {hasil.map((h) => (
                  <li
                    key={h.nama}
                    className={`rounded-xl border px-4 py-2.5 text-sm ${
                      h.ok
                        ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                        : "border-red-200 bg-red-50 text-red-800"
                    }`}
                  >
                    <span className="font-semibold">{h.nama}</span> — {h.pesan}
                  </li>
                ))}
              </ul>
              {selesaiSync && (
                <p className="mt-3 text-sm text-slate-600">
                  Sync selesai. Klik{" "}
                  <span className="font-semibold">Lihat Dashboard</span> di bawah
                  untuk menyelesaikan onboarding.
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {!loading && akun.length === 0 && (
        <div className="mt-5">
          <Button variant="secondary" onClick={onLihatDashboard}>
            Lihat Dashboard
          </Button>
        </div>
      )}
    </Card>
  );
}

// ---------- Wizard utama ----------
function OnboardingIsi() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const brandId = searchParams.get("brand");

  const [memuatStatus, setMemuatStatus] = useState(true);
  const [backendSiap, setBackendSiap] = useState(true);
  const [langkah, setLangkah] = useState(1);
  const [error, setError] = useState("");
  const [peringatan, setPeringatan] = useState("");

  // State langkah 1 (dibutuhkan juga oleh langkah 3 untuk kategori).
  const [nama, setNama] = useState("");
  const [kategori, setKategori] = useState("lainnya");
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [menyimpan, setMenyimpan] = useState(false);
  const [menutup, setMenutup] = useState(false);
  const [menyelesaikan, setMenyelesaikan] = useState(false);

  useEffect(() => {
    if (!brandId) {
      setMemuatStatus(false);
      return;
    }
    let batal = false;
    (async () => {
      const r = await panggilDefensif(() =>
        api.get<StatusOnboarding>(
          `/onboarding/status?brand_id=${encodeURIComponent(brandId)}`
        )
      );
      if (batal) return;
      if (r.ok) {
        const s = r.data;
        if (s.selesai) {
          router.replace(`/brand/${brandId}`);
          return;
        }
        const mulai = Math.min(4, Math.max(1, (s.langkah_terakhir ?? 0) + 1));
        setLangkah(mulai);
      } else {
        // Status tak tersedia — kemungkinan layanan onboarding di server
        // belum aktif. Wizard tetap bisa dijelajahi.
        setBackendSiap(false);
        setLangkah(1);
      }
      setMemuatStatus(false);
    })();
    return () => {
      batal = true;
    };
  }, [brandId, router]);

  useEffect(() => {
    if (!logoFile) {
      setLogoPreview(null);
      return;
    }
    const url = URL.createObjectURL(logoFile);
    setLogoPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [logoFile]);

  async function simpanProgress(l: number): Promise<boolean> {
    if (!brandId) return false;
    const r = await panggilDefensif(() =>
      api.put("/onboarding/progress", { brand_id: brandId, langkah: l })
    );
    if (r.ok) return true;
    if (r.takTersedia) {
      setBackendSiap(false);
      return true; // lanjut meski belum tersimpan
    }
    setError(r.pesan);
    return false;
  }

  async function lanjutDariProfil() {
    if (!brandId) return;
    setError("");
    setPeringatan("");
    if (!nama.trim()) {
      setError("Isi nama brand dulu ya.");
      return;
    }
    setMenyimpan(true);
    // Logo (opsional) — kegagalan di sini menghentikan, kecuali 404.
    if (logoFile) {
      const form = new FormData();
      form.append("file", logoFile);
      const rLogo = await panggilDefensif(() =>
        api.postForm<{ logo_url: string }>(
          `/onboarding/brands/${brandId}/logo`,
          form
        )
      );
      if (!rLogo.ok && !rLogo.takTersedia) {
        setError(rLogo.pesan);
        setMenyimpan(false);
        return;
      }
      if (!rLogo.ok) setBackendSiap(false);
    }
    const rProfil = await panggilDefensif(() =>
      api.put(`/onboarding/brands/${brandId}/profil`, {
        nama: nama.trim(),
        kategori_industri: kategori,
      })
    );
    if (!rProfil.ok && !rProfil.takTersedia) {
      setError(rProfil.pesan);
      setMenyimpan(false);
      return;
    }
    if (!rProfil.ok) {
      setBackendSiap(false);
      setPeringatan(
        "Layanan onboarding di server belum aktif — langkah tetap bisa " +
          "dilanjutkan, profil akan tersimpan setelah server siap."
      );
    }
    if (await simpanProgress(1)) setLangkah(2);
    setMenyimpan(false);
  }

  // Lanjut generik untuk langkah 2 & 3 (langkah 2 boleh dilewati).
  async function lanjutBiasa(langkahSelesai: number, ke: number) {
    setError("");
    setMenyimpan(true);
    if (await simpanProgress(langkahSelesai)) setLangkah(ke);
    setMenyimpan(false);
  }

  async function tutup() {
    if (!brandId) return;
    setMenutup(true);
    try {
      await api.post("/onboarding/tutup", { brand_id: brandId });
    } catch {
      // abaikan — tutup tetap jalan di sisi klien
    }
    router.push(`/brand/${brandId}`);
  }

  async function selesaikan() {
    if (!brandId) return;
    setMenyelesaikan(true);
    try {
      await api.post("/onboarding/selesai", { brand_id: brandId });
    } catch {
      // abaikan — selesaikan tetap jalan di sisi klien
    }
    router.push(`/brand/${brandId}`);
  }

  if (!brandId) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
        <PageHeader title="Onboarding" subtitle="Panduan 4 langkah memulai." />
        <EmptyBox
          title="Brand belum dipilih"
          description="Pilih dulu brand yang mau di-onboarding agar wizard tahu datanya milik siapa."
          icon={
            <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 5.25h.008v.008H12v-.008Z" />
            </svg>
          }
        />
        <div className="mt-4 text-center">
          <Link href="/pilih-brand">
            <Button>Pilih brand</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Onboarding"
        subtitle="Empat langkah cepat sebelum dasbor benar-benar berguna."
      />

      {!backendSiap && !memuatStatus && (
        <div className="mb-4">
          <Alert kind="warning">
            Layanan onboarding di server belum aktif — Anda tetap bisa
            menjelajahi wizard ini, tapi progress belum tersimpan permanen.
          </Alert>
        </div>
      )}

      {memuatStatus && <Spinner label="Memuat status onboarding…" />}

      {!memuatStatus && (
        <>
          <IndikatorLangkah aktif={langkah} />

          {error && (
            <div className="mb-4">
              <Alert kind="error">{error}</Alert>
            </div>
          )}
          {peringatan && (
            <div className="mb-4">
              <Alert kind="warning">{peringatan}</Alert>
            </div>
          )}

          {langkah === 1 && (
            <LangkahProfil
              nama={nama}
              setNama={setNama}
              kategori={kategori}
              setKategori={setKategori}
              logoPreview={logoPreview}
              onPilihLogo={setLogoFile}
            />
          )}
          {langkah === 2 && <LangkahKoneksi brandId={brandId} />}
          {langkah === 3 && (
            <LangkahKemenangan brandId={brandId} kategori={kategori} />
          )}
          {langkah === 4 && (
            <LangkahSync brandId={brandId} onLihatDashboard={selesaikan} />
          )}

          <div className="mt-6 flex flex-wrap items-center gap-2">
            {langkah > 1 && (
              <Button
                variant="secondary"
                onClick={() => {
                  setError("");
                  setLangkah(langkah - 1);
                }}
                disabled={menyimpan}
              >
                ← Kembali
              </Button>
            )}
            <span className="flex-1" />
            <Button variant="ghost" onClick={tutup} disabled={menutup}>
              {menutup ? "Menutup…" : "Tutup"}
            </Button>
            {langkah === 1 && (
              <Button onClick={lanjutDariProfil} disabled={menyimpan}>
                {menyimpan ? "Menyimpan…" : "Lanjut →"}
              </Button>
            )}
            {langkah === 2 && (
              <Button
                onClick={() => lanjutBiasa(2, 3)}
                disabled={menyimpan}
              >
                {menyimpan ? "Menyimpan…" : "Lewati dulu →"}
              </Button>
            )}
            {langkah === 3 && (
              <Button onClick={() => lanjutBiasa(3, 4)} disabled={menyimpan}>
                {menyimpan ? "Menyimpan…" : "Lanjut →"}
              </Button>
            )}
            {langkah === 4 && (
              <Button onClick={selesaikan} disabled={menyelesaikan}>
                {menyelesaikan ? "Menyelesaikan…" : "Lihat Dashboard"}
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <RequireAuth>
      <Suspense fallback={<Spinner label="Memuat onboarding…" />}>
        <OnboardingIsi />
      </Suspense>
    </RequireAuth>
  );
}
