/**
 * ADs Growth System - API Client
 *
 * Centralized axios client with authentication (single-client app —
 * no per-account routing header).
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';

// Runtime config (injected in index.html) takes priority over build-time env
const API_BASE_URL =
  window.__RUNTIME_CONFIG__?.VITE_API_URL || import.meta.env.VITE_API_URL || '/api/v1';

// Create axios instance with default config
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Token management — use in-memory + sessionStorage to reduce XSS persistence
// (sessionStorage is cleared when the tab closes, unlike localStorage)
let accessToken: string | null = null;

export const setAccessToken = (token: string | null) => {
  accessToken = token;
  if (token) {
    sessionStorage.setItem('access_token', token);
  } else {
    sessionStorage.removeItem('access_token');
  }
};

export const getAccessToken = (): string | null => {
  if (!accessToken) {
    accessToken = sessionStorage.getItem('access_token');
  }
  return accessToken;
};

// Request interceptor - add auth token
// NOTE: X-Superadmin-Bypass removed — bypass must be validated server-side only
apiClient.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // Let axios set the correct Content-Type with boundary for FormData
    if (config.data instanceof FormData && config.headers) {
      delete config.headers['Content-Type'];
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Token refresh mutex — prevents multiple concurrent 401s from each
// attempting their own refresh.  The first 401 triggers the refresh;
// subsequent 401s wait for the same promise to resolve.
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function onTokenRefreshed(newToken: string) {
  refreshSubscribers.forEach((cb) => cb(newToken));
  refreshSubscribers = [];
}

// Response interceptor - handle errors and token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // Handle 401 - try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      // If a refresh is already in progress, queue this request
      if (isRefreshing) {
        return new Promise((resolve) => {
          subscribeTokenRefresh((newToken: string) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
            }
            resolve(apiClient(originalRequest));
          });
        });
      }

      isRefreshing = true;

      try {
        const refreshToken = sessionStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          });

          // Backend returns APIResponse wrapper: { success, data: { access_token, refresh_token, ... } }
          const tokenData = response.data?.data ?? response.data;
          const newAccessToken = tokenData.access_token;
          const newRefreshToken = tokenData.refresh_token;

          if (!newAccessToken) {
            throw new Error('No access_token in refresh response');
          }

          setAccessToken(newAccessToken);

          // Persist the rotated refresh token so future refreshes work
          if (newRefreshToken) {
            sessionStorage.setItem('refresh_token', newRefreshToken);
          }

          isRefreshing = false;
          onTokenRefreshed(newAccessToken);

          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
          }
          return apiClient(originalRequest);
        }
      } catch (refreshError) {
        isRefreshing = false;
        refreshSubscribers = [];
        // Refresh failed - logout user
        setAccessToken(null);
        sessionStorage.removeItem('refresh_token');
        window.location.href = '/login?reason=session_expired';
      }
    }

    return Promise.reject(error);
  }
);

/**
 * Extract the human-readable message from an API error.
 *
 * Axios's own `error.message` is the useless "Request failed with status
 * code N" — the backend's actual explanation lives in the response body as
 * FastAPI's `detail` (HTTPException) or the ApiResponse wrapper's `message`.
 */
export function getApiErrorMessage(
  error: unknown,
  fallback = 'Something went wrong. Please try again.'
): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      | { detail?: unknown; message?: unknown }
      | undefined;
    const detail = data?.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (detail && typeof detail === 'object') {
      const msg = (detail as { message?: unknown }).message;
      if (typeof msg === 'string' && msg) return msg;
    }
    if (typeof data?.message === 'string' && data.message) return data.message;
    return error.message || fallback;
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

/** Machine-readable error code from typed backend errors (detail.code). */
export function getApiErrorCode(error: unknown): string | null {
  if (!axios.isAxiosError(error)) return null;
  const data = error.response?.data as
    | { detail?: unknown; code?: unknown }
    | undefined;
  const detail = data?.detail;
  if (detail && typeof detail === 'object') {
    const code = (detail as { code?: unknown }).code;
    if (typeof code === 'string') return code;
  }
  if (typeof data?.code === 'string') return data.code;
  return null;
}

// API Response types
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  meta?: Record<string, any>;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

export default apiClient;
