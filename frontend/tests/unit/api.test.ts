import { describe, expect, it } from "vitest";

import { clientPath, shouldRetry } from "@/lib/api/client";
import { ApiError, describeError, parseResponse } from "@/lib/api/errors";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("api client", () => {
  it("builds same-origin paths and drops empty params", () => {
    expect(clientPath("/players/search", { q: "curry", limit: 10, team: undefined, x: "" })).toBe(
      "/api/v1/players/search?q=curry&limit=10",
    );
    expect(clientPath("/teams")).toBe("/api/v1/teams");
  });

  it("returns the body for success", async () => {
    await expect(parseResponse(json(200, { ok: 1 }))).resolves.toEqual({ ok: 1 });
  });

  it("turns the error envelope into a typed ApiError", async () => {
    const body = {
      error: {
        code: "player_not_found",
        message: "No player with id 1.",
        request_id: "req-1",
        details: [{ field: "player_id", issue: "not_found" }],
      },
    };
    const error = (await parseResponse(json(404, body)).catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, code: "player_not_found", requestId: "req-1" });
    expect(error.details).toHaveLength(1);
  });

  it("handles non-JSON failures", async () => {
    const error = await parseResponse(new Response("<html>", { status: 502 })).catch((e) => e);
    expect(error).toMatchObject({ status: 502, code: "unexpected_response" });
  });

  it("retries only transient failures, at most twice", () => {
    expect(shouldRetry(0, new ApiError(503, "x", "x"))).toBe(true);
    expect(shouldRetry(0, new ApiError(0, "network_error", "x"))).toBe(true);
    expect(shouldRetry(2, new ApiError(503, "x", "x"))).toBe(false);
    expect(shouldRetry(0, new ApiError(404, "x", "x"))).toBe(false);
    expect(shouldRetry(0, new Error("x"))).toBe(false);
  });

  it("describes errors in plain language", () => {
    expect(describeError(new ApiError(0, "network_error", "x")).title).toBe("Can't reach the server");
    expect(describeError(new ApiError(500, "internal_error", "trace")).message).not.toContain("trace");
    expect(describeError(new ApiError(422, "insufficient_data", "Not enough games.")).message).toBe(
      "Not enough games.",
    );
    expect(describeError(new Error("boom")).title).toBe("Something went wrong");
  });
});
