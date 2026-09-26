// Lapisan akses API Dashboard Konten AI.
// Kontrak: base = (NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/v1'
// Error API berbentuk { "detail": "..." }.
// Header X-Organization-Id dikirim untuk endpoint yang org-scoped.

const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1";

const ACCESS_KEY = "dkai_access_token";
const REFRESH_KEY = "dkai_refresh_token";
const ORG_KEY = "dkai_org_id";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ---- Penyimpanan token & organisasi terpilih (localStorage) ----
export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

export function setTokens(accessToken: string, refreshToken: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACCESS_KEY, accessToken);
  window.localStorage.setItem(REFRESH_KEY, refreshToken);
}

export function clearTokens() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  window.localStorage.removeItem(ORG_KEY);
}

export function getSelectedOrgId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ORG_KEY);
}

export function setSelectedOrgId(id: string | null) {
  if (typeof window === "undefined") return;
  if (id) window.localStorage.setItem(ORG_KEY, id);
  else window.localStorage.removeItem(ORG_KEY);
}

function extractDetail(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const d = (payload as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      const msgs = d.map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item)
          return String((item as { msg: unknown }).msg);
        return JSON.stringify(item);
      });
      if (msgs.length > 0) return msgs.join("; ");
    }
  }
  return fallback;
}

let refreshPromise: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) {
      clearTokens();
      return false;
    }
    const data = await res.json();
    if (!data?.access_token) {
      clearTokens();
      return false;
    }
    setTokens(data.access_token, data.refresh_token ?? rt);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

interface RequestOptions {
  retry?: boolean;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  opts: RequestOptions = {}
): Promise<T> {
  const retry = opts.retry ?? true;
  const headers = new Headers(init.headers);

  const access = getAccessToken();
  if (access) headers.set("Authorization", `Bearer ${access}`);

  const orgId = getSelectedOrgId();
  if (orgId) headers.set("X-Organization-Id", orgId);

  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });

  // Auto-refresh sekali saat 401 (kecuali untuk endpoint auth itu sendiri).
  if (res.status === 401 && retry && !path.startsWith("/auth/")) {
    if (!refreshPromise) {
      refreshPromise = doRefresh().finally(() => {
        refreshPromise = null;
      });
    }
    const ok = await refreshPromise;
    if (ok) return apiFetch<T>(path, init, { retry: false });
  }

  if (!res.ok) {
    let detail = `Terjadi kesalahan (kode ${res.status})`;
    try {
      const payload = await res.json();
      detail = extractDetail(payload, detail);
    } catch {
      // abaikan, pakai fallback
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) return undefined as T;
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return (await res.json()) as T;
  }
  return (await res.text()) as unknown as T;
}

// Unduh berkas biner dengan Authorization header (mis. bukti pembayaran).
export async function apiDownload(path: string): Promise<Blob> {
  const headers = new Headers();
  const access = getAccessToken();
  if (access) headers.set("Authorization", `Bearer ${access}`);
  const orgId = getSelectedOrgId();
  if (orgId) headers.set("X-Organization-Id", orgId);

  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) {
    let detail = `Gagal mengunduh (kode ${res.status})`;
    try {
      const payload = await res.json();
      detail = extractDetail(payload, detail);
    } catch {
      // abaikan
    }
    throw new ApiError(detail, res.status);
  }
  return await res.blob();
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: "PATCH",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  postForm: <T>(path: string, form: FormData) =>
    apiFetch<T>(path, { method: "POST", body: form }),
  put: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, {
      method: "PUT",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  del: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};
