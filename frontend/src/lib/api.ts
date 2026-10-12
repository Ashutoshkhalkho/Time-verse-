/**
 * Centralized API client with automatic token injection and error handling.
 */

const isProduction = process.env.NODE_ENV === "production";
const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL;

// In local development, gracefully fall back to local FastAPI server on port 8000.
// In production, require NEXT_PUBLIC_API_URL to prevent silent requests to visitor's localhost.
const API_BASE = configuredApiUrl || (!isProduction ? "http://localhost:8000/api/v1" : "");

export interface ApiError {
  type: string;
  title: string;
  status: number;
  detail: string;
  code: string;
  errors?: Array<{ field: string; message: string }>;
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  if (!API_BASE && !endpoint.startsWith("http")) {
    const configErrorMsg =
      "Configuration Error: NEXT_PUBLIC_API_URL environment variable is not defined on this deployment. Please configure NEXT_PUBLIC_API_URL in your hosting settings (e.g. Vercel) to point to your backend API URL.";
    if (typeof window !== "undefined") {
      console.error(`[TIMEVERSE Configuration Error] ${configErrorMsg}`);
    }
    throw {
      status: 500,
      code: "CONFIGURATION_ERROR",
      title: "Missing API Configuration",
      detail: configErrorMsg,
    };
  }

  const token = typeof window !== "undefined" ? sessionStorage.getItem("timewise_token") : null;

  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    // Session expired or invalid
    if (typeof window !== "undefined") {
      sessionStorage.removeItem("timewise_token");
      sessionStorage.removeItem("timewise_refresh");
      sessionStorage.removeItem("timewise_user");
    }
    const errorData = await response.json().catch(() => ({}));
    throw {
      status: 401,
      code: "UNAUTHORIZED",
      detail: errorData.detail || "Session expired or invalid credentials.",
    };
  }

  if (!response.ok) {
    const errorData: ApiError = await response.json().catch(() => ({
      type: "https://timewise.internal/errors/unknown",
      title: "Request Failed",
      status: response.status,
      detail: response.statusText,
      code: `HTTP_${response.status}`,
    }));
    throw errorData;
  }

  return response.json();
}
