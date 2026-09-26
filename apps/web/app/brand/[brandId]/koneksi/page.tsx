"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { formatTanggal } from "@/lib/format";
import {
  Alert,
  Button,
  Card,
  EmptyBox,
  PageHeader,
  Spinner,
} from "@/components/ui";
import BrandNav from "@/components/BrandNav";

type Platform = "tiktok" | "instagram";

interface KoneksiAkun {
  id: string;
  platform: Platform;
  account_name: string;
  status: string;
  last_sync_at: string | null;
  connected_at: string;
}

interface BatasPlatform {
  terpakai: number;
  batas: number;
  boleh_tambah: boolean;
}

interface StatusKoneksi {
  platforms: Record<Platform, BatasPlatform>;
}

const PLATFORM_META: Record<Platform, { label: string; ikon: string }> = {
  tiktok: { label: "TikTok", ikon: "🎵" },
  instagram: { label: "Instagram", ikon: "📸" },
};

function badgeStatus(status: string) {
  const s = status.toLowerCase();
  const aktif = ["aktif", "connected", "tersambung"].includes(s);
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        aktif
          ? "bg-emerald-100 text-emerald-800"
          : "bg-amber-100 text-amber-800"
      }`}
    >
      {status}
    </span>
  );
}

function KartuAkun({
  akun,
  prosesId,
  onSync,
  onPutus,
}: {
  akun: KoneksiAkun;
  prosesId: string | null;
  onSync: (id: string) => void;
  onPutus: (id: string, nama: string) => void;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-base font-semibold text-slate-900">
            {akun.account_name}
          </p>
          <p className="mt-0.5 text-sm text-slate-500">
            Terhubung sejak {formatTanggal(akun.connected_at)}
          </p>
        </div>
        {badgeStatus(akun.status)}
      </div>
      <dl className="mt-4 space-y-1.5 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-slate-500">Sync terakhir</dt>
          <dd className="font-medium text-slate-700">
            {akun.last_sync_at
              ? formatTanggal(akun.last_sync_at, true)
              : "Belum pernah"}
          </dd>
        </div>
      </dl>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          variant="secondary"
          onClick={() => onSync(akun.id)}
          disabled={prosesId !== null}
        >
          {prosesId === akun.id ? "Sync…" : "Sync sekarang"}
        </Button>
        <Button
          variant="ghost"
          onClick={() => onPutus(akun.id, akun.account_name)}
          disabled={prosesId !== null}
          className="text-red-600 hover:bg-red-50"
        >
          Putus
        </Button>
      </div>
    </Card>
  );
}

function KoneksiIsi() {
  const params = useParams();
  const brandId = params.brandId as string;
  const searchParams = useSearchParams();

  const [items, setItems] = useState<KoneksiAkun[]>([]);
  const [batas, setBatas] = useState<StatusKoneksi | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sukses, setSukses] = useState("");
  const [prosesId, setProsesId] = useState<string | null>(null);
  const [menghubungkan, setMenghubungkan] = useState<Platform | null>(null);
  const [menghubungkanDemo, setMenghubungkanDemo] = useState<Platform | null>(null);

  const muat = useCallback(async () => {
    setLoading(true);
    setError("");
    const [hasilAkun, hasilBatas] = await Promise.allSettled([
      api.get<KoneksiAkun[]>(`/content/brands/${brandId}/koneksi`),
      api.get<StatusKoneksi>(`/content/brands/${brandId}/koneksi/status`),
    ]);
    if (hasilAkun.status === "fulfilled") {
      setItems(hasilAkun.value);
    } else {
      const err = hasilAkun.reason;
      setError(
        err instanceof ApiError
          ? err.message
          : "Gagal memuat daftar koneksi."
      );
    }
    // Status batas multi-akun: bila endpoint belum ada, biarkan null dan
    // tombol hubung tetap aktif (fetch defensif).
    if (hasilBatas.status === "fulfilled") {
      setBatas(hasilBatas.value);
    }
    setLoading(false);
  }, [brandId]);

  useEffect(() => {
    muat();
  }, [muat]);

  async function hubungkan(platform: Platform) {
    setMenghubungkan(platform);
    setError("");
    setSukses("");
    try {
      const res = await api.post<{ auth_url: string }>(
        `/content/brands/${brandId}/oauth/${platform}/mulai`
      );
      window.location.href = res.auth_url;
    } catch (err) {
      if (err instanceof ApiError && (err.status === 501 || err.status === 503)) {
        setError(
          "Koneksi nyata butuh kredensial — hubungi admin. " +
            "Kredensial API TikTok/Instagram belum disiapkan, jadi akun asli " +
            "belum bisa dihubungkan."
        );
      } else {
        setError(
          err instanceof ApiError
            ? err.message
            : "Gagal memulai proses koneksi."
        );
      }
    } finally {
      setMenghubungkan(null);
    }
  }

  async function hubungkanDemo(platform: Platform) {
    setMenghubungkanDemo(platform);
    setError("");
    setSukses("");
    try {
      await api.post("/dev/koneksi/mock", {
        brand_id: brandId,
        platform,
      });
      setSukses(
        `Akun demo ${PLATFORM_META[platform].label} terhubung. ` +
          `Klik "Sync sekarang" untuk menarik 15 data contoh.`
      );
      await muat();
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError(
          "Mode demo hanya tersedia di environment development. " +
            "Di production, hubungkan akun asli lewat tombol di atas."
        );
      } else {
        setError(
          err instanceof ApiError
            ? err.message
            : "Gagal menghubungkan akun demo."
        );
      }
    } finally {
      setMenghubungkanDemo(null);
    }
  }

  async function syncSekarang(connId: string) {
    setProsesId(connId);
    setError("");
    setSukses("");
    try {
      const hasil = await api.post<{ contents_baru: number; contents_diupdate: number }>(
        `/content/koneksi/${connId}/sync`
      );
      setSukses(
        `Sync selesai: ${hasil.contents_baru} konten baru, ${hasil.contents_diupdate} konten diperbarui.`
      );
      await muat();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal melakukan sync."
      );
    } finally {
      setProsesId(null);
    }
  }

  async function putus(connId: string, nama: string) {
    if (
      !window.confirm(
        `Putus koneksi akun "${nama}"? Data yang sudah ter-sync tidak ikut terhapus.`
      )
    )
      return;
    setProsesId(connId);
    setError("");
    setSukses("");
    try {
      await api.del(`/content/koneksi/${connId}`);
      setSukses(`Koneksi akun "${nama}" diputus.`);
      await muat();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal memutus koneksi."
      );
    } finally {
      setProsesId(null);
    }
  }

  const statusCallback = searchParams.get("status");
  const platformList: Platform[] = ["tiktok", "instagram"];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Koneksi Akun"
        subtitle="Hubungkan beberapa akun TikTok dan Instagram brand untuk sync data otomatis."
      />
      <BrandNav brandId={brandId} />

      {statusCallback === "ok" && (
        <div className="mb-4">
          <Alert kind="success">
            Akun berhasil terhubung. Daftar koneksi di bawah sudah diperbarui.
          </Alert>
        </div>
      )}
      {statusCallback === "gagal" && (
        <div className="mb-4">
          <Alert kind="error">
            Proses koneksi gagal atau dibatalkan. Silakan coba lagi.
          </Alert>
        </div>
      )}
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

      {loading && <Spinner label="Memuat koneksi…" />}

      {!loading &&
        platformList.map((p) => {
          const meta = PLATFORM_META[p];
          const infoBatas = batas?.platforms?.[p];
          const bolehTambah = infoBatas ? infoBatas.boleh_tambah : true;
          const akunPlatform = items.filter((k) => k.platform === p);
          const labelHitung = infoBatas
            ? `${akunPlatform.length} dari ${infoBatas.batas}`
            : `${akunPlatform.length}`;
          return (
            <section key={p} className="mb-8">
              <Card className="mb-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
                    <span aria-hidden>{meta.ikon}</span>
                    {meta.label}
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                      {labelHitung} akun
                    </span>
                  </h2>
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  Anda akan diarahkan ke halaman resmi {meta.label} untuk memberi
                  izin akses.
                </p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    onClick={() => hubungkan(p)}
                    disabled={menghubungkan !== null || !bolehTambah}
                  >
                    {menghubungkan === p
                      ? "Membuka…"
                      : `Hubungkan ${meta.label}`}
                  </Button>
                  <Button
                    onClick={() => hubungkanDemo(p)}
                    disabled={menghubungkanDemo !== null || !bolehTambah}
                    variant="secondary"
                  >
                    {menghubungkanDemo === p
                      ? "Menghubungkan…"
                      : `Akun demo ${meta.label}`}
                  </Button>
                </div>
                {!bolehTambah && infoBatas && (
                  <p className="mt-3 text-sm font-medium text-amber-700">
                    Batas {infoBatas.batas} akun {meta.label} per brand tercapai.
                  </p>
                )}
                <p className="mt-2 text-xs text-slate-400">
                  Belum punya kredensial {meta.label}? Tombol akun demo memakai
                  15 data contoh (hanya di development).
                </p>
              </Card>

              {akunPlatform.length === 0 ? (
                <EmptyBox
                  title={`Belum ada akun ${meta.label} terhubung`}
                  description={`Hubungkan akun ${meta.label} brand lewat tombol di atas agar data konten bisa di-sync otomatis.`}
                  icon={
                    <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m13.35-.622 1.757-1.757a4.5 4.5 0 0 0-6.364-6.364l-4.5 4.5a4.5 4.5 0 0 0 1.242 7.244" />
                    </svg>
                  }
                />
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  {akunPlatform.map((k) => (
                    <KartuAkun
                      key={k.id}
                      akun={k}
                      prosesId={prosesId}
                      onSync={syncSekarang}
                      onPutus={putus}
                    />
                  ))}
                </div>
              )}
            </section>
          );
        })}
    </div>
  );
}

export default function KoneksiPage() {
  return (
    <RequireAuth>
      <Suspense fallback={<Spinner label="Memuat koneksi…" />}>
        <KoneksiIsi />
      </Suspense>
    </RequireAuth>
  );
}
