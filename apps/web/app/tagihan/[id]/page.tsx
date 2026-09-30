"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { formatRupiah, formatSisaWaktu, formatTanggal } from "@/lib/format";
import type { Invoice } from "@/lib/types";
import { Alert, Button, Card, PageHeader, Spinner } from "@/components/ui";
import { invoiceStatusLabel, paymentStatusLabel } from "@/components/badges";

const MAX_FILE = 5 * 1024 * 1024; // 5 MB
const TIPE_DIIZINKAN = ["image/jpeg", "image/png", "application/pdf"];

function DetailTagihan() {
  const params = useParams();
  const invoiceId = params.id as string;

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sisa, setSisa] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [uploadSukses, setUploadSukses] = useState("");
  const [uploadLoading, setUploadLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const muat = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const inv = await api.get<Invoice>(`/billing/invoices/${invoiceId}`);
      setInvoice(inv);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal memuat detail invoice."
      );
    } finally {
      setLoading(false);
    }
  }, [invoiceId]);

  useEffect(() => {
    muat();
  }, [muat]);

  // Hitung mundur kedaluwarsa.
  useEffect(() => {
    if (!invoice?.expires_at) return;
    const target = new Date(invoice.expires_at).getTime();
    const tick = () => setSisa(formatSisaWaktu(target - Date.now()));
    tick();
    timerRef.current = setInterval(tick, 1000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [invoice?.expires_at]);

  function pilihFile(e: React.ChangeEvent<HTMLInputElement>) {
    setUploadError("");
    setUploadSukses("");
    const f = e.target.files?.[0];
    if (!f) {
      setFile(null);
      return;
    }
    if (!TIPE_DIIZINKAN.includes(f.type)) {
      setUploadError("Format berkas harus JPG, PNG, atau PDF.");
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      return;
    }
    if (f.size > MAX_FILE) {
      setUploadError("Ukuran berkas maksimal 5 MB.");
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      return;
    }
    setFile(f);
  }

  async function unggahBukti(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setUploadError("Pilih berkas bukti transfer terlebih dahulu.");
      return;
    }
    setUploadError("");
    setUploadSukses("");
    setUploadLoading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      await api.postForm(`/billing/invoices/${invoiceId}/payment-proof`, form);
      setUploadSukses(
        "Bukti transfer berhasil diunggah. Tim kami akan memverifikasi pembayaran Anda."
      );
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      await muat();
    } catch (err) {
      setUploadError(
        err instanceof ApiError
          ? err.message
          : "Gagal mengunggah bukti. Periksa koneksi internet Anda."
      );
    } finally {
      setUploadLoading(false);
    }
  }

  if (loading) return <Spinner label="Memuat detail invoice…" />;
  if (error || !invoice)
    return <Alert kind="error">{error || "Invoice tidak ditemukan."}</Alert>;

  const payment = invoice.payment;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <PageHeader
        title={`Invoice ${invoice.code}`}
        subtitle={`Paket ${invoice.plan_name}`}
        action={
          <Link href="/tagihan">
            <Button variant="secondary">Kembali</Button>
          </Link>
        }
      />

      {/* TOTAL TRANSFER — besar & jelas */}
      <Card className="mb-6 border-2 border-orange-200 bg-orange-50/50 text-center">
        <p className="text-sm font-medium uppercase tracking-wide text-slate-500">
          Total transfer
        </p>
        <p className="mt-2 text-4xl font-extrabold tracking-tight text-orange-700 sm:text-5xl">
          {formatRupiah(invoice.amount_total)}
        </p>
        <div className="mx-auto mt-4 max-w-md space-y-1 text-sm text-slate-600">
          <div className="flex justify-between">
            <span>Nominal dasar</span>
            <span className="font-medium">{formatRupiah(invoice.amount_base)}</span>
          </div>
          <div className="flex justify-between">
            <span>Kode unik</span>
            <span className="font-mono font-medium">
              {invoice.unique_code}
            </span>
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Transfer tepat sesuai total di atas agar pembayaran terverifikasi
          otomatis.
        </p>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Info bank */}
        <Card>
          <h2 className="text-base font-semibold text-slate-900">
            Transfer ke rekening
          </h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div>
              <dt className="text-slate-500">Bank</dt>
              <dd className="font-semibold text-slate-900">
                {invoice.bank.bank_name}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Nomor rekening</dt>
              <dd className="font-mono text-lg font-bold text-slate-900">
                {invoice.bank.account_number}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Atas nama</dt>
              <dd className="font-medium text-slate-900">
                {invoice.bank.account_name}
              </dd>
            </div>
          </dl>
        </Card>

        {/* Status & kedaluwarsa */}
        <Card>
          <h2 className="text-base font-semibold text-slate-900">
            Status invoice
          </h2>
          <dl className="mt-4 space-y-3 text-sm">
            <div>
              <dt className="text-slate-500">Status</dt>
              <dd className="font-semibold text-slate-900">
                {invoiceStatusLabel(invoice.status)}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Batas pembayaran</dt>
              <dd className="font-medium text-slate-900">
                {formatTanggal(invoice.expires_at, true)}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Sisa waktu</dt>
              <dd
                className={`font-bold ${
                  sisa === "Kedaluwarsa" ? "text-red-600" : "text-amber-600"
                }`}
              >
                {sisa}
              </dd>
            </div>
          </dl>
        </Card>
      </div>

      {/* Status pembayaran */}
      <Card className="mt-6">
        <h2 className="text-base font-semibold text-slate-900">
          Bukti pembayaran
        </h2>
        {payment ? (
          <div className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-500">Status</span>
              <span className="font-semibold text-slate-900">
                {paymentStatusLabel(payment.status)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Diunggah</span>
              <span className="text-slate-900">
                {formatTanggal(payment.uploaded_at, true)}
              </span>
            </div>
            {payment.status === "rejected" && payment.reason && (
              <Alert kind="error">
                Bukti ditolak: {payment.reason}. Silakan unggah ulang bukti
                yang valid.
              </Alert>
            )}
            {payment.status === "approved" && (
              <Alert kind="success">
                Pembayaran disetujui. Keanggotaan Anda sudah aktif.
              </Alert>
            )}
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-500">
            Belum ada bukti pembayaran yang diunggah.
          </p>
        )}

        {(!payment || payment.status === "rejected") && (
          <form onSubmit={unggahBukti} className="mt-4 space-y-3">
            {uploadError && <Alert kind="error">{uploadError}</Alert>}
            {uploadSukses && <Alert kind="success">{uploadSukses}</Alert>}
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-slate-700">
                Berkas bukti transfer (JPG/PNG/PDF, maks. 5 MB)
              </span>
              <input
                ref={fileRef}
                type="file"
                accept=".jpg,.jpeg,.png,.pdf"
                onChange={pilihFile}
                className="block w-full text-sm text-slate-600 file:mr-4 file:rounded-xl file:border-0 file:bg-orange-50 file:px-4 file:py-2.5 file:text-sm file:font-semibold file:text-orange-700 hover:file:bg-orange-100"
              />
            </label>
            {file && (
              <p className="text-sm text-slate-600">
                Berkas terpilih:{" "}
                <span className="font-medium">{file.name}</span>
              </p>
            )}
            <Button type="submit" disabled={uploadLoading || !file}>
              {uploadLoading ? "Mengunggah…" : "Unggah bukti transfer"}
            </Button>
          </form>
        )}
      </Card>
    </div>
  );
}

export default function DetailTagihanPage() {
  return (
    <RequireAuth>
      <DetailTagihan />
    </RequireAuth>
  );
}
