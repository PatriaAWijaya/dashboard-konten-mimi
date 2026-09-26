"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Alert, Button, Card, Input, Spinner } from "@/components/ui";

function LoginInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resetBerhasil = searchParams.get("reset") === "berhasil";
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email.trim(), password);
      router.push("/dashboard");
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

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <Link href="/" className="inline-flex items-center gap-2">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-lg font-bold text-white">
              D
            </span>
            <span className="text-xl font-bold text-slate-900">
              Dashboard Konten AI
            </span>
          </Link>
          <h1 className="mt-6 text-2xl font-bold text-slate-900">
            Selamat datang kembali
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Masuk untuk mengelola analisis konten Anda
          </p>
        </div>

        <Card>
          <form onSubmit={handleSubmit} className="space-y-4">
            {resetBerhasil && (
              <Alert kind="success">
                Kata sandi berhasil diubah. Silakan masuk dengan kata sandi
                baru Anda.
              </Alert>
            )}
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
            <Input
              label="Kata sandi"
              type="password"
              required
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <div className="text-right">
              <Link
                href="/forgot-password"
                className="text-sm font-medium text-indigo-600 hover:text-indigo-700"
              >
                Lupa password?
              </Link>
            </div>
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Memproses…" : "Masuk"}
            </Button>
          </form>
        </Card>

        <p className="mt-6 text-center text-sm text-slate-500">
          Belum punya akun?{" "}
          <Link
            href="/register"
            className="font-semibold text-indigo-600 hover:text-indigo-700"
          >
            Daftar
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<Spinner label="Memuat…" />}>
      <LoginInner />
    </Suspense>
  );
}
