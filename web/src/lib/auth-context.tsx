"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { authUserSchema, type AuthUser } from "./auth";
import { clearPrivateSessionData, syncPrivateSessionUser } from "./private-session";

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  setAuthenticatedUser: (user: AuthUser) => void;
}

const AuthContext = createContext<AuthState>({
  user: null,
  loading: true,
  logout: async () => undefined,
  refresh: async () => undefined,
  setAuthenticatedUser: () => undefined,
});

export function useAuth() {
  return useContext(AuthContext);
}

async function fetchUser(): Promise<AuthUser | null> {
  try {
    const response = await fetch("/api/auth/me", { cache: "no-store" });
    if (!response.ok) return null;
    const payload: unknown = await response.json();
    const parsed = authUserSchema.safeParse(
      typeof payload === "object" && payload && "user" in payload
        ? (payload as { user: unknown }).user
        : null,
    );
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchUser().then((result) => {
      if (!cancelled) {
        syncPrivateSessionUser(result?.id ?? null);
        setUser(result);
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    const result = await fetchUser();
    syncPrivateSessionUser(result?.id ?? null);
    setUser(result);
    setLoading(false);
  }, []);

  const setAuthenticatedUser = useCallback((authenticatedUser: AuthUser) => {
    syncPrivateSessionUser(authenticatedUser.id);
    setUser(authenticatedUser);
    setLoading(false);
  }, []);

  const logout = useCallback(async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    clearPrivateSessionData();
    syncPrivateSessionUser(null);
    setUser(null);
    window.location.href = "/";
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, logout, refresh, setAuthenticatedUser }}>
      {children}
    </AuthContext.Provider>
  );
}
