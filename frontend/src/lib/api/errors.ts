/** Mirrors the backend error envelope in docs/api-contracts.md. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string;
    details?: { field: string; issue: string }[];
  };
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId: string | null = null,
    readonly details: ApiErrorBody["error"]["details"] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }

  get retryable(): boolean {
    return this.status === 0 || this.status === 429 || this.status >= 500;
  }
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as ApiErrorBody).error?.code === "string"
  );
}

export async function parseResponse<T>(response: Response): Promise<T> {
  const body: unknown = await response.json().catch(() => null);
  if (response.ok) return body as T;
  if (isErrorBody(body)) {
    const { code, message, request_id, details } = body.error;
    throw new ApiError(response.status, code, message, request_id, details);
  }
  throw new ApiError(response.status, "unexpected_response", `Request failed (${response.status}).`);
}

export function networkError(cause: unknown): ApiError {
  const error = new ApiError(0, "network_error", "Could not reach the NBA Intelligence API.");
  error.cause = cause;
  return error;
}

/** Plain-language copy for the UI; never shows stack traces or internal details. */
export function describeError(error: unknown): { title: string; message: string } {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return { title: "Can't reach the server", message: "Check your connection and try again." };
    }
    if (error.status === 404) return { title: "Not found", message: error.message };
    if (error.status === 429) {
      return { title: "Too many requests", message: "Wait a moment, then try again." };
    }
    if (error.status >= 500) {
      return {
        title: "Something went wrong on our side",
        message: "The data service had a problem. Try again in a moment.",
      };
    }
    return { title: "Request not completed", message: error.message };
  }
  return { title: "Something went wrong", message: "An unexpected error occurred." };
}
