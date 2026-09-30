"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Alert, Button, Card, Input } from "@/components/ui";
import { KirimUlangVerifikasi } from "@/components/KirimUlangVerifikasi";

interface DevToken {
  token: string;
  [key: string]: unknown;
}

export default function RegisterPage() {
  const router = useRouter();
  const { login, refreshOrgs } = useAuth();

  const [langkah, setLangkah] = useState<1 | 2 | 3>(1);
  const [nama, setNama] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [konfirmasi, setKonfirmasi] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [namaOrg, setNamaOrg] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const [devToken, setDevToken] = useState<string | null>(null);
  const [devLoading, setDevLoading] = useState(false);

  async function handleBuatAkun(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setInfo("");
    if (password !== konfirmasi) {
      setError("Konfirmasi kata sandi tidak cocok.");
      return;
    }
    if (password.length < 8) {
      setError("Kata sandi minimal 8 karakter.");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/register", {
        name: nama.trim(),
        email: email.trim(),
        password,
        ...(whatsapp.trim() ? { whatsapp: whatsapp.trim() } : {}),
      });
      // Masuk otomatis agar bisa membuat organisasi di langkah 2.
      try {
        await login(email.trim(), password);
      } catch {
        setInfo(
          "Akun berhasil dibuat, tetapi masuk otomatis gagal. Silakan verifikasi email lalu masuk untuk melanjutkan."
        );
      }
      setLangkah(2);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Gagal membuat akun. Periksa koneksi internet Anda."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleBuatOrg(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const org = await api.post<{ id: string; name: string }>("/organizations", {
        name: namaOrg.trim(),
      });
      await refreshOrgs();
      // Pilih organisasi yang baru dibuat sebagai organisasi aktif.
      if (typeof window !== "undefined") {
        window.localStorage.setItem("dkai_org_id", org.id);
      }
      setLangkah(3);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Gagal membuat organisasi. Periksa koneksi internet Anda."
      );
    } finally {
      setLoading(false);
    }
  }

  async function ambilTokenDev() {
    setDevLoading(true);
    setError("");
    try {
      const list = await api.get<DevToken[]>(
        `/dev/email-tokens?email=${encodeURIComponent(email.trim())}`
      );
      if (list.length === 0) {
        setError("Token verifikasi belum tersedia. Coba lagi beberapa saat.");
      } else {
        setDevToken(list[0].token);
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Endpoint dev tidak tersedia (pastikan server berjalan dalam mode dev)."
      );
    } finally {
      setDevLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <Link href="/" className="inline-flex items-center gap-2">
            <img
              src="/logo.png"
              alt="MySocial Watch"
              className="h-10 w-10 rounded-xl"
            />
            <span className="flex flex-col items-end leading-none">
              <span className="text-xl font-bold text-slate-900">
                MySocial Watch
              </span>
              <span className="mt-0.5 text-[11px] font-medium text-slate-400">
                by Patria
              </span>
            </span>
          </Link>
          <h1 className="mt-6 text-2xl font-bold text-slate-900">
            Buat akun baru
          </h1>
        </div>

        {/* Indikator langkah */}
        <div className="mb-6 flex items-center justify-center gap-2 text-sm">
          {["Buat akun", "Profil organisasi", "Selesai"].map((label, i) => {
            const n = i + 1;
            const aktif = langkah === n;
            const selesai = langkah > n;
            return (
              <div key={label} className="flex items-center gap-2">
                <span
                  className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${
                    aktif
                      ? "bg-orange-600 text-white"
                      : selesai
                        ? "bg-emerald-500 text-white"
                        : "bg-slate-200 text-slate-500"
                  }`}
                >
                  {selesai ? "✓" : n}
                </span>
                <span
                  className={
                    aktif ? "font-semibold text-slate-900" : "text-slate-500"
                  }
                >
                  {label}
                </span>
                {n < 3 && <span className="mx-1 text-slate-300">—</span>}
              </div>
            );
          })}
        </div>

        <Card>
          {langkah === 1 && (
            <form onSubmit={handleBuatAkun} className="space-y-4">
              <h2 className="text-lg font-semibold text-slate-900">
                Langkah 1 — Buat akun
              </h2>
              {error && <Alert kind="error">{error}</Alert>}
              {info && <Alert kind="info">{info}</Alert>}
              <Input
                label="Nama lengkap"
                required
                autoComplete="name"
                placeholder="Nama Anda"
                value={nama}
                onChange={(e) => setNama(e.target.value)}
              />
              <Input
                label="Email"
                type="email"
                required
                autoComplete="email"
                placeholder="nama@perusahaan.id"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <Input
                label="Nomor WhatsApp (opsional)"
                type="tel"
                autoComplete="tel"
                placeholder="08xxxxxxxxxx"
                value={whatsapp}
                onChange={(e) => setWhatsapp(e.target.value)}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <Input
                  label="Kata sandi"
                  type="password"
                  required
                  autoComplete="new-password"
                  placeholder="Min. 8 karakter"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <Input
                  label="Konfirmasi kata sandi"
                  type="password"
                  required
                  autoComplete="new-password"
                  placeholder="Ulangi kata sandi"
                  value={konfirmasi}
                  onChange={(e) => setKonfirmasi(e.target.value)}
                />
              </div>
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? "Memproses…" : "Lanjut"}
              </Button>
            </form>
          )}

          {langkah === 2 && (
            <form onSubmit={handleBuatOrg} className="space-y-4">
              <h2 className="text-lg font-semibold text-slate-900">
                Langkah 2 — Profil organisasi
              </h2>
              <p className="text-sm text-slate-500">
                Organisasi adalah wadah untuk brand-brand yang Anda kelola.
              </p>
              {error && <Alert kind="error">{error}</Alert>}
              {info && <Alert kind="info">{info}</Alert>}
              <Input
                label="Nama organisasi"
                required
                placeholder="Contoh: PT Maju Bersama"
                value={namaOrg}
                onChange={(e) => setNamaOrg(e.target.value)}
              />
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? "Memproses…" : "Buat organisasi"}
              </Button>
              <button
                type="button"
                onClick={() => setLangkah(3)}
                className="w-full text-center text-sm font-medium text-slate-500 hover:text-slate-700"
              >
                Lewati untuk saat ini
              </button>
            </form>
          )}

          {langkah === 3 && (
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-3xl text-emerald-600">
                ✓
              </div>
              <h2 className="text-lg font-semibold text-slate-900">
                Akun berhasil dibuat!
              </h2>
              <p className="text-sm text-slate-600">
                Kami telah mengirim tautan verifikasi ke{" "}
                <span className="font-semibold">{email}</span>. Silakan cek
                email kamu dan klik tautan tersebut untuk mengaktifkan akun.
              </p>
              {error && <Alert kind="error">{error}</Alert>}
              <KirimUlangVerifikasi email={email} />

              {process.env.NODE_ENV === "development" && (
                <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Mode pengembang
                  </p>
                <Button
                  variant="secondary"
                  onClick={ambilTokenDev}
                  disabled={devLoading}
                  className="mt-2 w-full"
                >
                  {devLoading
                    ? "Mengambil token…"
                    : "Ambil token verifikasi (dev)"}
                </Button>
                {devToken && (
                  <Link
                    href={`/verify-email?token=${encodeURIComponent(devToken)}`}
                    className="mt-3 block break-all rounded-lg bg-white p-3 text-xs font-medium text-orange-600 underline hover:text-orange-800"
                  >
                    Klik di sini untuk verifikasi email
                  </Link>
                )}
              </div>
              )}
              <Button
                variant="secondary"
                onClick={() => router.push("/login")}
                className="w-full"
              >
                Ke halaman masuk
              </Button>
            </div>
          )}
        </Card>

        {langkah === 1 && (
          <p className="mt-6 text-center text-sm text-slate-500">
            Sudah punya akun?{" "}
            <Link
              href="/login"
              className="font-semibold text-orange-600 hover:text-orange-700"
            >
              Masuk
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}
