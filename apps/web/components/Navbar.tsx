"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { getSelectedBrandId } from "@/lib/content";
import type { OrganizationDetail } from "@/lib/types";
import { MembershipBadge } from "./badges";

const HIDDEN_PATHS = ["/login", "/register"];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const {
    user,
    loading,
    logout,
    organizations,
    selectedOrgId,
    selectOrg,
  } = useAuth();
  const [membershipStatus, setMembershipStatus] = useState<string | null>(null);
  const [orgMenuOpen, setOrgMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const orgMenuRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Brand aktif untuk tab "Analisa" (disimpan di localStorage oleh BrandSelector).
  const [brandId, setBrandId] = useState<string | null>(null);
  useEffect(() => {
    setBrandId(getSelectedBrandId());
    const segarkan = () => setBrandId(getSelectedBrandId());
    window.addEventListener("dkai:brand-change", segarkan);
    window.addEventListener("storage", segarkan);
    return () => {
      window.removeEventListener("dkai:brand-change", segarkan);
      window.removeEventListener("storage", segarkan);
    };
  }, [pathname]);

  const hideNavbar = HIDDEN_PATHS.some((p) => pathname?.startsWith(p));

  useEffect(() => {
    if (hideNavbar || !selectedOrgId) {
      setMembershipStatus(null);
      return;
    }
    let cancelled = false;
    api
      .get<OrganizationDetail>(`/organizations/${selectedOrgId}`)
      .then((org) => {
        if (!cancelled) setMembershipStatus(org.membership?.status ?? null);
      })
      .catch(() => {
        if (!cancelled) setMembershipStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedOrgId, hideNavbar, pathname]);

  // Tutup dropdown saat klik di luar.
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (orgMenuRef.current && !orgMenuRef.current.contains(e.target as Node))
        setOrgMenuOpen(false);
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node))
        setUserMenuOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  if (hideNavbar) return null;

  const selectedOrg = organizations.find((o) => o.id === selectedOrgId);

  // Link "Analitik" dihapus: duplikat dengan tab "Dasbor" di BrandNav
  // (keduanya mengarah ke /brand/{brandId}). Navigasi brand ditangani BrandNav.
  // Tab "Analisa" global: ke halaman analisa brand aktif, atau pilih brand dulu.
  const analisaHref = brandId ? `/brand/${brandId}/analisa` : "/pilih-brand?next=analisa";
  const navLinks: { href: string; label: string; match?: string; matchIncludes?: string }[] = [
    { href: analisaHref, label: "Analisa", matchIncludes: "/analisa" },
    { href: "/upload", label: "Upload" },
    { href: "/tagihan", label: "Tagihan" },
  ];
  if (user?.is_superadmin) navLinks.push({ href: "/admin", label: "Admin" });

  const linkAktif = (l: { href: string; match?: string; matchIncludes?: string }) => {
    if (l.matchIncludes) return pathname?.includes(l.matchIncludes) ?? false;
    return pathname?.startsWith(l.match ?? l.href) ?? false;
  };

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6">
        <Link href={user ? analisaHref : "/"} className="flex items-center gap-2">
          <img
            src="/logo.png"
            alt="MySocial Watch"
            className="h-9 w-9 rounded-xl"
          />
          <span className="hidden text-base font-bold tracking-tight text-slate-900 sm:block">
            MySocial Watch
          </span>
        </Link>

        {!loading && user && (
          <>
            <nav className="ml-2 hidden items-center gap-1 md:flex">
              {navLinks.map((l) => (
                <Link
                  key={l.href}
                  href={l.href}
                  className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
                    linkAktif(l)
                      ? "bg-orange-50 text-orange-700"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                >
                  {l.label}
                </Link>
              ))}
              {selectedOrgId && (
                <Link
                  href={`/organisasi/${selectedOrgId}`}
                  className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
                    pathname?.startsWith("/organisasi")
                      ? "bg-orange-50 text-orange-700"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                >
                  Organisasi
                </Link>
              )}
            </nav>

            <div className="ml-auto flex items-center gap-2 sm:gap-3">
              {/* Switcher organisasi */}
              <div ref={orgMenuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setOrgMenuOpen((v) => !v)}
                  className="flex max-w-[10rem] items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 sm:max-w-[14rem]"
                  title="Ganti organisasi"
                >
                  <svg
                    className="h-4 w-4 shrink-0 text-slate-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
                    />
                  </svg>
                  <span className="truncate">
                    {selectedOrg ? selectedOrg.name : "Pilih organisasi"}
                  </span>
                  <svg
                    className="h-4 w-4 shrink-0 text-slate-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="m19.5 8.25-7.5 7.5-7.5-7.5"
                    />
                  </svg>
                </button>
                {orgMenuOpen && (
                  <div className="absolute right-0 mt-2 w-64 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
                    {organizations.length === 0 && (
                      <p className="px-4 py-3 text-sm text-slate-500">
                        Belum ada organisasi.
                      </p>
                    )}
                    {organizations.map((o) => (
                      <button
                        key={o.id}
                        type="button"
                        onClick={() => {
                          selectOrg(o.id);
                          setOrgMenuOpen(false);
                        }}
                        className={`flex w-full items-center justify-between px-4 py-2.5 text-left text-sm hover:bg-slate-50 ${
                          o.id === selectedOrgId
                            ? "font-semibold text-orange-700"
                            : "text-slate-700"
                        }`}
                      >
                        <span className="truncate">{o.name}</span>
                        {o.id === selectedOrgId && (
                          <span className="ml-2 text-orange-600">✓</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {selectedOrgId && (
                <MembershipBadge status={membershipStatus} className="hidden sm:inline-flex" />
              )}

              {/* Menu user */}
              <div ref={userMenuRef} className="relative">
                <button
                  type="button"
                  onClick={() => setUserMenuOpen((v) => !v)}
                  className="flex items-center gap-0.5 rounded-full p-1 hover:bg-slate-100"
                  title={user.name}
                  aria-haspopup="menu"
                  aria-expanded={userMenuOpen}
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-orange-100 text-sm font-bold text-orange-700">
                    {user.name.charAt(0).toUpperCase()}
                  </span>
                  <svg
                    className={`h-4 w-4 text-slate-400 transition-transform ${userMenuOpen ? "rotate-180" : ""}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                  </svg>
                </button>
                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-56 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg">
                    <div className="border-b border-slate-100 px-4 py-3">
                      <p className="truncate text-sm font-semibold text-slate-900">
                        {user.name}
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {user.email}
                      </p>
                    </div>
                    {/* Navigasi mobile */}
                    <div className="border-b border-slate-100 py-1 md:hidden">
                      {navLinks.map((l) => (
                        <button
                          key={l.href}
                          type="button"
                          onClick={() => {
                            setUserMenuOpen(false);
                            router.push(l.href);
                          }}
                          className="block w-full px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50"
                        >
                          {l.label}
                        </button>
                      ))}
                      {selectedOrgId && (
                        <button
                          type="button"
                          onClick={() => {
                            setUserMenuOpen(false);
                            router.push(`/organisasi/${selectedOrgId}`);
                          }}
                          className="block w-full px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50"
                        >
                          Organisasi
                        </button>
                      )}
                    </div>
                    <div className="py-1">
                      <button
                        type="button"
                        onClick={() => {
                          setUserMenuOpen(false);
                          router.push("/dashboard");
                        }}
                        className="block w-full px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50"
                      >
                        Dasbor
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setUserMenuOpen(false);
                          router.push("/profil");
                        }}
                        className="block w-full px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50"
                      >
                        Profil
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setUserMenuOpen(false);
                          logout();
                        }}
                        className="block w-full px-4 py-2.5 text-left text-sm text-red-600 hover:bg-red-50"
                      >
                        Keluar
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {!loading && !user && (
          <div className="ml-auto flex items-center gap-2">
            <Link
              href="/login"
              className="rounded-xl px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            >
              Masuk
            </Link>
            <Link
              href="/register"
              className="rounded-xl bg-orange-600 px-4 py-2 text-sm font-semibold text-white hover:bg-orange-700"
            >
              Daftar
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
