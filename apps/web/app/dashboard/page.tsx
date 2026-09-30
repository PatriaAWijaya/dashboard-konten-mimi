"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth, RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { formatTanggal } from "@/lib/format";
import type { OrganizationDetail } from "@/lib/types";
import { Alert, Button, Card, Input, PageHeader, Spinner } from "@/components/ui";
import { KirimUlangVerifikasi } from "@/components/KirimUlangVerifikasi";
import { MembershipBadge, membershipLabel } from "@/components/badges";

// Wizard organisasi pertama untuk user yang belum punya organisasi.
function WizardOrganisasi({ onSelesai }: { onSelesai: () => void }) {
  const { user } = useAuth();
  const [nama, setNama] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const perluVerifikasi = error.toLowerCase().includes("verifikasi");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const org = await api.post<{ id: string; name: string }>("/organizations", {
        name: nama.trim(),
      });
      if (typeof window !== "undefined") {
        window.localStorage.setItem("dkai_org_id", org.id);
      }
      onSelesai();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Gagal membuat organisasi. Periksa koneksi internet Anda."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl py-12">
      <Card>
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-100 text-3xl">
            🏢
          </div>
          <h1 className="text-2xl font-bold text-slate-900">
            Buat organisasi pertama Anda
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Organisasi adalah wadah untuk brand-brand yang Anda kelola. Anda
            bisa menambah organisasi lain kapan saja.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          {error && <Alert kind="error">{error}</Alert>}
          {perluVerifikasi && user?.email && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
              <p className="mb-3 text-sm text-amber-800">
                Akun Anda belum terverifikasi. Verifikasi email terlebih dahulu,
                lalu coba buat organisasi lagi.
              </p>
              <KirimUlangVerifikasi email={user.email} />
            </div>
          )}
          <Input
            label="Nama organisasi"
            required
            placeholder="Contoh: PT Maju Bersama"
            value={nama}
            onChange={(e) => setNama(e.target.value)}
          />
          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "Memproses…" : "Buat organisasi"}
          </Button>
        </form>
      </Card>
    </div>
  );
}

function DasborIsi() {
  const { organizations, orgsLoading, selectedOrgId, refreshOrgs } = useAuth();
  const [org, setOrg] = useState<OrganizationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (orgsLoading) return;
    if (!selectedOrgId) {
      setOrg(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    api
      .get<OrganizationDetail>(`/organizations/${selectedOrgId}`)
      .then((d) => setOrg(d))
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : "Gagal memuat data organisasi."
        )
      )
      .finally(() => setLoading(false));
  }, [selectedOrgId, orgsLoading]);

  if (orgsLoading || loading) return <Spinner label="Memuat dasbor…" />;
  if (error) return <Alert kind="error">{error}</Alert>;

  // Belum punya organisasi → wizard.
  if (organizations.length === 0 || !selectedOrgId) {
    return <WizardOrganisasi onSelesai={refreshOrgs} />;
  }

  const membership = org?.membership;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader
        title={`Halo, selamat datang di ${org?.name ?? "dasbor Anda"}`}
        subtitle="Pantau status keanggotaan dan mulai analisis konten Anda."
        action={
          selectedOrgId && (
            <Link href={`/organisasi/${selectedOrgId}`}>
              <Button variant="secondary">Kelola organisasi</Button>
            </Link>
          )
        }
      />

      {/* Status membership */}
      <Card className="mb-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              Status keanggotaan
            </h2>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <MembershipBadge status={membership?.status} />
              {membership?.plan_name && (
                <span className="text-sm text-slate-600">
                  Paket: <span className="font-semibold">{membership.plan_name}</span>
                </span>
              )}
              {membership?.ends_at && (
                <span className="text-sm text-slate-500">
                  Berlaku hingga {formatTanggal(membership.ends_at)}
                </span>
              )}
            </div>
            {membership?.status === "grace" && membership.grace_ends_at && (
              <Alert kind="warning">
                Masa tenggang berakhir {formatTanggal(membership.grace_ends_at, true)}.
                Perpanjang keanggotaan agar fitur tidak terkunci.
              </Alert>
            )}
            {(!membership || membership.status !== "active") && (
              <p className="mt-2 text-sm text-slate-500">
                {membershipLabel(membership?.status)} — aktifkan keanggotaan
                untuk membuka seluruh fitur analisis.
              </p>
            )}
          </div>
          <Link href="/tagihan">
            <Button>
              {membership?.status === "active" ? "Perpanjang" : "Aktifkan"} keanggotaan
            </Button>
          </Link>
        </div>
      </Card>

      {/* Empty state Fase 0 */}
      <div className="mb-4">
        <h2 className="text-lg font-bold text-slate-900">Sumber data konten</h2>
        <p className="text-sm text-slate-500">
          Hubungkan sumber data untuk mulai menganalisis performa konten Anda.
        </p>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <Card className="flex flex-col">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-2xl">
            🔗
          </div>
          <h3 className="text-base font-bold text-slate-900">
            Hubungkan akun TikTok / Instagram
          </h3>
          <p className="mt-2 flex-1 text-sm text-slate-500">
            Sinkronisasi otomatis data performa dari akun TikTok dan Instagram
            brand Anda.
          </p>
          <div className="mt-4">
            <span className="inline-flex items-center rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">
              Segera hadir — Fase 1
            </span>
          </div>
        </Card>
        <Card className="flex flex-col">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-2xl">
            📤
          </div>
          <h3 className="text-base font-bold text-slate-900">Unggah CSV</h3>
          <p className="mt-2 flex-1 text-sm text-slate-500">
            Unggah data performa konten secara manual dalam format CSV untuk
            dianalisis.
          </p>
          <div className="mt-4">
            <Link href="/upload">
              <Button>Unggah sekarang</Button>
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DasborIsi />
    </RequireAuth>
  );
}
