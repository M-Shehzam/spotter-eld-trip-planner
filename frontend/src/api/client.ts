/**
 * Thin fetch wrapper around the planner API.
 *
 * The backend runs on Render's free tier, which suspends the service after
 * fifteen idle minutes and takes roughly fifty seconds to come back. Callers
 * get an `onSlow` hook so the UI can say the server is waking up instead of
 * appearing frozen.
 */

const BASE_URL = (import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const SLOW_REQUEST_MS = 3000;
const REQUEST_TIMEOUT_MS = 90_000;

export interface ApiErrorBody {
  code: string;
  message: string;
  detail?: Record<string, unknown>;
}

export class ApiError extends Error {
  readonly code: string;
  readonly detail: Record<string, unknown>;
  readonly status: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.detail = body.detail ?? {};
  }
}

interface RequestOptions {
  signal?: AbortSignal;
  onSlow?: () => void;
}

async function request<T>(path: string, init: RequestInit, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const slowTimer = options.onSlow ? setTimeout(options.onSlow, SLOW_REQUEST_MS) : undefined;

  options.signal?.addEventListener("abort", () => controller.abort(), { once: true });

  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...init.headers },
    });

    const payload = await response.json().catch(() => null);

    if (!response.ok) {
      const body = payload?.error ?? {
        code: "network_error",
        message: `The server responded with ${response.status}.`,
      };
      throw new ApiError(response.status, body);
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(0, {
        code: "timeout",
        message: "The request took too long. The server may be starting up — try again.",
      });
    }
    throw new ApiError(0, {
      code: "network_error",
      message: "Could not reach the planner service. Check your connection and try again.",
    });
  } finally {
    clearTimeout(timeout);
    if (slowTimer) clearTimeout(slowTimer);
  }
}

export const api = {
  get: <T,>(path: string, options?: RequestOptions) => request<T>(path, { method: "GET" }, options),
  post: <T,>(path: string, body: unknown, options?: RequestOptions) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }, options),
};

export const apiBaseUrl = BASE_URL;
