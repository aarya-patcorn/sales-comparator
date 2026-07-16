import type {
  AdminMeta,
  AdminUser,
  ApiItemResponse,
  AuthUser,
  CreateUserPayload,
  Competitor,
  CompetitorPayload,
  CompetitorProduct,
  CompetitorProductPayload,
  PaginatedCompetitors,
  DashboardResponse,
  PaginatedProducts,
  PaginatedUsers,
  ProductPayload,
  ProductRecord,
  UpdateUserPayload,
} from "../types/admin";

const AUTH_STORAGE_KEY = "kamdhenu_admin_session";

function normalizeBaseUrl(value: string) {
  return value.trim().replace(/\/+$/, "");
}

export function getApiBaseUrl() {
  const configured = normalizeBaseUrl(import.meta.env.VITE_API_URL ?? "");
  return configured || "http://localhost:8000";
}

export const API_BASE_URL = getApiBaseUrl();
export const API_BASE = `${API_BASE_URL}/api`;

export function getApiConfigurationError() {
  if (!API_BASE_URL) {
    return "Missing VITE_API_URL in admin environment configuration.";
  }

  return null;
}

export function readStoredSession() {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function writeStoredSession(session: unknown) {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
  }
}

export function clearStoredSession() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
  }
}

async function parseApiError(response: Response) {
  let message = `HTTP ${response.status}`;

  try {
    const payload = await response.json();
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      message = payload.detail;
    }
  } catch {}

  return message;
}

function buildHeaders(token?: string | null, headers: HeadersInit = {}) {
  const nextHeaders = new Headers(headers);
  if (!nextHeaders.has("Content-Type")) {
    nextHeaders.set("Content-Type", "application/json");
  }
  if (API_BASE_URL.includes("ngrok")) {
    nextHeaders.set("ngrok-skip-browser-warning", "true");
  }
  if (token) {
    nextHeaders.set("Authorization", `Bearer ${token}`);
  }
  return nextHeaders;
}

export async function request<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const configError = getApiConfigurationError();
  if (configError) {
    throw new Error(configError);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: buildHeaders(token, init.headers),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function loginAdmin(userId: string, password: string) {
  return request<{
    session_token: string;
    token_type: string;
    expires_at: string;
    user: AuthUser;
  }>("/admin/auth/login", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, password }),
  });
}

export async function fetchAdminMe(token: string) {
  return request<AuthUser>("/admin/auth/me", { method: "GET" }, token);
}

export async function logoutAdmin(token?: string | null) {
  if (!token) {
    return;
  }

  await request("/admin/auth/logout", { method: "POST" }, token);
}

export async function fetchDashboard(token: string) {
  return request<DashboardResponse>("/admin/dashboard", { method: "GET" }, token);
}

export async function fetchAdminMeta(token: string) {
  return request<AdminMeta>("/admin/meta", { method: "GET" }, token);
}

export async function fetchUsers(
  token: string,
  params: { page: number; pageSize: number; search: string; statusFilter: string; roleFilter: string },
) {
  const query = new URLSearchParams({
    page: String(params.page),
    page_size: String(params.pageSize),
    search: params.search,
    status_filter: params.statusFilter,
    role_filter: params.roleFilter,
  });

  return request<PaginatedUsers>(`/admin/users?${query.toString()}`, { method: "GET" }, token);
}

export async function createUser(token: string, payload: CreateUserPayload) {
  return request<ApiItemResponse<AdminUser> & { temporary_password?: string }>(
    "/admin/users",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export async function updateUser(token: string, userId: string, payload: UpdateUserPayload) {
  return request<ApiItemResponse<AdminUser>>(
    `/admin/users/${encodeURIComponent(userId)}`,
    { method: "PUT", body: JSON.stringify(payload) },
    token,
  );
}

export async function setUserActive(token: string, userId: string, active: boolean) {
  return request<ApiItemResponse<AdminUser>>(
    `/admin/users/${encodeURIComponent(userId)}/${active ? "activate" : "deactivate"}`,
    { method: "POST" },
    token,
  );
}

export async function resetUserPassword(token: string, userId: string, password?: string) {
  return request<{ ok: true; temporary_password?: string }>(
    `/admin/users/${encodeURIComponent(userId)}/reset-password`,
    { method: "POST", body: JSON.stringify(password ? { password } : {}) },
    token,
  );
}

export async function deleteUser(token: string, userId: string) {
  return request<{ ok: true }>(`/admin/users/${encodeURIComponent(userId)}`, { method: "DELETE" }, token);
}

export async function fetchCompetitors(token: string, params: { page: number; pageSize: number; search: string; statusFilter: string }) {
  const query = new URLSearchParams({ page: String(params.page), page_size: String(params.pageSize), search: params.search, status_filter: params.statusFilter });
  return request<PaginatedCompetitors>(`/admin/competitors?${query.toString()}`, { method: "GET" }, token);
}

export async function createCompetitor(token: string, payload: CompetitorPayload) {
  return request<ApiItemResponse<Competitor>>("/admin/competitors", { method: "POST", body: JSON.stringify(payload) }, token);
}

export async function updateCompetitor(token: string, id: string, payload: Partial<CompetitorPayload>) {
  return request<ApiItemResponse<Competitor>>(`/admin/competitors/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(payload) }, token);
}

export async function setCompetitorActive(token: string, id: string, active: boolean) {
  return request<ApiItemResponse<Competitor>>(`/admin/competitors/${encodeURIComponent(id)}/action/${active ? "activate" : "deactivate"}`, { method: "POST" }, token);
}

export async function deleteCompetitor(token: string, id: string) {
  return request<{ ok: true }>(`/admin/competitors/${encodeURIComponent(id)}`, { method: "DELETE" }, token);
}

export async function fetchCompetitorProducts(token: string, id: string) {
  return request<{ items: CompetitorProduct[] }>(`/admin/competitors/${encodeURIComponent(id)}/products`, { method: "GET" }, token);
}

export async function createCompetitorProduct(token: string, id: string, payload: CompetitorProductPayload) {
  return request<ApiItemResponse<CompetitorProduct>>(`/admin/competitors/${encodeURIComponent(id)}/products`, { method: "POST", body: JSON.stringify(payload) }, token);
}

export async function updateCompetitorProduct(token: string, competitorId: string, productId: string, payload: Partial<CompetitorProductPayload>) {
  return request<ApiItemResponse<CompetitorProduct>>(`/admin/competitors/${encodeURIComponent(competitorId)}/products/${encodeURIComponent(productId)}`, { method: "PUT", body: JSON.stringify(payload) }, token);
}

export async function deleteCompetitorProduct(token: string, competitorId: string, productId: string) {
  return request<{ ok: true }>(`/admin/competitors/${encodeURIComponent(competitorId)}/products/${encodeURIComponent(productId)}`, { method: "DELETE" }, token);
}
export async function fetchProducts(
  token: string,
  params: { page: number; pageSize: number; search: string; statusFilter: string; areaFilter: string },
) {
  const query = new URLSearchParams({
    page: String(params.page),
    page_size: String(params.pageSize),
    search: params.search,
    status_filter: params.statusFilter,
    area_filter: params.areaFilter,
  });

  return request<PaginatedProducts>(`/admin/products?${query.toString()}`, { method: "GET" }, token);
}

export async function createProduct(token: string, payload: ProductPayload) {
  return request<ApiItemResponse<ProductRecord>>(
    "/admin/products",
    { method: "POST", body: JSON.stringify(payload) },
    token,
  );
}

export async function updateProduct(token: string, code: string, payload: Partial<ProductPayload>) {
  return request<ApiItemResponse<ProductRecord>>(
    `/admin/products/${encodeURIComponent(code)}`,
    { method: "PUT", body: JSON.stringify(payload) },
    token,
  );
}

export async function setProductActive(token: string, code: string, active: boolean) {
  return request<ApiItemResponse<ProductRecord>>(
    `/admin/products/${encodeURIComponent(code)}/${active ? "activate" : "deactivate"}`,
    { method: "POST" },
    token,
  );
}

export async function deleteProduct(token: string, code: string) {
  return request<{ ok: true }>(`/admin/products/${encodeURIComponent(code)}`, { method: "DELETE" }, token);
}
