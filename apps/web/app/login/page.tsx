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
  const [couponCode, setCouponCode] = useState("");
  const [error, setError] = useState("");
  const [couponInfo, setCouponInfo] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setCouponInfo("");
    setLoading(true);
    try {
      const res = await login(email.trim(), password, couponCode);
      const params = new URLSearchParams();
      if (res.coupon_error) {
        params.set("coupon_error", res.coupon_error);
      } else if (res.coupon_applied && res.coupon_applied.length > 0) {
        const d = res.coupon_applied[0];
        params.set("coupon_ok", `${d.discount_percent}`);
        if (d.expires_at) params.set("coupon_exp", d.expires_at.slice(0, 10));
      }
      const qs = params.toString();
      router.push(qs ? `/dashboard?${qs}` : "/dashboard");
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
            {couponInfo && <Alert kind="success">{couponInfo}</Alert>}
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
            <Input
              label="Kode kupon (opsional)"
              placeholder="Punya kode kupon? Masukkan di sini"
              value={couponCode}
              onChange={(e) => setCouponCode(e.target.value)}
            />
            <div className="text-right">
              <Link
                href="/forgot-password"
                className="text-sm font-medium text-orange-600 hover:text-orange-700"
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
            className="font-semibold text-orange-600 hover:text-orange-700"
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
