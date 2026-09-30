"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import {
  api,
  clearTokens,
  getSelectedOrgId,
  setSelectedOrgId,
  setTokens,
} from "./api";
import type { OrganizationSummary, User } from "./types";

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
  coupon_applied?: Array<{
    organization_id: string;
    discount_percent: number;
    expires_at: string | null;
  }> | null;
  coupon_error?: string | null;
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, couponCode?: string) => Promise<LoginResponse>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  organizations: OrganizationSummary[];
  orgsLoading: boolean;
  selectedOrgId: string | null;
  selectOrg: (id: string) => void;
  refreshOrgs: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [organizations, setOrganizations] = useState<OrganizationSummary[]>([]);
  const [orgsLoading, setOrgsLoading] = useState(false);
  const [selectedOrgId, setSelectedOrgIdState] = useState<string | null>(null);

  const refreshOrgs = useCallback(async () => {
    setOrgsLoading(true);
    try {
      const list = await api.get<OrganizationSummary[]>("/organizations");
      setOrganizations(list);
      const saved = getSelectedOrgId();
      const valid = list.find((o) => o.id === saved);
      if (valid) {
        setSelectedOrgIdState(valid.id);
      } else if (list.length > 0) {
        setSelectedOrgIdState(list[0].id);
        setSelectedOrgId(list[0].id);
      } else {
        setSelectedOrgIdState(null);
        setSelectedOrgId(null);
      }
    } catch {
      setOrganizations([]);
    } finally {
      setOrgsLoading(false);
    }
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const me = await api.get<User>("/auth/me");
      setUser(me);
      await refreshOrgs();
    } catch {
      setUser(null);
      setOrganizations([]);
      setSelectedOrgIdState(null);
    }
  }, [refreshOrgs]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await refreshUser();
      setLoading(false);
    })();
  }, [refreshUser]);

  const login = useCallback(
    async (email: string, password: string, couponCode?: string) => {
      const res = await api.post<LoginResponse>("/auth/login", {
        email,
        password,
        ...(couponCode?.trim() ? { coupon_code: couponCode.trim() } : {}),
      });
      setTokens(res.access_token, res.refresh_token);
      setUser(res.user);
      await refreshOrgs();
      return res;
    },
    [refreshOrgs]
  );

  const logout = useCallback(() => {
    const rt =
      typeof window !== "undefined"
        ? window.localStorage.getItem("dkai_refresh_token")
        : null;
    // Beritahu server (best-effort), lalu bersihkan sesi lokal.
    if (rt) {
      api.post("/auth/logout", { refresh_token: rt }).catch(() => {});
    }
    clearTokens();
    setUser(null);
    setOrganizations([]);
    setSelectedOrgIdState(null);
    router.push("/login");
  }, [router]);

  const selectOrg = useCallback((id: string) => {
    setSelectedOrgId(id);
    setSelectedOrgIdState(id);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      login,
      logout,
      refreshUser,
      organizations,
      orgsLoading,
      selectedOrgId,
      selectOrg,
      refreshOrgs,
    }),
    [
      user,
      loading,
      login,
      logout,
      refreshUser,
      organizations,
      orgsLoading,
      selectedOrgId,
      selectOrg,
      refreshOrgs,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth harus dipakai di dalam AuthProvider");
  return ctx;
}

// Guard: hanya untuk halaman yang butuh login. Opsional: butuh superadmin.
export function RequireAuth({
  children,
  superadmin = false,
}: {
  children: ReactNode;
  superadmin?: boolean;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (superadmin && !user.is_superadmin) {
      router.replace("/dashboard");
    }
  }, [user, loading, superadmin, router]);

  if (loading || !user || (superadmin && !user.is_superadmin)) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex items-center gap-3 text-slate-500">
          <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
          <span>Memuat…</span>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
