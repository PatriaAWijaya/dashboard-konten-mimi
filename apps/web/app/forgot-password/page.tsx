"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Alert, Button, Card, Input, Spinner } from "@/components/ui";

function ForgotPasswordInner() {
  const searchParams = useSearchParams();
  const prefill = searchParams.get("email") || "";
  const [email, setEmail] = useState(prefill);
  const [terkirim, setTerkirim] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [devToken, setDevToken] = useState<string | null>(null);
  const [devLoading, setDevLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email: email.trim() });
      setTerkirim(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Gagal memproses permintaan. Periksa koneksi internet Anda."
      );
    } finally {
      setLoading(false);
    }
  }

  async function ambilTokenDev() {
    setDevLoading(true);
    setError("");
    try {
      const list = await api.get<{ token: string }[]>(
        `/dev/password-reset-tokens?email=${encodeURIComponent(email.trim())}`
      );
      if (list.length === 0) {
        setError("Token reset belum tersedia. Coba lagi beberapa saat.");
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
            Lupa kata sandi
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Masukkan email akun Anda untuk menerima tautan reset
          </p>
        </div>

        <Card>
          {!terkirim ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && <Alert kind="error">{error}</Alert>}
              <Input
                label="Email"
                type="email"
                required
                autoComplete="email"
                placeholder="nama@perusahaan.id"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? "Memproses…" : "Kirim tautan reset"}
              </Button>
            </form>
          ) : (
            <div className="space-y-4">
              <Alert kind="success">
                Jika email <span className="font-semibold">{email}</span>{" "}
                terdaftar, tautan reset kata sandi telah dikirim. Silakan cek
                kotak masuk (dan folder spam) Anda.
              </Alert>
              {error && <Alert kind="error">{error}</Alert>}

              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Mode pengembang
                </p>
                <Button
                  variant="secondary"
                  onClick={ambilTokenDev}
                  disabled={devLoading || !email}
                  className="mt-2 w-full"
                >
                  {devLoading
                    ? "Mengambil token…"
                    : "Ambil token reset (dev)"}
                </Button>
                {devToken && (
                  <Link
                    href={`/reset-password?token=${encodeURIComponent(devToken)}`}
                    className="mt-3 block break-all rounded-lg bg-white p-3 text-xs font-medium text-orange-600 underline hover:text-orange-800"
                  >
                    Klik di sini untuk reset kata sandi
                  </Link>
                )}
              </div>

              <Link href="/login" className="block text-center">
                <Button variant="ghost" className="w-full">
                  Kembali ke halaman masuk
                </Button>
              </Link>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

export default function ForgotPasswordPage() {
  return (
    <Suspense fallback={<Spinner label="Memuat…" />}>
      <ForgotPasswordInner />
    </Suspense>
  );
}
