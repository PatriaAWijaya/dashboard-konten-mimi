"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { RequireAuth } from "@/lib/auth";
import { api, apiDownload, ApiError } from "@/lib/api";
import { formatRupiah, formatTanggal } from "@/lib/format";
import type {
  AdminUserRow,
  AuditLog,
  QueuedPayment,
} from "@/lib/types";
import {
  Alert,
  Button,
  Card,
  Input,
  PageHeader,
  Spinner,
} from "@/components/ui";
import { paymentStatusLabel } from "@/components/badges";

type Tab = "antrean" | "riwayat" | "member" | "audit";

function unduhBukti(paymentId: string, fileName: string, setError: (s: string) => void) {
  apiDownload(`/billing/payments/${paymentId}/file`)
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName || `bukti-${paymentId}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    })
    .catch((err) =>
      setError(
        err instanceof ApiError ? err.message : "Gagal mengunduh bukti."
      )
    );
}

// ---------- Tab Antrean ----------
function TabAntrean() {
  const [items, setItems] = useState<QueuedPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sukses, setSukses] = useState("");
  const [prosesId, setProsesId] = useState<string | null>(null);
  const [alasan, setAlasan] = useState<Record<string, string>>({});

  const muat = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get<QueuedPayment[]>("/admin/payments/queue");
      setItems(data);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal memuat antrean."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    muat();
  }, [muat]);

  async function setujui(paymentId: string) {
    setProsesId(paymentId);
    setError("");
    setSukses("");
    try {
      await api.post(`/admin/payments/${paymentId}/approve`, {});
      setSukses("Pembayaran disetujui, keanggotaan diaktifkan.");
      await muat();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal menyetujui.");
    } finally {
      setProsesId(null);
    }
  }

  async function tolak(paymentId: string) {
    const reason = (alasan[paymentId] || "").trim();
    if (!reason) {
      setError("Isi alasan penolakan terlebih dahulu.");
      return;
    }
    setProsesId(paymentId);
    setError("");
    setSukses("");
    try {
      await api.post(`/admin/payments/${paymentId}/reject`, { reason });
      setSukses("Pembayaran ditolak.");
      await muat();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal menolak.");
    } finally {
      setProsesId(null);
    }
  }

  if (loading) return <Spinner label="Memuat antrean…" />;

  return (
    <div className="space-y-4">
      {error && <Alert kind="error">{error}</Alert>}
      {sukses && <Alert kind="success">{sukses}</Alert>}
      {items.length === 0 && (
        <Card>
          <p className="text-sm text-slate-500">
            Antrean kosong. Tidak ada pembayaran menunggu verifikasi.
          </p>
        </Card>
      )}
      {items.map((item) => (
        <Card key={item.payment.id}>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-1 text-sm">
              <p className="text-base font-bold text-slate-900">
                {formatRupiah(item.invoice.amount_total)}
              </p>
              <p className="text-slate-600">
                <span className="font-medium">User:</span> {item.user.name} (
                {item.user.email})
              </p>
              <p className="text-slate-600">
                <span className="font-medium">Organisasi:</span>{" "}
                {item.organization.name}
              </p>
              <p className="text-slate-600">
                <span className="font-medium">Invoice:</span>{" "}
                <span className="font-mono text-xs">{item.invoice.code}</span> —{" "}
                {item.invoice.plan_name}
              </p>
              <p className="text-slate-500">
                Diunggah {formatTanggal(item.payment.uploaded_at, true)} ·{" "}
                {item.payment.file_name}
              </p>
              <button
                type="button"
                onClick={() =>
                  unduhBukti(item.payment.id, item.payment.file_name, setError)
                }
                className="font-semibold text-indigo-600 underline hover:text-indigo-800"
              >
                Unduh bukti pembayaran
              </button>
            </div>
            <div className="w-full space-y-3 lg:w-72">
              <div className="flex gap-2">
                <Button
                  onClick={() => setujui(item.payment.id)}
                  disabled={prosesId === item.payment.id}
                  className="flex-1"
                >
                  {prosesId === item.payment.id ? "Memproses…" : "Setujui"}
                </Button>
                <Button
                  variant="danger"
                  onClick={() => tolak(item.payment.id)}
                  disabled={prosesId === item.payment.id}
                  className="flex-1"
                >
                  Tolak
                </Button>
              </div>
              <Input
                label="Alasan penolakan"
                placeholder="Wajib diisi jika menolak"
                value={alasan[item.payment.id] || ""}
                onChange={(e) =>
                  setAlasan((prev) => ({
                    ...prev,
                    [item.payment.id]: e.target.value,
                  }))
                }
              />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

// ---------- Tab Riwayat ----------
function TabRiwayat() {
  const [items, setItems] = useState<QueuedPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<QueuedPayment[]>("/admin/payments/history")
      .then(setItems)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Gagal memuat riwayat.")
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner label="Memuat riwayat…" />;
  if (error) return <Alert kind="error">{error}</Alert>;

  return (
    <Card className="overflow-x-auto p-0">
      {items.length === 0 ? (
        <p className="p-5 text-sm text-slate-500">Belum ada riwayat pembayaran.</p>
      ) : (
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <th className="px-5 py-3 font-semibold">Tanggal</th>
              <th className="px-5 py-3 font-semibold">User</th>
              <th className="px-5 py-3 font-semibold">Organisasi</th>
              <th className="px-5 py-3 font-semibold">Nominal</th>
              <th className="px-5 py-3 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.payment.id} className="border-b border-slate-100 last:border-0">
                <td className="px-5 py-3 text-slate-600">
                  {formatTanggal(item.payment.uploaded_at, true)}
                </td>
                <td className="px-5 py-3 text-slate-900">{item.user.name}</td>
                <td className="px-5 py-3 text-slate-600">
                  {item.organization.name}
                </td>
                <td className="px-5 py-3 font-semibold text-slate-900">
                  {formatRupiah(item.invoice.amount_total)}
                </td>
                <td className="px-5 py-3 text-slate-600">
                  {paymentStatusLabel(item.payment.status)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

// ---------- Tab Member ----------
function TabMember() {
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sukses, setSukses] = useState("");
  const [prosesId, setProsesId] = useState<string | null>(null);

  const muat = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.get<AdminUserRow[]>("/admin/users");
      setUsers(data);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal memuat daftar user."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    muat();
  }, [muat]);

  async function ubahStatus(userId: string, aktif: boolean) {
    setProsesId(userId);
    setError("");
    setSukses("");
    try {
      await api.post(
        `/admin/users/${userId}/${aktif ? "activate" : "suspend"}`,
        {}
      );
      setSukses(
        aktif ? "User diaktifkan kembali." : "User ditangguhkan (suspend)."
      );
      await muat();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Gagal mengubah status.");
    } finally {
      setProsesId(null);
    }
  }

  if (loading) return <Spinner label="Memuat daftar user…" />;

  return (
    <div className="space-y-4">
      {error && <Alert kind="error">{error}</Alert>}
      {sukses && <Alert kind="success">{sukses}</Alert>}
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <th className="px-5 py-3 font-semibold">Nama</th>
              <th className="px-5 py-3 font-semibold">Email</th>
              <th className="px-5 py-3 font-semibold">Status</th>
              <th className="px-5 py-3 font-semibold">Admin</th>
              <th className="px-5 py-3 font-semibold"></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-slate-100 last:border-0">
                <td className="px-5 py-3 font-medium text-slate-900">{u.name}</td>
                <td className="px-5 py-3 text-slate-600">{u.email}</td>
                <td className="px-5 py-3">
                  <span
                    className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      u.is_active
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-red-100 text-red-800"
                    }`}
                  >
                    {u.is_active ? "Aktif" : "Ditangguhkan"}
                  </span>
                </td>
                <td className="px-5 py-3 text-slate-600">
                  {u.is_superadmin ? "Ya" : "-"}
                </td>
                <td className="px-5 py-3 text-right">
                  <Button
                    variant="secondary"
                    onClick={() => ubahStatus(u.id, !u.is_active)}
                    disabled={prosesId === u.id}
                    className="px-3! py-1.5! text-xs"
                  >
                    {prosesId === u.id
                      ? "Memproses…"
                      : u.is_active
                        ? "Tangguhkan"
                        : "Aktifkan"}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

// ---------- Tab Audit Log ----------
function TabAudit() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<AuditLog[]>("/admin/audit-logs?limit=50")
      .then(setLogs)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Gagal memuat audit log.")
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner label="Memuat audit log…" />;
  if (error) return <Alert kind="error">{error}</Alert>;

  return (
    <Card className="overflow-x-auto p-0">
      {logs.length === 0 ? (
        <p className="p-5 text-sm text-slate-500">Belum ada aktivitas tercatat.</p>
      ) : (
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
              <th className="px-5 py-3 font-semibold">Waktu</th>
              <th className="px-5 py-3 font-semibold">Aktor</th>
              <th className="px-5 py-3 font-semibold">Aksi</th>
              <th className="px-5 py-3 font-semibold">Detail</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id} className="border-b border-slate-100 last:border-0">
                <td className="whitespace-nowrap px-5 py-3 text-slate-600">
                  {formatTanggal(log.created_at, true)}
                </td>
                <td className="px-5 py-3 text-slate-900">
                  {log.actor_name || log.actor_email || "-"}
                </td>
                <td className="px-5 py-3 font-medium text-slate-900">
                  {log.action}
                </td>
                <td className="px-5 py-3 text-slate-600">{log.detail || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

// ---------- Halaman ----------
const TABS: { id: Tab; label: string }[] = [
  { id: "antrean", label: "Antrean" },
  { id: "riwayat", label: "Riwayat" },
  { id: "member", label: "Member" },
  { id: "audit", label: "Audit Log" },
];

function AdminIsi() {
  const [tab, setTab] = useState<Tab>("antrean");

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Panel Admin"
        subtitle="Verifikasi pembayaran, kelola user, dan pantau aktivitas."
        action={
          <Link href="/admin/pengaturan">
            <Button variant="secondary">Pengaturan Integrasi</Button>
          </Link>
        }
      />
      <div className="mb-6 flex gap-1 overflow-x-auto border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`whitespace-nowrap px-4 py-2.5 text-sm font-semibold transition ${
              tab === t.id
                ? "border-b-2 border-indigo-600 text-indigo-700"
                : "text-slate-500 hover:text-slate-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "antrean" && <TabAntrean />}
      {tab === "riwayat" && <TabRiwayat />}
      {tab === "member" && <TabMember />}
      {tab === "audit" && <TabAudit />}
    </div>
  );
}

export default function AdminPage() {
  return (
    <RequireAuth superadmin>
      <AdminIsi />
    </RequireAuth>
  );
}
