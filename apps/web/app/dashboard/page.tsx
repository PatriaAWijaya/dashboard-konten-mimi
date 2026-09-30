"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
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

interface PeriodeData {
  tahun: number;
  bulan: number;
  label: string;
  jumlah_konten: number;
}

interface BrandRingkasan {
  id: string;
  name: string;
  platform: string | null;
  display_name: string;
  total_konten: number;
  periode: PeriodeData[];
}

function DasborIsi() {
  const { organizations, orgsLoading, selectedOrgId, refreshOrgs } = useAuth();
  const searchParams = useSearchParams();
  const [org, setOrg] = useState<OrganizationDetail | null>(null);
  const [ringkasan, setRingkasan] = useState<BrandRingkasan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [couponBanner, setCouponBanner] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    const ok = searchParams.get("coupon_ok");
    const exp = searchParams.get("coupon_exp");
    const err = searchParams.get("coupon_error");
    if (ok) {
      setCouponBanner({
        kind: "success",
        text: `Kupon diterapkan: diskon ${ok}%${exp ? `, berlaku hingga ${exp}` : ""}.`,
      });
    } else if (err) {
      setCouponBanner({ kind: "error", text: err });
    }
    // Bersihkan query param agar banner tidak muncul lagi saat refresh.
    if (ok || err) {
      const url = new URL(window.location.href);
      url.searchParams.delete("coupon_ok");
      url.searchParams.delete("coupon_exp");
      url.searchParams.delete("coupon_error");
      window.history.replaceState({}, "", url.toString());
    }
  }, [searchParams]);

  useEffect(() => {
    if (orgsLoading) return;
    if (!selectedOrgId) {
      setOrg(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    Promise.all([
      api.get<OrganizationDetail>(`/organizations/${selectedOrgId}`),
      api
        .get<{ brands: BrandRingkasan[] }>(`/organizations/${selectedOrgId}/ringkasan-data`)
        .catch(() => ({ brands: [] as BrandRingkasan[] })),
    ])
      .then(([d, r]) => {
        setOrg(d);
        setRingkasan(r.brands || []);
      })
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
  const brandsBerdata = ringkasan.filter((b) => b.periode.length > 0);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      {couponBanner && (
        <div className="mb-4">
          <Alert kind={couponBanner.kind}>{couponBanner.text}</Alert>
        </div>
      )}
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
        <Card className="relative flex flex-col overflow-hidden">
          {/* Latar gradien lembut — eye-catching tapi minimalis */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(420px 220px at 15% 0%, rgba(99,102,241,0.14), transparent 60%), radial-gradient(360px 220px at 90% 100%, rgba(236,72,153,0.12), transparent 60%)",
            }}
          />
          <div className="relative flex flex-1 flex-col">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/80 text-2xl shadow-sm">
              🔗
            </div>
            <h3 className="text-base font-bold text-slate-900">Coming Soon</h3>
            <p className="mt-2 flex-1 text-sm text-slate-500">
              Analisa realtime performa sosial media — sinkronisasi otomatis
              dari akun TikTok dan Instagram brand Anda.
            </p>
            <div className="mt-4 flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-base text-white shadow-sm">
                🎵
              </span>
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-amber-400 via-pink-500 to-purple-600 text-base text-white shadow-sm">
                📸
              </span>
              <span className="text-xs font-medium text-slate-400">
                TikTok & Instagram
              </span>
            </div>
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

      {/* Data yang sudah diinput — hanya tampil bila member sudah pernah upload */}
      {brandsBerdata.length > 0 && (
        <>
          <div className="mb-4 mt-10">
            <h2 className="text-lg font-bold text-slate-900">Data yang sudah diinput</h2>
            <p className="text-sm text-slate-500">
              Daftar akun dan periode data yang sudah pernah Anda masukkan.
            </p>
          </div>
          <div className="space-y-4">
            {brandsBerdata.map((b) => (
              <Card key={b.id}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-base font-bold text-slate-900">
                    {b.display_name}
                  </h3>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                    {b.total_konten} konten
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {b.periode.map((p) => (
                    <Link
                      key={`${p.tahun}-${p.bulan}`}
                      href={`/brand/${b.id}/analisa?bulan=${p.tahun}-${String(p.bulan).padStart(2, "0")}`}
                      className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
                    >
                      📅 {p.label}
                      <span className="text-slate-400">· {p.jumlah_konten}</span>
                    </Link>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <Suspense fallback={<Spinner label="Memuat dasbor…" />}>
        <DasborIsi />
      </Suspense>
    </RequireAuth>
  );
}
