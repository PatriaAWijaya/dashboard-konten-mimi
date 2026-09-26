"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { Alert, Button, Card, Spinner } from "@/components/ui";

function VerifyEmailInner() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading"
  );
  const [pesan, setPesan] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setPesan("Token verifikasi tidak ditemukan di tautan.");
      return;
    }
    api
      .post("/auth/verify-email", { token })
      .then(() => {
        setStatus("success");
      })
      .catch((err) => {
        setStatus("error");
        setPesan(
          err instanceof ApiError
            ? err.message
            : "Verifikasi gagal. Coba lagi nanti."
        );
      });
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-md">
        <Card>
          {status === "loading" && <Spinner label="Memverifikasi email…" />}
          {status === "success" && (
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-3xl text-emerald-600">
                ✓
              </div>
              <h1 className="text-xl font-bold text-slate-900">
                Email berhasil diverifikasi
              </h1>
              <p className="text-sm text-slate-600">
                Akun Anda sudah aktif. Silakan masuk untuk mulai menggunakan
                Dashboard Konten AI.
              </p>
              <Link href="/login" className="block">
                <Button className="w-full">Ke halaman masuk</Button>
              </Link>
            </div>
          )}
          {status === "error" && (
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-3xl text-red-600">
                ✕
              </div>
              <h1 className="text-xl font-bold text-slate-900">
                Verifikasi gagal
              </h1>
              <Alert kind="error">{pesan}</Alert>
              <p className="text-sm text-slate-600">
                Tautan mungkin sudah kedaluwarsa atau sudah dipakai. Coba daftar
                ulang atau hubungi dukungan.
              </p>
              <Link href="/login" className="block">
                <Button variant="secondary" className="w-full">
                  Ke halaman masuk
                </Button>
              </Link>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<Spinner label="Memverifikasi email…" />}>
      <VerifyEmailInner />
    </Suspense>
  );
}
