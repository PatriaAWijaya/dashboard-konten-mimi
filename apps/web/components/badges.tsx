"use client";

// Badge status membership: Aktif / Tenggang / Kedaluwarsa / Belum ada.
export function membershipLabel(status: string | null | undefined): string {
  switch ((status || "").toLowerCase()) {
    case "active":
      return "Aktif";
    case "grace":
      return "Tenggang";
    case "expired":
      return "Kedaluwarsa";
    default:
      return "Belum ada";
  }
}

export function membershipTone(status: string | null | undefined): string {
  switch ((status || "").toLowerCase()) {
    case "active":
      return "bg-emerald-100 text-emerald-800 ring-emerald-200";
    case "grace":
      return "bg-amber-100 text-amber-800 ring-amber-200";
    case "expired":
      return "bg-red-100 text-red-800 ring-red-200";
    default:
      return "bg-slate-100 text-slate-600 ring-slate-200";
  }
}

export function MembershipBadge({
  status,
  className = "",
}: {
  status: string | null | undefined;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${membershipTone(
        status
      )} ${className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {membershipLabel(status)}
    </span>
  );
}

export function invoiceStatusLabel(status: string): string {
  switch ((status || "").toLowerCase()) {
    case "pending":
      return "Menunggu pembayaran";
    case "paid":
      return "Lunas";
    case "expired":
      return "Kedaluwarsa";
    case "cancelled":
      return "Dibatalkan";
    default:
      return status || "-";
  }
}

export function paymentStatusLabel(status: string): string {
  switch ((status || "").toLowerCase()) {
    case "menunggu_verifikasi":
    case "pending":
      return "Menunggu verifikasi";
    case "disetujui":
    case "approved":
      return "Disetujui";
    case "ditolak":
    case "rejected":
      return "Ditolak";
    default:
      return status || "-";
  }
}

// Badge status konten AI: MENANG / CUKUP / KURANG / DATA_BELUM_CUKUP.
export function statusKontenLabel(status: string): string {
  switch ((status || "").toUpperCase()) {
    case "MENANG":
      return "MENANG";
    case "CUKUP":
      return "CUKUP";
    case "KURANG":
      return "KURANG";
    case "DATA_BELUM_CUKUP":
      return "DATA BELUM CUKUP";
    default:
      return status || "-";
  }
}

export function statusKontenTone(status: string): string {
  switch ((status || "").toUpperCase()) {
    case "MENANG":
      return "bg-emerald-100 text-emerald-800 ring-emerald-200";
    case "CUKUP":
      return "bg-amber-100 text-amber-800 ring-amber-200";
    case "KURANG":
      return "bg-red-100 text-red-800 ring-red-200";
    default:
      return "bg-slate-100 text-slate-600 ring-slate-200";
  }
}

export function StatusKontenBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${statusKontenTone(
        status
      )}`}
    >
      {statusKontenLabel(status)}
    </span>
  );
}

// Badge verdict analisa: Sesuai / Kurang sesuai / Tidak sesuai.
export function verdictTone(verdict: string): string {
  const v = (verdict || "").toLowerCase();
  if (v.startsWith("tidak")) return "bg-red-100 text-red-800 ring-red-200";
  if (v.startsWith("kurang")) return "bg-amber-100 text-amber-800 ring-amber-200";
  return "bg-emerald-100 text-emerald-800 ring-emerald-200";
}

// Badge label sumber niche: DATA / ESTIMASI / KLAIM.
export function labelSumberTone(label: string): string {
  switch ((label || "").toUpperCase()) {
    case "DATA":
      return "bg-emerald-100 text-emerald-800 ring-emerald-200";
    case "ESTIMASI":
      return "bg-sky-100 text-sky-800 ring-sky-200";
    default:
      return "bg-slate-100 text-slate-600 ring-slate-200";
  }
}
