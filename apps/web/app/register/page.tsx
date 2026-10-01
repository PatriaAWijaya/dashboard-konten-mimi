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

/** Tautan kotak masuk berdasarkan domain email (null bila tidak dikenali). */
function infoInbox(emailAddr: string): { url: string; label: string } | null {
  const domain = (emailAddr.split("@")[1] || "").toLowerCase().trim();
  if (domain === "gmail.com" || domain === "googlemail.com")
    return { url: "https://mail.google.com/", label: "Gmail" };
  if (domain.endsWith("yahoo.com") || domain.endsWith("yahoo.co.id"))
    return { url: "https://mail.yahoo.com/", label: "Yahoo Mail" };
  if (
    ["outlook.com", "hotmail.com", "live.com", "msn.com"].includes(domain)
  )
    return { url: "https://outlook.live.com/", label: "Outlook" };
  if (["icloud.com", "me.com", "mac.com"].includes(domain))
    return { url: "https://www.icloud.com/mail", label: "iCloud Mail" };
  return null;
}

export default function RegisterPage() {
  const router = useRouter();
  const { login, refreshOrgs } = useAuth();

  const [langkah, setLangkah] = useState<1 | 2 | 3 | 4>(1);
  const [nama, setNama] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [konfirmasi, setKonfirmasi] = useState("");
  const [whatsapp, setWhatsapp] = useState("");
  const [namaOrg, setNamaOrg] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [devToken, setDevToken] = useState<string | null>(null);
  const [devLoading, setDevLoading] = useState(false);

  async function handleBuatAkun(e: React.FormEvent) {
    e.preventDefault();
    setError("");
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
      // Lanjut ke langkah verifikasi email — JANGAN langsung ke profil
      // organisasi karena langkah itu butuh email yang sudah terverifikasi.
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

  async function handleSudahVerifikasi() {
    setError("");
    setLoading(true);
    try {
      const res = await login(email.trim(), password);
      if (!res.user.email_verified) {
        setError(
          "Email Anda belum terverifikasi. Klik tautan di email yang kami kirim, lalu coba lagi."
        );
        return;
      }
      setLangkah(3);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Gagal masuk. Periksa koneksi internet Anda."
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
      setLangkah(4);
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

  const inbox = infoInbox(email);

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
          {["Buat akun", "Verifikasi email", "Profil organisasi", "Selesai"].map(
            (label, i) => {
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
                  {n < 4 && <span className="mx-1 text-slate-300">—</span>}
                </div>
              );
            }
          )}
        </div>

        <Card>
          {langkah === 1 && (
            <form onSubmit={handleBuatAkun} className="space-y-4">
              <h2 className="text-lg font-semibold text-slate-900">
                Langkah 1 — Buat akun
              </h2>
              {error && <Alert kind="error">{error}</Alert>}
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
                  togglePassword
                />
                <Input
                  label="Konfirmasi kata sandi"
                  type="password"
                  required
                  autoComplete="new-password"
                  placeholder="Ulangi kata sandi"
                  value={konfirmasi}
                  onChange={(e) => setKonfirmasi(e.target.value)}
                  togglePassword
                />
              </div>
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? "Memproses…" : "Lanjut"}
              </Button>
            </form>
          )}

          {langkah === 2 && (
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-orange-100 text-3xl text-orange-600">
                ✉
              </div>
              <h2 className="text-lg font-semibold text-slate-900">
                Langkah 2 — Verifikasi email
              </h2>
              <p className="text-sm text-slate-600">
                Silakan cek konfirmasi di email{" "}
                <span className="font-semibold text-slate-900">{email}</span>{" "}
                Anda. Klik tautan verifikasi di dalamnya (berlaku 15 menit)
                untuk mengaktifkan akun.
              </p>
              {error && <Alert kind="error">{error}</Alert>}
              {inbox && (
                <a
                  href={inbox.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2"
                >
                  Buka {inbox.label}
                </a>
              )}
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
                onClick={handleSudahVerifikasi}
                disabled={loading}
                className="w-full"
              >
                {loading ? "Memeriksa…" : "Saya sudah verifikasi, lanjutkan"}
              </Button>
            </div>
          )}

          {langkah === 3 && (
            <form onSubmit={handleBuatOrg} className="space-y-4">
              <h2 className="text-lg font-semibold text-slate-900">
                Langkah 3 — Profil organisasi
              </h2>
              <p className="text-sm text-slate-500">
                Organisasi adalah wadah untuk brand-brand yang Anda kelola.
              </p>
              {error && <Alert kind="error">{error}</Alert>}
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
                onClick={() => setLangkah(4)}
                className="w-full text-center text-sm font-medium text-slate-500 hover:text-slate-700"
              >
                Lewati untuk saat ini
              </button>
            </form>
          )}

          {langkah === 4 && (
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-3xl text-emerald-600">
                ✓
              </div>
              <h2 className="text-lg font-semibold text-slate-900">
                Pendaftaran selesai!
              </h2>
              <p className="text-sm text-slate-600">
                Akun Anda sudah aktif dan email terverifikasi. Selamat datang
                di MySocial Watch!
              </p>
              {error && <Alert kind="error">{error}</Alert>}
              <Button
                onClick={() => router.push("/dashboard")}
                className="w-full"
              >
                Ke dashboard
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
