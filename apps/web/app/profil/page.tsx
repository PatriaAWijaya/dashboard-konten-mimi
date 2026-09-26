"use client";

import { useEffect, useState } from "react";
import { useAuth, RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { Alert, Button, Card, Input, PageHeader, Spinner } from "@/components/ui";

interface PreferensiNotifikasi {
  rekomendasi_baru: boolean;
  ringkasan_mingguan: boolean;
}

function Toggle({
  label,
  deskripsi,
  aktif,
  sibuk,
  onUbah,
}: {
  label: string;
  deskripsi: string;
  aktif: boolean;
  sibuk: boolean;
  onUbah: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div>
        <p className="text-sm font-semibold text-slate-900">{label}</p>
        <p className="mt-0.5 text-xs text-slate-500">{deskripsi}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={aktif}
        aria-label={label}
        disabled={sibuk}
        onClick={() => onUbah(!aktif)}
        className={`relative h-7 w-12 shrink-0 rounded-full transition ${
          aktif ? "bg-indigo-600" : "bg-slate-200"
        } disabled:opacity-50`}
      >
        <span
          className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-all ${
            aktif ? "left-6" : "left-1"
          }`}
        />
      </button>
    </div>
  );
}

function SeksiNotifikasi() {
  const [prefs, setPrefs] = useState<PreferensiNotifikasi | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sukses, setSukses] = useState("");
  const [sibuk, setSibuk] = useState<keyof PreferensiNotifikasi | null>(null);

  useEffect(() => {
    api
      .get<PreferensiNotifikasi>("/notifikasi/preferensi")
      .then(setPrefs)
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : "Gagal memuat preferensi notifikasi."
        )
      )
      .finally(() => setLoading(false));
  }, []);

  async function ubah(kunci: keyof PreferensiNotifikasi, nilai: boolean) {
    if (!prefs) return;
    const sebelumnya = prefs;
    const berikutnya = { ...prefs, [kunci]: nilai };
    setPrefs(berikutnya);
    setSibuk(kunci);
    setError("");
    setSukses("");
    try {
      const disimpan = await api.put<PreferensiNotifikasi>(
        "/notifikasi/preferensi",
        berikutnya
      );
      setPrefs(disimpan);
      setSukses("Preferensi notifikasi tersimpan.");
    } catch (err) {
      setPrefs(sebelumnya);
      setError(
        err instanceof ApiError
          ? err.message
          : "Gagal menyimpan preferensi notifikasi."
      );
    } finally {
      setSibuk(null);
    }
  }

  return (
    <Card className="mt-6">
      <h2 className="text-base font-semibold text-slate-900">Notifikasi</h2>
      <p className="mt-1 text-sm text-slate-500">
        Atur notifikasi yang Anda terima lewat WhatsApp.
      </p>
      {loading && <Spinner label="Memuat preferensi…" />}
      {!loading && error && !prefs && <Alert kind="error">{error}</Alert>}
      {!loading && prefs && (
        <div className="mt-2 divide-y divide-slate-100">
          {error && (
            <div className="py-2">
              <Alert kind="error">{error}</Alert>
            </div>
          )}
          {sukses && (
            <div className="py-2">
              <Alert kind="success">{sukses}</Alert>
            </div>
          )}
          <Toggle
            label="Rekomendasi baru"
            deskripsi="Beri tahu saya saat rekomendasi AI baru dibuat untuk brand saya."
            aktif={prefs.rekomendasi_baru}
            sibuk={sibuk !== null}
            onUbah={(v) => ubah("rekomendasi_baru", v)}
          />
          <Toggle
            label="Ringkasan mingguan"
            deskripsi="Kirim ringkasan performa konten setiap pekan."
            aktif={prefs.ringkasan_mingguan}
            sibuk={sibuk !== null}
            onUbah={(v) => ubah("ringkasan_mingguan", v)}
          />
        </div>
      )}
    </Card>
  );
}

function ProfilIsi() {
  const { user, refreshUser } = useAuth();

  const [nama, setNama] = useState(user?.name ?? "");
  const [whatsapp, setWhatsapp] = useState(user?.whatsapp ?? "");
  const [profilError, setProfilError] = useState("");
  const [profilSukses, setProfilSukses] = useState("");
  const [profilLoading, setProfilLoading] = useState(false);

  const [lama, setLama] = useState("");
  const [baru, setBaru] = useState("");
  const [konfirmasi, setKonfirmasi] = useState("");
  const [passError, setPassError] = useState("");
  const [passSukses, setPassSukses] = useState("");
  const [passLoading, setPassLoading] = useState(false);

  async function simpanProfil(e: React.FormEvent) {
    e.preventDefault();
    setProfilError("");
    setProfilSukses("");
    setProfilLoading(true);
    try {
      await api.patch("/users/me", {
        name: nama.trim(),
        whatsapp: whatsapp.trim() || null,
      });
      await refreshUser();
      setProfilSukses("Profil berhasil diperbarui.");
    } catch (err) {
      setProfilError(
        err instanceof ApiError
          ? err.message
          : "Gagal memperbarui profil. Periksa koneksi internet Anda."
      );
    } finally {
      setProfilLoading(false);
    }
  }

  async function gantiPassword(e: React.FormEvent) {
    e.preventDefault();
    setPassError("");
    setPassSukses("");
    if (baru !== konfirmasi) {
      setPassError("Konfirmasi kata sandi baru tidak cocok.");
      return;
    }
    if (baru.length < 8) {
      setPassError("Kata sandi baru minimal 8 karakter.");
      return;
    }
    setPassLoading(true);
    try {
      await api.post("/users/me/change-password", {
        old_password: lama,
        new_password: baru,
      });
      setPassSukses("Kata sandi berhasil diubah.");
      setLama("");
      setBaru("");
      setKonfirmasi("");
    } catch (err) {
      setPassError(
        err instanceof ApiError
          ? err.message
          : "Gagal mengubah kata sandi. Periksa koneksi internet Anda."
      );
    } finally {
      setPassLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <PageHeader title="Profil" subtitle="Kelola data akun dan kata sandi Anda." />

      <Card className="mb-6">
        <h2 className="text-base font-semibold text-slate-900">Data profil</h2>
        <form onSubmit={simpanProfil} className="mt-4 space-y-4">
          {profilError && <Alert kind="error">{profilError}</Alert>}
          {profilSukses && <Alert kind="success">{profilSukses}</Alert>}
          <Input
            label="Nama lengkap"
            required
            value={nama}
            onChange={(e) => setNama(e.target.value)}
          />
          <Input label="Email" type="email" value={user?.email ?? ""} disabled />
          <Input
            label="Nomor WhatsApp"
            type="tel"
            placeholder="08xxxxxxxxxx"
            value={whatsapp}
            onChange={(e) => setWhatsapp(e.target.value)}
          />
          <Button type="submit" disabled={profilLoading}>
            {profilLoading ? "Menyimpan…" : "Simpan perubahan"}
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className="text-base font-semibold text-slate-900">Ganti kata sandi</h2>
        <form onSubmit={gantiPassword} className="mt-4 space-y-4">
          {passError && <Alert kind="error">{passError}</Alert>}
          {passSukses && <Alert kind="success">{passSukses}</Alert>}
          <Input
            label="Kata sandi lama"
            type="password"
            required
            autoComplete="current-password"
            value={lama}
            onChange={(e) => setLama(e.target.value)}
          />
          <Input
            label="Kata sandi baru"
            type="password"
            required
            autoComplete="new-password"
            placeholder="Min. 8 karakter"
            value={baru}
            onChange={(e) => setBaru(e.target.value)}
          />
          <Input
            label="Konfirmasi kata sandi baru"
            type="password"
            required
            autoComplete="new-password"
            value={konfirmasi}
            onChange={(e) => setKonfirmasi(e.target.value)}
          />
          <Button type="submit" disabled={passLoading}>
            {passLoading ? "Memproses…" : "Ganti kata sandi"}
          </Button>
        </form>
      </Card>

      <SeksiNotifikasi />
    </div>
  );
}

export default function ProfilPage() {
  return (
    <RequireAuth>
      <ProfilIsi />
    </RequireAuth>
  );
}
