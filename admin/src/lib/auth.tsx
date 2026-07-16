import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import {
  clearStoredSession,
  fetchAdminMe,
  loginAdmin,
  logoutAdmin,
  readStoredSession,
  writeStoredSession,
} from "./api";
import type { AuthUser, StoredAuthSession } from "../types/admin";

type AuthContextValue = {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (userId: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<StoredAuthSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;

    async function restoreSession() {
      const stored = readStoredSession() as StoredAuthSession | null;
      if (!stored?.sessionToken) {
        if (alive) {
          setLoading(false);
        }
        return;
      }

      try {
        const user = await fetchAdminMe(stored.sessionToken);
        if (user.role !== "ADMIN") {
          throw new Error("Admin access required");
        }
        if (alive) {
          const nextSession = { ...stored, user };
          setSession(nextSession);
          writeStoredSession(nextSession);
        }
      } catch {
        clearStoredSession();
        if (alive) {
          setSession(null);
        }
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    }

    void restoreSession();
    return () => {
      alive = false;
    };
  }, []);

  async function handleLogin(userId: string, password: string) {
    const payload = await loginAdmin(userId, password);
    if (payload.user.role !== "ADMIN") {
      throw new Error("Admin access required");
    }
    const nextSession: StoredAuthSession = {
      sessionToken: payload.session_token,
      tokenType: payload.token_type,
      expiresAt: payload.expires_at,
      user: payload.user,
    };
    setSession(nextSession);
    writeStoredSession(nextSession);
  }

  async function handleLogout() {
    const token = session?.sessionToken ?? null;
    try {
      await logoutAdmin(token);
    } catch {}
    clearStoredSession();
    setSession(null);
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      token: session?.sessionToken ?? null,
      loading,
      isAuthenticated: Boolean(session?.sessionToken && session?.user),
      login: handleLogin,
      logout: handleLogout,
    }),
    [loading, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
