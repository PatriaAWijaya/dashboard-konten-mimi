"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useAuth, RequireAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { formatTanggal } from "@/lib/format";
import type { Brand, Membership, OrgMember } from "@/lib/types";
import {
  Alert,
  Button,
  Card,
  Input,
  PageHeader,
  Select,
  Spinner,
} from "@/components/ui";
import { MembershipBadge } from "@/components/badges";

interface Undangan {
  id: string;
  email: string;
  role: string;
  status: string;
  created_at: string;
}

interface OrgDetail {
  id: string;
  name: string;
  created_at: string;
  membership: Membership | null;
}

function KelolaOrganisasi() {
  const params = useParams();
  const orgId = params.id as string;
  const { user, selectOrg } = useAuth();

  const [org, setOrg] = useState<OrgDetail | null>(null);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [undangan, setUndangan] = useState<Undangan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Form brand
  const [namaBrand, setNamaBrand] = useState("");
  const [platformBrand, setPlatformBrand] = useState("");
  const [industri, setIndustri] = useState("");
  const [brandError, setBrandError] = useState("");
  const [brandLoading, setBrandLoading] = useState(false);

  // Form undang member
  const [emailUndang, setEmailUndang] = useState("");
  const [roleUndang, setRoleUndang] = useState("viewer");
  const [undangError, setUndangError] = useState("");
  const [undangSukses, setUndangSukses] = useState("");
  const [undangLoading, setUndangLoading] = useState(false);
  const [prosesUndangan, setProsesUndangan] = useState<string | null>(null);

  const muat = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [d, b, m, u] = await Promise.all([
        api.get<OrgDetail>(`/organizations/${orgId}`),
        api.get<Brand[]>(`/organizations/${orgId}/brands`),
        api.get<OrgMember[]>(`/organizations/${orgId}/members`),
        api.get<Undangan[]>(`/organizations/${orgId}/undangan`),
      ]);
      setOrg(d);
      setBrands(b);
      setMembers(m);
      setUndangan(u);
      selectOrg(orgId);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Gagal memuat data organisasi."
      );
    } finally {
      setLoading(false);
    }
  }, [orgId, selectOrg]);

  useEffect(() => {
    muat();
  }, [muat]);

  async function tambahBrand(e: React.FormEvent) {
    e.preventDefault();
    setBrandError("");
    setBrandLoading(true);
    try {
      const baru = await api.post<Brand>(`/organizations/${orgId}/brands`, {
        name: namaBrand.trim(),
        ...(platformBrand ? { platform: platformBrand } : {}),
        ...(industri.trim() ? { industry: industri.trim() } : {}),
      });
      setBrands((prev) => [...prev, baru]);
      setNamaBrand("");
      setPlatformBrand("");
      setIndustri("");
    } catch (err) {
      setBrandError(
        err instanceof ApiError
          ? err.message
          : "Gagal menambah brand. Periksa koneksi internet Anda."
      );
    } finally {
      setBrandLoading(false);
    }
  }

  async function undangMember(e: React.FormEvent) {
    e.preventDefault();
    setUndangError("");
    setUndangSukses("");
    setUndangLoading(true);
    try {
      await api.post(`/organizations/${orgId}/undangan`, {
        email: emailUndang.trim(),
        role: roleUndang,
      });
      setUndangSukses(`Undangan terkirim ke ${emailUndang.trim()}.`);
      setEmailUndang("");
      const u = await api.get<Undangan[]>(`/organizations/${orgId}/undangan`);
      setUndangan(u);
    } catch (err) {
      setUndangError(
        err instanceof ApiError
          ? err.message
          : "Gagal mengundang member. Periksa koneksi internet Anda."
      );
    } finally {
      setUndangLoading(false);
    }
  }

  async function batalkanUndangan(id: string, email: string) {
    setProsesUndangan(id);
    setUndangError("");
    try {
      await api.del(`/organizations/${orgId}/undangan/${id}`);
      setUndangan((prev) => prev.filter((u) => u.id !== id));
      setUndangSukses(`Undangan untuk ${email} dibatalkan.`);
    } catch (err) {
      setUndangError(
        err instanceof ApiError ? err.message : "Gagal membatalkan undangan."
      );
    } finally {
      setProsesUndangan(null);
    }
  }

  async function keluarkanMember(m: OrgMember) {
    if (
      !window.confirm(
        `Keluarkan ${m.name} (${m.email}) dari organisasi ini?`
      )
    )
      return;
    setProsesUndangan(m.user_id);
    setUndangError("");
    try {
      await api.del(`/organizations/${orgId}/members/${m.user_id}`);
      setMembers((prev) => prev.filter((x) => x.user_id !== m.user_id));
      setUndangSukses(`${m.name} dikeluarkan dari organisasi.`);
    } catch (err) {
      const pesan =
        err instanceof ApiError
          ? err.message
          : "Gagal mengeluarkan member.";
      setUndangError(
        /diri sendiri|sendiri|owner terakhir|terakhir/i.test(pesan)
          ? pesan
          : `${pesan} (Anda tidak bisa mengeluarkan diri sendiri atau owner terakhir.)`
      );
    } finally {
      setProsesUndangan(null);
    }
  }

  if (loading) return <Spinner label="Memuat data organisasi…" />;
  if (error || !org) return <Alert kind="error">{error || "Data tidak ditemukan."}</Alert>;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <PageHeader
        title={org.name}
        subtitle={`Dibuat ${formatTanggal(org.created_at)}`}
        action={
          <Link href="/dashboard">
            <Button variant="secondary">Kembali ke dasbor</Button>
          </Link>
        }
      />

      {/* Info membership */}
      <Card className="mb-6">
        <h2 className="text-base font-semibold text-slate-900">Keanggotaan</h2>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <MembershipBadge status={org.membership?.status} />
          {org.membership?.plan_name && (
            <span className="text-sm text-slate-600">
              Paket:{" "}
              <span className="font-semibold">{org.membership.plan_name}</span>
            </span>
          )}
          {org.membership?.ends_at && (
            <span className="text-sm text-slate-500">
              Berlaku hingga {formatTanggal(org.membership.ends_at)}
            </span>
          )}
          <Link href="/tagihan" className="ml-auto">
            <Button variant="secondary">Kelola tagihan</Button>
          </Link>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Brand */}
        <Card>
          <h2 className="text-base font-semibold text-slate-900">Brand</h2>
          <p className="mt-1 text-sm text-slate-500">
            Brand-brand yang dikelola organisasi ini.
          </p>

          <form onSubmit={tambahBrand} className="mt-4 space-y-3">
            {brandError && <Alert kind="error">{brandError}</Alert>}
            <Select
              label="Platform"
              value={platformBrand}
              onChange={(e) => setPlatformBrand(e.target.value)}
            >
              <option value="">Pilih platform…</option>
              <option value="instagram">Instagram</option>
              <option value="facebook">Facebook</option>
              <option value="tiktok">TikTok</option>
            </Select>
            <Input
              label="Nama akun"
              required
              placeholder="Contoh: @insanmandiri.id"
              value={namaBrand}
              onChange={(e) => setNamaBrand(e.target.value)}
            />
            <Input
              label="Industri (opsional)"
              placeholder="Contoh: F&B"
              value={industri}
              onChange={(e) => setIndustri(e.target.value)}
            />
            <Button type="submit" disabled={brandLoading} className="w-full">
              {brandLoading ? "Menambahkan…" : "Tambah brand"}
            </Button>
          </form>

          <div className="mt-5 space-y-2">
            {brands.length === 0 && (
              <p className="text-sm text-slate-500">
                Belum ada brand. Tambahkan brand pertama Anda di atas.
              </p>
            )}
            {brands.map((b) => (
              <div
                key={b.id}
                className="flex items-center justify-between rounded-xl border border-slate-200 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-semibold text-slate-900">
                    {b.display_name || b.name}
                  </p>
                  {b.industry && (
                    <p className="text-xs text-slate-500">{b.industry}</p>
                  )}
                </div>
                <span className="text-xs text-slate-400">Brand</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Anggota & Undangan */}
        <Card>
          <h2 className="text-base font-semibold text-slate-900">
            Anggota &amp; Undangan
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Undang anggota tim ke organisasi ini.
          </p>

          <form onSubmit={undangMember} className="mt-4 space-y-3">
            {undangError && <Alert kind="error">{undangError}</Alert>}
            {undangSukses && <Alert kind="success">{undangSukses}</Alert>}
            <Input
              label="Email member"
              type="email"
              required
              placeholder="rekan@perusahaan.id"
              value={emailUndang}
              onChange={(e) => setEmailUndang(e.target.value)}
            />
            <Select
              label="Peran"
              value={roleUndang}
              onChange={(e) => setRoleUndang(e.target.value)}
            >
              <option value="viewer">Viewer</option>
              <option value="editor">Editor</option>
              <option value="admin">Admin</option>
              <option value="owner">Owner</option>
            </Select>
            <Button type="submit" disabled={undangLoading} className="w-full">
              {undangLoading ? "Mengundang…" : "Undang member"}
            </Button>
          </form>

          {/* Undangan pending */}
          <h3 className="mt-6 text-sm font-semibold text-slate-900">
            Undangan menunggu ({undangan.length})
          </h3>
          <div className="mt-3 space-y-2">
            {undangan.length === 0 && (
              <p className="text-sm text-slate-500">
                Tidak ada undangan yang menunggu.
              </p>
            )}
            {undangan.map((u) => (
              <div
                key={u.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">
                    {u.email}
                  </p>
                  <p className="text-xs text-slate-500">
                    {u.role} · {u.status} · {formatTanggal(u.created_at)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  onClick={() => batalkanUndangan(u.id, u.email)}
                  disabled={prosesUndangan === u.id}
                  className="px-3! py-1.5! text-xs text-red-600 hover:bg-red-50"
                >
                  {prosesUndangan === u.id ? "…" : "Batalkan"}
                </Button>
              </div>
            ))}
          </div>

          {/* Daftar anggota */}
          <h3 className="mt-6 text-sm font-semibold text-slate-900">
            Anggota ({members.length})
          </h3>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-4 font-semibold">Nama</th>
                  <th className="py-2 pr-4 font-semibold">Email</th>
                  <th className="py-2 pr-4 font-semibold">Peran</th>
                  <th className="py-2 font-semibold"></th>
                </tr>
              </thead>
              <tbody>
                {members.map((m) => {
                  const diriSendiri =
                    user?.email?.toLowerCase() === m.email.toLowerCase();
                  const terkunci = diriSendiri || m.role === "owner";
                  return (
                    <tr key={m.user_id} className="border-b border-slate-100">
                      <td className="py-2.5 pr-4 font-medium text-slate-900">
                        {m.name}
                        {diriSendiri && (
                          <span className="ml-2 rounded-full bg-indigo-100 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
                            Anda
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 pr-4 text-slate-600">{m.email}</td>
                      <td className="py-2.5 pr-4">
                        <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                          {m.role}
                        </span>
                      </td>
                      <td className="py-2.5 text-right">
                        <span
                          title={
                            diriSendiri
                              ? "Anda tidak bisa mengeluarkan diri sendiri"
                              : m.role === "owner"
                                ? "Owner terakhir tidak bisa dikeluarkan"
                                : "Keluarkan dari organisasi"
                          }
                        >
                          <Button
                            variant="ghost"
                            onClick={() => keluarkanMember(m)}
                            disabled={
                              terkunci || prosesUndangan === m.user_id
                            }
                            className="px-3! py-1.5! text-xs text-red-600 hover:bg-red-50 disabled:text-slate-300"
                          >
                            {prosesUndangan === m.user_id
                              ? "Memproses…"
                              : "Keluarkan"}
                          </Button>
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {members.length === 0 && (
              <p className="py-4 text-sm text-slate-500">
                Belum ada member selain Anda.
              </p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

export default function OrganisasiPage() {
  return (
    <RequireAuth>
      <KelolaOrganisasi />
    </RequireAuth>
  );
}
