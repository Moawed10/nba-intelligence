import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Forecast } from "@/app/predict/forecast";
import { clientPost } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { Prediction } from "@/lib/api/types";

vi.mock("@/lib/api/client", () => ({ clientPost: vi.fn() }));

const stale = {
  id: "00000000-0000-4000-8000-000000000001",
  player_id: 1,
  game_id: "g",
  release_version: "r",
  kind: "pregame",
  status: "ok",
  created_at: "2099-11-10T18:00:00Z",
  data_cutoff_at: "2099-11-10T18:00:00Z",
  feature_schema_version: "f",
  double_double_probability: null,
  supersedes_prediction_id: null,
  freshness: "stale",
  freshness_reason: "New games or injury news since this forecast.",
  values: [{ stat: "pts", point: 21.7, lower: 18.7, upper: 24.7, interval_level: 0.8 }],
  actuals: null,
  explanation: null,
} as Prediction;

describe("Forecast", () => {
  it("keeps the stored forecast and says why when an update is refused", async () => {
    vi.mocked(clientPost).mockRejectedValue(
      new ApiError(409, "game_already_started", "Pregame predictions close at tip-off."),
    );
    render(
      <Forecast
        initial={stale}
        playerId={1}
        gameId="g"
        playerName="Test Player"
        opponentName="Bears"
        history={[]}
        seasonAverages={null}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Update forecast" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("This game has started");
    expect(alert).toHaveTextContent("Pregame predictions close at tip-off.");
    expect(screen.getByText("21.7")).toBeInTheDocument();
  });
});
