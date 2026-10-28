import "server-only";

import { networkError, parseResponse } from "./errors";

const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

type Query = Record<string, string | number | boolean | undefined | null>;

export function apiUrl(path: string, query?: Query): string {
  const url = new URL(`/api/v1${path}`, API_INTERNAL_URL);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value != null) url.searchParams.set(key, String(value));
  }
  return url.toString();
}

/**
 * Server Component reads. Callers that can be cached wrap this in a `'use cache'` function with a
 * `cacheLife` matching the dataset's policy in docs/api-contracts.md.
 */
export async function serverGet<T>(path: string, query?: Query): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path, query), { headers: { accept: "application/json" } });
  } catch (cause) {
    throw networkError(cause);
  }
  return parseResponse<T>(response);
}
