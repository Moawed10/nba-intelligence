import { ApiError, networkError, parseResponse } from "./errors";

type Query = Record<string, string | number | boolean | undefined | null>;

/** Browser reads go to the same origin; next.config.ts rewrites /api/v1 to FastAPI (ADR 0005). */
export function clientPath(path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value != null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return `/api/v1${path}${qs ? `?${qs}` : ""}`;
}

export async function clientGet<T>(path: string, query?: Query, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(clientPath(path, query), {
      headers: { accept: "application/json" },
      signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw networkError(cause);
  }
  return parseResponse<T>(response);
}

export async function clientPost<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(clientPath(path), {
      method: "POST",
      headers: { accept: "application/json", "content-type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (cause) {
    throw networkError(cause);
  }
  return parseResponse<T>(response);
}

export function shouldRetry(failureCount: number, error: unknown): boolean {
  return error instanceof ApiError && error.retryable && failureCount < 2;
}
