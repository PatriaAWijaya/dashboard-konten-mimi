"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth, RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { formatRupiah, formatTanggal } from "@/lib/format";
import type { Invoice, Membership, Plan } from "@/lib/types";
import {
  Alert,
  Button,
  Card,
  PageHeader,
  Spinner,
} from "@/components/ui";
import { MembershipBadge, invoiceStatusLabel } from "@/components/badges";

function TagihanIsi() {
  const router = useRouter();
  const { selectedOrgId, organizations } = useAuth();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [membership, setMembership] = useState<Membership | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [buatLoading, setBuatLoading] = useState<string | null>(null);

  const org = organizations.find((o) => o.id === selectedOrgId);

  useEffect(() => {
    if (!selectedOrgId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    Promise.all([
      api.get<Plan[]>("/plans"),
      api.get<Invoice[]>(`/billing/invoices?organization_id=${selectedOrgId}`),
      api.get<Membership | null>(
        `/billing/memberships?organization_id=${selectedOrgId}`
      ),
    ])
      .then(([p, inv, m]) => {
        setPlans(p);
        setInvoices(inv);
        setMembership(m);
      })
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : "Gagal memuat data tagihan."
        )
      )
      .finally(() => setLoading(false));
  }, [selectedOrgId]);

  async function buatInvoice(planId: string) {
    if (!selectedOrgId) return;
    setBuatLoading(planId);
    setError("");
    try {
      const inv = await api.post<Invoice>("/billing/invoices", {
        organization_id: selectedOrgId,
        plan_id: planId,
      });
      router.push(`/tagihan/${inv.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal membuat invoice."
      );
    } finally {
      setBuatLoading(null);
    }
  }

  if (loading) return <Spinner label="Memuat data tagihan…" />;

  if (!selectedOrgId) {
    return (
      <div className="mx-auto max-w-xl py-12 text-center">
        <Alert kind="warning">
          Pilih atau buat organisasi terlebih dahulu untuk mengelola tagihan.
        </Alert>
        <Link href="/dashboard" className="mt-4 inline-block">
          <Button>Ke dasbor</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader
        title="Tagihan"
        subtitle={`Organisasi: ${org?.name ?? "-"}`}
        action={membership && <MembershipBadge status={membership.status} />}
      />
      {error && (
        <div className="mb-6">
          <Alert kind="error">{error}</Alert>
        </div>
      )}

      {/* Pilih paket */}
      <h2 className="mb-4 text-lg font-bold text-slate-900">Pilih paket</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {plans.map((plan) => (
          <Card key={plan.id} className="flex flex-col">
            <h3 className="text-lg font-bold text-slate-900">{plan.name}</h3>
            <p className="mt-2 text-3xl font-extrabold text-orange-600">
              {formatRupiah(plan.price)}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              per {plan.period_months} bulan · {plan.seats} kursi
            </p>
            <ul className="mt-4 flex-1 space-y-2">
              {plan.features.map((f, i) => (
                <li key={i} className="flex gap-2 text-sm text-slate-600">
                  <span className="text-emerald-500">✓</span>
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <Button
              onClick={() => buatInvoice(plan.id)}
              disabled={buatLoading !== null}
              className="mt-5 w-full"
            >
              {buatLoading === plan.id ? "Membuat invoice…" : "Pilih paket ini"}
            </Button>
          </Card>
        ))}
      </div>
      {plans.length === 0 && (
        <p className="text-sm text-slate-500">
          Daftar paket belum tersedia. Coba muat ulang halaman.
        </p>
      )}

      {/* Daftar invoice */}
      <h2 className="mb-4 mt-10 text-lg font-bold text-slate-900">
        Riwayat invoice
      </h2>
      {invoices.length === 0 ? (
        <Card>
          <p className="text-sm text-slate-500">
            Belum ada invoice. Pilih paket di atas untuk membuat invoice
            pertama Anda.
          </p>
        </Card>
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <th className="px-5 py-3 font-semibold">Kode</th>
                <th className="px-5 py-3 font-semibold">Paket</th>
                <th className="px-5 py-3 font-semibold">Total</th>
                <th className="px-5 py-3 font-semibold">Status</th>
                <th className="px-5 py-3 font-semibold">Kedaluwarsa</th>
                <th className="px-5 py-3 font-semibold"></th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-5 py-3 font-mono text-xs text-slate-700">
                    {inv.code}
                  </td>
                  <td className="px-5 py-3 text-slate-900">{inv.plan_name}</td>
                  <td className="px-5 py-3 font-semibold text-slate-900">
                    {formatRupiah(inv.amount_total)}
                  </td>
                  <td className="px-5 py-3 text-slate-600">
                    {invoiceStatusLabel(inv.status)}
                  </td>
                  <td className="px-5 py-3 text-slate-600">
                    {formatTanggal(inv.expires_at, true)}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Link
                      href={`/tagihan/${inv.id}`}
                      className="font-semibold text-orange-600 hover:text-orange-700"
                    >
                      Detail
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

export default function TagihanPage() {
  return (
    <RequireAuth>
      <TagihanIsi />
    </RequireAuth>
  );
}
