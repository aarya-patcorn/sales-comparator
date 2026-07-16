export type AuthUser = {
  user_id: string;
  email: string;
  name: string;
  picture?: string;
  role: string;
};

export type StoredAuthSession = {
  sessionToken: string;
  tokenType?: string;
  expiresAt?: string;
  user?: AuthUser;
};

export type DashboardMetrics = {
  total_rm_users: number;
  active_rm_users: number;
  total_products: number;
  active_products: number;
};

export type DashboardResponse = {
  metrics: DashboardMetrics;
};

export type AdminMeta = {
  roles: string[];
  areas: string[];
  product_param_keys: string[];
  seed_product_codes: string[];
};

export type AdminUser = {
  user_id: string;
  name: string;
  email: string;
  role: "RM" | "ADMIN";
  is_active: boolean;
  status: "active" | "inactive";
  created_at?: string | null;
  updated_at?: string | null;
  last_login_at?: string | null;
  must_change_password: boolean;
};

export type PaginatedUsers = {
  items: AdminUser[];
  total: number;
  page: number;
  page_size: number;
};

export type UserPayload = {
  user_id: string;
  name: string;
  email: string;
  role: "RM" | "ADMIN";
  is_active: boolean;
};

export type CreateUserPayload = UserPayload & {
  password?: string;
};

export type UpdateUserPayload = Partial<UserPayload>;

export type ProductRecord = {
  code: string;
  name: string;
  is_type: string;
  en_type: string;
  tagline: string;
  description: string;
  max_tile_size: string;
  areas: string[];
  params: Record<string, string>;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  source: string;
};

export type PaginatedProducts = {
  items: ProductRecord[];
  total: number;
  page: number;
  page_size: number;
};

export type ProductPayload = {
  code: string;
  name: string;
  is_type: string;
  en_type: string;
  tagline: string;
  description: string;
  max_tile_size: string;
  areas: string[];
  params: Record<string, string>;
  is_active: boolean;
};

export type ApiItemResponse<T> = {
  item: T;
};

export type CompetitorProduct = {
  id: string;
  competitor_id: string;
  name: string;
  is_type: string;
  en_type: string;
  competes_with: string;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export type Competitor = {
  id: string;
  name: string;
  is_active: boolean;
  product_count: number;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CompetitorPayload = { id?: string; name: string; is_active: boolean };
export type CompetitorProductPayload = { name: string; is_type: string; en_type: string; competes_with: string; is_active: boolean };
export type PaginatedCompetitors = { items: Competitor[]; total: number; page: number; page_size: number };