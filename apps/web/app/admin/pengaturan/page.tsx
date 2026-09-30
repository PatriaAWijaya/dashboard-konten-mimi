"use client";

import { useCallback, useEffect, useState } from "react";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { formatTanggal } from "@/lib/format";
import {
  Alert,
  Button,
  Card,
  Input,
  PageHeader,
  Spinner,
} from "@/components/ui";

interface ItemPengaturan {
  key: string;
  label: string;
  configured: boolean;
  updated_at: string | null;
}

const API_PUBLIK =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const REDIRECT_URI = `${API_PUBLIK}/api/v1/content/oauth/callback`;

function KartuPengaturan({
  item,
  onSimpan,
}: {
  item: ItemPengaturan;
  onSimpan: () => Promise<void>;
}) {
  const [nilai, setNilai] = useState("");
  const [sibuk, setSibuk] = useState(false);
  const [error, setError] = useState("");
  const [sukses, setSukses] = useState("");

  async function simpan() {
    setSibuk(true);
    setError("");
    setSukses("");
    try {
      await api.put("/admin/pengaturan", { key: item.key, value: nilai });
      setNilai("");
      setSukses("Tersimpan.");
      await onSimpan();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal menyimpan pengaturan."
      );
    } finally {
      setSibuk(false);
    }
  }

  async function hapus() {
    if (
      !window.confirm(
        `Hapus nilai "${item.label}"? Fitur terkait kembali memakai mode Mock.`
      )
    )
      return;
    setSibuk(true);
    setError("");
    setSukses("");
    try {
      await api.put("/admin/pengaturan", { key: item.key, value: null });
      setSukses("Dihapus — kembali ke mode Mock.");
      await onSimpan();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal menghapus pengaturan."
      );
    } finally {
      setSibuk(false);
    }
  }

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900">
            {item.label}
          </h3>
          <p className="mt-0.5 font-mono text-xs text-slate-400">{item.key}</p>
        </div>
        <span
          className={`inline-flex shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
            item.configured
              ? "bg-emerald-100 text-emerald-800"
              : "bg-slate-100 text-slate-500"
          }`}
        >
          {item.configured ? "Terkonfigurasi" : "Belum"}
        </span>
      </div>
      {item.updated_at && (
        <p className="mt-2 text-xs text-slate-400">
          Terakhir diubah {formatTanggal(item.updated_at, true)}
        </p>
      )}
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
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <Input
          label="Nilai baru"
          type="password"
          placeholder={
            item.configured ? "•••••••• (kosongkan = tidak diubah)" : "Tempel nilai di sini"
          }
          value={nilai}
          onChange={(e) => setNilai(e.target.value)}
        />
      </div>
      <div className="mt-3 flex gap-2">
        <Button onClick={simpan} disabled={sibuk || !nilai}>
          {sibuk ? "Menyimpan…" : "Simpan"}
        </Button>
        {item.configured && (
          <Button variant="ghost" onClick={hapus} disabled={sibuk}>
            Hapus
          </Button>
        )}
      </div>
    </Card>
  );
}

function PanduanPatria() {
  return (
    <Card className="mb-6 border-amber-200 bg-amber-50">
      <h2 className="text-base font-semibold text-slate-900">
        📋 Checklist panduan Patria — wajib sebelum koneksi nyata jalan
      </h2>
      <p className="mt-1 text-sm text-slate-600">
        Tanpa langkah di bawah ini, semua integrasi tetap berjalan dalam{" "}
        <strong>mode Mock</strong> (simulasi) — tombol sync, ringkasan, dan
        notifikasi WhatsApp tidak memproses data asli.
      </p>
      <ol className="mt-4 space-y-4 text-sm text-slate-700">
        <li>
          <p className="font-semibold text-slate-900">
            (a) TikTok Developers — Login Kit
          </p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            <li>Buat aplikasi di TikTok Developers.</li>
            <li>Aktifkan produk <strong>Login Kit</strong>.</li>
            <li>
              Daftarkan Redirect URI:{" "}
              <code className="rounded bg-white px-1.5 py-0.5 font-mono text-xs text-orange-700">
                {REDIRECT_URI}
              </code>
            </li>
            <li>Salin <strong>Client Key</strong> &amp; <strong>Client Secret</strong>.</li>
            <li>Tempel keduanya di kartu pengaturan di bawah halaman ini.</li>
          </ul>
        </li>
        <li>
          <p className="font-semibold text-slate-900">
            (b) Meta Developers — Instagram Graph API
          </p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            <li>Buat aplikasi di Meta Developers.</li>
            <li>
              Tambahkan produk <strong>Instagram Graph API</strong> ke aplikasi.
            </li>
            <li>
              Daftarkan Redirect URI yang sama:{" "}
              <code className="rounded bg-white px-1.5 py-0.5 font-mono text-xs text-orange-700">
                {REDIRECT_URI}
              </code>
            </li>
            <li>Salin <strong>App ID</strong> &amp; <strong>App Secret</strong>.</li>
            <li>Tempel keduanya di kartu pengaturan di bawah.</li>
          </ul>
        </li>
        <li>
          <p className="font-semibold text-slate-900">
            (c) WhatsApp API — provider notifikasi
          </p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            <li>
              Daftar sendiri ke salah satu provider:{" "}
              <strong>Fonnte</strong>, <strong>Wablas</strong>, atau{" "}
              <strong>Meta WhatsApp Business</strong> (API resmi).
            </li>
            <li>
              Tempel nama provider &amp; API key-nya di kartu pengaturan di
              bawah.
            </li>
          </ul>
        </li>
        <li>
          <p className="font-semibold text-slate-900">(d) LLM API key</p>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            <li>
              Tempel API key model bahasa pilihan Anda agar narasi rekomendasi
              AI memakai model asli, bukan template Mock.
            </li>
          </ul>
        </li>
      </ol>
    </Card>
  );
}

function PengaturanIsi() {
  const [items, setItems] = useState<ItemPengaturan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const muat = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get<ItemPengaturan[]>("/admin/pengaturan");
      setItems(data);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal memuat pengaturan."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    muat();
  }, [muat]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Pengaturan Integrasi"
        subtitle="Kredensial pihak ketiga untuk koneksi nyata TikTok, Instagram, WhatsApp, dan LLM."
      />

      <PanduanPatria />

      {loading && <Spinner label="Memuat pengaturan…" />}
      {error && <Alert kind="error">{error}</Alert>}

      {!loading && !error && items.length === 0 && (
        <Card>
          <p className="text-sm text-slate-500">
            Belum ada kunci pengaturan terdaftar. Semua integrasi berjalan
            dalam mode Mock.
          </p>
        </Card>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((item) => (
            <KartuPengaturan key={item.key} item={item} onSimpan={muat} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function PengaturanAdminPage() {
  return (
    <RequireAuth superadmin>
      <PengaturanIsi />
    </RequireAuth>
  );
}
