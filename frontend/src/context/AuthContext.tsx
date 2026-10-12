"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { apiRequest } from "@/lib/api";

export type UserRole = "ADMIN" | "HOD" | "COORDINATOR" | "TEACHER" | "CR" | "STUDENT" | "MENTOR";

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  institution_id: string;
  department_ids: string[];
  section_ids: string[];
  permissions: string[];
  is_active: boolean;
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasPermission: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Rehydrate session from storage
    const storedToken = sessionStorage.getItem("timewise_token");
    const storedUser = sessionStorage.getItem("timewise_user");

    if (storedToken && storedUser) {
      try {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      } catch {
        sessionStorage.clear();
      }
    }
    setIsLoading(false);
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const data = await apiRequest<{
        tokens: { access_token: string; refresh_token: string };
        user: UserProfile;
      }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      setToken(data.tokens.access_token);
      setUser(data.user);

      sessionStorage.setItem("timewise_token", data.tokens.access_token);
      sessionStorage.setItem("timewise_refresh", data.tokens.refresh_token);
      sessionStorage.setItem("timewise_user", JSON.stringify(data.user));
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    if (token) {
      try {
        await apiRequest("/auth/logout", { method: "POST" });
      } catch {
        // Fallback logout
      }
    }
    setToken(null);
    setUser(null);
    sessionStorage.clear();
  };

  const hasPermission = (permission: string) => {
    if (!user) return false;
    if (user.role === "ADMIN") return true;
    return user.permissions.includes(permission);
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout, hasPermission }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
