"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { Alert, Button } from "@/components/ui";

// Jeda antar kirim ulang (detik) — selaras dengan cooldown di backend.
const COOLDOWN_DETIK = 60;

export function KirimUlangVerifikasi({ email }: { email: string }) {
  const [status, setStatus] = useState<"idle" | "loading" | "terkirim" | "error">("idle");
  const [sisa, setSisa] = useState(0);
  const [pesanError, setPesanError] = useState("");
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, []);

  function mulaiCooldown() {
    setSisa(COOLDOWN_DETIK);
    timer.current = setInterval(() => {
      setSisa((s) => {
        if (s <= 1) {
          if (timer.current) clearInterval(timer.current);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
  }

  async function handleKirim() {
    if (!email.trim() || status === "loading" || sisa > 0) return;
    setStatus("loading");
    setPesanError("");
    try {
      const res = await api.post<{ message: string }>("/auth/resend-verification", {
        email: email.trim(),
      });
      setStatus("terkirim");
      mulaiCooldown();
      // Sambutan backend generik; tampilkan panduan yang jelas.
      void res;
    } catch (err) {
      setStatus("error");
      setPesanError(
        err instanceof ApiError ? err.message : "Gagal mengirim ulang. Coba lagi nanti."
      );
    }
  }

  return (
    <div className="space-y-2">
      {status === "terkirim" && (
        <Alert kind="success">
          Email verifikasi baru telah dikirim ke <span className="font-semibold">{email}</span>.
          Periksa kotak masuk (dan folder spam) Anda.
        </Alert>
      )}
      {status === "error" && <Alert kind="error">{pesanError}</Alert>}
      <Button
        type="button"
        variant="secondary"
        onClick={handleKirim}
        disabled={status === "loading" || sisa > 0 || !email.trim()}
        className="w-full"
      >
        {status === "loading"
          ? "Mengirim…"
          : sisa > 0
            ? `Kirim ulang dalam ${sisa} detik`
            : status === "terkirim"
              ? "Kirim ulang email verifikasi"
              : "Tidak menerima email? Kirim ulang"}
      </Button>
    </div>
  );
}
