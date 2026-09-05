import { useState, useEffect } from "react";

const BASE_URL = "http://127.0.0.1:8000/api/v1";
const TOKEN_KEY = "retry_auth_token";
const USER_KEY = "retry_auth_user";

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: string;
  created_at?: string;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setSession(token: string, user: AuthUser) {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  window.dispatchEvent(new Event("auth_state_changed"));
}

export function clearSession() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new Event("auth_state_changed"));
}

export async function loginApi(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Invalid email or password.");
  }

  const data: AuthResponse = await res.json();
  setSession(data.token, data.user);
  return data;
}

export async function signupApi(
  name: string,
  email: string,
  password: string,
  role: string = "recovery_specialist"
): Promise<AuthResponse> {
  const res = await fetch(`${BASE_URL}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, password, role }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to create account.");
  }

  const data: AuthResponse = await res.json();
  setSession(data.token, data.user);
  return data;
}

export async function logoutApi(): Promise<void> {
  const token = getStoredToken();
  if (token) {
    try {
      await fetch(`${BASE_URL}/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (e) {
      console.error("Logout request failed:", e);
    }
  }
  clearSession();
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    function updateState() {
      setUser(getStoredUser());
      setToken(getStoredToken());
      setLoading(false);
    }

    updateState();

    window.addEventListener("auth_state_changed", updateState);
    window.addEventListener("storage", updateState);

    return () => {
      window.removeEventListener("auth_state_changed", updateState);
      window.removeEventListener("storage", updateState);
    };
  }, []);

  return {
    user,
    token,
    loading,
    isLoggedIn: !!user,
    login: loginApi,
    signup: signupApi,
    logout: logoutApi,
  };
}
