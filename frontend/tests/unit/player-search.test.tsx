import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlayerSearch } from "@/components/data/player-search";
import type { PlayerSearchResult } from "@/lib/api/types";

// Synthetic fixtures; not real players.
const RESULTS: PlayerSearchResult[] = [
  { id: 1, full_name: "Alpha Tester", position: "G", is_active: true, team_abbreviation: "AAA" },
  { id: 2, full_name: "Beta Tester", position: null, is_active: false, team_abbreviation: null },
];

function respond(status: number, body: unknown) {
  const fetchMock = vi.fn<typeof fetch>(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function setup(onSelect = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PlayerSearch onSelect={onSelect} />
    </QueryClientProvider>,
  );
  const input = screen.getByRole("combobox", { name: "Search players" });
  return { user: userEvent.setup(), input, onSelect };
}

const visible = { selector: "p:not(.sr-only)" };

afterEach(() => vi.unstubAllGlobals());

describe("PlayerSearch", () => {
  it("waits for two characters before searching", async () => {
    const fetchMock = respond(200, RESULTS);
    const { user, input } = setup();
    await user.type(input, "a");
    await new Promise((r) => setTimeout(r, 300));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText("Type at least 2 characters to search.")).toBeInTheDocument();
  });

  it("debounces within the 200–350 ms window", async () => {
    const fetchMock = respond(200, RESULTS);
    const { user, input } = setup();
    await user.type(input, "tes");
    const typed = performance.now();
    await new Promise((r) => setTimeout(r, 190));
    expect(fetchMock).not.toHaveBeenCalled();
    await screen.findByRole("option", { name: /Alpha Tester/ });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(performance.now() - typed).toBeLessThan(350 + 150);
  });

  it("queries the API once typing pauses and lists results", async () => {
    const fetchMock = respond(200, RESULTS);
    const { user, input } = setup();
    await user.type(input, "tes");
    expect(await screen.findByRole("option", { name: /Alpha Tester/ })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toBe("/api/v1/players/search?q=tes&limit=10");
    expect(input).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("2 players found.")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Beta Tester/ })).toHaveTextContent("Former player");
  });

  it("selects with the keyboard", async () => {
    respond(200, RESULTS);
    const { user, input, onSelect } = setup();
    await user.type(input, "tes");
    await screen.findByRole("option", { name: /Alpha Tester/ });
    await user.keyboard("{ArrowDown}{ArrowDown}");
    const beta = screen.getByRole("option", { name: /Beta Tester/ });
    expect(beta).toHaveAttribute("aria-selected", "true");
    expect(input).toHaveAttribute("aria-activedescendant", beta.id);
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith(RESULTS[1]);
    expect(input).toHaveValue("Beta Tester");
    expect(input).toHaveAttribute("aria-expanded", "false");
  });

  it("closes on Escape, then clears on a second Escape", async () => {
    respond(200, RESULTS);
    const { user, input } = setup();
    await user.type(input, "tes");
    await screen.findByRole("option", { name: /Alpha Tester/ });
    await user.keyboard("{Escape}");
    expect(input).toHaveAttribute("aria-expanded", "false");
    expect(input).toHaveValue("tes");
    await user.keyboard("{Escape}");
    expect(input).toHaveValue("");
  });

  it("selects with a pointer", async () => {
    respond(200, RESULTS);
    const { user, input, onSelect } = setup();
    await user.type(input, "tes");
    await user.click(await screen.findByRole("option", { name: /Alpha Tester/ }));
    expect(onSelect).toHaveBeenCalledWith(RESULTS[0]);
    expect(input).toHaveValue("Alpha Tester");
  });

  it("says so when nothing matches", async () => {
    respond(200, []);
    const { user, input } = setup();
    await user.type(input, "zzz");
    expect(await screen.findByText("No players match that name.", visible)).toBeVisible();
    expect(input).toHaveAttribute("aria-expanded", "false");
  });

  it("shows a plain-language error", async () => {
    respond(503, {
      error: {
        code: "database_unavailable",
        message: "The database is temporarily unavailable.",
        request_id: "r",
      },
    });
    const { user, input } = setup();
    await user.type(input, "tes");
    const message = await screen.findByText(/./, { selector: "p.text-negative" });
    expect(message.textContent).not.toMatch(/database_unavailable|stack/i);
  });
});
