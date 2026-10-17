import React, { createContext, useContext, useEffect, useState, useCallback } from "react";

interface AuthContextType {
  token: string | null;
  setToken: (token: string) => void;
  clearToken: () => void;
  isAuthenticated: boolean;
  devMode: boolean;
  setDevMode: (dev: boolean) => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = "schemawatch_bearer_token";

export function AuthProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const [token, setTokenState] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  });

  const [devMode, setDevMode] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Check config on initial mount to see if server is in dev_mode
  useEffect(() => {
    let isMounted = true;
    fetch("/api/config")
      .then((res) => {
        if (res.ok) return res.json();
        return null;
      })
      .then((cfg) => {
        if (isMounted && cfg && typeof cfg.dev_mode === "boolean") {
          setDevMode(cfg.dev_mode);
        }
      })
      .catch(() => {
        // network error or not ready
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const setToken = useCallback((newToken: string): void => {
    try {
      sessionStorage.setItem(TOKEN_KEY, newToken.trim());
    } catch {
      // ignore
    }
    setTokenState(newToken.trim());
  }, []);

  const clearToken = useCallback((): void => {
    try {
      sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      // ignore
    }
    setTokenState(null);
  }, []);

  // Listen to custom 401 unauthorized events dispatched by API client
  useEffect(() => {
    const handleUnauthorized = (): void => {
      clearToken();
    };

    window.addEventListener("schemawatch:unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("schemawatch:unauthorized", handleUnauthorized);
    };
  }, [clearToken]);

  const isAuthenticated = Boolean(token) || devMode;

  return (
    <AuthContext.Provider
      value={{
        token,
        setToken,
        clearToken,
        isAuthenticated,
        devMode,
        setDevMode,
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
