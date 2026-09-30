"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Alert, Button, Card, Input, Spinner } from "@/components/ui";

function ResetPasswordInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [password, setPassword] = useState("");
  const [konfirmasi, setKonfirmasi] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
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
      await api.post("/auth/reset-password", {
        token,
        new_password: password,
      });
      router.push("/login?reset=berhasil");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Gagal mereset kata sandi. Coba lagi nanti."
      );
    } finally {
      setLoading(false);
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
            <span className="flex flex-col items-start leading-none">
              <span className="text-xl font-bold text-slate-900">
                MySocial Watch
              </span>
              <span className="mt-0.5 text-[11px] font-medium text-slate-400">
                by Patria
              </span>
            </span>
          </Link>
          <h1 className="mt-6 text-2xl font-bold text-slate-900">
            Atur ulang kata sandi
          </h1>
        </div>

        <Card>
          {!token ? (
            <div className="space-y-4 text-center">
              <Alert kind="error">
                Token reset tidak ditemukan di tautan. Silakan minta tautan
                reset baru.
              </Alert>
              <Link href="/forgot-password" className="block">
                <Button variant="secondary" className="w-full">
                  Minta tautan baru
                </Button>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && <Alert kind="error">{error}</Alert>}
              <Input
                label="Kata sandi baru"
                type="password"
                required
                autoComplete="new-password"
                placeholder="Min. 8 karakter"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <Input
                label="Konfirmasi kata sandi baru"
                type="password"
                required
                autoComplete="new-password"
                placeholder="Ulangi kata sandi baru"
                value={konfirmasi}
                onChange={(e) => setKonfirmasi(e.target.value)}
              />
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? "Memproses…" : "Simpan kata sandi baru"}
              </Button>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<Spinner label="Memuat…" />}>
      <ResetPasswordInner />
    </Suspense>
  );
}
